"""
RealtimeCameraNode: reads frames from shared memory, runs charuco detection,
publishes CameraNodeOutputMessages. Skeleton inference runs in the group's RealtimeSkeletonInferenceNode.

Runs indefinitely until shutdown. Responds to pipeline config updates
(toggling trackers, changing charuco board params, etc).
"""
from freemocap.core.tracking.charuco_detection import CHARUCO_STAGE, create_charuco_detector
from freemocap.core.tracking.charuco_detection import charuco_observation as board_observation
from freemocap.core.streaming.outputs.capture_time import camera_capture_timestamp_ns
import logging
import queue
import time
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.types.type_overloads import TopicPublicationQueue
from freemocap.core.pipeline.pipeline_stage_timer import PipelineStageTimer
from freemocap.core.pipeline.realtime.temporal_pipeline import capture_timestamp
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    ProcessFrameNumberTopic,
    PipelineConfigUpdateTopic,
    CameraNodeOutputTopic,
    PipelineConfigUpdateMessage,
    ProcessFrameNumberMessage,
    CameraNodeOutputMessage,
    PipelineTimingTopic,
)

import numpy as np
from skellyforge.core.data_tensors.channel_values import ChannelValues
from skellytracker.core.data_primitives.observation import Observation

logger = logging.getLogger(__name__)

_CHARUCO_MISS_SKIP_FRAMES = 10
"""After a frame where the board was not seen, skip charuco detection for this
many frames. One probe per window while the board is absent; a hit resumes
per-frame detection immediately."""


def _board_was_seen(observation: Observation | None) -> bool:
    """A board counts as seen when at least three corner positions are finite.

    Three non-collinear corners are the minimum a reconstruction can use, so the
    skip gate triggers exactly when the detector's output could not matter."""
    if observation is None:
        return False
    stage = observation.stages.get(CHARUCO_STAGE)
    keypoints = getattr(stage, "keypoints", None)
    if keypoints is None or keypoints.xyz is None or len(keypoints.xyz) == 0:
        return False
    return int(np.isfinite(keypoints.xyz).all(axis=1).sum()) >= 3


