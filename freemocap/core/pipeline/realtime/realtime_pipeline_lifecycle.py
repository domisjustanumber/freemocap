"""Pure restart decisions for the global realtime pipeline."""

from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig


def needs_centralized_rtmpose(cfg: RealtimePipelineConfig) -> bool:
    return (
        cfg.use_centralized_gpu_inference
        and cfg.camera_node_config.skeleton_tracking_enabled
        and cfg.realtime_detector_kind == "rtmpose"
    )


def skeleton_session_config_changed(
    old: RealtimePipelineConfig,
    new: RealtimePipelineConfig,
) -> bool:
    if not (needs_centralized_rtmpose(old) and needs_centralized_rtmpose(new)):
        return False
    if old.skeleton_inference_node_config.model_dump() != new.skeleton_inference_node_config.model_dump():
        return True
    if old.log_pipeline_times != new.log_pipeline_times:
        return True
    return (
        old.camera_node_config.skeleton_detector_config.model_dump()
        != new.camera_node_config.skeleton_detector_config.model_dump()
    )
