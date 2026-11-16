"""The board detector comes from skellytracker's public factory and gives the sfn26 charuco stage form."""
import cv2
import numpy as np
from skellytracker.core.detectors.calibration import CharucoBoardDefinition

from freemocap.core.tracking.charuco_detection import CHARUCO_STAGE, charuco_observation, create_charuco_detector


def test_a_generated_board_is_found_in_the_charuco_stage():
    board = CharucoBoardDefinition.create_letter_size_5x3()
    image = cv2.cvtColor(board.cv2_board.generateImage((840, 600), marginSize=30), cv2.COLOR_GRAY2BGR)
    detector = create_charuco_detector(board)
    try:
        observation = charuco_observation(detector, image, frame_number=4)
    finally:
        detector.close()
    assert (observation.frame_number, observation.image_size) == (4, (600, 840))
    stage = observation.stages[CHARUCO_STAGE]
    assert not stage.detector_ran
    box = stage.bounding_boxes[0]
    assert (box.x1, box.y1, box.x2, box.y2) == (0.0, 0.0, 840.0, 600.0)
    corners = [name for name in stage.keypoints.names if name.startswith("CharucoCorner-")]
    assert len(corners) == board.n_corners
    found = np.isfinite(stage.keypoints.xyz[: len(corners)]).all(axis=1)
    assert found.sum() >= 3
