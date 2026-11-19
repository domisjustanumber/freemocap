"""Config for the centralized RealtimeSkeletonInferenceNode."""
from typing import Literal

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

    # The old skellytracker Tracker (YOLOX + RTMW x-l 256x192) on cpu or cuda, to compare it with 2.0; realtime only.  # Deleted at skellytracker stage 2.4 (legacy tracker benchmark).
    legacy_tracker_benchmark: bool = False  # Deleted at skellytracker stage 2.4 (legacy tracker benchmark).
    # skellytracker's `start_pipeline(preprocess=...)`, for a benchmark of where the frame preprocessing runs:
    # "auto" its default, "cpu" all frame work on the CPU, "gpu" the GPU preprocess on each EP that has it.
    preprocess: Literal["auto", "cpu", "gpu"] = "auto"

    # When True, writes debug frames with bbox overlays to
    # {freemocap_data}/debug_bboxes/. (requires GPU mode)
    debug_draw_bboxes: bool = False
