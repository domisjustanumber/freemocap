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

    def test_face_points_are_drawn_smaller_by_their_group_for_each_detector(self) -> None:
        from freemocap.core.pipeline.posthoc.annotation_style import FACE_KEYPOINT_RADIUS
        from freemocap.core.tracking.tracker_definitions import tracker_definition
        for detector in ("rtmpose", "mediapipe"):
            points = tracker_definition(detector).tracked_points
            face = next(name for name in points if name.startswith("face/"))
            other = next(name for name in points if not name.startswith("face/"))
            body = StageObservation(name="body", keypoints=Keypoints(
                names=(face, other), xyz=np.array([[30.0, 30.0, 0.0], [90.0, 30.0, 0.0]]), visibility=np.ones(2)))
            output = build_observation_annotator(detector_type=detector).annotate(
                image=np.zeros((60, 120, 3), dtype=np.uint8), observation=Observation(frame_number=0, image_size=(60, 120), stages={"body": body}))
            drawn = lambda x: int(np.any(output[30, x - 10:x + 11] != 0, axis=1).sum())  # the dot's width along its row
            self.assertEqual(drawn(30), 2 * FACE_KEYPOINT_RADIUS + 1, detector)
            self.assertGreater(drawn(90), drawn(30), detector)
