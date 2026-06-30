"""Tests for realtime pipeline lifecycle helpers and manager singleton behavior."""

import multiprocessing
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector import RTMPoseDetectorConfig

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_camera_selection import (
    camera_ids_for_realtime_pipeline as _camera_ids_for_realtime_pipeline,
)
from freemocap.core.pipeline.realtime.realtime_pipeline_lifecycle import (
    needs_centralized_rtmpose,
    skeleton_session_config_changed,
)
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node_config import (
    RealtimeSkeletonInferenceNodeConfig,
)


@pytest.fixture
def worker_registry() -> WorkerRegistry:
    return WorkerRegistry(
        global_kill_flag=multiprocessing.Value("b", False),
        worker_mode=WorkerMode.THREAD,
    )


def _centralized_config(**updates) -> RealtimePipelineConfig:
    cfg = RealtimePipelineConfig(
        use_centralized_gpu_inference=True,
        camera_node_config=CameraNodeConfig(
            skeleton_tracking_enabled=True,
            skeleton_detector_config=RTMPoseDetectorConfig(mode="balanced"),
        ),
        skeleton_inference_node_config=RealtimeSkeletonInferenceNodeConfig(
            execution_provider="cuda",
        ),
    )
    if updates:
        return cfg.model_copy(update=updates)
    return cfg


class TestNeedsCentralizedRtmpose:
    def test_true_only_when_all_conditions_met(self) -> None:
        assert needs_centralized_rtmpose(_centralized_config()) is True

    def test_false_when_centralized_disabled(self) -> None:
        assert needs_centralized_rtmpose(
            _centralized_config(use_centralized_gpu_inference=False)
        ) is False

    def test_false_when_skeleton_tracking_disabled(self) -> None:
        assert needs_centralized_rtmpose(
            _centralized_config(
                camera_node_config=CameraNodeConfig(
                    skeleton_tracking_enabled=False,
                    skeleton_detector_config=RTMPoseDetectorConfig(mode="balanced"),
                ),
            )
        ) is False

    def test_false_when_detector_not_rtmpose(self) -> None:
        assert needs_centralized_rtmpose(
            _centralized_config(realtime_detector_kind="mediapipe_js")
        ) is False


class TestSkeletonSessionConfigChanged:
    def test_ep_change_when_both_centralized(self) -> None:
        old = _centralized_config()
        new = _centralized_config(
            skeleton_inference_node_config=RealtimeSkeletonInferenceNodeConfig(
                execution_provider="trt",
            ),
        )
        assert skeleton_session_config_changed(old, new) is True

    def test_log_timing_change(self) -> None:
        old = _centralized_config(log_pipeline_times=False)
        new = _centralized_config(log_pipeline_times=True)
        assert skeleton_session_config_changed(old, new) is True

    def test_false_when_not_centralized(self) -> None:
        old = _centralized_config(use_centralized_gpu_inference=False)
        new = _centralized_config()
        assert skeleton_session_config_changed(old, new) is False

    def test_triangulation_only_change_is_false(self) -> None:
        old = _centralized_config()
        new = _centralized_config(
            aggregator_config=RealtimeAggregatorNodeConfig(triangulation_enabled=False),
        )
        assert skeleton_session_config_changed(old, new) is False


def _mock_pipeline(
    *,
    pipeline_id: str = "pipe_1",
    camera_group_id: str = "group_a",
    camera_ids: list[str] | None = None,
    alive: bool = True,
    config: RealtimePipelineConfig | None = None,
) -> MagicMock:
    pipeline = MagicMock()
    pipeline.id = pipeline_id
    pipeline.camera_group_id = camera_group_id
    pipeline.camera_ids = camera_ids or ["cam_a"]
    pipeline.alive = alive
    pipeline.config = config or _centralized_config()
    pipeline.camera_group = _camera_group(
        group_id=camera_group_id,
        camera_keys=camera_ids or ["cam_a"],
    )
    return pipeline


def _camera_group(*, group_id: str = "group_a", camera_keys: list[str] | None = None) -> CameraGroup:
    keys = camera_keys or ["cam_a"]
    return cast(
        CameraGroup,
        SimpleNamespace(id=group_id, configs={key: object() for key in keys}),
    )


