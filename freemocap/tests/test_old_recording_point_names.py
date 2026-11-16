"""A restart from saved 2D observations refuses the skellytracker 1 point names with a clear error."""
import pytest

from freemocap.core.recording.result_processing.saved_observations import (
    SkellytrackerOnePointNamesError, require_current_point_names,
)


@pytest.mark.parametrize("detector_type,old", [
    ("rtmpose", ("body.nose", "body.left_shoulder", "body.left_hand_thumb1")),
    ("mediapipe", ("body.nose", "body.right_hand_wrist", "body.face_0")),
])
def test_sfn26_names_are_refused_with_the_detector_and_an_example(detector_type, old):
    with pytest.raises(SkellytrackerOnePointNamesError, match=rf"saved '{detector_type}' observations .*\(for example '{sorted(name.partition('.')[2] for name in old)[0]}'\)"):
        require_current_point_names(old + ("charuco.CharucoCorner-0",), detector_type)


@pytest.mark.parametrize("detector_type", ["rtmpose", "mediapipe"])
def test_current_names_board_only_and_other_stages_pass(detector_type):
    require_current_point_names(("body.body/nose", "body.left_hand/wrist", "charuco.CharucoCorner-0"), detector_type)
    require_current_point_names(("charuco.CharucoCorner-0", "charuco.ArucoMarkerCorner-0-0"), detector_type)
    require_current_point_names(("subject.point 0",), detector_type)  # a stage of no detector choice
    require_current_point_names((), detector_type)
