export type CalibrationSource = 'most_recent' | 'specified';

export interface CharucoBoardConfigForPipeline {
    squares_x: number;
    squares_y: number;
    square_length_mm: number;
}

export type RealtimeDetectorKind = 'rtmpose' | 'mediapipe_js';
export type RealtimeModelSize = 'lite' | 'full' | 'heavy';

/**
 * `TrackedObjectDefinition.name` shipped in `tracker_schemas` — must stay aligned
 * with skellytracker (see `tracker_schema_message.collect_active_tracker_schemas`).
 */
export const TRACKER_SCHEMA_NAME_BY_DETECTOR_KIND: Record<RealtimeDetectorKind, string> = {
    rtmpose: 'rtmpose_wholebody',
    /** Browser MediaPipe packs into the same rtmpose_wholebody point order/names. */
    mediapipe_js: 'rtmpose_wholebody',
};

export interface CameraNodeConfig {
    charuco_tracking_enabled: boolean;
    skeleton_tracking_enabled: boolean;
    charuco_detector_config?: { board: CharucoBoardConfigForPipeline } | null;
    realtime_detector_kind?: RealtimeDetectorKind;
    realtime_model_size?: RealtimeModelSize;
    use_centralized_gpu_inference?: boolean;
}

export interface RealtimeAggregatorNodeConfig {
    calibration_toml_source: CalibrationSource;
    calibration_toml_path: string | null;
    triangulation_enabled: boolean;
    filter_enabled: boolean;
    skeleton_enabled: boolean;
}

export interface RealtimePipelineConfig {
    realtime_detector_kind?: RealtimeDetectorKind;
    realtime_model_size?: RealtimeModelSize;
    camera_node_config: CameraNodeConfig;
    aggregator_config: RealtimeAggregatorNodeConfig;
    /** When false, backend stops publishing pipeline_timing samples */
    log_pipeline_times?: boolean;
    use_centralized_gpu_inference?: boolean;
}

export const defaultRealtimePipelineConfig: RealtimePipelineConfig = {
    realtime_detector_kind: 'rtmpose',
    realtime_model_size: 'full',
    camera_node_config: {
        charuco_tracking_enabled: true,
        skeleton_tracking_enabled: true,
        realtime_detector_kind: 'rtmpose',
        realtime_model_size: 'full',
        use_centralized_gpu_inference: true,
    },
    aggregator_config: {
        calibration_toml_source: 'most_recent',
        calibration_toml_path: null,
        triangulation_enabled: true,
        filter_enabled: false,
        skeleton_enabled: true,
    },
    log_pipeline_times: true,
    use_centralized_gpu_inference: true,
};

// ==================== API Request/Response ====================

export interface PipelineApplyRequest {
    realtime_config: RealtimePipelineConfig;
}

export interface PipelineApplyResponse {
    camera_group_id: string;
    pipeline_id: string;
}

// ==================== Redux State ====================

export interface PipelineState {
    pipelineConfig: RealtimePipelineConfig;
    cameraGroupId: string | null;
    pipelineId: string | null;
    isConnected: boolean;
    isLoading: boolean;
    error: string | null;
}
