"""Batch gating and inference orchestration for the realtime skeleton worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseObservation
from skellytracker.trackers.rtmpose_tracker.rtmpose_observation import RTMPoseObservation
from skellytracker.trackers.rtmpose_tracker.rtmpose_session import RTMPoseSession
from skellytracker.trackers.rtmpose_tracker.rtmpose_session_errors import (
    BatchSizeMismatchError,
)

from freemocap.core.pipeline.pipeline_timing_events import call_with_supported_kwargs
from freemocap.core.types.type_overloads import TopicPublicationQueue
from freemocap.pubsub.pubsub_topics import SkeletonInferenceResultMessage


@dataclass(frozen=True)
class SkeletonBatchOutcome:
    kind: Literal["skip", "catch_mismatch", "infer"]
    per_camera_skeleton: dict[CameraIdString, BaseObservation | None] | None = None
    mismatch_actual: int | None = None
    mismatch_expected: int | None = None


def should_run_inference(
    images: list[NDArray[np.uint8]],
    ordered_camera_ids: list[CameraIdString],
    camera_ids: list[CameraIdString],
    session: RTMPoseSession,
) -> bool:
    n = len(images)
    return (
        n > 0
        and n == len(ordered_camera_ids)
        and n == len(camera_ids)
        and n == session.batch_size
    )


def publish_skipped_batch(
    *,
    frame_number: int,
    camera_ids: list[CameraIdString],
    pub: TopicPublicationQueue,
) -> None:
    pub.put(
        SkeletonInferenceResultMessage(
            frame_number=frame_number,
            per_camera_skeleton={camera_id: None for camera_id in camera_ids},
        ),
    )


def infer_or_skip_batch(
    *,
    frame_number: int,
    images: list[NDArray[np.uint8]],
    ordered_camera_ids: list[CameraIdString],
    camera_ids: list[CameraIdString],
    session: RTMPoseSession,
    parent_task_ids: list[str] | None = None,
    event_collector: object | None = None,
) -> SkeletonBatchOutcome:
    if not should_run_inference(images, ordered_camera_ids, camera_ids, session):
        return SkeletonBatchOutcome(kind="skip")

    try:
        batch_results = call_with_supported_kwargs(
            session.predict_batch,
            images,
            frame_number=frame_number,
            camera_ids=ordered_camera_ids,
            parent_task_ids=parent_task_ids,
            event_collector=event_collector,
        )
    except BatchSizeMismatchError as exc:
        return SkeletonBatchOutcome(
            kind="catch_mismatch",
            mismatch_actual=exc.actual,
            mismatch_expected=exc.expected,
        )

    if len(batch_results) != len(images):
        raise ValueError(
            f"predict_batch returned {len(batch_results)} results for {len(images)} images"
        )
    if ordered_camera_ids != camera_ids:
        raise ValueError(
            "full-read gate passed but ordered_camera_ids != camera_ids — "
            "_read_frames must iterate camera_ids in pipeline order"
        )

    per_camera_skeleton: dict[CameraIdString, BaseObservation | None] = {}
    for camera_id, image, (keypoints, scores) in zip(
        ordered_camera_ids, images, batch_results
    ):
        per_camera_skeleton[camera_id] = RTMPoseObservation.from_detection_results(
            frame_number=frame_number,
            keypoints=keypoints,
            scores=scores,
            image_size=(int(image.shape[0]), int(image.shape[1])),
        )
    if __debug__:
        assert len(per_camera_skeleton) == len(camera_ids)
    return SkeletonBatchOutcome(kind="infer", per_camera_skeleton=per_camera_skeleton)
