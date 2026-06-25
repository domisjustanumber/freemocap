import {RootState} from '@/store';
import {createSelector} from '@reduxjs/toolkit';
import {selectCameras} from '@/store/slices/cameras';

// ==================== Primitive Selectors ====================

export const selectPipelineState = (state: RootState) => state.realtime;
export const selectIsPipelineConnected = (state: RootState) => state.realtime.isConnected;
export const selectPipelineId = (state: RootState) => state.realtime.pipelineId;
export const selectCameraGroupId = (state: RootState) => state.realtime.cameraGroupId;
export const selectIsPipelineLoading = (state: RootState) => state.realtime.isLoading;
export const selectPipelineError = (state: RootState) => state.realtime.error;
export const selectPipelineConfig = (state: RootState) => state.realtime.pipelineConfig;
export const selectCameraNodeConfig = (state: RootState) => state.realtime.pipelineConfig.camera_node_config;
export const selectAggregatorConfig = (state: RootState) => state.realtime.pipelineConfig.aggregator_config;
export const selectSkeletonInferenceNodeConfig = (state: RootState) =>
    state.realtime.pipelineConfig.skeleton_inference_node_config;
export const selectRtmposeDetectorConfig = (state: RootState) =>
    state.realtime.pipelineConfig.camera_node_config.skeleton_detector_config;
export const selectGpuCapabilities = (state: RootState) => state.realtime.gpuCapabilities;
export const selectGpuCapabilitiesLoading = (state: RootState) => state.realtime.gpuCapabilitiesLoading;
export const selectActiveExecutionProvider = (state: RootState) => state.realtime.activeExecutionProvider;

// ==================== Derived Selectors ====================

export const selectCanConnectPipeline = createSelector(
    [selectIsPipelineConnected, selectIsPipelineLoading, selectCameras],
    (isConnected, isLoading, cameras) => {
        const anyCameraRealtimeEnabled = cameras.some(cam => cam.selected && cam.realtimeEnabled);
        return !isConnected && !isLoading && anyCameraRealtimeEnabled;
    },
);

export const selectCanDisconnectPipeline = createSelector(
    [selectIsPipelineConnected, selectIsPipelineLoading],
    (isConnected, isLoading) => isConnected && !isLoading,
);

export const selectDisplayedExecutionProvider = createSelector(
    [selectActiveExecutionProvider, selectIsPipelineConnected, selectSkeletonInferenceNodeConfig, selectGpuCapabilities],
    (activeProvider, isConnected, skeletonInfConfig, gpuCapabilities) => {
        if (isConnected && activeProvider) {
            return activeProvider;
        }
        const requested = skeletonInfConfig?.execution_provider;
        if (requested) {
            return requested;
        }
        return gpuCapabilities?.execution_providers.recommended_provider_id ?? null;
    },
);
