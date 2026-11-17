# Deleted at skellytracker stage 2.4 (legacy tracker benchmark).
"""The legacy tracker benchmark: the old skellytracker `Tracker` (YOLOX dynamic batch + RTMW x-l 256x192), realtime only.

It exists to compare the old run code with the 2.0 pipeline on the metrics timeline, and nothing is saved from it.
The session and the Tracker are built as the old freemocap factory built them (`dadfe94c:tracker_factory.py:67-143`).
The old RTMW points become the 2.0 canonical names through `to_canonical`, so mapping and overlays need nothing new.
Its scores stay the old raw SimCC scores (old detector threshold 0.004); `rtmpose_confidence_threshold` is not applied.
"""
from collections.abc import Callable, Mapping, Sequence
import logging
from pathlib import Path

import numpy as np

from freemocap.core.pipeline.pipeline_timing_events import SKELETON_INFERENCE, span_event
from freemocap.core.pipeline.pipeline_timing_task_ids import batch_task_id, camera_task_id
from freemocap.core.tracking.pipeline_runs import RTMW_NODE, PERSON_NODE, STAGE, _output_schema, _person
from freemocap.pubsub.pubsub_topics import PipelineTimingEvent

logger = logging.getLogger(__name__)

LEGACY_ENGINE = "legacy"
CUDA, TRT_RTX = "cuda", "trt-rtx"
LEGACY_EPS = ("cpu", CUDA)
"""The EPs of the old session (user ruling L3: TensorRT does not run the old models); the test of EP knowledge allows the keys."""
YOLOX_MODEL = "yolox-m"
RTMW_MODEL = "rtmw-x-l_256x192"
CONFIDENCE_THRESHOLD = 0.004
"""The old RTMW detector default; the aggregator's own confidence threshold applies afterwards."""
_REDETECT_SECONDS = 5.0
_VIDEO_FPS = 30.0


def legacy_ep_choice(requested: str | None) -> str:
    """The legacy EP for the user's EP choice: cpu and cuda as chosen; Auto or trt-rtx run cuda when its pack is usable, else cpu."""
    if requested in LEGACY_EPS:
        return requested
    if requested not in (None, "auto", TRT_RTX):
        raise ValueError(f"The legacy tracker benchmark runs on cpu or cuda only, not on {requested!r}. Choose CPU, CUDA or Auto.")
    from skellytracker.core import eps
    applied = CUDA if any(pack.key == CUDA and pack.usable for pack in eps.status().eps) else "cpu"
    logger.info("Legacy tracker benchmark: execution provider %s applied for requested %s", applied, requested or "auto")
    return applied


def _model_specs() -> list:
    try:
        from skellytracker.core.detectors.keypoint_detectors.rtmpose import RTMPoseKeypointDetector
        from skellytracker.core.detectors.object_detectors.yolox import YoloxPersonDetector
    except ModuleNotFoundError as error:
        if error.name != "onnx":
            raise
        raise RuntimeError("The legacy tracker benchmark needs the onnx package (skellytracker's onnx extra) "
                           "for the old YOLOX dynamic batch; it is not installed.") from error
    return [YoloxPersonDetector.model_spec(YOLOX_MODEL), RTMPoseKeypointDetector.model_spec(RTMW_MODEL)]


def _cached_file(spec) -> Path:
    """Where `resolve_model_path` finds the model of a spec without downloading it."""
    from skellytracker.core.sessions import model_registry
    if spec.source.local_path:
        return Path(spec.source.local_path)
    if spec.source.url is None:
        raise ValueError(f"The legacy model {spec.name!r} has no URL source, so its cache file is unknown")
    url_name = spec.source.url.rsplit("/", 1)[-1]
    return model_registry.DEFAULT_CACHE_DIR / (spec.expected_filename or url_name.replace(".zip", ".onnx"))