_resolve_camera_ids = getattr(
    _camera_ids_for_realtime_pipeline,
    "__wrapped__",
    _camera_ids_for_realtime_pipeline,
)
_apply_pipeline_config = RealtimePipelineManager._apply_pipeline_config.__wrapped__
_update_pipeline_config = RealtimePipelineManager.update_pipeline_config.__wrapped__
_has_active_realtime_pipeline = RealtimePipelineManager.has_active_realtime_pipeline.__wrapped__


@pytest.fixture(autouse=True)
def unwrapped_camera_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "freemocap.core.pipeline.realtime.realtime_pipeline_manager.camera_ids_for_realtime_pipeline",
        _resolve_camera_ids,
    )
    monkeypatch.setattr(
        RealtimePipelineManager,
        "_snapshot_and_clear_duplicate_pipelines",
        RealtimePipelineManager._snapshot_and_clear_duplicate_pipelines.__wrapped__,
    )
    monkeypatch.setattr(
        RealtimePipelineManager,
        "_get_realtime_pipeline",
        RealtimePipelineManager._get_realtime_pipeline.__wrapped__,
    )
    monkeypatch.setattr(
        RealtimePipelineManager,
        "_apply_pipeline_config",
        RealtimePipelineManager._apply_pipeline_config.__wrapped__,
    )