@dataclass
class CameraNode(SourceNode):
    camera_id: CameraIdString

    @classmethod
    def create(
            cls,
            *,
            camera_id: CameraIdString,
            camera_shm_dto: SharedMemoryRingBufferDTO,
            worker_registry: WorkerRegistry,
            config: CameraNodeConfig,
            ipc: PipelineIPC,
            pubsub: PubSubTopicManager,
            log_pipeline_times: bool = False,
    ) -> "CameraNode":
        shutdown_self_flag, worker = cls._create_worker(
            owner_shutdown_flag=ipc.pipeline_shutdown_flag,
            worker_mode=config.worker_mode,
            target=cls._run,
            name=f"RealtimeCameraNode-{camera_id}",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                camera_id=camera_id,
                ipc=ipc,
                config=config,
                camera_shm_dto=camera_shm_dto,
                log_pipeline_times=log_pipeline_times,
                process_frame_number_sub=pubsub.get_subscription(
                    ProcessFrameNumberTopic,
                ),
                pipeline_config_sub=pubsub.get_subscription(
                    PipelineConfigUpdateTopic,
                ),
                camera_output_pub=pubsub.get_publication_queue(
                    CameraNodeOutputTopic,
                ),
                timing_pub=pubsub.get_publication_queue(
                    PipelineTimingTopic,
                ),
            ),
        )
        return cls(
            camera_id=camera_id,
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
            *,
            camera_id: CameraIdString,
            ipc: PipelineIPC,
            config: CameraNodeConfig,
            process_frame_number_sub: TopicSubscriptionQueue,
            pipeline_config_sub: TopicSubscriptionQueue,
            camera_output_pub: TopicPublicationQueue,
            timing_pub: TopicPublicationQueue,
            shutdown_self_flag: Synchronized,
            camera_shm_dto: SharedMemoryRingBufferDTO,
            log_pipeline_times: bool = False,
    ) -> None:
        import cv2

        logger.debug(f"RealtimeCameraNode [{camera_id}] initializing")
        camera_shm = CameraSharedMemoryRingBuffer.recreate(
            dto=camera_shm_dto,
            read_only=False,
        )

        charuco_detector = None

        # After a miss, skip detection for `_CHARUCO_MISS_SKIP_FRAMES` frames.
        charuco_skip_until_frame_number = -1

        try:
            if config.charuco_tracking_enabled:
                charuco_detector = create_charuco_detector(config.charuco_board)

            frame_recarray: np.recarray | None = None
            timer = None
            if log_pipeline_times:
                timer = PipelineStageTimer(name=f"CameraNode-{camera_id}")

            logger.debug(f"RealtimeCameraNode [{camera_id}] entering main loop")
            while ipc.should_continue and not shutdown_self_flag.value:
                # ---- Handle config updates ----
                while True:
                    try:
                        update_msg: PipelineConfigUpdateMessage = pipeline_config_sub.get_nowait()
                    except queue.Empty:
                        break
                    new_config: CameraNodeConfig = update_msg.pipeline_config.camera_node_config
                    logger.debug(f"RealtimeCameraNode [{camera_id}] received config update")

                    if (new_config.charuco_tracking_enabled
                            and (new_config.charuco_board != config.charuco_board
                                 or new_config.charuco_tracking_enabled != config.charuco_tracking_enabled)):
                        if charuco_detector is not None:
                            charuco_detector.close()
                        charuco_detector = create_charuco_detector(new_config.charuco_board)
                        charuco_skip_until_frame_number = -1
                    elif not new_config.charuco_tracking_enabled:
                        if charuco_detector is not None:
                            charuco_detector.close()
                        charuco_detector = None

                    config = new_config

                # ---- Check shared memory validity every iteration ----
                if not camera_shm.valid:
                    logger.debug(
                        f"RealtimeCameraNode [{camera_id}] "
                        f"shared memory invalidated, exiting"
                    )
                    break

                # ---- Block until a frame request arrives (up to 5ms) ----
                try:
                    frame_msg: ProcessFrameNumberMessage = process_frame_number_sub.get(timeout=0.005)
                except queue.Empty:
                    continue
                except InterruptedError:
                    # Windows Ctrl+C interrupts the wait syscall during
                    # shutdown; re-check the loop condition.
                    continue
                frame_recarray = camera_shm.get_data_by_index(
                    index=frame_msg.frame_number,
                    rec_array=frame_recarray,
                )

                if frame_recarray.frame_metadata.camera_info.rotation != -1:
                    image = cv2.rotate(
                        src=frame_recarray.image[0],
                        rotateCode=frame_recarray.frame_metadata.camera_info.rotation[0]
                    )
                else:
                    image = frame_recarray.image[0]

                actual_frame_number: int = int(frame_recarray.frame_metadata.frame_number[0])
                actual_camera_id: CameraIdString = frame_recarray.frame_metadata.camera_info.camera_id[0]
                if actual_camera_id != camera_id:
                    raise RuntimeError(
                        f"RealtimeCameraNode [{camera_id}]: expected camera ID {camera_id} "
                        f"but got frame with camera ID {actual_camera_id}"
                    )
                if actual_frame_number != frame_msg.frame_number:
                    logger.warning(
                        f"RealtimeCameraNode [{camera_id}]: requested frame {frame_msg.frame_number} "
                        f"but ring buffer contained frame {actual_frame_number} — possible ring buffer overwrite"
                    )
                charuco_observation = None
                t_frame_start = time.perf_counter() if timer is not None else 0.0

                if charuco_detector is not None:
                    if actual_frame_number > charuco_skip_until_frame_number:
                        t0 = time.perf_counter() if timer is not None else 0.0
                        charuco_observation = board_observation(charuco_detector, image, actual_frame_number)
                        if timer is not None:
                            timer.record("charuco_detection", (time.perf_counter() - t0) * 1e3)

                        if not _board_was_seen(charuco_observation):
                            # Board not in view: skip the next N frames instead of
                            # paying full-frame detection every frame. A hit leaves
                            # the gate open for per-frame detection immediately.
                            charuco_skip_until_frame_number = (
                                actual_frame_number + _CHARUCO_MISS_SKIP_FRAMES
                            )

                if timer is not None:
                    timer.record("total_camera_node", (time.perf_counter() - t_frame_start) * 1e3)

                camera_output_pub.put(
                    CameraNodeOutputMessage(
                        camera_id=actual_camera_id,
                        frame_number=actual_frame_number,
                        capture_timestamp_s=capture_timestamp(frame_recarray),
                        capture_timestamp_ns=camera_capture_timestamp_ns(frame_recarray),
                        charuco_observation=charuco_observation,
                        skeleton_observation=None,
                    ),
                )
                if timer is not None:
                    timer.maybe_flush(
                        publication_queue=timing_pub,
                        node_kind="camera",
                        camera_id=camera_id,
                    )

        except Exception as e:
            logger.exception(f"Exception in RealtimeCameraNode [{camera_id}]: {e}")
            ipc.shutdown_pipeline()
            raise
        finally:
            try:
                if charuco_detector is not None:
                    charuco_detector.close()
            finally:
                camera_shm.close()
            logger.debug(f"RealtimeCameraNode [{camera_id}] exiting")
