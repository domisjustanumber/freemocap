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


def test_a_key_passes_unchanged_and_auto_takes_the_recommendation(monkeypatch):
    from skellytracker.core import eps
    monkeypatch.setattr(eps, "recommend", lambda form: SimpleNamespace(chosen=SimpleNamespace(ep_key="cpu", device_key=None), options=()))
    assert pipeline_runs.run_ep_choice("any-ep-key") == ("any-ep-key", None, None)
    for auto in (None, "auto"):
        assert pipeline_runs.run_ep_choice(auto)[0] == "cpu"


@pytest.mark.parametrize(("detector_type", "needs_ep", "expected"), [("rtmpose", True, "cpu"), ("mediapipe", False, None)])
def test_an_ep_is_given_only_when_the_pipeline_needs_one(monkeypatch, detector_type, needs_ep, expected):
    import skellytracker.core.pipelines as pipelines
    started = {}
    monkeypatch.setattr(pipeline_runs, "load_detector_pipeline", lambda *args: "config")
    monkeypatch.setattr(pipelines, "check_pipeline", lambda config: SimpleNamespace(needs_execution_provider=needs_ep))
    monkeypatch.setattr(pipelines, "export_pipeline", lambda config, resolved: {})
    monkeypatch.setattr(pipelines, "start_pipeline", lambda config, **kwargs: started.update(kwargs) or "run")
    monkeypatch.setattr(pipeline_runs, "run_ep_choice", lambda requested, device=None: ("cpu", None, None))
    run, record = pipeline_runs.start_detector_run(detector_type=detector_type, camera_ids=["0", "1"], running_mode="live")
    assert run == "run" and record["execution"]["requested"] == expected
    assert started["execution_provider"] == expected and started["ep_options"] is None and started["device"] is None
    assert started["camera_ids"] == ["0", "1"] and started["running_mode"] == "live"


def test_auto_passes_the_options_and_device_of_the_recommendation_to_the_run(monkeypatch):
    import skellytracker.core.pipelines as pipelines
    from skellytracker.core import eps
    recommendation = SimpleNamespace(chosen=SimpleNamespace(ep_key="gpu-ep", device_key="gpu:0"), options=(("prefer_nhwc", "1"),))
    monkeypatch.setattr(eps, "recommend", lambda form: recommendation if form == "performance" else None)
    started = {}
    monkeypatch.setattr(pipeline_runs, "load_detector_pipeline", lambda *args: "config")
    monkeypatch.setattr(pipelines, "check_pipeline", lambda config: SimpleNamespace(needs_execution_provider=True))
    monkeypatch.setattr(pipelines, "start_pipeline", lambda config, **kwargs: started.update(kwargs) or "run")
    monkeypatch.setattr(pipelines, "export_pipeline", lambda config, resolved: {"exported": config, "resolved": resolved})
    run, record = pipeline_runs.start_detector_run(detector_type="rtmpose", camera_ids=["0"], running_mode="live")
    assert run == "run" and record["execution"] == {"selected": None, "selected_device": None, "requested": "gpu-ep",
                                                    "options": {"prefer_nhwc": "1"}, "device": "gpu:0"}
    assert (started["execution_provider"], started["ep_options"], started["device"]) == ("gpu-ep", {"prefer_nhwc": "1"}, "gpu:0")


@pytest.fixture(scope="module")
def rtmw_schema():
    run, _ = pipeline_runs.start_detector_run(detector_type="rtmpose", camera_ids=["0"], running_mode="live", execution_provider="cpu")
    with run:
        return run.output_schema


