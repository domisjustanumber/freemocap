import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np
from skellytracker.core.data_primitives.observation import Observation, StageObservation
from skellytracker.core.detectors.calibration import CharucoBoardDefinition

from freemocap.core.pipeline.posthoc.video_node import CACHE_FILENAME, _get_observation, _load_cache_by_connection_frame


class BoardCacheScopeTests(unittest.TestCase):
    def test_a_frame_without_a_cache_entry_is_detected(self) -> None:
        detector = Mock()
        detector.detect.return_value = "board keypoints"
        result = _get_observation(frame_number=3, image=np.zeros((24, 32, 3), dtype=np.uint8), detector=detector, cache={})
        detector.detect.assert_called_once()
        self.assertEqual((result.frame_number, result.image_size), (3, (24, 32)))
        self.assertEqual(result.stages["charuco"].keypoints, "board keypoints")

    def test_board_only_cache_requires_matching_stage_structure(self) -> None:
        board = CharucoBoardDefinition.create_letter_size_5x3()
        for stage_name in ("charuco", "another_board"):
            with self.subTest(stage_name=stage_name), tempfile.TemporaryDirectory() as directory:
                recording_path = Path(directory)
                cache_path = recording_path / "output_data" / CACHE_FILENAME
                cache_path.parent.mkdir()
                observation = Observation(frame_number=10, image_size=(24, 32), stages={
                    stage_name: StageObservation(name=stage_name),
                })
                cache_path.write_bytes(pickle.dumps({
                    "board_definition": board, "observations": {"camera": {10: observation}},
                }))
                cache = _load_cache_by_connection_frame(recording_path=recording_path, camera_id="camera", board=board)
                if stage_name == "charuco":
                    self.assertEqual(cache, {10: observation})
                else:
                    self.assertIsNone(cache)
