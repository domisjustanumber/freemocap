import {createAsyncThunk} from '@reduxjs/toolkit';
import {RootState, selectRealtimeEnabledCameraConfigs, selectSelectedCameraConfigs} from '@/store';
import {serverUrls} from '@/services';
import {GpuCapabilitiesResponse} from '@/types/gpu-capabilities';
import {PipelineApplyResponse, RealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';
import {selectCalibrationConfig} from '@/store/slices/calibration/calibration-slice';

export const fetchGpuCapabilities = createAsyncThunk<
    GpuCapabilitiesResponse,
    void,
    { state: RootState }
>(
    'realtime/fetchGpuCapabilities',
    async () => {
        const response = await fetch(serverUrls.endpoints.systemGpu);
        if (!response.ok) {
            throw new Error(`Failed to fetch GPU capabilities: ${response.statusText}`);
        }
        return response.json() as Promise<GpuCapabilitiesResponse>;
    },
);

export const applyRealtimePipeline = createAsyncThunk<
    PipelineApplyResponse,
    RealtimePipelineConfig,
    { state: RootState }
>(
    'realtime/apply',
    async (realtimeConfig, {getState}) => {
        const state = getState();
        const cameraConfigs = selectSelectedCameraConfigs(state);
        const realtimeCameraIds = Object.keys(selectRealtimeEnabledCameraConfigs(state));
        const calibrationConfig = selectCalibrationConfig(state);
        const recommended =
            state.realtime.gpuCapabilities?.execution_providers.recommended_provider_id;

        let config = realtimeConfig;
        if (
            recommended &&
            config.skeleton_inference_node_config?.execution_provider == null
        ) {
            config = {
                ...config,
                skeleton_inference_node_config: {
                    ...config.skeleton_inference_node_config,
                    execution_provider: recommended,
                    fallback_on_missing_provider:
                        config.skeleton_inference_node_config?.fallback_on_missing_provider ?? true,
                    max_batch_size: config.skeleton_inference_node_config?.max_batch_size ?? 8,
                },
            };
        }

        const configWithBoard: RealtimePipelineConfig = {
            ...config,
            camera_node_config: {
                ...config.camera_node_config,
                charuco_detector_config: {
                    board: calibrationConfig.charucoBoard,
                },
            },
        };

        const response = await fetch(serverUrls.endpoints.realtimeConnectOrUpdate, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                realtimeConfig: configWithBoard,
                cameraConfigs,
                realtimeCameraIds,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Failed to apply realtime: ${error.detail || response.statusText}`);
        }

        return response.json() as Promise<PipelineApplyResponse>;
    },
);

export const closePipeline = createAsyncThunk<void, void, { state: RootState }>(
    'realtime/close',
    async () => {
        const response = await fetch(serverUrls.endpoints.realtimeClose, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to close realtime: ${response.statusText}`);
        }
    },
);
