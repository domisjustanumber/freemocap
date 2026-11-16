"""Config for the centralized RealtimeSkeletonInferenceNode."""
from pydantic import BaseModel


class RealtimeSkeletonInferenceNodeConfig(BaseModel):
    # Upper bound on batch size. The node uses min(num_cameras, max_batch_size)
    # at runtime. Set to 1 to disable batching across cameras while keeping the
    # single-model-session win.
    max_batch_size: int = 8

    # None: Auto, the skellytracker recommendation for this host — recommended.
    # Otherwise a skellytracker EP key; skellytracker refuses a key it does not
    # have, or one that cannot start, when the run starts. MediaPipe takes no EP.
    execution_provider: str | None = None
    # A skellytracker device key of the chosen EP; None is skellytracker's choice. Auto ignores it.
    execution_device: str | None = None

    # When True, writes debug frames with bbox overlays to
    # {freemocap_data}/debug_bboxes/. (requires GPU mode)
    debug_draw_bboxes: bool = False
