"""The detector choice selects a skellytracker 2.0 built-in pipeline, its RTMW size and its EP."""
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("skellytracker.core.pipelines")

from freemocap.core.tracking import pipeline_runs


def test_rtmw_size_follows_the_old_model_name():
    config = pipeline_runs.load_detector_pipeline("rtmpose", "rtmw-x-l_384x288")
    sizes = {node.id: node.params.size for node in config.nodes if node.type == "onnx_model"}
    assert sizes[pipeline_runs.RTMW_NODE] == "l-384"
    assert sizes[pipeline_runs.PERSON_NODE] == "m"  # the YOLOX size of the built-in stays


def test_v2_providers_pass_and_removed_ones_fall_back_to_the_recommendation(monkeypatch):
    from skellytracker.core import eps
    monkeypatch.setattr(eps, "recommend", lambda form: SimpleNamespace(chosen=SimpleNamespace(ep_key="cpu")))
    assert pipeline_runs.run_execution_provider("cuda") == "cuda"
    for old in (None, "auto", "trt", "directml"):
        assert pipeline_runs.run_execution_provider(old) == "cpu"
    with pytest.raises(ValueError):
        pipeline_runs.run_execution_provider("vulkan")


@pytest.mark.parametrize(("detector_type", "needs_ep", "expected"), [("rtmpose", True, "cpu"), ("mediapipe", False, None)])
def test_an_ep_is_given_only_when_the_pipeline_needs_one(monkeypatch, detector_type, needs_ep, expected):
    import skellytracker.core.pipelines as pipelines
    started = {}
    monkeypatch.setattr(pipeline_runs, "load_detector_pipeline", lambda *args: "config")
    monkeypatch.setattr(pipelines, "check_pipeline", lambda config: SimpleNamespace(needs_execution_provider=needs_ep))
    monkeypatch.setattr(pipelines, "start_pipeline", lambda config, **kwargs: started.update(kwargs) or "run")
    monkeypatch.setattr(pipeline_runs, "run_execution_provider", lambda requested: "cpu")
    run = pipeline_runs.start_detector_run(detector_type=detector_type, camera_ids=["0", "1"], running_mode="live")
    assert run == ("run", expected)
    assert started["execution_provider"] == expected
    assert started["camera_ids"] == ["0", "1"] and started["running_mode"] == "live"


@pytest.fixture(scope="module")
def rtmw_schema():
    run, _ = pipeline_runs.start_detector_run(detector_type="rtmpose", camera_ids=["0"], running_mode="live", execution_provider="cpu")
    with run:
        return run.output_schema


def _rtmw_result(schema, *, score, roi, present=True, person_ran=True):
    from skellytracker.core.pipelines import InstanceKeypoints, InstanceRois
    names = tuple(schema[pipeline_runs.RTMW_NODE]["point_names"])
    xyz = np.stack([np.arange(len(names), dtype=float), np.arange(len(names), dtype=float) + 0.5, np.full(len(names), np.nan)], axis=-1)
    keypoints = InstanceKeypoints(names, xyz[None], np.asarray(score, float)[None], np.ones(1), np.array([present]), np.array([-1]))
    rois = InstanceRois(np.asarray([roi], float), np.array([0.8]), np.array([present]))
    return {"0": {pipeline_runs.RTMW_NODE: keypoints, pipeline_runs.PERSON_ROI: rois, "frame_index": 12,
                  "image_size": (640, 480), "timestamp_ms": 5.0, "node_ran": {pipeline_runs.PERSON_NODE: person_ran}}}


