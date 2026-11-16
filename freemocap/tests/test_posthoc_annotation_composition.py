import unittest

import numpy as np
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.detectors.calibration import CharucoBoardDefinition

from freemocap.core.pipeline.posthoc.annotation_style import build_observation_annotator


class PosthocAnnotationCompositionTests(unittest.TestCase):
    def test_configured_board_and_body_are_both_rendered(self) -> None:
        board = CharucoBoardDefinition.create_letter_size_5x3()
        renderer = build_observation_annotator(detector_type="rtmpose", board=board)
        stages = {
            "body": StageObservation(name="body", keypoints=Keypoints(
                names=("test_point",), xyz=np.array([[40.0, 70.0, 0.0]]), visibility=np.ones(1))),
            "charuco": StageObservation(name="charuco", keypoints=Keypoints(
                names=("CharucoCorner-0",), xyz=np.array([[180.0, 160.0, 0.0]]), visibility=np.ones(1))),
        }
        base = np.zeros((360, 600, 3), dtype=np.uint8)
        base[320:330, 20:30] = 255
        output = renderer.annotate(image=base, observation=Observation(frame_number=0, image_size=(360, 600), stages=stages))
        self.assertTrue(np.any(output[65:76, 35:46]))
        self.assertTrue(np.any(output[153:168, 173:188]))
        np.testing.assert_array_equal(output[320:330, 20:30], base[320:330, 20:30])
        self.assertFalse(np.any(base[:300]))

    def test_a_calibration_annotator_draws_only_the_board(self) -> None:
        renderer = build_observation_annotator(board=CharucoBoardDefinition.create_letter_size_5x3())
        body = StageObservation(name="body", keypoints=Keypoints(
            names=("test_point",), xyz=np.array([[40.0, 70.0, 0.0]]), visibility=np.ones(1)))
        output = renderer.annotate(image=np.zeros((120, 160, 3), dtype=np.uint8),
                                   observation=Observation(frame_number=0, image_size=(120, 160), stages={"body": body}))
        self.assertFalse(np.any(output))
