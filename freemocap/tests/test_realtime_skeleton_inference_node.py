"""Unit tests for realtime skeleton batch gating and frame read order."""

from __future__ import annotations

from multiprocessing import Queue
from unittest.mock import MagicMock, create_autospec, patch

import numpy as np
import pytest
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import (
    CameraSharedMemoryRingBuffer,
)

from freemocap.core.pipeline.realtime.realtime_skeleton_batch_logic import (
    SkeletonBatchOutcome,
    infer_or_skip_batch,
    publish_skipped_batch,
    should_run_inference,
)
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node import _read_frames
from freemocap.pubsub.pubsub_topics import SkeletonInferenceResultMessage
from skellytracker.trackers.rtmpose_tracker.rtmpose_session import RTMPoseSession, RTMPoseSessionConfig
from skellytracker.trackers.rtmpose_tracker.rtmpose_session_errors import BatchSizeMismatchError


def _session(*, batch_size: int) -> RTMPoseSession:
    return RTMPoseSession(
        config=RTMPoseSessionConfig(batch_size=batch_size),
        _active_provider="cpu",
    )


def _image() -> np.ndarray:
    return np.zeros((32, 32, 3), dtype=np.uint8)


class TestShouldRunInference:
    def test_full_read(self) -> None:
        session = _session(batch_size=3)
        images = [_image(), _image(), _image()]
        camera_ids = ["cam_a", "cam_b", "cam_c"]
        assert should_run_inference(images, camera_ids, camera_ids, session) is True

    def test_partial_read(self) -> None:
        session = _session(batch_size=3)
        images = [_image(), _image()]
        ordered = ["cam_a", "cam_b"]
        camera_ids = ["cam_a", "cam_b", "cam_c"]
        assert should_run_inference(images, ordered, camera_ids, session) is False

    def test_desynced_lists(self) -> None:
        session = _session(batch_size=3)
        images = [_image(), _image(), _image()]
        ordered = ["cam_a", "cam_b"]
        camera_ids = ["cam_a", "cam_b", "cam_c"]
        assert should_run_inference(images, ordered, camera_ids, session) is False

    def test_empty(self) -> None:
        session = _session(batch_size=3)
        assert should_run_inference([], [], ["cam_a"], session) is False


class TestPublishSkippedBatch:
    def test_publishes_full_camera_none_map(self) -> None:
        pub = Queue()
        publish_skipped_batch(
            frame_number=42,
            camera_ids=["cam_a", "cam_b"],
            pub=pub,
        )
        message = pub.get_nowait()
        assert isinstance(message, SkeletonInferenceResultMessage)
        assert message.frame_number == 42
        assert message.per_camera_skeleton == {"cam_a": None, "cam_b": None}


class TestInferOrSkipBatch:
    def test_skip_on_partial_read(self) -> None:
        session = _session(batch_size=3)
        with patch.object(session, "predict_batch") as predict_mock:
            outcome = infer_or_skip_batch(
                frame_number=1,
                images=[_image()],
                ordered_camera_ids=["cam_a"],
                camera_ids=["cam_a", "cam_b", "cam_c"],
                session=session,
            )
        assert outcome == SkeletonBatchOutcome(kind="skip")
        predict_mock.assert_not_called()

    def test_infer_on_full_read(self) -> None:
        session = _session(batch_size=2)
        images = [_image(), _image()]
        camera_ids = ["cam_a", "cam_b"]
        keypoints = np.zeros((1, 133, 2), dtype=np.float64)
        scores = np.zeros((1, 133), dtype=np.float32)
        with patch.object(
            session,
            "predict_batch",
            return_value=[(keypoints, scores), (keypoints, scores)],
        ):
            outcome = infer_or_skip_batch(
                frame_number=7,
                images=images,
                ordered_camera_ids=camera_ids,
                camera_ids=camera_ids,
                session=session,
            )
        assert outcome.kind == "infer"
        assert outcome.per_camera_skeleton is not None
        assert set(outcome.per_camera_skeleton.keys()) == set(camera_ids)

    def test_catch_mismatch(self) -> None:
        session = _session(batch_size=2)
        with patch.object(
            session,
            "predict_batch",
            side_effect=BatchSizeMismatchError(actual=2, expected=3),
        ):
            outcome = infer_or_skip_batch(
                frame_number=3,
                images=[_image(), _image()],
                ordered_camera_ids=["cam_a", "cam_b"],
                camera_ids=["cam_a", "cam_b"],
                session=session,
            )
        assert outcome.kind == "catch_mismatch"
        assert outcome.mismatch_actual == 2
        assert outcome.mismatch_expected == 3

    def test_short_results_raises(self) -> None:
        session = _session(batch_size=2)
        keypoints = np.zeros((1, 133, 2), dtype=np.float64)
        scores = np.zeros((1, 133), dtype=np.float32)
        with patch.object(
            session,
            "predict_batch",
            return_value=[(keypoints, scores)],
        ):
            with pytest.raises(ValueError, match="returned 1 results"):
                infer_or_skip_batch(
                    frame_number=5,
                    images=[_image(), _image()],
                    ordered_camera_ids=["cam_a", "cam_b"],
                    camera_ids=["cam_a", "cam_b"],
                    session=session,
                )


class TestReadFramesOrder:
    def test_full_read_preserves_camera_ids_order(self) -> None:
        camera_ids = ["cam_a", "cam_b", "cam_c"]
        frame_recarrays: dict[str, np.recarray | None] = {cam_id: None for cam_id in camera_ids}
        camera_shms: dict[str, CameraSharedMemoryRingBuffer] = {}
        for cam_id in camera_ids:
            shm = create_autospec(CameraSharedMemoryRingBuffer, instance=True)
            rec = MagicMock()
            rec.frame_metadata.frame_number = np.array([10])
            rec.frame_metadata.camera_info.rotation = np.array([-1])
            rec.image = np.array([_image()])
            shm.get_data_by_index.return_value = rec
            camera_shms[cam_id] = shm

        images, ordered_camera_ids = _read_frames(
            camera_ids=camera_ids,
            camera_shms=camera_shms,
            frame_recarrays=frame_recarrays,
            requested_frame_number=10,
        )
        assert len(images) == 3
        assert ordered_camera_ids == camera_ids