def test_rtmw_points_are_taken_by_name_and_gated_at_0_4(rtmw_schema):
    names = tuple(rtmw_schema[pipeline_runs.RTMW_NODE]["point_names"])
    score = np.full(len(names), 0.9)
    score[names.index("body/left_shoulder")] = 0.39
    score[names.index("body/right_shoulder")] = 0.4
    observation = pipeline_runs.observations_from_results(
        _rtmw_result(rtmw_schema, score=score, roi=(100.0, 50.0, 40.0, 20.0, 0.0)), rtmw_schema, "rtmpose")["0"]
    assert observation.frame_number == 12 and observation.image_size == (480, 640)
    stage = observation.stages[pipeline_runs.STAGE]
    keypoints = stage.keypoints
    assert keypoints.names == tuple(rtmw_schema[pipeline_runs.RTMW_NODE]["canonical_names"])
    # by name, not by column: the canonical column of a point is not its column in the output
    column = names.index("left_hand/left_hand_root")
    np.testing.assert_array_equal(keypoints.xyz_by_name("left_hand/wrist"), [column, column + 0.5, 0.0])
    assert np.isnan(keypoints.xyz_by_name("body/left_shoulder")).all()
    assert keypoints.visibility[keypoints.index_of("body/left_shoulder")] == 0.0
    assert keypoints.visibility[keypoints.index_of("body/right_shoulder")] == 0.4
    box = stage.bounding_boxes[0]
    assert (box.x1, box.y1, box.x2, box.y2, box.confidence) == (80.0, 40.0, 120.0, 60.0, 0.8)
    assert stage.detector_ran


def test_the_rtmw_box_is_clipped_to_whole_pixels_and_an_absent_person_has_no_box(rtmw_schema):
    count = len(rtmw_schema[pipeline_runs.RTMW_NODE]["point_names"])
    clipped = pipeline_runs.observations_from_results(
        _rtmw_result(rtmw_schema, score=np.ones(count), roi=(630.7, 10.2, 41.0, 31.3, 0.0), person_ran=False), rtmw_schema, "rtmpose")
    box = clipped["0"].stages[pipeline_runs.STAGE].bounding_boxes[0]
    assert (box.x1, box.y1, box.x2, box.y2) == (610.0, 0.0, 640.0, 25.0)
    assert not clipped["0"].stages[pipeline_runs.STAGE].detector_ran
    absent = pipeline_runs.observations_from_results(
        _rtmw_result(rtmw_schema, score=np.zeros(count), roi=(np.nan,) * 5, present=False), rtmw_schema, "rtmpose")
    stage = absent["0"].stages[pipeline_runs.STAGE]
    assert stage.bounding_boxes == [] and stage.keypoints.n_valid == 0


@pytest.mark.parametrize("detector_type", ["rtmpose", "mediapipe"])
def test_point_names_and_connections_use_the_names_of_the_observations(detector_type):
    names = pipeline_runs.detector_point_names(detector_type)
    edges = pipeline_runs.detector_connections(detector_type)
    node = pipeline_runs.RTMW_NODE if detector_type == "rtmpose" else pipeline_runs.HOLISTIC_NODE
    assert len(edges) == len(pipeline_runs._output_schema(detector_type)[node]["edges"])  # no edge is lost
    assert all(a in names and b in names for a, b in edges)
    assert {"body/nose", "left_hand/wrist", "left_hand/thumb_cmc"} <= set(names)
    if detector_type == "rtmpose":
        # a raw RTMW hand or foot name is not a canonical name
        assert ("body/left_ankle", "body/left_big_toe") in edges or ("body/left_big_toe", "body/left_ankle") in edges
        assert not any(name.startswith("feet/") or name.endswith("_thumb1") for edge in edges for name in edge)


def test_a_real_holistic_run_gives_one_body_stage_with_its_point_names():
    run, provider = pipeline_runs.start_detector_run(detector_type="mediapipe", camera_ids=["0", "1"], running_mode="live")
    from skellytracker.core.pipelines import Frame
    with run:
        results = run.process_batch({"1": Frame(np.zeros((48, 64, 3), np.uint8), frame_index=3, timestamp_ms=10.0)})
        observations = pipeline_runs.observations_from_results(results, run.output_schema, "mediapipe")
    assert provider is None and set(observations) == {"1"}
    stage = observations["1"].stages[pipeline_runs.STAGE]
    assert stage.keypoints.names[:2] == ("body/nose", "body/left_eye_inner") and len(stage.keypoints.names) == 553
    assert stage.bounding_boxes == [] and stage.detector_ran
    assert observations["1"].image_size == (48, 64) and observations["1"].frame_number == 3