def _require_cached(specs) -> None:
    """Refuse a run whose old model file is not cached (user ruling L4): the legacy path never downloads."""
    missing = [str(path) for path in map(_cached_file, specs) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"The legacy tracker benchmark does not download models; these are not cached: {', '.join(missing)}")


def _build_tracker(session):
    from skellytracker.core import DetectionStageConfig, Tracker, TrackerConfig
    from skellytracker.core.detectors.keypoint_detectors.rtmpose import RTMPoseDetectorConfig
    from skellytracker.core.detectors.object_detectors.yolox import YoloxPersonDetectorConfig
    from skellytracker.core.temporal_processing.temporal_processing_config import (
        BBoxPolicyConfig, BBoxSmoothingConfig, KeypointsWithinBBoxRatioConfig,
    )
    config = TrackerConfig(stages=[DetectionStageConfig(
        name=STAGE,
        object_detector=YoloxPersonDetectorConfig(),
        keypoint_detectors=[RTMPoseDetectorConfig(model_name=RTMW_MODEL, confidence_threshold=CONFIDENCE_THRESHOLD)],
        bbox_policy=BBoxPolicyConfig(
            redetect_interval=max(1, round(_REDETECT_SECONDS * _VIDEO_FPS)), keypoint_bbox_expansion=0.05,
            fitness_checks=[KeypointsWithinBBoxRatioConfig(threshold=0.5)], min_shrink_ratio_per_frame=0.995,
            min_bbox_size_px=80.0),
        bbox_smoothing=BBoxSmoothingConfig(alpha=0.4),
    )])
    return Tracker.create(config, {"onnx": session})


def timing_events_from_legacy(events, pipeline_id: str) -> list[PipelineTimingEvent]:
    """The old Tracker's task events as freemocap's, under the frame's `predict_batch`; the stage keeps the old span name."""
    converted = []
    for event in events:
        frame = event.frame_number
        task_id = (camera_task_id(frame_number=frame, camera_id=event.camera_id, node_kind=SKELETON_INFERENCE, stage=event.stage)
                   if event.camera_id is not None else
                   batch_task_id(frame_number=frame, node_kind=SKELETON_INFERENCE, stage=event.stage))
        timing = span_event(task_id=f"{pipeline_id}:{task_id}", stage=event.stage, node_kind=SKELETON_INFERENCE,
                            frame_number=frame, start_time_ns=event.start_time_ns, end_time_ns=event.end_time_ns,
                            camera_id=event.camera_id, batch_size=event.batch_size)
        timing.batch_index = event.batch_index
        timing.parent_task_ids = [batch_task_id(frame_number=frame, node_kind=SKELETON_INFERENCE, stage="predict_batch")]
        converted.append(timing)
    return converted


def observations_from_legacy(observations: Mapping, output_schema: Mapping) -> dict:
    """The old observations in the 2.0 canonical names of the run schema; boxes and `detector_ran` pass through.

    The old RTMW gives the 133 COCO-WholeBody points in the order of the 2.0 `point_names`; a point is missing when
    its x or y is not finite or its old score is 0.
    """
    from skellytracker.core.data_primitives import Keypoints, Observation, StageObservation
    from skellytracker.core.pipelines import to_canonical
    from skellytracker.core.pipelines.values import InstanceKeypoints
    schema = output_schema[RTMW_NODE]
    point_names = tuple(schema["point_names"])
    converted = {}
    for camera_id, observation in observations.items():
        old = observation.stages[STAGE]
        xy, score = np.full((1, len(point_names), 2), np.nan), np.zeros((1, len(point_names)))
        if old.keypoints is not None:
            if len(old.keypoints.names) != len(point_names):
                raise ValueError(f"The old RTMW gave {len(old.keypoints.names)} points; the run schema has {len(point_names)}")
            xy[0], score[0] = old.keypoints.xyz[:, :2], old.keypoints.visibility
        present = np.isfinite(xy[0]).all(axis=1) & (score[0] > 0)
        xy[0, ~present], score[0, ~present] = np.nan, 0.0
        value = InstanceKeypoints(point_names, xy, score, score.copy(), np.ones(1), np.array([present.any()]), np.full(1, -1))
        canonical = to_canonical(value, schema)
        names, xyz, scores = _person(canonical.point_names, canonical.xy, None, canonical.score, value.present)
        missing = ~np.isfinite(xyz[:, :2]).all(axis=1)
        xyz[missing], scores[missing] = np.nan, 0.0
        stage = StageObservation(name=STAGE, bounding_boxes=list(old.bounding_boxes), detector_ran=old.detector_ran,
                                 keypoints=Keypoints(names=names, xyz=xyz, visibility=scores))
        converted[camera_id] = Observation(frame_number=observation.frame_number, image_size=observation.image_size,
                                           stages={STAGE: stage})
    return converted


