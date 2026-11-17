import multiprocessing
import time
import unittest
from concurrent.futures import Future
from functools import partial
from unittest.mock import Mock, patch

import numpy as np

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.inference_service import InferenceMode, InferenceRequest, InferenceService
from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer
from freemocap.core.pipeline.realtime.camera_node import CameraNode
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node import RealtimeSkeletonInferenceNode
from freemocap.pubsub.pubsub_topics import ProcessFrameNumberMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE
from skellytracker.core.data_primitives.observation import Observation


class RealtimeInferenceAdapterTests(unittest.TestCase):
    def test_adapter_submits_to_service_and_publishes_matching_results(self) -> None:
        for detector in ("rtmpose", "mediapipe"):
            with self.subTest(detector=detector):
                queues = [multiprocessing.Queue() for _ in range(5)]
                requests, configs, results, timings, logs = queues
                ipc = PipelineIPC(pipeline_id="live", ws_queue=logs,
                    global_kill_flag=multiprocessing.Value("b", False),
                    heartbeat_timestamp=multiprocessing.Value("d", time.perf_counter()))
                service = Mock(spec=InferenceService)
                client = service.register.return_value
                client.failure = None
                camera_ids = ["left", "right", "overhead"]
                dto = Mock(spec=CameraGroupSharedMemoryDTO)
                dto.camera_shm_dtos = dict.fromkeys(camera_ids, Mock())
                images = [np.zeros((8, 12, 3), dtype=np.uint8) for _ in camera_ids]

                def read_frames(*, frame_recarrays, **kwargs):
                    for index, camera_id in enumerate(camera_ids):
                        record = np.zeros(1, dtype=[('frame_metadata', FRAME_METADATA_DTYPE)]).view(np.recarray)
                        record.frame_metadata.timestamps.pre_frame_grab_ns = 1_000_000_000 + index * 2_000_000
                        record.frame_metadata.timestamps.post_frame_grab_ns = 1_002_000_000 + index * 2_000_000
                        frame_recarrays[camera_id] = record
                    return images, camera_ids

                def infer(request: InferenceRequest) -> Future[dict[str, Observation]]:
                    future: Future[dict[str, Observation]] = Future()
                    future.set_result({key: Observation(frame_number=request.frame_number,
                        image_size=image.shape[:2], stages={}) for key, image in request.images.items()})
                    ipc.shutdown_pipeline()
                    return future

                client.submit.side_effect = infer
                config = RealtimePipelineConfig(log_pipeline_times=False,
                    camera_node_config={"detector_type": detector})
                requests.put(ProcessFrameNumberMessage(frame_number=7))
                try:
                    with patch("freemocap.core.pipeline.realtime.realtime_skeleton_inference_node.CameraGroupSharedMemory.recreate"), \
                         patch("freemocap.core.pipeline.realtime.realtime_skeleton_inference_node.CameraSharedMemoryRingBuffer.recreate", return_value=Mock(spec=CameraSharedMemoryRingBuffer)), \
                         patch("freemocap.core.pipeline.realtime.realtime_skeleton_inference_node._read_frames", side_effect=read_frames):
                        RealtimeSkeletonInferenceNode._run(camera_group_id="group", camera_ids=camera_ids,
                            pipeline_config=config, ipc=ipc, shutdown_self_flag=multiprocessing.Value("b", False),
                            camera_group_shm_dto=dto, process_frame_number_sub=requests,
                            pipeline_config_sub=configs, skeleton_result_pub=results, timing_pub=timings,
                            inference_service=service)
                    result = results.get(timeout=2)
                    self.assertEqual(result.frame_number, 7)
                    self.assertEqual(set(result.per_camera_skeleton), set(camera_ids))
                    self.assertEqual(client.submit.call_args.args[0].timestamps_ms,
                                     {"left": 1001.0, "right": 1003.0, "overhead": 1005.0})
                    registration = service.register.call_args.args[0]
                    self.assertEqual(registration.mode, InferenceMode.REALTIME)
                    self.assertEqual((registration.detector_type, registration.camera_ids), (detector, tuple(camera_ids)))
                    self.assertEqual(registration.pipeline_id, ipc.pipeline_id)
                    client.close.assert_called_once()
                finally:
                    for queue in queues:
                        queue.close()
                        queue.join_thread()