def _rtmw_result(schema, *, score, box, present=True, person_ran=True):
    from skellytracker.core.pipelines import InstanceBoxes, InstanceKeypoints
    names = tuple(schema[pipeline_runs.RTMW_NODE]["point_names"])
    xy = np.stack([np.arange(len(names), dtype=float), np.arange(len(names), dtype=float) + 0.5], axis=-1)
    # raw_score is skellytracker's decode score before its [0, 1] map; freemocap does not read it.
    keypoints = InstanceKeypoints(names, xy[None], np.asarray(score, float)[None], np.asarray(score, float)[None],
                                  np.ones(1), np.array([present]), np.array([-1]))
    boxes = InstanceBoxes(np.asarray([box], float), np.array([0.8]), np.array([-1]), np.array([present]), np.array([-1]))
    return {"0": {pipeline_runs.RTMW_NODE: keypoints, pipeline_runs.CROP_BOX: boxes, "frame_index": 12,
                  "image_width": 640, "image_height": 480, "timestamp_ms": 5.0, "node_ran": {pipeline_runs.PERSON_NODE: person_ran}}}


def test_rtmw_points_are_taken_by_name_and_gated_at_0_5(rtmw_schema):
    names = tuple(rtmw_schema[pipeline_runs.RTMW_NODE]["point_names"])
    score = np.full(len(names), 0.9)
    score[names.index("body/left_shoulder")] = 0.49
    score[names.index("body/right_shoulder")] = 0.5
    observation = pipeline_runs.observations_from_results(
        _rtmw_result(rtmw_schema, score=score, box=(100.0, 50.0, 40.0, 20.0, 0.0)), rtmw_schema, "rtmpose")["0"]
    assert observation.frame_number == 12 and observation.image_size == (480, 640)
    stage = observation.stages[pipeline_runs.STAGE]
    keypoints = stage.keypoints
    assert keypoints.names == tuple(rtmw_schema[pipeline_runs.RTMW_NODE]["canonical_names"])
    # by name, not by column: the canonical column of a point is not its column in the output
    column = names.index("left_hand/left_hand_root")
    np.testing.assert_array_equal(keypoints.xyz_by_name("left_hand/wrist"), [column, column + 0.5, 0.0])
    assert np.isnan(keypoints.xyz_by_name("body/left_shoulder")).all()
    assert keypoints.visibility[keypoints.index_of("body/left_shoulder")] == 0.0
    assert keypoints.visibility[keypoints.index_of("body/right_shoulder")] == 0.5
    box = stage.bounding_boxes[0]
    assert (box.x1, box.y1, box.x2, box.y2, box.confidence) == (80.0, 40.0, 120.0, 60.0, 0.8)
    assert stage.detector_ran


def test_the_user_confidence_threshold_sets_the_rtmw_gate(rtmw_schema):
    names = tuple(rtmw_schema[pipeline_runs.RTMW_NODE]["point_names"])
    result = _rtmw_result(rtmw_schema, score=np.full(len(names), 0.5), box=(100.0, 50.0, 40.0, 20.0, 0.0))
    kept = pipeline_runs.observations_from_results(result, rtmw_schema, "rtmpose")["0"].stages[pipeline_runs.STAGE]
    gated = pipeline_runs.observations_from_results(result, rtmw_schema, "rtmpose", rtmw_min_score=0.6)["0"].stages[pipeline_runs.STAGE]
    assert np.isfinite(kept.keypoints.xyz_by_name("body/nose")).all()
    assert np.isnan(gated.keypoints.xyz_by_name("body/nose")).all() and gated.keypoints.n_valid == 0


def test_the_rtmw_box_is_clipped_to_whole_pixels_and_an_absent_person_has_no_box(rtmw_schema):
    count = len(rtmw_schema[pipeline_runs.RTMW_NODE]["point_names"])
    clipped = pipeline_runs.observations_from_results(
        _rtmw_result(rtmw_schema, score=np.ones(count), box=(630.7, 10.2, 41.0, 31.3, 0.0), person_ran=False), rtmw_schema, "rtmpose")
    box = clipped["0"].stages[pipeline_runs.STAGE].bounding_boxes[0]
    assert (box.x1, box.y1, box.x2, box.y2) == (610.0, 0.0, 640.0, 25.0)
    assert not clipped["0"].stages[pipeline_runs.STAGE].detector_ran
    absent = pipeline_runs.observations_from_results(
        _rtmw_result(rtmw_schema, score=np.zeros(count), box=(np.nan,) * 5, present=False), rtmw_schema, "rtmpose")
    stage = absent["0"].stages[pipeline_runs.STAGE]
    assert stage.bounding_boxes == [] and stage.keypoints.n_valid == 0


