"""Pure unit tests for realtime_pipeline_lifecycle helpers."""

from copy import deepcopy

from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import (
    RealtimeAggregatorNodeConfig,
)
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_lifecycle import (
    needs_centralized_rtmpose,
    skeleton_session_config_changed,
)


def _centralized_config(**overrides) -> RealtimePipelineConfig:
    cfg = RealtimePipelineConfig(
        use_centralized_gpu_inference=True,
        camera_node_config=RealtimePipelineConfig().camera_node_config.model_copy(
            update={"skeleton_tracking_enabled": True},
        ),
        realtime_detector_kind="rtmpose",
    )
    if overrides:
        return cfg.model_copy(update=overrides)
    return cfg


class TestNeedsCentralizedRtmpose:
    def test_true_when_centralized_rtmpose_enabled(self) -> None:
        assert needs_centralized_rtmpose(_centralized_config()) is True

    def test_false_when_skeleton_tracking_disabled(self) -> None:
        cfg = _centralized_config()
        cfg = cfg.model_copy(
            update={
                "camera_node_config": cfg.camera_node_config.model_copy(
                    update={"skeleton_tracking_enabled": False},
                ),
            },
        )
        assert needs_centralized_rtmpose(cfg) is False


class TestSkeletonSessionConfigChanged:
    def test_ep_change_when_both_centralized(self) -> None:
        old = _centralized_config()
        new = deepcopy(old)
        new.skeleton_inference_node_config.execution_provider = "trt"
        assert skeleton_session_config_changed(old, new) is True

    def test_log_timing_change_when_both_centralized(self) -> None:
        old = _centralized_config(log_pipeline_times=True)
        new = deepcopy(old)
        new.log_pipeline_times = False
        assert skeleton_session_config_changed(old, new) is True

    def test_false_when_centralized_off_on_either_side(self) -> None:
        old = _centralized_config()
        new = _centralized_config(use_centralized_gpu_inference=False)
        assert skeleton_session_config_changed(old, new) is False

    def test_false_for_triangulation_only_change(self) -> None:
        old = _centralized_config()
        new = deepcopy(old)
        new.aggregator_config = RealtimeAggregatorNodeConfig(triangulation_enabled=False)
        assert skeleton_session_config_changed(old, new) is False
