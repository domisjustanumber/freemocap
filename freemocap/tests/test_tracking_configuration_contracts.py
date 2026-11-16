import pytest
from pydantic import ValidationError

from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


@pytest.mark.parametrize("config_type", [CameraNodeConfig, PosthocMocapPipelineConfig])
@pytest.mark.parametrize("hand_count", [0, 1, 3, 4])
def test_two_sided_presets_reject_ineffective_hand_counts(config_type, hand_count):
    with pytest.raises(ValidationError, match="mediapipe_num_hands"):
        config_type(mediapipe_num_hands=hand_count)


@pytest.mark.parametrize("config_type,fields", [
    (CameraNodeConfig, ("skeleton_tracker_config", "charuco_tracker_config")),
    (PosthocMocapPipelineConfig, ("tracker_config", "pipelineImplementation", "videoFps"))])
def test_saved_skellytracker_1_recipes_load_and_are_not_written_again(config_type, fields):
    saved = {field: {"stages": []} if field.endswith("config") else ("typed_dataflow" if field == "pipelineImplementation" else 30.0)
             for field in fields}
    config = config_type.model_validate({"detector_type": "mediapipe", **saved})
    assert config.detector_type == "mediapipe"
    dumped = config.model_dump(by_alias=True)
    assert not set(fields) & set(dumped) and not set(fields) & set(config.model_dump())
