"""Parse client → server MediaPipe browser snapshots packed as RTMPose whole-body (133 points).

Wire layout (little-endian):

``CLIENT_SKELETON_PAYLOAD_HEADER`` (``MessageType.CLIENT_SKELETON_PAYLOAD_HEADER``)

* ``message_type`` u1
* ``frame_number`` i8
* ``num_cameras`` u4
* ``camera_group_id`` S64 (UTF-8, zero padded)

Repeated ``num_cameras`` times:

* ``camera_id`` S16 (ASCII / UTF-8, zero padded — matches skellycam width)
* ``image_width`` u4
* ``image_height`` u4
* ``num_points`` u4  (must match ``rtmpose_wholebody`` schema length — 133)
* ``data`` float32 ``num_points * 3`` — interleaved ``(x_px, y_px, visibility)``

``CLIENT_SKELETON_PAYLOAD_FOOTER`` mirrors the header (integrity check).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString
from skellytracker.trackers.base_tracker.point_cloud import PointCloud
from skellytracker.trackers.rtmpose_tracker.names_and_connections import RTMPOSE_WHOLEBODY_DEFINITION
from skellytracker.trackers.rtmpose_tracker.rtmpose_observation import RTMPoseObservation

from freemocap.api.websocket.binary_keypoints_protocol import (
    MessageType,
)
from freemocap.pubsub.pubsub_topics import SkeletonInferenceResultMessage

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_EXPECTED_NUM_POINTS: int = len(RTMPOSE_WHOLEBODY_DEFINITION.tracked_points)
_POINT_NAMES: tuple[str, ...] = RTMPOSE_WHOLEBODY_DEFINITION.tracked_points

_CLIENT_HEADER_DTYPE = np.dtype(
    [
        ("message_type", "<u1"),
        ("frame_number", "<i8"),
        ("num_cameras", "<u4"),
        ("camera_group_id", "S64"),
    ],
)

_PER_CAMERA_META_DTYPE = np.dtype(
    [
        ("camera_id", "S16"),
        ("image_width", "<u4"),
        ("image_height", "<u4"),
        ("num_points", "<u4"),
    ],
)


def parse_client_skeleton_binary(data: bytes | bytearray) -> tuple[CameraGroupIdString, SkeletonInferenceResultMessage] | None:
    """Return ``(camera_group_id, message)`` or ``None`` if bytes are not a client skeleton payload."""
    buf = memoryview(data)
    if len(buf) < _CLIENT_HEADER_DTYPE.itemsize:
        return None
    header = np.frombuffer(buf[: _CLIENT_HEADER_DTYPE.itemsize], dtype=_CLIENT_HEADER_DTYPE, count=1)[0]
    if int(header["message_type"]) != int(MessageType.CLIENT_SKELETON_PAYLOAD_HEADER):
        return None
    frame_number = int(header["frame_number"])
    num_cameras = int(header["num_cameras"])
    camera_group_id = str(np.char.decode(header["camera_group_id"], "utf-8")).strip("\x00").strip()

    offset = _CLIENT_HEADER_DTYPE.itemsize
    per_camera: dict[CameraIdString, RTMPoseObservation | None] = {}

    for _ in range(num_cameras):
        meta_end = offset + _PER_CAMERA_META_DTYPE.itemsize
        if meta_end > len(buf):
            logger.warning("client skeleton binary truncated at camera meta")
            return None
        meta = np.frombuffer(buf[offset:meta_end], dtype=_PER_CAMERA_META_DTYPE, count=1)[0]
        offset = meta_end
        cam_raw = meta["camera_id"]
        cam_id = str(np.char.decode(cam_raw, "utf-8")).strip("\x00").strip()
        w = int(meta["image_width"])
        h = int(meta["image_height"])
        n_pts = int(meta["num_points"])
        if n_pts != _EXPECTED_NUM_POINTS:
            logger.warning(
                "client skeleton num_points=%s != expected %s for camera %s",
                n_pts,
                _EXPECTED_NUM_POINTS,
                cam_id,
            )
            return None
        data_bytes = n_pts * 3 * 4
        if offset + data_bytes > len(buf):
            logger.warning("client skeleton binary truncated at float payload")
            return None
        flat = np.frombuffer(buf[offset : offset + data_bytes], dtype="<f4").reshape(n_pts, 3)
        offset += data_bytes
        xy = flat[:, :2].astype(np.float64, copy=False)
        vis = flat[:, 2].astype(np.float64, copy=False)
        z_zeros = np.zeros((n_pts,), dtype=np.float64)
        xyz = np.column_stack([xy[:, 0], xy[:, 1], z_zeros])
        nan_rows = vis <= 1e-6
        xyz[nan_rows] = np.nan
        cloud = PointCloud(names=_POINT_NAMES, xyz=xyz, visibility=vis)
        per_camera[cam_id] = RTMPoseObservation(
            frame_number=frame_number,
            image_size=(h, w),
            points=cloud,
        )

    # Optional footer (same layout as header)
    fh = _CLIENT_HEADER_DTYPE.itemsize
    if offset + fh <= len(buf):
        foot = np.frombuffer(buf[offset : offset + fh], dtype=_CLIENT_HEADER_DTYPE, count=1)[0]
        if int(foot["message_type"]) == int(MessageType.CLIENT_SKELETON_PAYLOAD_FOOTER):
            if int(foot["frame_number"]) != frame_number or int(foot["num_cameras"]) != num_cameras:
                logger.trace("client skeleton footer mismatch (continuing)")

    return (
        camera_group_id,
        SkeletonInferenceResultMessage(frame_number=frame_number, per_camera_skeleton=per_camera),
    )
