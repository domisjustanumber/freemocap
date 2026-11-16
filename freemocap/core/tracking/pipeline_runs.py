"""Start the skellytracker 2.0 pipeline run of a detector choice.

One run serves one realtime camera group (`live`) or one posthoc recording (`video`). The run
is thread-safe: its calls are serial, `close()` from another thread waits for the call that
runs, and two runs can run at the same time on two threads.
"""
from collections.abc import Mapping, Sequence
import logging
from typing import Any

import numpy as np

from freemocap.core.tracking.execution_providers import EXECUTION_PROVIDERS, REMOVED_PROVIDERS

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
PERSON_ROI = "person_roi"
HOLISTIC_NODE = "holistic"
RTMW_MIN_SCORE = 0.4
"""An RTMW point with a lower score is missing, as the `sfn26` RTMW detector did."""
STAGE = "body"
"""The one stage of a converted observation; its point names are the `<group>/<point>` names of the run."""
RUNNING_MODES = {"realtime": "live", "posthoc": "video"}


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
    if requested not in (None, "auto", *REMOVED_PROVIDERS):
        raise ValueError(f"Unknown execution provider {requested!r}; choose one of {EXECUTION_PROVIDERS}")
    chosen = eps.recommend("performance").chosen.ep_key
    logger.info("Execution provider %s chosen for requested %s", chosen, requested or "auto")
    return chosen


def start_detector_run(*, detector_type: str, camera_ids: Sequence[str], running_mode: str,
                       rtmpose_model_name: str | None = None, execution_provider: str | None = None):
    """Start the run of a detector choice; return it with its EP key. Give an EP only when the pipeline needs one."""
    from skellytracker.core.pipelines import check_pipeline, start_pipeline
    config = load_detector_pipeline(detector_type, rtmpose_model_name)
    provider = run_execution_provider(execution_provider) if check_pipeline(config).needs_execution_provider else None
    run = start_pipeline(config, camera_ids=list(camera_ids), running_mode=running_mode, execution_provider=provider)
    return run, provider


def observations_from_results(results: Mapping[str, Mapping[str, Any]], output_schema: Mapping[str, Any],
                              detector_type: str) -> dict:
    """The one boundary from a pipeline result to freemocap's observation type, for each camera.

    Points are taken by name: RTMW through `to_canonical`, Holistic by its point names. An RTMW
    point with a score below 0.4 or no x and y is missing (NaN, score 0); a kept 2D point has z 0.
    """
    # shortcut: the observation type is still skellytracker's; the user's answer to V1 sets freemocap's own.
    from skellytracker.core.data_primitives import BoundingBox, Keypoints, Observation, StageObservation
    from skellytracker.core.pipelines import to_canonical
    observations = {}
    for camera_id, result in results.items():
        width, height = result["image_size"]
        boxes = []
        if detector_type == "rtmpose":
            canonical = to_canonical(result[RTMW_NODE], output_schema[RTMW_NODE])
            names, xyz, score = canonical.names, canonical.xyz[0].copy(), canonical.score[0].copy()
            missing = (score < RTMW_MIN_SCORE) | ~np.isfinite(xyz[:, :2]).all(axis=1)
            xyz[:, 2] = 0.0
            xyz[missing], score[missing] = np.nan, 0.0
            roi = result[PERSON_ROI]
            if roi.present[0]:
                cx, cy, w, h, _ = roi.rois[0]
                # clip, then int(), as the sfn26 crop box was
                x1, x2 = (int(min(max(0.0, value), width)) for value in (cx - w / 2, cx + w / 2))
                y1, y2 = (int(min(max(0.0, value), height)) for value in (cy - h / 2, cy + h / 2))
                boxes.append(BoundingBox(x1, y1, x2, y2, float(roi.instance_score[0])))
            detector_ran = bool(result["node_ran"][PERSON_NODE])
        else:
            value = result[HOLISTIC_NODE]
            names, xyz, score = value.point_names, value.xyz[0].copy(), value.score[0].copy()
            detector_ran = True  # Holistic has no person detector
        stage = StageObservation(name=STAGE, bounding_boxes=boxes, detector_ran=detector_ran,
                                 keypoints=Keypoints(names=tuple(names), xyz=xyz, visibility=score))
        observations[camera_id] = Observation(frame_number=int(result["frame_index"]), image_size=(height, width),
                                              stages={STAGE: stage})
    return observations
