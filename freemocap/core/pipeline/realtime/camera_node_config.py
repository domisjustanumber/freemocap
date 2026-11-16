from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.core.detectors.calibration import (
    CharucoBoardDefinition,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.mediapipe_model_manager import (
    MediapipePoseModelComplexity,
)



# The one definition point for the default skeleton detector. Everything that
# needs "the detector we assume when none is running" reads this.
DEFAULT_DETECTOR_TYPE: Literal["rtmpose", "mediapipe"] = "rtmpose"


#TODO - JSM - Yee-ikes! this is awful and ugly and NEEDS FIXED

class CameraNodeConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    worker_mode: WorkerMode = WorkerMode.PROCESS
    charuco_tracking_enabled: bool = True
    skeleton_tracking_enabled: bool = True
    detector_type: Literal["rtmpose", "mediapipe"] = DEFAULT_DETECTOR_TYPE
    # RTMW settings (only used when detector_type="rtmpose")
    rtmpose_model_name: Literal["rtmw-x-l_256x192", "rtmw-x-l_384x288", "rtmw-l-m_256x192"] = "rtmw-x-l_256x192"
    rtmpose_confidence_threshold: float = 0.4
    # MediaPipe config (only used when detector_type="mediapipe")
    mediapipe_model_complexity: MediapipePoseModelComplexity = MediapipePoseModelComplexity.LITE
    mediapipe_detection_confidence: float = 0.5
    mediapipe_presence_confidence: float = 0.5
    mediapipe_tracking_confidence: float = 0.5
    mediapipe_num_hands: Literal[2] = 2
    mediapipe_num_faces: int = 1
    charuco_board: CharucoBoardDefinition = Field(
        default_factory=CharucoBoardDefinition.create_letter_size_5x3
    )
    # Confidence gating threshold — keypoints below this visibility score
    # have their xy NaN-ed before publication so triangulation skips them.
    # RTMPose visibility is the raw SIMCC peak clipped to [0, 1]; 0.4 clears the
    # measured no-person response band (person-free crops top out at ~0.33) while
    # keeping >=96% of visible keypoints. See RTMPoseDetectorConfig in
    # skellytracker's rtmpose/wholebody for the full measured distribution.
    # Kept permissive on purpose — triangulation rejects bad points by
    # reprojection error better than one view's confidence can.
    confidence_threshold: float = 0.4

    @property
    def skeleton_settings(self) -> tuple:
        """Settings consumed when constructing either live skeleton tracker."""
        return (self.detector_type, self.rtmpose_model_name, self.rtmpose_confidence_threshold,
                self.mediapipe_model_complexity, self.mediapipe_detection_confidence,
                self.mediapipe_presence_confidence, self.mediapipe_tracking_confidence,
                self.mediapipe_num_hands, self.mediapipe_num_faces)

    @property
    def tracking2d_enabled(self) -> bool:
        return self.charuco_tracking_enabled or self.skeleton_tracking_enabled

    @model_validator(mode="before")
    @classmethod
    def _drop_retired_tracker_recipes(cls, value):
        """Saved settings and older clients may still send the server-generated skellytracker 1 recipes."""
        if isinstance(value, dict):
            return {key: item for key, item in value.items() if key not in ("skeleton_tracker_config", "charuco_tracker_config")}
        return value
