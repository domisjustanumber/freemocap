"""Builds a posthoc annotation StageAnnotationSchema that matches the realtime
browser overlay's region-based coloring (see freemocap-ui's
skeleton-overlay-renderer.ts: classifySide/classifyHand/classifyFace/styleFor).
"""
from __future__ import annotations

from skellytracker.core.annotation.keypoint_annotator import (
    ConnectionGroupSchema,
    StageAnnotationSchema,
)

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray
from skellytracker.core.annotation.keypoint_annotator import KeypointAnnotator, KeypointAnnotatorConfig
from skellytracker.core.data_primitives import Keypoints, Observation, StageObservation
from skellytracker.core.detectors.calibration import CharucoAnnotator, CharucoAnnotatorConfig, CharucoBoardDefinition
from freemocap.core.tracking.charuco_detection import CHARUCO_STAGE
from freemocap.core.tracking.tracker_definitions import tracker_definition

# BGR (cv2 convention) equivalents of the realtime renderer's hex colors.
_CENTER_COLOR = (0, 170, 0)       # #00AA00
_RIGHT_COLOR = (68, 68, 255)      # #FF4444
_LEFT_COLOR = (255, 136, 68)      # #4488FF
_RIGHT_HAND_COLOR = (0, 100, 255)  # #FF6400
_LEFT_HAND_COLOR = (255, 170, 0)  # #00AAFF
_FACE_COLOR = (0, 215, 255)       # #FFD700
# The points of the `face` group are dense: at the stage radius their dots cover the face lines between them
# (user V3). Body, hand and foot points keep the stage radius.
FACE_KEYPOINT_RADIUS = 2
_FACE_POINTS_STAGE = "face_points"  # drawing only: the face points of the body stage, with their own radius

_BOX_COLOR_DETECTED = (0, 255, 0)   # #00FF00
_BOX_COLOR_REUSED = (0, 140, 255)   # #FF8C00


def _classify_hand(name: str) -> str | None:
    lc = name.lower()
    if lc.startswith("left_hand"):
        return "left_hand"
    if lc.startswith("right_hand"):
        return "right_hand"
    return None


def _classify_face(name: str) -> bool:
    lc = name.lower()
    return lc.startswith("face")


def _classify_side(name: str) -> str:
    lc = name.lower()
    if "left" in lc:
        return "left"
    if "right" in lc:
        return "right"
    return "center"


def _is_center(name: str) -> bool:
    return (
        not _classify_face(name)
        and _classify_hand(name) is None
        and _classify_side(name) == "center"
    )


def _color_for(name: str) -> tuple[int, int, int]:
    if _classify_face(name):
        return _FACE_COLOR
    hand = _classify_hand(name)
    if hand == "left_hand":
        return _LEFT_HAND_COLOR
    if hand == "right_hand":
        return _RIGHT_HAND_COLOR
    side = _classify_side(name)
    if side == "left":
        return _LEFT_COLOR
    if side == "right":
        return _RIGHT_COLOR
    return _CENTER_COLOR


def _thickness_for(name: str) -> int:
    # 1px face lines match the realtime canvas overlay but don't survive H.264
    # compression in the saved video (thin diagonal strokes get smoothed away
    # while the solid keypoint dots don't), so use 2px here instead.
    return 2