class LegacyTrackerRun:
    """The old Tracker behind the 2.0 run interface of the inference service: `process_batch` gives observations."""

    def __init__(self, tracker, *, pipeline_id: str, models: dict, timing_sink: Callable[[object], None] | None) -> None:
        self._tracker = tracker
        self._states: dict = {}
        self._pipeline_id = pipeline_id
        self._timing_sink = timing_sink
        self.models = models
        self.output_schema = _output_schema("rtmpose")

    def process_batch(self, frames: Mapping) -> dict:
        """One call as the old realtime node made it: the newest frame of each camera, one batched call."""
        collector = None
        if self._timing_sink is not None:
            from skellytracker.core.tracker.task_events import TrackerTaskEventCollector
            collector = TrackerTaskEventCollector()
        frame_number = next(iter(frames.values())).frame_index
        observations, states = self._tracker.process_batch(
            {camera: frame.image for camera, frame in frames.items()}, frame_number, self._states, event_collector=collector)
        self._states.update(states)
        if collector is not None:
            for event in timing_events_from_legacy(collector.events, self._pipeline_id):
                self._timing_sink(event)
        return observations_from_legacy(observations, self.output_schema)

    def close(self) -> None:
        self._tracker.close()


def start_legacy_run(*, camera_ids: Sequence[str], pipeline_id: str, execution_provider: str,
                     selected_provider: str | None = None, timing_sink: Callable[[object], None] | None = None):
    """Start the old Tracker on `execution_provider` (cpu or cuda); return the run, its provider statuses and its record.

    A `timing_sink` gets each task event of a call as a `PipelineTimingEvent`; without one no collector is made.
    The errors of the cuda pack (`EpUnavailableError`, `SessionCreationError`, ...) reach the caller: no CPU retry.
    """
    if execution_provider not in LEGACY_EPS:
        raise ValueError(f"The legacy tracker benchmark runs on cpu or cuda only; {execution_provider!r} is refused "
                         "(TensorRT does not run the old models).")
    from skellytracker.core.sessions.onnx_session import OnnxSession, OnnxSessionConfig
    specs = _model_specs()
    _require_cached(specs)
    session = OnnxSession.create(OnnxSessionConfig(batch_size=len(camera_ids), models=specs, execution_provider=execution_provider))
    try:
        tracker = _build_tracker(session)
    except Exception:
        session.close()
        raise
    # The file the session loaded: `prepare` (the YOLOX dynamic batch) reuses its cached output.
    models = {node: {"key": spec.name, "engine": LEGACY_ENGINE, "file": (spec.prepare or Path)(_cached_file(spec)).name,
                     "execution_provider": session.execution_provider, "device": None}
              for node, spec in zip((PERSON_NODE, RTMW_NODE), specs)}
    record = {"engine": LEGACY_ENGINE, "running_mode": "live",
              "execution": {"selected": selected_provider, "requested": execution_provider, "options": None, "device": None},
              "models": models}
    run = LegacyTrackerRun(tracker, pipeline_id=pipeline_id, models=models, timing_sink=timing_sink)
    return run, tuple({"node": node, **model} for node, model in models.items()), record