class RealtimeTimingEventTests(unittest.TestCase):
    """With pipeline times on, the nodes flush task events with perf_counter_ns ends on the timing topic."""

    def setUp(self) -> None:
        self.ipc = PipelineIPC(pipeline_id="live", ws_queue=multiprocessing.Queue(),
                               global_kill_flag=multiprocessing.Value("b", False),
                               heartbeat_timestamp=multiprocessing.Value("d", time.perf_counter()))

    def queues(self, count: int) -> list[multiprocessing.Queue]:
        queues = [multiprocessing.Queue() for _ in range(count)]
        for queue in queues:
            self.addCleanup(queue.join_thread)
            self.addCleanup(queue.close)
        return queues

    def test_skeleton_inference_flushes_frame_read_and_predict_batch_events(self) -> None:
        requests, configs, results, timings = self.queues(4)
        service = Mock(spec=InferenceService)
        client = service.register.return_value
        client.failure = None
        camera_ids = ["left", "right"]
        dto = Mock(spec=CameraGroupSharedMemoryDTO)
        dto.camera_shm_dtos = dict.fromkeys(camera_ids, Mock())
        images = [np.zeros((8, 12, 3), dtype=np.uint8) for _ in camera_ids]

        def infer(request: InferenceRequest) -> Future[dict[str, Observation]]:
            future: Future[dict[str, Observation]] = Future()
            future.set_result({key: Observation(frame_number=request.frame_number, image_size=(8, 12), stages={})
                               for key in request.images})
            self.ipc.shutdown_pipeline()
            return future

        client.submit.side_effect = infer
        requests.put(ProcessFrameNumberMessage(frame_number=7))
        node = "freemocap.core.pipeline.realtime.realtime_skeleton_inference_node"
        with patch(f"{node}.CameraGroupSharedMemory.recreate"), \
             patch(f"{node}.CameraSharedMemoryRingBuffer.recreate", return_value=Mock(spec=CameraSharedMemoryRingBuffer)), \
             patch(f"{node}._read_frames", return_value=(images, camera_ids)), \
             patch(f"{node}.capture_timestamp_ms", return_value=1.0), \
             patch(f"{node}.PipelineStageTimer", partial(PipelineStageTimer, flush_interval=0.0)):
            RealtimeSkeletonInferenceNode._run(camera_group_id="group", camera_ids=camera_ids,
                pipeline_config=RealtimePipelineConfig(log_pipeline_times=True), ipc=self.ipc,
                shutdown_self_flag=multiprocessing.Value("b", False), camera_group_shm_dto=dto,
                process_frame_number_sub=requests, pipeline_config_sub=configs, skeleton_result_pub=results,
                timing_pub=timings, inference_service=service)
        message = timings.get(timeout=5)
        events = {event.stage: event for event in message.events}
        self.assertEqual(set(events), {"frame_read", "predict_batch"})
        self.assertEqual(events["predict_batch"].task_id, "7:batch:skeleton_inference:predict_batch")
        self.assertEqual({event.frame_number for event in message.events}, {7})
        self.assertEqual({event.batch_size for event in message.events}, {2})
        self.assertLessEqual(events["frame_read"].end_time_ns, events["predict_batch"].start_time_ns)
        self.assertEqual(message.samples["predict_batch"], [events["predict_batch"].duration_ms])
        self.assertEqual(message.samples["predict_per_camera"], [events["predict_batch"].duration_ms / 2])

    def test_camera_node_flushes_one_charuco_detection_event(self) -> None:
        requests, configs, outputs, timings = self.queues(4)
        record = np.zeros(1, dtype=[("frame_metadata", FRAME_METADATA_DTYPE), ("image", np.uint8, (8, 12, 3))]).view(np.recarray)
        record.frame_metadata.frame_number = 4
        record.frame_metadata.camera_info.camera_id = "left"
        record.frame_metadata.camera_info.rotation = -1
        shm = Mock(spec=CameraSharedMemoryRingBuffer, valid=True)
        shm.get_data_by_index.return_value = record
        requests.put(ProcessFrameNumberMessage(frame_number=4))
        node = "freemocap.core.pipeline.realtime.camera_node"
        with patch(f"{node}.CameraSharedMemoryRingBuffer.recreate", return_value=shm), \
             patch(f"{node}.create_charuco_detector"), \
             patch(f"{node}.board_observation", side_effect=lambda *args: self.ipc.shutdown_pipeline()), \
             patch(f"{node}.capture_timestamp", return_value=1.0), \
             patch(f"{node}.camera_capture_timestamp_ns", return_value=1), \
             patch(f"{node}.PipelineStageTimer", partial(PipelineStageTimer, flush_interval=0.0)):
            CameraNode._run(camera_id="left", ipc=self.ipc, config=CameraNodeConfig(charuco_tracking_enabled=True),
                            process_frame_number_sub=requests, pipeline_config_sub=configs, camera_output_pub=outputs,
                            timing_pub=timings, shutdown_self_flag=multiprocessing.Value("b", False),
                            camera_shm_dto=Mock(spec=SharedMemoryRingBufferDTO), log_pipeline_times=True)
        message = timings.get(timeout=5)
        (event,) = message.events
        self.assertEqual((event.task_id, event.stage, event.camera_id, event.frame_number),
                         ("4:left:camera:charuco_detection", "charuco_detection", "left", 4))
        self.assertGreaterEqual(event.end_time_ns, event.start_time_ns)
        self.assertEqual(message.samples["charuco_detection"], [event.duration_ms])


if __name__ == "__main__":
    unittest.main()

