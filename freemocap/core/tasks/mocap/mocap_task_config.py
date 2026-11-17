from freemocap.core.blender.blender_export_config import BlenderExportConfig
from freemocap.core.recording.exports.requests import ExportOptions
from typing import Literal
from freemocap.core.reconstruction.alignment_config import MocapAlignmentConfig
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterConfig

from pydantic import BaseModel, ConfigDict, Field, model_validator

from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingConfig
from freemocap.core.tracking.board_selection import CharucoBoardMode
from freemocap.core.tracking.pipeline_runs import RTMW_MIN_SCORE
from skellytracker.core.detectors.calibration import CharucoBoardDefinition



class PosthocMocapPipelineConfig(BaseModel):
    anchor_segment_name: str = Field(default="pelvis", min_length=1, alias="anchorSegmentName")
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode='before')
    @classmethod
    def migrate_export_settings(cls, value):
        """Accept historical saved settings; emit only the canonical field names."""
        if not isinstance(value, dict):
            return value
        names = ('export_options', 'exportOptions', 'scientific_exports', 'scientificExports')
        present = [name for name in names if name in value]
        if not present:
            return value
        options = ExportOptions.model_validate(value[present[0]])
        if any(ExportOptions.model_validate(value[name]) != options for name in present[1:]):
            raise ValueError('Conflicting export options in saved settings: ' + ', '.join(present))
        migrated = {key: item for key, item in value.items() if key not in names}
        migrated['export_options'] = options
        return migrated

    @model_validator(mode='before')
    @classmethod
    def migrate_graph_execution_provider(cls, value):
        """A saved retired `graphExecutionProvider` keeps its meaning when no `executionProvider` is saved,
        as `execution_provider or graph_execution_provider` gave it; it is not written again."""
        if not isinstance(value, dict):
            return value
        names = ('graphExecutionProvider', 'graph_execution_provider')
        saved = next((value[name] for name in names if name in value), None)
        migrated = {key: item for key, item in value.items() if key not in names}
        if saved not in (None, 'auto') and not {'executionProvider', 'execution_provider'} & value.keys():
            migrated['execution_provider'] = saved
        return migrated

    graph_annotate: bool = Field(default=True, alias="graphAnnotate")
    log_pipeline_times: bool = Field(default=False, alias="logPipelineTimes",
        description="Record the tracking run's timing for the pipeline metrics window; read when the run starts.")

    start_stage: Literal['observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction'] = Field(
        default='observations', alias='startStage')
    # Keep unsupported finish points explicit until their save contracts
    # are implemented. Pydantic otherwise ignores stopStage and runs everything.
    stop_stage: Literal['observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction'] = Field(default='reconstruction', alias='stopStage',
        description='Last requested stage; early finishes require typed data flow graph V1.')
    base_run_id: int = Field(default=0, ge=0, alias='baseRunId')
    run_save_mode: Literal['overwrite', 'new_run'] = Field(default='overwrite', alias='runSaveMode')
    sensor_group: str | None = Field(default=None, alias='sensorGroup')

    camera_matching: CameraMatchingConfig = Field(default_factory=CameraMatchingConfig, alias="cameraMatching")
    body_alignment: MocapAlignmentConfig = Field(default_factory=MocapAlignmentConfig, alias="bodyAlignment")
    filter_config: PosthocFilterConfig = Field(default_factory=PosthocFilterConfig, alias="filterConfig")

    charuco_tracking_enabled: bool = Field(default=True, alias="charucoTrackingEnabled")
    board_mode: CharucoBoardMode = Field(default=CharucoBoardMode.AUTO, alias="boardMode")
    charuco_board: CharucoBoardDefinition = Field(
        default_factory=CharucoBoardDefinition.create_letter_size_5x3, alias="charucoBoard",
    )

    detector_type: Literal["rtmpose", "mediapipe"] = Field(
        default="rtmpose",
        alias="detectorType",
        description="Tracking preset: RTMW or MediaPipe.",
    )
    # RTMPose settings
    rtmpose_model_name: Literal["rtmw-x-l_256x192", "rtmw-x-l_384x288", "rtmw-l-m_256x192"] = Field(
        default="rtmw-x-l_256x192",
        alias="rtmPoseModelName",
        description="RTMPose wholebody model variant. Only used when detector_type='rtmpose'.",
    )
    rtmpose_confidence_threshold: float = Field(
        default=RTMW_MIN_SCORE,
        alias="rtmPoseConfidenceThreshold",
        ge=0.0,
        le=1.0,
        description=(
            "Keypoint confidence threshold for RTMPose. The score is skellytracker's calibrated "
            "value in [0, 1]; 0.5 means even odds that the point is present and close to its true "
            "position. Only used when detector_type='rtmpose'."
        ),
    )
    execution_provider: str | None = Field(
        default=None,
        alias="executionProvider",
        description="A skellytracker EP key for RTMPose. None is Auto, the skellytracker recommendation; skellytracker refuses a key it does not have, or one that cannot start, when the run starts.",
    )
    execution_device: str | None = Field(
        default=None,
        alias="executionDevice",
        description="A skellytracker device key of the chosen EP. None is skellytracker's choice; Auto ignores it.",
    )
    # MediaPipe Holistic takes no model size, confidences or face count (user F1, 2026-11-16).
    mediapipe_num_hands: Literal[2] = Field(
        default=2,
        alias="mediapipeNumHands",
        description="Two-sided human presets detect one hand per side; the count is fixed at two.",
    )
    calibration_toml_path: str | None = Field(
        default=None,
        alias="calibrationTomlPath",
        description="Selected calibration TOML. Required for multicamera processing; no implicit file selection.",
    )

    triangulation_config: TriangulationConfig = Field(
        default_factory=TriangulationConfig,
        alias="triangulationConfig",
        description="Configuration for the triangulation step of the mocap pipeline.",
    )


    export_tall_csv: bool = Field(default=False, alias="exportTallCsv")
    export_options: ExportOptions = Field(default_factory=lambda: ExportOptions(formats=('npz', 'wide_csv', 'notebook')), alias='exportOptions')

    blender_import_route: Literal['auto', 'legacy_npy', 'parquet_segments', 'parquet_constraints'] = Field(default='auto', alias='blenderImportRoute')
    blender_package: str | None = Field(default=None, alias='blenderPackage')
    blender_development_build_hash: str | None = Field(default=None, alias='blenderDevelopmentBuildHash', pattern=r'^[0-9a-f]{64}$')
    blender_export: BlenderExportConfig = Field(default_factory=BlenderExportConfig, alias='blenderExportConfig')

    export_to_blender: bool = Field(
        default=True,
        alias="exportToBlender",
        description="If True, export the processed mocap recording to a .blend file after processing.",
    )
    blender_exe_path: str | None = Field(
        default=None,
        alias="blenderExePath",
        description="Path to the Blender executable. If None, auto-detect.",
    )
    auto_open_blend_file: bool = Field(
        default=True,
        alias="autoOpenBlendFile",
        description="If True, open the .blend file in Blender after export completes.",
    )

    @model_validator(mode="after")
    def _validate_stage_range(self) -> "PosthocMocapPipelineConfig":
        stages = ('observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction')
        if stages.index(self.start_stage) > stages.index(self.stop_stage):
            raise ValueError('stopStage must not precede startStage')
        return self

