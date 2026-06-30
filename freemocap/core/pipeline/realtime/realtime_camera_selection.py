"""Shared camera subset/order resolution for realtime pipelines."""

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraIdString


def camera_ids_for_realtime_pipeline(
    camera_group: CameraGroup,
    realtime_camera_ids: list[CameraIdString] | None,
) -> list[CameraIdString]:
    """Camera IDs attached to realtime nodes (subset or full group).

    Order follows camera_group.configs.keys(), not the request array order.
    """
    if realtime_camera_ids is not None:
        return [cid for cid in camera_group.configs.keys() if cid in realtime_camera_ids]
    return list(camera_group.configs.keys())