class TestRealtimePipelineManagerSingleton:
    def test_legacy_duplicates_on_read_return_none(self, worker_registry: WorkerRegistry) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        manager.pipelines = {
            "a": _mock_pipeline(pipeline_id="a"),
            "b": _mock_pipeline(pipeline_id="b"),
        }
        assert manager.get_pipeline() is None

    @patch.object(RealtimePipeline, "create")
    def test_first_connect_creates_and_starts_pipeline(
        self, mock_create: MagicMock, worker_registry: WorkerRegistry
    ) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        created = _mock_pipeline(pipeline_id="new_pipe")
        mock_create.return_value = created
        camera_group = _camera_group()

        result = _apply_pipeline_config(
            manager,
            camera_group=camera_group,
            pipeline_config=_centralized_config(),
            realtime_camera_ids=["cam_a"],
        )

        mock_create.assert_called_once()
        created.start.assert_called_once()
        assert len(manager.pipelines) == 1
        assert manager.pipelines[created.id] is created
        assert result is created

    @patch.object(RealtimePipeline, "create")
    def test_ep_change_recenters_pipeline(
        self, mock_create: MagicMock, worker_registry: WorkerRegistry
    ) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        existing = _mock_pipeline(pipeline_id="pipe_1", camera_ids=["cam_a"])
        manager.pipelines = {existing.id: existing}
        replacement = _mock_pipeline(pipeline_id="pipe_2", camera_ids=["cam_a"])
        mock_create.return_value = replacement
        new_config = _centralized_config(
            skeleton_inference_node_config=RealtimeSkeletonInferenceNodeConfig(
                execution_provider="trt",
            ),
        )

        result = _apply_pipeline_config(
            manager,
            camera_group=_camera_group(),
            pipeline_config=new_config,
            realtime_camera_ids=["cam_a"],
        )

        existing.shutdown.assert_called_once()
        existing.update_config.assert_not_called()
        replacement.start.assert_called_once()
        assert len(manager.pipelines) == 1
        assert result is replacement

    def test_triangulation_only_change_updates_config_in_place(
        self, worker_registry: WorkerRegistry
    ) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        existing = _mock_pipeline(pipeline_id="pipe_1", camera_ids=["cam_a"])
        manager.pipelines = {existing.id: existing}
        new_config = _centralized_config(
            aggregator_config=RealtimeAggregatorNodeConfig(triangulation_enabled=False),
        )

        result = _apply_pipeline_config(
            manager,
            camera_group=_camera_group(),
            pipeline_config=new_config,
            realtime_camera_ids=["cam_a"],
        )

        existing.shutdown.assert_not_called()
        existing.update_config.assert_called_once_with(new_config)
        assert result is existing
        assert len(manager.pipelines) == 1

    @patch.object(RealtimePipeline, "create")
    def test_dead_pipeline_is_recreated(
        self, mock_create: MagicMock, worker_registry: WorkerRegistry
    ) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        existing = _mock_pipeline(pipeline_id="pipe_1", alive=False)
        manager.pipelines = {existing.id: existing}
        replacement = _mock_pipeline(pipeline_id="pipe_2")
        mock_create.return_value = replacement

        result = _apply_pipeline_config(
            manager,
            camera_group=_camera_group(),
            pipeline_config=_centralized_config(),
            realtime_camera_ids=["cam_a"],
        )

        existing.shutdown.assert_called_once()
        existing.update_config.assert_not_called()
        replacement.start.assert_called_once()
        assert result is replacement

    @patch.object(RealtimePipeline, "create")
    def test_camera_set_change_recenters_pipeline(
        self, mock_create: MagicMock, worker_registry: WorkerRegistry
    ) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        existing = _mock_pipeline(pipeline_id="pipe_1", camera_ids=["cam_a"])
        manager.pipelines = {existing.id: existing}
        replacement = _mock_pipeline(pipeline_id="pipe_2", camera_ids=["cam_a", "cam_b"])
        mock_create.return_value = replacement
        camera_group = _camera_group(camera_keys=["cam_a", "cam_b"])

        result = _apply_pipeline_config(
            manager,
            camera_group=camera_group,
            pipeline_config=_centralized_config(),
            realtime_camera_ids=["cam_a", "cam_b"],
        )

        existing.shutdown.assert_called_once()
        replacement.start.assert_called_once()
        assert result is replacement

    @patch.object(RealtimePipeline, "create")
    def test_legacy_duplicates_are_shutdown_before_recreate(
        self, mock_create: MagicMock, worker_registry: WorkerRegistry
    ) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        duplicate_a = _mock_pipeline(pipeline_id="a")
        duplicate_b = _mock_pipeline(pipeline_id="b")
        manager.pipelines = {"a": duplicate_a, "b": duplicate_b}
        replacement = _mock_pipeline(pipeline_id="new")
        mock_create.return_value = replacement

        _apply_pipeline_config(
            manager,
            camera_group=_camera_group(),
            pipeline_config=_centralized_config(),
            realtime_camera_ids=["cam_a"],
        )

        duplicate_a.shutdown.assert_called_once()
        duplicate_b.shutdown.assert_called_once()
        replacement.start.assert_called_once()
        assert len(manager.pipelines) == 1

    def test_read_during_empty_registry_returns_no_payloads(
        self, worker_registry: WorkerRegistry
    ) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        assert manager.get_latest_frontend_payloads(if_newer_than=0) == []
        assert _has_active_realtime_pipeline(manager) is False

    @patch.object(RealtimePipeline, "create")
    def test_update_pipeline_config_preserves_camera_ids(
        self, mock_create: MagicMock, worker_registry: WorkerRegistry
    ) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        existing = _mock_pipeline(pipeline_id="pipe_1", camera_ids=["cam_a", "cam_b"])
        manager.pipelines = {existing.id: existing}
        new_config = _centralized_config(
            aggregator_config=RealtimeAggregatorNodeConfig(triangulation_enabled=False),
        )

        result = _update_pipeline_config(
            manager,
            pipeline_id=existing.id,
            new_config=new_config,
        )

        mock_create.assert_not_called()
        existing.update_config.assert_called_once_with(new_config)
        assert result is existing

    @patch.object(RealtimePipeline, "create")
    def test_recreate_failure_leaves_manager_empty(
        self, mock_create: MagicMock, worker_registry: WorkerRegistry
    ) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        existing = _mock_pipeline(pipeline_id="pipe_1")
        manager.pipelines = {existing.id: existing}
        mock_create.side_effect = RuntimeError("create failed")

        with pytest.raises(RuntimeError, match="create failed"):
            _apply_pipeline_config(
                manager,
                camera_group=_camera_group(),
                pipeline_config=_centralized_config(
                    skeleton_inference_node_config=RealtimeSkeletonInferenceNodeConfig(
                        execution_provider="trt",
                    ),
                ),
                realtime_camera_ids=["cam_a"],
            )

        existing.shutdown.assert_called_once()
        assert manager.pipelines == {}

    def test_has_active_realtime_pipeline(self, worker_registry: WorkerRegistry) -> None:
        manager = RealtimePipelineManager(worker_registry=worker_registry)
        alive = _mock_pipeline(alive=True)
        dead = _mock_pipeline(alive=False)
        manager.pipelines = {alive.id: alive}
        assert _has_active_realtime_pipeline(manager) is True
        manager.pipelines = {dead.id: dead}
        assert _has_active_realtime_pipeline(manager) is False
