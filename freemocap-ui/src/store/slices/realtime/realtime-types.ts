import {GpuCapabilitiesResponse} from '@/types/gpu-capabilities';

export type CalibrationSource = 'most_recent' | 'specified';

export type ExecutionProviderName =
    | 'trt-trx'
    | 'trt'
    | 'cuda'
    | 'directml'
    | 'coreml'
    | 'cpu';

export type RtmposeMode = 'performance' | 'balanced' | 'lightweight';

export interface CharucoBoardConfigForPipeline {
    squares_x: number;
    squares_y: number;
    square_length_mm: number;
}

export interface RtmposeDetectorConfig {
    tracker_type: 'rtmpose';
    mode: RtmposeMode;
    detector_model: string | null;
    pose_model: string | null;
    confidence_threshold?: number;
}

export interface CameraNodeConfig {
    charuco_tracking_enabled: boolean;
    skeleton_tracking_enabled: boolean;
    charuco_detector_config?: { board: CharucoBoardConfigForPipeline } | null;
    skeleton_detector_config?: RtmposeDetectorConfig;
}

export interface SkeletonInferenceNodeConfig {
    execution_provider: ExecutionProviderName | null;
    fallback_on_missing_provider?: boolean;
    max_batch_size?: number;
}

export interface RealtimeAggregatorNodeConfig {
    calibration_toml_source: CalibrationSource;
    calibration_toml_path: string | null;
    triangulation_enabled: boolean;
    filter_enabled: boolean;
    skeleton_enabled: boolean;
}

export interface RealtimePipelineConfig {
    /** When true, backend publishes detailed per-stage timings (websocket `pipeline_timing`). */
    log_pipeline_times?: boolean;
    /** When true, one shared GPU worker runs skeleton inference for all cameras. */
    use_centralized_gpu_inference?: boolean;
    skeleton_inference_node_config?: SkeletonInferenceNodeConfig;
    camera_node_config: CameraNodeConfig;
    aggregator_config: RealtimeAggregatorNodeConfig;
}

export const defaultRtmposeDetectorConfig: RtmposeDetectorConfig = {
    tracker_type: 'rtmpose',
    mode: 'balanced',
    detector_model: null,
    pose_model: null,
    confidence_threshold: 5,
};

export const defaultRealtimePipelineConfig: RealtimePipelineConfig = {
    log_pipeline_times: true,
    use_centralized_gpu_inference: true,
    skeleton_inference_node_config: {
        execution_provider: null,
        fallback_on_missing_provider: true,
        max_batch_size: 8,
    },
    camera_node_config: {
        charuco_tracking_enabled: true,
        skeleton_tracking_enabled: true,
        skeleton_detector_config: defaultRtmposeDetectorConfig,
    },
    aggregator_config: {
        calibration_toml_source: 'most_recent',
        calibration_toml_path: null,
        triangulation_enabled: true,
        filter_enabled: false,
        skeleton_enabled: true,
    },
};

// ==================== API Request/Response ====================

export interface PipelineApplyRequest {
    realtime_config: RealtimePipelineConfig;
}

export interface PipelineApplyResponse {
    camera_group_id: string;
    pipeline_id: string;
    active_execution_provider?: string | null;
}

// ==================== Redux State ====================

export interface PipelineState {
    pipelineConfig: RealtimePipelineConfig;
    cameraGroupId: string | null;
    pipelineId: string | null;
    isConnected: boolean;
    isLoading: boolean;
    error: string | null;
    gpuCapabilities: GpuCapabilitiesResponse | null;
    gpuCapabilitiesLoading: boolean;
    gpuCapabilitiesError: string | null;
    activeExecutionProvider: string | null;
}