def test_an_absent_rtmw_row_is_all_missing_whatever_its_values():
    names, xyz, score = pipeline_runs._person(("a", "b"), np.ones((1, 2, 2)), None, np.ones((1, 2)), np.array([False]))
    assert names == ("a", "b") and np.isnan(xyz).all() and not score.any()


def test_a_3d_holistic_value_keeps_its_z_and_a_2d_value_gets_z_0():
    xy, z, score = np.ones((1, 2, 2)), np.array([[0.25, np.nan]]), np.full((1, 2), 0.7)
    _, holistic, _ = pipeline_runs._person(("a", "b"), xy, z, score, np.array([True]))
    np.testing.assert_array_equal(holistic, [[1.0, 1.0, 0.25], [1.0, 1.0, np.nan]])
    _, flat, kept = pipeline_runs._person(("a", "b"), xy, None, score, np.array([True]))
    np.testing.assert_array_equal(flat, [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0]])
    np.testing.assert_array_equal(kept, [0.7, 0.7])


@pytest.mark.parametrize("detector_type", ["rtmpose", "mediapipe"])
def test_point_names_and_connections_use_the_names_of_the_observations(detector_type):
    names = pipeline_runs.detector_point_names(detector_type)
    edges = pipeline_runs.detector_connections(detector_type)
    node = pipeline_runs.RTMW_NODE if detector_type == "rtmpose" else pipeline_runs.HOLISTIC_NODE
    assert 0 < len(edges) == len(pipeline_runs._output_schema(detector_type)[node]["canonical_edges"])
    assert all(a in names and b in names for a, b in edges)
    assert {"body/nose", "left_hand/wrist", "left_hand/thumb_cmc"} <= set(names)
    if detector_type == "rtmpose":
        # a raw RTMW hand or foot name is not a canonical name
        assert ("body/left_ankle", "body/left_big_toe") in edges or ("body/left_big_toe", "body/left_ankle") in edges
        assert not any(name.startswith("feet/") or name.endswith("_thumb1") for edge in edges for name in edge)


def test_a_real_holistic_run_gives_one_body_stage_with_its_point_names():
    run, record = pipeline_runs.start_detector_run(detector_type="mediapipe", camera_ids=["0", "1"], running_mode="live")
    from skellytracker.core.pipelines import Frame
    with run:
        results = run.process_batch({"1": Frame(np.zeros((48, 64, 3), np.uint8), frame_index=3, timestamp_ms=10.0)})
        observations = pipeline_runs.observations_from_results(results, run.output_schema, "mediapipe")
    assert record["execution"]["requested"] is None and set(observations) == {"1"}
    stage = observations["1"].stages[pipeline_runs.STAGE]
    assert stage.keypoints.names[:2] == ("body/nose", "body/left_eye_inner") and len(stage.keypoints.names) == 553
    assert stage.bounding_boxes == [] and stage.detector_ran
    assert observations["1"].image_size == (48, 64) and observations["1"].frame_number == 3


def test_skellytracker_says_which_detector_takes_an_ep():
    assert pipeline_runs.detector_takes_execution_provider("rtmpose")
    assert not pipeline_runs.detector_takes_execution_provider("mediapipe")