def build_skeleton_stage_schema(
    connections: tuple[tuple[str, str], ...],
    tracked_points: tuple[str, ...],
) -> StageAnnotationSchema:
    """Build a StageAnnotationSchema whose connection_groups reproduce the
    realtime overlay's per-region coloring for the given connection list.

    Point color and line color are computed independently, matching the
    realtime renderer: each point is colored by its own name (`styleFor`),
    while each line takes its non-center endpoint's color. `KeypointAnnotator`
    only exposes per-point color via a connection group's shared
    `keypoint_color` (applied to both of that connection's endpoints), so line
    groups leave `keypoint_color` unset and a separate set of single-point
    "self-connection" groups carries the actual per-point colors.
    """
    line_buckets: dict[tuple[int, int, int], list[tuple[str, str]]] = {}
    for name_a, name_b in connections:
        color = _color_for(name_b) if _is_center(name_a) else _color_for(name_a)
        line_buckets.setdefault(color, []).append((name_a, name_b))

    point_buckets: dict[tuple[int, int, int], list[str]] = {}
    for name in tracked_points:
        point_buckets.setdefault(_color_for(name), []).append(name)

    connection_groups = tuple(
        ConnectionGroupSchema(
            connections=tuple(group_connections),
            connection_color=color,
            connection_thickness=_thickness_for(group_connections[0][0]),
        )
        for color, group_connections in line_buckets.items()
    ) + tuple(
        ConnectionGroupSchema(
            connections=tuple((name, name) for name in names),
            connection_color=color,
            connection_thickness=1,
            keypoint_color=color,
        )
        for color, names in point_buckets.items()
    )

    return StageAnnotationSchema(
        connections=connections,
        connection_groups=connection_groups,
        draw_boxes=True,
        box_color_detected=_BOX_COLOR_DETECTED,
        box_color_reused=_BOX_COLOR_REUSED,
    )


def _split_face_points(stage: StageObservation) -> tuple[StageObservation, StageObservation | None]:
    """The stage without the points of the `face` group, and those points as the drawing stage of their own radius."""
    keypoints = stage.keypoints
    if keypoints is None:
        return stage, None
    face = [index for index, name in enumerate(keypoints.names) if _classify_face(name)]
    if not face:
        return stage, None
    rest = [index for index in range(len(keypoints.names)) if index not in set(face)]
    part = lambda indices: Keypoints(tuple(keypoints.names[i] for i in indices), keypoints.xyz[indices], keypoints.visibility[indices])
    return replace(stage, keypoints=part(rest)), StageObservation(name=_FACE_POINTS_STAGE, keypoints=part(face))


@dataclass(frozen=True)
class ObservationAnnotator:
    """Draws the body stages with `KeypointAnnotator` and the charuco stage with `CharucoAnnotator`."""

    body: KeypointAnnotator | None
    board: CharucoAnnotator | None

    def annotate(self, image: NDArray[np.uint8], observation: Observation) -> NDArray[np.uint8]:
        out = image.copy()
        if self.body is not None:
            # KeypointAnnotator draws every stage; the board has its own annotator.
            stages = {}
            for name, stage in observation.stages.items():
                if name == CHARUCO_STAGE and self.board is not None:
                    continue
                stages[name], face = _split_face_points(stage) if name == "body" else (stage, None)
                if face is not None:
                    stages[_FACE_POINTS_STAGE] = face
            out = self.body.annotate(out, replace(observation, stages=stages))
        stage = observation.stages.get(CHARUCO_STAGE)
        if self.board is not None and stage is not None and stage.keypoints is not None:
            out = self.board.annotate(out, stage.keypoints)
        return out


def build_observation_annotator(*, detector_type: str | None = None,
                                board: CharucoBoardDefinition | None = None) -> ObservationAnnotator:
    """Draw the body stage of a detector choice and the charuco stage of a board, each when given."""
    body = None
    if detector_type is not None:
        definition = tracker_definition(detector_type)
        # No connection joins a face point to another group, so each drawing stage keeps all of its lines.
        face_edges = tuple(edge for edge in definition.connections if _classify_face(edge[0]))
        face_points = tuple(name for name in definition.tracked_points if _classify_face(name))
        body = KeypointAnnotator(config=KeypointAnnotatorConfig(stage_schemas={
            "body": build_skeleton_stage_schema(
                tuple(edge for edge in definition.connections if edge not in face_edges),
                tuple(name for name in definition.tracked_points if name not in face_points)),
            _FACE_POINTS_STAGE: replace(build_skeleton_stage_schema(face_edges, face_points),
                                        keypoint_radius=FACE_KEYPOINT_RADIUS, draw_boxes=False)}))
    board_annotator = None if board is None else CharucoAnnotator(config=CharucoAnnotatorConfig(), board_def=board)
    return ObservationAnnotator(body=body, board=board_annotator)
