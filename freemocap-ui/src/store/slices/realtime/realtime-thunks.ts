import {createAsyncThunk} from '@reduxjs/toolkit';
import type {AppDispatch, RootState} from '@/store/types';
import {selectRealtimeEnabledCameraConfigs, selectSelectedCameraConfigs} from '@/store/slices/cameras/cameras-selectors';
import {serverUrls} from '@/services';
import {GpuCapabilitiesResponse} from '@/types/gpu-capabilities';
import {PipelineApplyResponse, RealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';
import {guardRealtimeApply} from '@/store/slices/realtime/guardRealtimeApply';
import {countRealtimeApplyCameras} from '@/store/slices/realtime/realtime-apply-camera-count';
import {REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE} from '@/store/slices/realtime/realtime-messages';
import {formatApplyErrorDetail} from '@/store/slices/realtime/formatApplyErrorDetail';

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
    { state: RootState; dispatch: AppDispatch; rejectValue: string }
>(
    'realtime/apply',
    async (realtimeConfig, {dispatch, getState, rejectWithValue}) => {
        if (!guardRealtimeApply(dispatch, getState)) {
            return rejectWithValue(REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE);
        }
        const state = getState();
        const cameraConfigs = selectSelectedCameraConfigs(state);
        const realtimeCameraIds = Object.keys(selectRealtimeEnabledCameraConfigs(state));
        const calibrationConfig = getState().calibration;
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
                    max_batch_size: config.skeleton_inference_node_config?.max_batch_size ?? 8,
                },
            };
        }

        const configWithBoard: RealtimePipelineConfig = {
            ...config,
            camera_node_config: {
                ...config.camera_node_config,
                charuco_detector_config: {
                    ...config.camera_node_config.charuco_detector_config,
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
            const body = await response.json().catch(() => ({}));
            return rejectWithValue(formatApplyErrorDetail(body, response.status));
        }

        return response.json() as Promise<PipelineApplyResponse>;
    },
    {
        condition: (_, {getState}) => countRealtimeApplyCameras(getState()) > 0,
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