def test_the_users_device_of_an_explicit_ep_reaches_the_run_and_auto_ignores_it(monkeypatch):
    import skellytracker.core.pipelines as pipelines
    from skellytracker.core import eps
    recommendation = SimpleNamespace(chosen=SimpleNamespace(ep_key="gpu-ep", device_key="gpu:0"), options=())
    monkeypatch.setattr(eps, "recommend", lambda form: recommendation)
    monkeypatch.setattr(pipeline_runs, "load_detector_pipeline", lambda *args: "config")
    monkeypatch.setattr(pipelines, "check_pipeline", lambda config: SimpleNamespace(needs_execution_provider=True))
    monkeypatch.setattr(pipelines, "export_pipeline", lambda config, resolved: {})
    started = {}
    monkeypatch.setattr(pipelines, "start_pipeline", lambda config, **kwargs: started.update(kwargs) or "run")
    pipeline_runs.start_detector_run(detector_type="rtmpose", camera_ids=["0"], running_mode="live",
                                     execution_provider="gpu-ep", execution_device="gpu:1")
    assert (started["execution_provider"], started["device"]) == ("gpu-ep", "gpu:1")
    pipeline_runs.start_detector_run(detector_type="rtmpose", camera_ids=["0"], running_mode="live", execution_device="gpu:1")
    assert (started["execution_provider"], started["device"]) == ("gpu-ep", "gpu:0")


def test_the_record_of_a_real_run_is_the_exported_pipeline_and_the_ep_choice_as_data():
    import json
    run, record = pipeline_runs.start_detector_run(detector_type="rtmpose", camera_ids=["0"], running_mode="video",
                                                   rtmpose_model_name="rtmw-l-m_256x192", execution_provider="cpu")
    with run:
        models = run.models
    assert json.loads(json.dumps(record)) == record  # JSON types only, as a recording keeps it
    assert record["pipeline"]["pipeline_id"] and record["running_mode"] == "video"
    nodes = {node["id"]: node for node in record["pipeline"]["nodes"]}
    assert all(nodes[node]["params"]["sidecar_sha256"] == model["sidecar_sha256"] for node, model in models.items())
    assert nodes[pipeline_runs.RTMW_NODE]["params"]["size"] == pipeline_runs.RTMW_SIZES["rtmw-l-m_256x192"]
    assert record["execution"] == {"selected": "cpu", "selected_device": None, "requested": "cpu", "options": None, "device": None}


def test_the_stored_confidence_is_the_score_after_the_gate_and_raw_score_is_not_stored(rtmw_schema):
    """skellytracker's score is in [0, 1] (RTMW calibrated, Holistic visibility); freemocap stores it as given."""
    names = tuple(rtmw_schema[pipeline_runs.RTMW_NODE]["point_names"])
    score = np.full(len(names), 0.9)
    score[names.index("body/left_shoulder")] = 0.97
    score[names.index("body/right_shoulder")] = 0.3
    keypoints = pipeline_runs.observations_from_results(
        _rtmw_result(rtmw_schema, score=score, box=(100.0, 50.0, 40.0, 20.0, 0.0)), rtmw_schema, "rtmpose")["0"].stages[pipeline_runs.STAGE].keypoints
    assert keypoints.visibility[keypoints.index_of("body/left_shoulder")] == 0.97
    assert np.isfinite(keypoints.xyz_by_name("body/left_shoulder")).all()
    assert keypoints.visibility[keypoints.index_of("body/right_shoulder")] == 0.0  # below the gate: missing
    assert np.isnan(keypoints.xyz_by_name("body/right_shoulder")).all()

    from skellytracker.core.pipelines import InstanceKeypoints
    holistic_names = ("body/nose", "body/left_eye", "body/right_eye")
    visibility = np.array([[0.8, 0.1, np.nan]])
    value = InstanceKeypoints(holistic_names, np.ones((1, 3, 2)), visibility, visibility.copy(), np.ones(1), np.array([True]),
                              np.array([-1]), z=np.zeros((1, 3)))
    result = {"0": {pipeline_runs.HOLISTIC_NODE: value, "frame_index": 0, "image_width": 64, "image_height": 48}}
    stored = pipeline_runs.observations_from_results(result, {}, "mediapipe")["0"].stages[pipeline_runs.STAGE].keypoints.visibility
    assert stored[0] == 0.8 and stored[1] == 0.1 and np.isnan(stored[2])
