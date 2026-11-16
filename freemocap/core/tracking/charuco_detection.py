"""Charuco board detection through skellytracker's public detector factory.

freemocap imports no calibration detector class: `create_detector("charuco@skellytracker", board=...)`
makes the detector, and `skellytracker.core.detectors.calibration` holds the board model and helpers.
"""
from numpy.typing import NDArray
import numpy as np
from skellytracker.core.data_primitives import BoundingBox, Observation, StageObservation

CHARUCO_STAGE = "charuco"
CHARUCO_DETECTOR_KEY = "charuco@skellytracker"


def create_charuco_detector(board):
    """The board detector: `detect(image)` gives the board `Keypoints`; call `close()` when done."""
    from skellytracker.core.detectors import create_detector
    return create_detector(CHARUCO_DETECTOR_KEY, board=board)


def charuco_observation(detector, image: NDArray[np.uint8], frame_number: int) -> Observation:
    """One frame of the board, in the stage form of the sfn26 charuco tracker: a full-image box, no object detector."""
    height, width = image.shape[:2]
    stage = StageObservation(name=CHARUCO_STAGE, bounding_boxes=[BoundingBox(0, 0, width, height)],
                             keypoints=detector.detect(image), detector_ran=False)
    return Observation(frame_number=frame_number, image_size=(height, width), stages={CHARUCO_STAGE: stage})
