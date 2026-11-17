from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.core.detectors.calibration import (
    CharucoBoardDefinition,
)

from freemocap.core.tracking.pipeline_runs import RTMW_MIN_SCORE


# The one definition point for the default skeleton detector. Everything that
# needs "the detector we assume when none is running" reads this.
DEFAULT_DETECTOR_TYPE: Literal["rtmpose", "mediapipe"] = "rtmpose"


RETIRED_REALTIME_FIELDS = frozenset({
    "skeleton_tracker_config", "charuco_tracker_config", "mediapipe_model_complexity",
    "mediapipe_detection_confidence", "mediapipe_presence_confidence", "mediapipe_tracking_confidence",
    "mediapipe_num_faces"})


#TODO - JSM - Yee-ikes! this is awful and ugly and NEEDS FIXED

class CameraNodeConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    worker_mode: WorkerMode = WorkerMode.PROCESS
    charuco_tracking_enabled: bool = True
    skeleton_tracking_enabled: bool = True
    detector_type: Literal["rtmpose", "mediapipe"] = DEFAULT_DETECTOR_TYPE
    # RTMW settings (only used when detector_type="rtmpose")
    rtmpose_model_name: Literal["rtmw-x-l_256x192", "rtmw-x-l_384x288", "rtmw-l-m_256x192"] = "rtmw-x-l_256x192"
    rtmpose_confidence_threshold: float = RTMW_MIN_SCORE
    # MediaPipe config (only used when detector_type="mediapipe")
    mediapipe_num_hands: Literal[2] = 2
    charuco_board: CharucoBoardDefinition = Field(
        default_factory=CharucoBoardDefinition.create_letter_size_5x3
    )
    # Confidence gating threshold for both detectors — keypoints below this score
    # have their xy NaN-ed before publication so triangulation skips them.
    # RTMW points already passed rtmpose_confidence_threshold; for MediaPipe this is
    # the only gate on its visibility, so it is not the RTMW threshold (user T1 scope).
    # Kept permissive on purpose — triangulation rejects bad points by
    # reprojection error better than one view's confidence can.
    confidence_threshold: float = 0.4

    @property
    def skeleton_settings(self) -> tuple:
        """Settings consumed when constructing either live skeleton tracker."""
        return (self.detector_type, self.rtmpose_model_name, self.rtmpose_confidence_threshold,
                self.mediapipe_num_hands)

    @property
    def tracking2d_enabled(self) -> bool:
        return self.charuco_tracking_enabled or self.skeleton_tracking_enabled

    @model_validator(mode="before")
    @classmethod
    def _drop_retired_tracker_recipes(cls, value):
        """Saved settings and older clients may still send skellytracker 1 recipes and MediaPipe settings Holistic ignores."""
        if isinstance(value, dict):
            return {key: item for key, item in value.items() if key not in RETIRED_REALTIME_FIELDS}
        return value
