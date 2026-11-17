# Deleted at skellytracker stage 2.4 (legacy tracker benchmark).
"""The legacy tracker benchmark seam: EP choice, cache-only start, name translation, task events, realtime only."""
import importlib.util
import json
import multiprocessing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from skellytracker.core.data_primitives import BoundingBox, Keypoints, Observation, StageObservation
from skellytracker.core.pipelines import Frame
from skellytracker.core.sessions import model_registry
from skellytracker.core.sessions.model_registry import ModelSource
from skellytracker.core.sessions.onnx_session import OnnxModelSpec, OnnxSession
from skellytracker.core.tracker.task_events import TrackerTaskEvent

import freemocap.core.tracking.legacy_tracker_run as legacy
from freemocap.core.pipeline.inference_service import InferenceClient, InferenceMode, InferenceRegistration, InferenceService
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node_config import RealtimeSkeletonInferenceNodeConfig
from freemocap.core.tracking.pipeline_runs import detector_point_names

CAMERAS = ("cam0", "cam1", "cam2")
CUDA, TRT_RTX = legacy.CUDA, legacy.TRT_RTX


def _status(monkeypatch, cuda_usable: bool) -> None:
    from skellytracker.core import eps
    packs = [SimpleNamespace(key=TRT_RTX, usable=True), SimpleNamespace(key=CUDA, usable=cuda_usable),
             SimpleNamespace(key="cpu", usable=True)]
    monkeypatch.setattr(eps, "status", lambda: SimpleNamespace(eps=packs))


@pytest.mark.parametrize("cuda_usable", [True, False])
def test_auto_and_trt_rtx_use_cuda_when_its_pack_is_usable_else_cpu(monkeypatch, cuda_usable):
    _status(monkeypatch, cuda_usable)
    expected = CUDA if cuda_usable else "cpu"
    assert [legacy.legacy_ep_choice(key) for key in (None, "auto", TRT_RTX)] == [expected] * 3
    assert (legacy.legacy_ep_choice("cpu"), legacy.legacy_ep_choice(CUDA)) == ("cpu", CUDA)
    with pytest.raises(ValueError, match="cpu or cuda only"):
        legacy.legacy_ep_choice("another-ep")


def test_a_trt_rtx_run_is_refused_before_anything_is_built(monkeypatch):
    monkeypatch.setattr(legacy, "_model_specs", lambda: pytest.fail("built a model for a refused EP"))
    with pytest.raises(ValueError, match="cpu or cuda only; .trt-rtx. is refused"):
        legacy.start_legacy_run(camera_ids=CAMERAS, pipeline_id="p", execution_provider=TRT_RTX)


def _specs(cache: Path, cached: bool) -> list[OnnxModelSpec]:
    specs = [OnnxModelSpec(name="yolox-m", source=ModelSource(url="https://example.invalid/yolox.zip"), input_size=(640, 640),
                           expected_filename="yolox-m_b1_fp32.onnx"),
             OnnxModelSpec(name="rtmw-x-l_256x192", source=ModelSource(url="https://example.invalid/rtmw.zip"),
                           input_size=(256, 192), expected_filename="rtmw-x-l_256x192_b1_fp32.onnx")]
    if cached:
        for spec in specs:
            (cache / spec.expected_filename).write_bytes(b"")
    return specs


