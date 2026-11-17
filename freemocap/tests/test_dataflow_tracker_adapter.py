"""Real readers and real inference scheduling, with controlled detector work."""
from collections import Counter
from contextlib import closing
from threading import Event, Lock
import unittest
from unittest.mock import Mock, patch

from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.dataflow.tracker_adapter import SkellyTrackerAdapter, TrackedCameraFrame
from freemocap.core.pipeline.dataflow.video_sources import VideoSourceFinished
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.tests import test_dataflow_video_sources as source_tests


class TrackerAdapterTests(unittest.TestCase):
    setUp = source_tests.VideoSourceTests.setUp

    def make_adapter(self, infer, detector_type="rtmpose"):
        """`infer(frames)` stands in for the run; its results are already observations."""
        run = Mock(models={})
        run.process_batch.side_effect = infer
        for target, replacement in (("start_detector_run", lambda **kwargs: (run, {"execution": {"requested": None}})),
                                    ("observations_from_results", lambda results, schema, detector, threshold: results)):
            patcher = patch(f"freemocap.core.pipeline.inference_service.{target}", side_effect=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        return self.real_adapter(detector_type)

    def real_adapter(self, detector_type="mediapipe"):
        service = InferenceService(worker_registry=self.registry)
        service.start()
        self.addCleanup(service.close)
        return SkellyTrackerAdapter(inference_service=service, detector_type=detector_type, performance_report=PerformanceReport())

    @staticmethod
    def infer(frames):
        return {camera: Observation(frame_number=frame.frame_index, image_size=frame.image.shape[:2], stages={})
                for camera, frame in frames.items()}

    def stream(self, adapter):
        return adapter.track_recording(sources=self.sources, execution_id="test-tracking",
                                       shutdown_flag=self.shutdown, queued_frames_per_camera=1)

    def test_inference_starts_early_and_loading_overlaps_with_bounded_read_ahead(self):
        from freemocap.core.pipeline.dataflow import video_sources
        original_reader = video_sources.SequentialVideoReader
        counts = Counter()
        lock = Lock()
        all_loaded_ahead = Event()

        class ObservedReader:
            def __init__(self, *, path):
                self.camera = path.name
                self.reader = original_reader(path=path)

            def read_bgr(self, *, frame_number):
                image = self.reader.read_bgr(frame_number=frame_number)
                with lock:
                    counts[self.camera] += 1
                    if len(counts) == 3 and min(counts.values()) >= 3:
                        all_loaded_ahead.set()
                return image

            def close(self):
                self.reader.close()

        calls = []

        def infer(frames):
            frame = next(iter(frames.values())).frame_index
            self.assertEqual({item.frame_index for item in frames.values()}, {frame})
            self.assertEqual({item.timestamp_ms for item in frames.values()}, {round(frame * 1000 / 30)})
            calls.append(frame)
            if frame == 0:
                self.assertTrue(all_loaded_ahead.wait(3), "Loading should overlap active inference")
                with lock:
                    self.assertEqual(dict(counts), {source.camera_id: 3 for source in self.sources.camera_sources})
                # At most active + one queued + one reader-local image per camera.
            return self.infer(frames)

        adapter = self.make_adapter(infer)
        with patch.object(video_sources, "SequentialVideoReader", ObservedReader):
            events = list(self.stream(adapter))
        self.assertEqual(calls, list(range(8)))
        self.assertEqual(sum(isinstance(event, TrackedCameraFrame) for event in events), 24)
        self.assertEqual(sum(isinstance(event, VideoSourceFinished) for event in events), 3)
        self.assertEqual(adapter.performance_report.images, 24)

    def test_report_counts_actual_detector_runs_separately_from_camera_images(self):
        from skellytracker.core.data_primitives.observation import StageObservation
        def infer(frames):
            observations = self.infer(frames)
            for observation in observations.values():
                observation.stages["body"] = StageObservation(name="body", detector_ran=observation.frame_number % 3 == 0)
            return observations
        adapter = self.make_adapter(infer)
        list(self.stream(adapter))
        self.assertEqual(adapter.performance_report.counts_snapshot(), {
            "tracking.body.camera_images": 24, "tracking.body.object_detector_runs": 9})

    @staticmethod
    def failing_reader():
        from freemocap.core.pipeline.dataflow import video_sources
        original_reader = video_sources.SequentialVideoReader

        class FailingReader:
            def __init__(self, *, path):
                self.path = path
                self.reader = original_reader(path=path)

            def read_bgr(self, *, frame_number):
                if self.path.name == "camera1.avi" and frame_number == 2:
                    raise IndexError("early EOF")
                return self.reader.read_bgr(frame_number=frame_number)

            def close(self):
                self.reader.close()

        return patch.object(video_sources, "SequentialVideoReader", FailingReader)

    def test_a_source_failure_stops_the_recording_run_with_the_camera_and_frame(self):
        """A `video` run takes a frame from each camera on each call (skellytracker V-pipeline.running-2)."""
        from freemocap.core.pipeline.dataflow.tracker_adapter import CameraSourceEndedError
        adapter = self.real_adapter()
        events = []
        with self.failing_reader(), self.assertRaisesRegex(CameraSourceEndedError, "frame 2: camera camera1.avi"):
            for event in self.stream(adapter):
                events.append(event)
        counts = Counter(event.frame_key.camera for event in events if isinstance(event, TrackedCameraFrame))
        self.assertEqual(counts, {"camera0.avi": 2, "camera1.avi": 2, "camera2.avi": 2})
        self.assertFalse(self.shutdown.value)

    def test_inference_failure_does_not_cancel_graph_or_retry(self):
        infer = Mock(side_effect=ValueError("inference failed"))
        adapter = self.make_adapter(infer)
        with self.assertRaisesRegex(ValueError, "inference failed"):
            list(self.stream(adapter))
        self.assertEqual(infer.call_count, 1)
        self.assertFalse(self.shutdown.value)
        self.assertEqual(len(self.registry.alive_workers), 1)  # Shared inference service only.

    def test_closing_observation_stream_stops_readers(self):
        adapter = self.make_adapter(self.infer)
        with closing(self.stream(adapter)) as stream:
            self.assertIsInstance(next(stream), TrackedCameraFrame)
        self.assertEqual(len(self.registry.alive_workers), 1)

    def test_cancelled_graph_does_not_emit_finished_inference_results(self):
        from concurrent.futures import CancelledError

        def infer(frames):
            self.shutdown.value = True
            return self.infer(frames)

        adapter = self.make_adapter(infer)
        with self.assertRaises(CancelledError):
            next(self.stream(adapter))

    def test_timestamp_collision_is_rejected_before_inference(self):
        from dataclasses import replace
        from skellycam.core.timestamps.recording_timing_reader import RecordingTiming
        from freemocap.core.pipeline.dataflow.tracker_adapter import recording_timestamps_ms
        timing = RecordingTiming(timestamps_s=tuple(index * 0.0001 for index in range(8)),
                                 method=self.sources.group_timing.method)
        with self.assertRaisesRegex(ValueError, "millisecond"):
            recording_timestamps_ms(replace(self.sources, group_timing=timing))

    def test_a_timing_sink_gets_the_run_records_and_a_camera_wait_per_frame_tagged_with_the_pipeline_id(self):
        from collections import deque
        from freemocap.core.pipeline.pipeline_timing_events import SkellytrackerTimingEvents
        started = {}
        run = Mock(models={})

        def infer(frames):
            # A skellytracker run calls its sink after each call: the header first, then the call's spans.
            frame = next(iter(frames.values())).frame_index
            if frame == 0:
                started["timing_sink"]({"schema": "skellytracker.timing/1", "run_id": "r1", "nodes": []})
            images = [{"frame_index": frame, "camera_id": camera} for camera in frames]
            started["timing_sink"]({"images": images, "node_id": "pipeline", "span": "run", "batch_size": len(frames),
                                    "start_ns": 1, "end_ns": 2})
            return self.infer(frames)

        run.process_batch.side_effect = infer
        for target, replacement in (("start_detector_run", lambda **kwargs: (started.update(kwargs) or run, {"execution": {}})),
                                    ("observations_from_results", lambda results, schema, detector, threshold: results)):
            patcher = patch(f"freemocap.core.pipeline.inference_service.{target}", side_effect=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        service = InferenceService(worker_registry=self.registry)
        service.start()
        self.addCleanup(service.close)
        records = deque()
        adapter = SkellyTrackerAdapter(inference_service=service, detector_type="rtmpose", performance_report=PerformanceReport(),
                                       timing_sink=records.append, timing_pipeline_id="posthoc-run")
        list(self.stream(adapter))
        self.assertEqual(started["running_mode"], "video")
        converter = SkellytrackerTimingEvents(pipeline_id="posthoc-run")
        events = converter.convert(list(records))
        self.assertEqual(converter.header["run_id"], "r1")
        waits = [event for event in events if event.stage == "graph.camera_batch_wait"]
        self.assertEqual([event.frame_number for event in waits], list(range(8)))
        self.assertEqual({(event.node_kind, event.batch_size) for event in waits}, {("video_read", 3)})
        self.assertTrue(all(event.end_time_ns >= event.start_time_ns for event in waits))
        runs = [event for event in events if event.stage == "pipeline.run"]
        self.assertEqual([event.frame_number for event in runs], list(range(8)))
        self.assertTrue(all(event.task_id.startswith("posthoc-run:") for event in events))
        # The camera wait of a frame comes before that frame's tracker call.
        self.assertEqual([event.stage for event in events[:2]], ["graph.camera_batch_wait", "pipeline.run"])

    def test_installed_skellytracker_holistic_run_works_without_mocked_inference(self):
        adapter = self.real_adapter()
        events = list(self.stream(adapter))
        tracked = [event for event in events if isinstance(event, TrackedCameraFrame)]
        self.assertEqual(len(tracked), 24)
        self.assertTrue(all("body" in event.observation.stages for event in tracked))
        self.assertEqual(adapter.performance_report.snapshot()["inference.process_batch.images=3"]["count"], 8)


if __name__ == "__main__":
    unittest.main()
