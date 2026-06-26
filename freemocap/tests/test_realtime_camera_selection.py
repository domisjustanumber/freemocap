"""Tests for realtime_camera_selection helpers."""

from unittest.mock import MagicMock

from skellycam.core.camera_group.camera_group import CameraGroup

from freemocap.core.pipeline.realtime.realtime_camera_selection import (
    camera_ids_for_realtime_pipeline,
)


def _camera_group(config_keys: list[str]) -> CameraGroup:
    group = MagicMock(spec=CameraGroup)
    group.configs = {key: object() for key in config_keys}
    return group


class TestCameraIdsForRealtimePipeline:
    def test_explicit_subset_preserves_group_key_order(self) -> None:
        group = _camera_group(["cam_b", "cam_a", "cam_c"])
        assert camera_ids_for_realtime_pipeline(group, ["cam_c", "cam_a"]) == ["cam_a", "cam_c"]

    def test_unknown_ids_filtered_out(self) -> None:
        group = _camera_group(["cam_a"])
        assert camera_ids_for_realtime_pipeline(group, ["cam_a", "missing"]) == ["cam_a"]

    def test_empty_request_returns_empty(self) -> None:
        group = _camera_group(["cam_a"])
        assert camera_ids_for_realtime_pipeline(group, []) == []

    def test_none_returns_all_group_cameras(self) -> None:
        group = _camera_group(["cam_b", "cam_a"])
        assert camera_ids_for_realtime_pipeline(group, None) == ["cam_b", "cam_a"]