def test_an_uncached_model_is_refused_and_nothing_is_downloaded(monkeypatch, tmp_path):
    monkeypatch.setattr(model_registry, "DEFAULT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(model_registry, "_download_to_temp", lambda *args, **kwargs: pytest.fail("downloaded a model"))
    monkeypatch.setattr(OnnxSession, "create", classmethod(lambda cls, config: pytest.fail("started a session")))
    monkeypatch.setattr(legacy, "_model_specs", lambda: _specs(tmp_path, cached=False))
    with pytest.raises(FileNotFoundError, match="does not download models.*yolox-m_b1_fp32.onnx"):
        legacy.start_legacy_run(camera_ids=CAMERAS, pipeline_id="p", execution_provider="cpu")


def test_the_cuda_run_builds_one_session_on_cuda_for_every_camera_and_reports_it(monkeypatch, tmp_path):
    monkeypatch.setattr(model_registry, "DEFAULT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(legacy, "_model_specs", lambda: _specs(tmp_path, cached=True))
    configs = []
    session = SimpleNamespace(execution_provider=CUDA, close=lambda: None)
    monkeypatch.setattr(OnnxSession, "create", classmethod(lambda cls, config: configs.append(config) or session))
    monkeypatch.setattr(legacy, "_build_tracker", lambda built: SimpleNamespace(session=built))
    run, statuses, record = legacy.start_legacy_run(camera_ids=CAMERAS, pipeline_id="p", execution_provider=CUDA,
                                                    selected_provider=TRT_RTX)
    assert (configs[0].execution_provider, configs[0].batch_size, [spec.name for spec in configs[0].models]) == (
        CUDA, 3, ["yolox-m", "rtmw-x-l_256x192"])
    assert run._tracker.session is session
    assert [(status["node"], status["execution_provider"], status["engine"]) for status in statuses] == [
        ("person", CUDA, "legacy"), ("wholebody", CUDA, "legacy")]
    assert record["execution"] == {"selected": TRT_RTX, "requested": CUDA, "options": None, "device": None}


def _old_observation(frame: int) -> Observation:
    names = tuple(f"old_{index}" for index in range(133))
    xyz = np.column_stack([np.arange(133.0) + 10, np.arange(133.0) + 20, np.zeros(133)])
    visibility = np.full(133, 0.006)
    xyz[5] = np.nan
    visibility[5] = 0.0
    visibility[6] = 0.0  # under the old detector threshold: finite xy, score 0
    box = BoundingBox(1, 2, 300, 400, 0.9)
    stage = StageObservation(name="body", bounding_boxes=[box], detector_ran=False,
                             keypoints=Keypoints(names=names, xyz=xyz, visibility=visibility))
    return Observation(frame_number=frame, image_size=(480, 640), stages={"body": stage})


def test_old_points_get_the_2_0_canonical_names_and_keep_their_raw_scores():
    converted = legacy.observations_from_legacy({"cam0": _old_observation(4)}, legacy.wholebody_port())["cam0"]
    stage = converted.stages["body"]
    names = detector_point_names("rtmpose")
    assert len(legacy.wholebody_port().point_names) == 133 and len(names) == 137  # raw port names in, canonical out
    assert stage.keypoints.names == names
    assert (converted.frame_number, converted.image_size, stage.detector_ran) == (4, (480, 640), False)
    assert stage.bounding_boxes == [BoundingBox(1, 2, 300, 400, 0.9)]
    nose = names.index("body/nose")
    np.testing.assert_allclose(stage.keypoints.xyz[nose], [10.0, 20.0, 0.0])
    assert stage.keypoints.visibility[nose] == pytest.approx(0.006)  # rtmpose_confidence_threshold is not applied
    assert np.isnan(stage.keypoints.xyz[[5, 6]]).all() and not stage.keypoints.visibility[[5, 6]].any()
    with pytest.raises(ValueError, match="gave 17 points"):
        old = _old_observation(0)
        old.stages["body"].keypoints = Keypoints(names=tuple("abcdefghijklmnopq"), xyz=np.zeros((17, 3)), visibility=np.ones(17))
        legacy.observations_from_legacy({"cam0": old}, legacy.wholebody_port())


def test_legacy_points_are_gated_at_the_old_threshold_and_the_aggregator_uses_it_for_legacy_runs():
    old = _old_observation(4)
    old.stages["body"].keypoints.visibility[0] = 0.0024  # the old point 0 is body/nose
    converted = legacy.observations_from_legacy({"cam0": old}, legacy.wholebody_port())["cam0"].stages["body"].keypoints
    nose = detector_point_names("rtmpose").index("body/nose")
    assert np.isnan(converted.xyz[nose]).all() and converted.visibility[nose] == 0.0
    from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
    config = RealtimePipelineConfig()
    assert legacy.realtime_confidence_threshold(config) == config.camera_node_config.confidence_threshold
    config.skeleton_inference_node_config.legacy_tracker_benchmark = True
    assert legacy.realtime_confidence_threshold(config) == legacy.LEGACY_MIN_SCORE == 0.0025


def _event(stage: str, camera_id: str | None) -> TrackerTaskEvent:
    return TrackerTaskEvent(task_id="ignored", parent_task_ids=(), stage=stage, node_kind="skeleton_inference",
                            camera_id=camera_id, frame_number=9, start_time_ns=1_000, end_time_ns=3_000_000, duration_ms=2.999)


def test_old_task_events_become_pipeline_timing_events_under_the_frame_predict_batch():
    batch, camera = legacy.timing_events_from_legacy([_event("object_detection_infer", None), _event("crop", "cam1")], "p")
    assert (batch.task_id, batch.stage, batch.camera_id, batch.frame_number) == (
        "p:9:batch:skeleton_inference:object_detection_infer", "object_detection_infer", None, 9)
    assert (camera.task_id, camera.camera_id) == ("p:9:cam1:skeleton_inference:crop", "cam1")
    assert batch.parent_task_ids == camera.parent_task_ids == ["9:batch:skeleton_inference:predict_batch"]
    assert (batch.start_time_ns, batch.end_time_ns, batch.duration_ms) == (1_000, 3_000_000, pytest.approx(2.999))


class _FakeTracker:
    def __init__(self) -> None:
        self.collectors = []

    def process_batch(self, images, frame_number, states, event_collector=None):
        self.collectors.append(event_collector)
        if event_collector is not None:
            event_collector.append(_event("keypoint_detection_infer", None))
        return {camera: _old_observation(frame_number) for camera in images}, {camera: f"state-{frame_number}" for camera in images}


@pytest.mark.parametrize("timed", [False, True])
def test_a_run_without_timing_makes_no_collector_and_no_events(timed):
    tracker, events = _FakeTracker(), []
    run = legacy.LegacyTrackerRun(tracker, pipeline_id="p", models={}, timing_sink=events.append if timed else None)
    frames = {camera: Frame(np.zeros((4, 4, 3), np.uint8), frame_index=9) for camera in CAMERAS[:2]}
    observations = run.process_batch(frames)
    assert set(observations) == set(CAMERAS[:2]) and observations["cam0"].frame_number == 9
    assert (tracker.collectors[0] is not None) == timed
    assert [event.stage for event in events] == (["keypoint_detection_infer"] if timed else [])
    assert run._states == {"cam0": "state-9", "cam1": "state-9"}


def _client(mode: InferenceMode, provider: str | None = TRT_RTX) -> InferenceClient:
    return InferenceClient(registration=InferenceRegistration(
        pipeline_id="p", mode=mode, detector_type="rtmpose", camera_ids=CAMERAS, shutdown_flag=multiprocessing.Value("b", False),
        execution_provider=provider, legacy_tracker_benchmark=True), _service=Mock(spec=InferenceService))


def test_posthoc_can_never_start_a_legacy_run(monkeypatch):
    monkeypatch.setattr(legacy, "start_legacy_run", lambda **kwargs: pytest.fail("started a legacy run in posthoc"))
    with pytest.raises(ValueError, match="real-time processing only"):
        InferenceService._start_run(_client(InferenceMode.POSTHOC))


def test_a_realtime_legacy_registration_starts_the_seam_on_the_applied_ep(monkeypatch):
    _status(monkeypatch, cuda_usable=True)
    started = []
    monkeypatch.setattr(legacy, "start_legacy_run", lambda **kwargs: started.append(kwargs) or ("run", (), {}))
    monkeypatch.setattr("freemocap.core.pipeline.inference_service.start_detector_run", lambda **kwargs: pytest.fail("started 2.0"))
    assert InferenceService._start_run(_client(InferenceMode.REALTIME)) == ("run", (), {})
    assert (started[0]["execution_provider"], started[0]["selected_provider"], started[0]["camera_ids"]) == (CUDA, TRT_RTX, CAMERAS)
    assert started[0]["timing_sink"] is None, "a registration without timing gives the seam no sink, so no collector"


def test_the_flag_round_trips_through_the_contract():
    contract = json.loads((Path(__file__).parents[2] / "packages/freemocap-client/contracts/openapi.json").read_text(encoding="utf-8"))
    published = contract["components"]["schemas"]["RealtimeSkeletonInferenceNodeConfig"]["properties"]["legacy_tracker_benchmark"]
    assert published == RealtimeSkeletonInferenceNodeConfig.model_json_schema()["properties"]["legacy_tracker_benchmark"]
    config = RealtimeSkeletonInferenceNodeConfig.model_validate({"legacy_tracker_benchmark": True})
    assert RealtimeSkeletonInferenceNodeConfig.model_validate(config.model_dump(mode="json")).legacy_tracker_benchmark is True
    assert RealtimeSkeletonInferenceNodeConfig().legacy_tracker_benchmark is False


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("onnx") is None, reason="the old YOLOX dynamic batch needs the onnx package")
def test_a_real_cpu_legacy_run_on_the_cached_old_models():
    specs = legacy._model_specs()
    if not all(legacy._cached_file(spec).exists() for spec in specs):
        pytest.skip("the old model files are not cached; this test does not download them")
    events = []
    run, statuses, _record = legacy.start_legacy_run(camera_ids=CAMERAS[:2], pipeline_id="p", execution_provider="cpu",
                                                     timing_sink=events.append)
    try:
        frames = {camera: Frame(np.zeros((240, 320, 3), np.uint8), frame_index=0) for camera in CAMERAS[:2]}
        observations = run.process_batch(frames)
    finally:
        run.close()
    assert [status["file"] for status in statuses] == ["yolox-m_b1_fp32.onnx.prenms.onnx", "rtmw-x-l_256x192_b1_fp32.onnx"]
    assert {status["execution_provider"] for status in statuses} == {"cpu"}
    assert observations["cam0"].stages["body"].keypoints.names == detector_point_names("rtmpose")
    assert "object_detection_infer" in {event.stage for event in events}
