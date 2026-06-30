"""Tests for realtime camera selection helper."""

from types import SimpleNamespace

from typing import cast

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.core.pipeline.realtime.realtime_camera_selection import camera_ids_for_realtime_pipeline

_resolve_camera_ids = getattr(
    camera_ids_for_realtime_pipeline,
    "__wrapped__",
    camera_ids_for_realtime_pipeline,
)


def _camera_group(config_keys: list[str]) -> CameraGroup:
    return cast(CameraGroup, SimpleNamespace(configs={key: object() for key in config_keys}))


class TestCameraIdsForRealtimePipeline:
    def test_explicit_subset_preserves_group_key_order(self) -> None:
        group = _camera_group(["cam_b", "cam_a", "cam_c"])
        assert _resolve_camera_ids(group, ["cam_c", "cam_a"]) == ["cam_a", "cam_c"]

    def test_unknown_ids_filtered_out(self) -> None:
        group = _camera_group(["cam_a"])
        assert _resolve_camera_ids(group, ["cam_a", "missing"]) == ["cam_a"]

    def test_empty_request_returns_empty(self) -> None:
        group = _camera_group(["cam_a"])
        assert _resolve_camera_ids(group, []) == []

    def test_none_returns_all_group_cameras(self) -> None:
        group = _camera_group(["cam_a", "cam_b"])
        assert _resolve_camera_ids(group, None) == ["cam_a", "cam_b"]
