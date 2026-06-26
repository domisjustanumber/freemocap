import type {RootState} from '@/store/types';
import {createSelector} from '@reduxjs/toolkit';
import {selectCameras} from '@/store/slices/cameras/cameras-selectors';
import {countRealtimeApplyCameras} from './realtime-apply-camera-count';

export const selectPipelineState = (state: RootState) => state.realtime;
export const selectIsPipelineConnected = (state: RootState) => state.realtime.isConnected;
export const selectPipelineId = (state: RootState) => state.realtime.pipelineId;
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
export const selectExecutionProvider = (state: RootState) => state.realtime.executionProvider;
export const selectRealtimeApplyBlockedMessage = (state: RootState) =>
    state.realtime.realtimeApplyBlockedMessage;
export const selectIsRealtimePipelineRestartRequired = (state: RootState) =>
    state.realtime.restartRequired;
export const selectRealtimePipelineRestartRequiredMessage = (state: RootState) =>
    state.realtime.restartRequiredMessage;

export const selectCanConnectPipeline = createSelector(
    [selectIsPipelineConnected, selectIsPipelineLoading, (state: RootState) => state],
    (isConnected, isLoading, state) =>
        !isConnected && !isLoading && countRealtimeApplyCameras(state) > 0,
);

export const selectCanDisconnectPipeline = createSelector(
    [selectIsPipelineConnected, selectIsPipelineLoading],
    (isConnected, isLoading) => isConnected && !isLoading,
);

export const selectDisplayedExecutionProvider = createSelector(
    [selectExecutionProvider, selectIsPipelineConnected, selectSkeletonInferenceNodeConfig, selectGpuCapabilities],
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

// Back-compat alias
export const selectActiveExecutionProvider = selectExecutionProvider;
