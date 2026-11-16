"""Config for the centralized RealtimeSkeletonInferenceNode."""
from pydantic import BaseModel
from freemocap.core.tracking.execution_providers import RequestedExecutionProvider


class RealtimeSkeletonInferenceNodeConfig(BaseModel):
    # Upper bound on batch size. The node uses min(num_cameras, max_batch_size)
    # at runtime. Set to 1 to disable batching across cameras while keeping the
    # single-CUDA-context win.
    max_batch_size: int = 8

    # None: Auto, the skellytracker recommendation for this host — recommended.
    # "cpu", "coreml", "cuda", "trt-rtx": a skellytracker 2.0 EP key. An explicit
    # key that cannot start raises when the run starts. MediaPipe takes no EP.
    execution_provider: RequestedExecutionProvider = None

    # When True, writes debug frames with bbox overlays to
    # {freemocap_data}/debug_bboxes/. (requires GPU mode)
    debug_draw_bboxes: bool = False
