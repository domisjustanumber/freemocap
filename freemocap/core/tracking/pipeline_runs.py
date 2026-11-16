"""Start the skellytracker 2.0 pipeline run of a detector choice.

One run serves one realtime camera group (`live`) or one posthoc recording (`video`). The run
is thread-safe: its calls are serial, `close()` from another thread waits for the call that
runs, and two runs can run at the same time on two threads.
"""
from collections.abc import Sequence
import logging

logger = logging.getLogger(__name__)

PIPELINE_KEYS: dict[str, str] = {
    "rtmpose": "yolox-rtmw-wholebody@skellytracker",
    "mediapipe": "mediapipe-holistic-tasks@skellytracker",
}
RTMW_SIZES: dict[str, str] = {
    "rtmw-l-m_256x192": "m",
    "rtmw-x-l_256x192": "l-256",
    "rtmw-x-l_384x288": "l-384",
}
"""The old RTMW model names of the UI and of saved settings, mapped to the sizes of the sidecar."""
RTMW_NODE = "wholebody"
PERSON_NODE = "person"
EXECUTION_PROVIDERS: tuple[str, ...] = ("cpu", "coreml", "cuda", "trt-rtx")
"""The EP keys of skellytracker 2.0. DirectML and the classic TensorRT are not in v2."""


def load_detector_pipeline(detector_type: str, rtmpose_model_name: str | None = None):
    """The pipeline config of a detector choice, with the RTMW size of the model name."""
    from skellytracker.core.pipelines import load_pipeline
    config = load_pipeline(PIPELINE_KEYS[detector_type])
    if detector_type == "rtmpose" and rtmpose_model_name is not None:
        size = RTMW_SIZES[rtmpose_model_name]
        nodes = [node.model_copy(update={"params": node.params.model_copy(update={"size": size})})
                 if node.id == RTMW_NODE else node for node in config.nodes]
        config = config.model_copy(update={"nodes": nodes})
    return config


def run_execution_provider(requested: str | None) -> str:
    """The EP key of a run: the user's choice, or the skellytracker recommendation.

    An old saved choice that v2 does not have (`trt`, `directml`) is treated as Auto, as
    freemocap already did for `trt`.
    """
    from skellytracker.core import eps
    if requested in EXECUTION_PROVIDERS:
        return requested
    if requested not in (None, "auto", "trt", "directml"):
        raise ValueError(f"Unknown execution provider {requested!r}; choose one of {EXECUTION_PROVIDERS}")
    chosen = eps.recommend("performance").chosen.ep_key
    logger.info("Execution provider %s chosen for requested %s", chosen, requested or "auto")
    return chosen


def start_detector_run(*, detector_type: str, camera_ids: Sequence[str], running_mode: str,
                       rtmpose_model_name: str | None = None, execution_provider: str | None = None):
    """Start the run of a detector choice. Give an EP only when the pipeline needs one."""
    from skellytracker.core.pipelines import check_pipeline, start_pipeline
    config = load_detector_pipeline(detector_type, rtmpose_model_name)
    provider = run_execution_provider(execution_provider) if check_pipeline(config).needs_execution_provider else None
    return start_pipeline(config, camera_ids=list(camera_ids), running_mode=running_mode, execution_provider=provider)
