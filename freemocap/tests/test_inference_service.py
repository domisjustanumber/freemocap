import multiprocessing
import unittest
from concurrent.futures import CancelledError
from threading import Event
from unittest.mock import Mock, patch

import numpy as np
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.core.data_primitives.observation import Observation

from freemocap.core.pipeline.inference_service import (
    InferenceClient, InferenceMode, InferenceRegistration, InferenceRequest, InferenceService,
)


class InferenceServiceTests(unittest.TestCase):
    """One fake pipeline run for each client; the boundary function is patched to keep frame identity."""

    def setUp(self) -> None:
        self.global_shutdown = multiprocessing.Value("b", False)
        self.registry = WorkerRegistry(global_kill_flag=self.global_shutdown, worker_mode=WorkerMode.THREAD)
        self.runs: list[Mock] = []
        self.started: list[dict] = []
        for target, replacement in (("start_detector_run", self.start_run), ("observations_from_results", self.observations)):
            patcher = patch(f"freemocap.core.pipeline.inference_service.{target}", side_effect=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.service = InferenceService(worker_registry=self.registry)
        self.service.start()
        self.addCleanup(self.service.close)

    def start_run(self, **kwargs):
        self.started.append(kwargs)
        run = Mock()
        run.models = {"person": {"key": "yolox-person@openmmlab-exporter", "execution_provider": "gpu-ep", "device": "gpu:0"},
                      "wholebody": {"key": "rtmw-wholebody133@openmmlab-exporter", "execution_provider": "gpu-ep", "device": "gpu:0"}}
        run.process_batch.side_effect = self.infer
        self.runs.append(run)
        return run, "gpu-ep"

    @staticmethod
    def infer(frames):
        return {camera: {"frame_index": frame.frame_index, "image_width": frame.image.shape[1], "image_height": frame.image.shape[0]} for camera, frame in frames.items()}

    @staticmethod
    def observations(results, output_schema, detector_type, rtmw_min_score=0.4):
        return {camera: Observation(frame_number=result["frame_index"], image_size=(result["image_height"], result["image_width"]), stages={})
                for camera, result in results.items()}

    def client(self, *, name: str, mode: InferenceMode = InferenceMode.POSTHOC) -> InferenceClient:
        return self.service.register(InferenceRegistration(
            pipeline_id=name, mode=mode, detector_type="rtmpose", camera_ids=("same-camera",),
            shutdown_flag=multiprocessing.Value("b", False),
        ))

    @staticmethod
    def request(frame: int = 0) -> InferenceRequest:
        return InferenceRequest(frame_number=frame, images={"same-camera": np.zeros((8, 12, 3), dtype=np.uint8)},
                                timestamps_ms={"same-camera": frame * 33.5})

    def test_each_camera_frame_gets_its_own_timestamp_and_the_frame_index(self) -> None:
        client = self.client(name="recording-time", mode=InferenceMode.REALTIME)
        images = {"a": np.zeros((8, 12, 3), dtype=np.uint8), "b": np.zeros((8, 12, 3), dtype=np.uint8)}
        result = client.submit(InferenceRequest(frame_number=7, images=images, timestamps_ms={"a": 100.25, "b": 101.5})).result(timeout=2)
        frames = self.runs[0].process_batch.call_args.args[0]
        self.assertEqual({camera: (frame.frame_index, frame.timestamp_ms) for camera, frame in frames.items()},
                         {"a": (7, 100.25), "b": (7, 101.5)})
        self.assertIs(frames["a"].image, images["a"])
        self.assertEqual(result["a"].image_size, (8, 12))
        self.assertEqual(self.started[0]["running_mode"], "live")

    def test_a_request_needs_one_timestamp_for_each_image(self) -> None:
        client = self.client(name="missing-time")
        with self.assertRaisesRegex(ValueError, "timestamp"):
            client.submit(InferenceRequest(frame_number=0, images={"a": np.zeros((2, 2, 3), np.uint8)}, timestamps_ms={}))

    def test_the_run_starts_once_with_the_detector_choice_and_diagnostics_separate_setup(self) -> None:
        from freemocap.core.pipeline.performance_report import PerformanceReport
        report = PerformanceReport()
        client = self.service.register(InferenceRegistration(
            pipeline_id="diagnostics", mode=InferenceMode.POSTHOC, detector_type="rtmpose", camera_ids=("0", "1", "2"),
            rtmpose_model_name="rtmw-x-l_384x288", execution_provider="gpu-ep", execution_device="gpu:1",
            shutdown_flag=multiprocessing.Value("b", False)))
        images = {str(i): np.zeros((8, 12, 3), dtype=np.uint8) for i in range(3)}
        for frame in range(2):
            result = client.submit(InferenceRequest(frame_number=frame, images=images, performance=report,
                                                    timestamps_ms={camera: frame * 33 for camera in images})).result(timeout=2)
            self.assertEqual(set(result), set(images))
        rows = report.snapshot()
        self.assertEqual(rows["inference.session_setup"]["count"], 1)
        self.assertEqual(rows["inference.queue_wait"]["count"], 2)
        self.assertEqual(rows["inference.process_batch.images=3"]["count"], 2)
        self.assertEqual(self.started, [dict(detector_type="rtmpose", camera_ids=("0", "1", "2"), running_mode="video",
                                             rtmpose_model_name="rtmw-x-l_384x288", execution_provider="gpu-ep",
                                             execution_device="gpu:1")])
        self.assertEqual(self.runs[0].process_batch.call_count, 2)

    def test_the_registered_confidence_threshold_reaches_the_boundary(self) -> None:
        seen = []
        with patch("freemocap.core.pipeline.inference_service.observations_from_results",
                   side_effect=lambda results, schema, detector, threshold: seen.append(threshold) or self.observations(results, schema, detector)):
            client = self.service.register(InferenceRegistration(
                pipeline_id="threshold", mode=InferenceMode.POSTHOC, detector_type="rtmpose", camera_ids=("same-camera",),
                rtmpose_confidence_threshold=0.65, shutdown_flag=multiprocessing.Value("b", False)))
            client.submit(self.request()).result(timeout=2)
        self.assertEqual(seen, [0.65])

    def test_a_failed_start_runs_no_frame_and_reports_no_provider(self) -> None:
        with patch("freemocap.core.pipeline.inference_service.start_detector_run", side_effect=RuntimeError("EP did not load")):
            client = self.client(name="bad-provider")
            with self.assertRaisesRegex(RuntimeError, "EP did not load"):
                client.submit(self.request()).result(timeout=2)
        self.assertEqual(self.service.provider_status(), [])
        self.assertEqual(self.service.startup_status("bad-provider")["status"], "failed")

    def test_provider_status_is_the_run_record_of_each_model_with_nothing_made_up(self) -> None:
        client = self.client(name="observed-provider")
        client.submit(self.request()).result(timeout=2)
        client.submit(self.request(frame=1)).result(timeout=2)
        observed = self.service.provider_status()[0]
        self.assertEqual(observed["pipeline_id"], "observed-provider")
        self.assertIsNone(observed["requested_provider"])
        self.assertEqual(observed["models"], [{"node": node, **model} for node, model in self.runs[0].models.items()])

    def test_each_client_has_its_own_run_and_a_retired_run_is_closed(self) -> None:
        first = self.client(name="first")
        second = self.client(name="second")
        first.submit(self.request()).result(timeout=2)
        second.submit(self.request()).result(timeout=2)
        self.assertEqual(len(self.runs), 2)
        closed = Event()
        self.runs[0].close.side_effect = closed.set
        first.close()
        self.assertTrue(closed.wait(timeout=2))
        second.submit(self.request(frame=1)).result(timeout=2)
        self.runs[1].close.assert_not_called()

    def test_closing_the_service_closes_each_run(self) -> None:
        client = self.client(name="open")
        client.submit(self.request()).result(timeout=2)
        self.service.close()
        self.runs[0].close.assert_called_once()

    def test_inference_failure_stops_only_its_client(self) -> None:
        first = self.client(name="failed")
        second = self.client(name="healthy")
        first.submit(self.request()).result(timeout=2)
        self.runs[0].process_batch.side_effect = ValueError("bad input")
        with self.assertRaisesRegex(ValueError, "bad input"):
            first.submit(self.request(frame=1)).result(timeout=2)
        second.submit(self.request()).result(timeout=2)
        self.assertTrue(first.registration.shutdown_flag.value)
        self.assertFalse(second.registration.shutdown_flag.value)
        self.assertFalse(self.global_shutdown.value)

    def test_submission_during_run_close_does_not_sleep_with_work_ready(self) -> None:
        retiring = self.client(name="retiring")
        ready = self.client(name="ready", mode=InferenceMode.REALTIME)
        retiring.submit(self.request()).result(timeout=2)
        submitted, completed, slept_with_work = Event(), Event(), Event()
        original_wait = self.service._condition.wait

        def submit_during_close() -> None:
            future = ready.submit(self.request())
            future.add_done_callback(lambda result: completed.set())
            submitted.set()

        def observe_wait(timeout: float | None = None) -> bool:
            if ready._pending is not None:
                slept_with_work.set()
            return original_wait(timeout=timeout)

        self.runs[0].close.side_effect = submit_during_close
        with patch.object(self.service._condition, "wait", side_effect=observe_wait):
            retiring.close()
            self.assertTrue(submitted.wait(timeout=2))
            self.assertTrue(completed.wait(timeout=2))
        self.assertFalse(slept_with_work.is_set())
        self.assertIsNone(ready.failure)

    def test_active_cancellation_waits_for_native_work_and_discards_result(self) -> None:
        client = self.client(name="cancelled")
        client.submit(self.request()).result(timeout=2)
        entered, release = Event(), Event()

        def blocking_infer(frames):
            entered.set()
            if not release.wait(timeout=2):
                raise TimeoutError("Test inference was not released")
            return self.infer(frames)

        self.runs[0].process_batch.side_effect = blocking_infer
        future = client.submit(self.request(frame=1))
        try:
            self.assertTrue(entered.wait(timeout=2))
            with self.assertRaisesRegex(RuntimeError, "outstanding"):
                client.submit(self.request(frame=2))
            client.close()
            self.assertFalse(future.done())
            self.runs[0].close.assert_not_called()
        finally:
            release.set()
        with self.assertRaises(CancelledError):
            future.result(timeout=2)

    def test_posthoc_rejects_skips_but_realtime_accepts_selected_ordinals(self) -> None:
        posthoc = self.client(name="recording")
        live = self.client(name="live", mode=InferenceMode.REALTIME)
        with self.assertRaisesRegex(ValueError, "consecutive"):
            posthoc.submit(self.request(frame=2))
        live.submit(self.request(frame=20)).result(timeout=2)
        live.submit(self.request(frame=25)).result(timeout=2)

    def test_ready_posthoc_is_scheduled_after_three_realtime_requests(self) -> None:
        entered, release = Event(), Event()
        blocker = self.client(name="blocker")
        blocker.submit(self.request()).result(timeout=2)

        def blocking_infer(frames):
            entered.set()
            if not release.wait(timeout=2):
                raise TimeoutError("Test inference was not released")
            return self.infer(frames)

        self.runs[0].process_batch.side_effect = blocking_infer
        active = blocker.submit(self.request(frame=1))
        self.assertTrue(entered.wait(timeout=2))
        completed: list[str] = []
        futures = []
        try:
            for index in range(4):
                name = f"live-{index}"
                future = self.client(name=name, mode=InferenceMode.REALTIME).submit(self.request())
                future.add_done_callback(lambda result, label=name: completed.append(label))
                futures.append(future)
            future = self.client(name="posthoc").submit(self.request())
            future.add_done_callback(lambda result: completed.append("posthoc"))
            futures.append(future)
        finally:
            release.set()
        active.result(timeout=2)
        for future in futures:
            future.result(timeout=2)
        self.assertEqual(completed, ["live-0", "live-1", "live-2", "posthoc", "live-3"])


if __name__ == "__main__":
    unittest.main()
