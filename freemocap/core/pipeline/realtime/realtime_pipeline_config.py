from pydantic import BaseModel, Field

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node_config import (
    RealtimeSkeletonInferenceNodeConfig,
)


class RealtimePipelineConfig(BaseModel):
    camera_node_config: CameraNodeConfig = Field(
        default_factory=CameraNodeConfig,
    )
    aggregator_config: RealtimeAggregatorNodeConfig = Field(
        default_factory=RealtimeAggregatorNodeConfig,
    )
    log_pipeline_times: bool = True

    skeleton_inference_node_config: RealtimeSkeletonInferenceNodeConfig = Field(
        default_factory=RealtimeSkeletonInferenceNodeConfig,
    )
