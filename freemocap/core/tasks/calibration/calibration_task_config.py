from enum import Enum
from typing import Literal
from freemocap.core.tracking.board_selection import CharucoBoardMode
from freemocap.core.tasks.calibration.shared.groundplane_alignment import CalibrationAlignmentMethod

from pydantic import BaseModel, ConfigDict, Field
from skellytracker.core.detectors.calibration import CharucoBoardDefinition

from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig


class CalibrationSolverMethod(str, Enum):
    """Which calibration solver backend to use."""
    ANIPOSE = "anipose"


class PosthocCalibrationPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    calibration_recording_folder: str | None = Field(
        default=None, alias="calibrationRecordingFolder",
    )
    board_mode: CharucoBoardMode = Field(default=CharucoBoardMode.AUTO, alias="boardMode")
    charuco_board: CharucoBoardDefinition = Field(default_factory=CharucoBoardDefinition.create_letter_size_5x3,
                                                  alias="charucoBoard",
                                                  description="Definition of the charuco board used for calibration")
    solver_method: CalibrationSolverMethod = Field(
        default=CalibrationSolverMethod.ANIPOSE,
        alias="solverMethod",
        description="Calibration solver method.",
    )

    alignment_method: Literal[CalibrationAlignmentMethod.CHARUCO] | None = Field(
        default=None,
        alias="alignmentMethod",
        description="Optionally use the ChArUco board pose to align the generated calibration.",
    )

    triangulation_config: TriangulationConfig = Field(
        default_factory=TriangulationConfig,
        alias="triangulationConfig",
        description=(
            "Configuration for the post-calibration triangulator: simple DLT "
            "vs. subset-ensemble outlier rejection, plus the outlier-rejection knobs."
        ),
    )

    @property
    def use_groundplane(self) -> bool:
        return self.alignment_method is CalibrationAlignmentMethod.CHARUCO

    @property
    def detection_board(self) -> CharucoBoardDefinition:
        """The board that the calibration detector looks for."""
        if self.board_mode == CharucoBoardMode.AUTO:
            raise ValueError("Resolve AUTO board selection before constructing calibration detectors")
        return self.charuco_board
