"""The detector choice selects a skellytracker 2.0 built-in pipeline, its RTMW size and its EP."""
from types import SimpleNamespace

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
    monkeypatch.setattr(pipelines, "start_pipeline", lambda config, **kwargs: started.update(kwargs))
    monkeypatch.setattr(pipeline_runs, "run_execution_provider", lambda requested: "cpu")
    pipeline_runs.start_detector_run(detector_type=detector_type, camera_ids=["0", "1"], running_mode="live")
    assert started["execution_provider"] == expected
    assert started["camera_ids"] == ["0", "1"] and started["running_mode"] == "live"
