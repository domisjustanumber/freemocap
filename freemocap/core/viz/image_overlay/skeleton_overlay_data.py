"""
Flat, schema-driven skeleton overlay payload.

A `SkeletonOverlayData` carries a per-camera snapshot of a tracker's output as
a single list of fully-prefixed named points (e.g. `body.nose`, `left_hand.wrist`,
`face.contour_0`). It references a tracker schema by id — the frontend looks up
the matching `TrackedObjectDefinition` (sent separately over the `tracker_schemas`
WebSocket message) to draw connections.

This decoupling means adding a new tracker requires authoring a YAML definition,
not editing renderer code on either side.
"""
import msgspec
import numpy as np
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.rtmpose_tracker.names_and_connections import RTMPOSE_WHOLEBODY_DEFINITION
from skellytracker.trackers.rtmpose_tracker.rtmpose_observation import RTMPoseObservation
from skellytracker.trackers.mediapipe_tracker.composite.mediapipe_composite_observation import (
    MediapipeCompositeObservation,
)
from skellytracker.trackers.mediapipe_tracker.names_and_connections import MEDIAPIPE_HOLISTIC_DEFINITION


class SkeletonPointModel(msgspec.Struct):
    """A single detected landmark point. `name` is the fully-prefixed id that
    matches an entry in the active tracker's `TrackedObjectDefinition.tracked_points`."""
    name: str
    x: float
    y: float
    z: float
    visibility: float


class SkeletonOverlayData(msgspec.Struct):
    """Per-camera flat list of detected skeleton points for a single frame.

    `tracker_id` points at a `TrackedObjectDefinition` already sent to the
    frontend via the `tracker_schemas` handshake message. The frontend resolves
    connections by name against that schema.
    """
    camera_id: str
    frame_number: int
    tracker_id: str
    image_width: int
    image_height: int
    message_type: str = "skeleton_overlay"
    points: list[SkeletonPointModel] = []

    @classmethod
    def from_rtmpose_observation(
            cls,
            *,
            camera_id: CameraIdString,
            observation: RTMPoseObservation,
            scale: float = 1.0,
    ) -> "SkeletonOverlayData":
        """Flatten an RTMPose COCO-WholeBody observation into the schema-driven
        payload.

        Names come straight from `observation.points.names`, matching
        `RTMPOSE_WHOLEBODY_DEFINITION.tracked_points`. NaN rows are dropped.

        Coordinates are image-space pixels from inference (GPU or browser); use
        ``scale=1.0`` unchanged. ``scale`` exists for rare non-pixel pipelines.
        RTMPose is 2D only so z is always 0.
        """
        xyz: np.ndarray = observation.points.xyz * scale
        visibility: np.ndarray = observation.points.visibility
        names: tuple[str, ...] = observation.points.names

        points: list[SkeletonPointModel] = []
        for i, name in enumerate(names):
            x, y, z = xyz[i]
            if np.isnan(x) or np.isnan(y) or np.isnan(z):
                continue
            points.append(
                SkeletonPointModel(
                    name=name,
                    x=float(x),
                    y=float(y),
                    z=float(z),
                    visibility=float(visibility[i]),
                )
            )

        return cls(
            camera_id=camera_id,
            frame_number=observation.frame_number,
            tracker_id=RTMPOSE_WHOLEBODY_DEFINITION.name,
            image_width=observation.image_size[1],
            image_height=observation.image_size[0],
            message_type="skeleton_overlay",
            points=points,
        )

    @classmethod
    def from_mediapipe_composite_observation(
            cls,
            *,
            camera_id: CameraIdString,
            observation: MediapipeCompositeObservation,
            scale: float = 1.0,
    ) -> "SkeletonOverlayData":
        """Flatten a fused MediaPipe holistic PointCloud into the schema-driven payload."""
        xyz: np.ndarray = observation.points.xyz * scale
        visibility: np.ndarray = observation.points.visibility
        names: tuple[str, ...] = observation.points.names

        points: list[SkeletonPointModel] = []
        for i, name in enumerate(names):
            x, y, z = xyz[i]
            if np.isnan(x) or np.isnan(y) or np.isnan(z):
                continue
            points.append(
                SkeletonPointModel(
                    name=name,
                    x=float(x),
                    y=float(y),
                    z=float(z),
                    visibility=float(visibility[i]),
                ),
            )

        return cls(
            camera_id=camera_id,
            frame_number=observation.frame_number,
            tracker_id=MEDIAPIPE_HOLISTIC_DEFINITION.name,
            image_width=observation.image_size[1],
            image_height=observation.image_size[0],
            message_type="skeleton_overlay",
            points=points,
        )
