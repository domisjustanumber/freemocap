import {createSlice, isRejectedWithValue, PayloadAction} from '@reduxjs/toolkit';
import {defaultRealtimePipelineConfig, PipelineState, RealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';
import {applyRealtimePipeline, closePipeline, fetchGpuCapabilities} from '@/store/slices/realtime/realtime-thunks';
import {REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE} from '@/store/slices/realtime/realtime-messages';
import {
    pipelineErrorDismissed,
    realtimeApplyBlocked,
    realtimeApplyBlockedDismissed,
    realtimePipelineRestartRequired,
    realtimePipelineRestartRequiredDismissed,
} from '@/store/slices/realtime/realtime-notify-actions';

const initialState: PipelineState = {
    pipelineConfig: defaultRealtimePipelineConfig,
    pipelineId: null,
    isConnected: false,
    isLoading: false,
    error: null,
    gpuCapabilities: null,
    gpuCapabilitiesLoading: false,
    gpuCapabilitiesError: null,
    executionProvider: null,
    latestApplyRequestId: null,
    realtimeApplyBlockedMessage: null,
    restartRequired: false,
    restartRequiredMessage: null,
};

export const realtimeSlice = createSlice({
    name: 'realtime',
    initialState,
    reducers: {
        pipelineStateReset: () => initialState,

        pipelineConfigUpdated: (state, action: PayloadAction<RealtimePipelineConfig>) => {
            state.pipelineConfig = action.payload;
        },

        executionProviderCleared: (state) => {
            state.executionProvider = null;
        },

        realtimePipelineErrorReceived: (state, action: PayloadAction<string>) => {
            state.error = action.payload;
            state.isLoading = false;
            state.isConnected = false;
            state.pipelineId = null;
            state.executionProvider = null;
            state.realtimeApplyBlockedMessage = null;
            state.restartRequired = false;
            state.restartRequiredMessage = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchGpuCapabilities.pending, (state) => {
                state.gpuCapabilitiesLoading = true;
                state.gpuCapabilitiesError = null;
            })
            .addCase(fetchGpuCapabilities.fulfilled, (state, action) => {
                state.gpuCapabilities = action.payload;
                state.gpuCapabilitiesLoading = false;

                const recommended = action.payload.execution_providers.recommended_provider_id;
                if (
                    recommended &&
                    state.pipelineConfig.skeleton_inference_node_config?.execution_provider == null
                ) {
                    state.pipelineConfig = {
                        ...state.pipelineConfig,
                        skeleton_inference_node_config: {
                            ...state.pipelineConfig.skeleton_inference_node_config,
                            execution_provider: recommended,
                            max_batch_size:
                                state.pipelineConfig.skeleton_inference_node_config?.max_batch_size ?? 8,
                        },
                    };
                }
            })
            .addCase(fetchGpuCapabilities.rejected, (state, action) => {
                state.gpuCapabilitiesLoading = false;
                state.gpuCapabilitiesError = action.error.message || 'Failed to fetch GPU capabilities';
            })

            .addCase(applyRealtimePipeline.pending, (state, action) => {
                state.latestApplyRequestId = action.meta.requestId;
                state.isLoading = true;
                state.error = null;
                state.realtimeApplyBlockedMessage = null;
                state.restartRequired = false;
                state.restartRequiredMessage = null;
            })
            .addCase(applyRealtimePipeline.fulfilled, (state, action) => {
                if (state.latestApplyRequestId !== action.meta.requestId) return;
                state.latestApplyRequestId = null;
                state.pipelineId = action.payload.pipeline_id;
                state.pipelineConfig = action.meta.arg;
                state.executionProvider = action.payload.execution_provider ?? null;
                state.isConnected = true;
                state.isLoading = false;
                state.error = null;
                state.realtimeApplyBlockedMessage = null;
                state.restartRequired = false;
                state.restartRequiredMessage = null;
            })
            .addCase(applyRealtimePipeline.rejected, (state, action) => {
                if (state.latestApplyRequestId !== action.meta.requestId) return;
                state.latestApplyRequestId = null;
                state.isLoading = false;
                if (!isRejectedWithValue(action)) {
                    state.error = action.error.message ?? 'Failed to apply pipeline';
                    state.isConnected = false;
                    state.pipelineId = null;
                    state.executionProvider = null;
                    return;
                }
                const message = action.payload as string;
                if (message === REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE) {
                    state.realtimeApplyBlockedMessage = message;
                    return;
                }
                state.error = message;
                state.isConnected = false;
                state.pipelineId = null;
                state.executionProvider = null;
            })

            .addCase(closePipeline.pending, (state) => {
                state.latestApplyRequestId = null;
                state.isLoading = true;
                state.error = null;
                state.realtimeApplyBlockedMessage = null;
            })
            .addCase(closePipeline.fulfilled, (state) => {
                state.pipelineId = null;
                state.isConnected = false;
                state.executionProvider = null;
                state.isLoading = false;
                state.error = null;
                state.realtimeApplyBlockedMessage = null;
                state.latestApplyRequestId = null;
                state.restartRequired = false;
                state.restartRequiredMessage = null;
            })
            .addCase(closePipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to close pipeline';
            })

            .addCase(realtimeApplyBlocked, (state, action) => {
                state.realtimeApplyBlockedMessage = action.payload.message;
            })
            .addCase(realtimeApplyBlockedDismissed, (state) => {
                state.realtimeApplyBlockedMessage = null;
            })
            .addCase(pipelineErrorDismissed, (state) => {
                state.error = null;
            })
            .addCase(realtimePipelineRestartRequired, (state, action) => {
                state.restartRequired = true;
                state.restartRequiredMessage = action.payload.message;
            })
            .addCase(realtimePipelineRestartRequiredDismissed, (state) => {
                state.restartRequired = false;
                state.restartRequiredMessage = null;
            });
    },
});

export const {
    pipelineStateReset,
    pipelineConfigUpdated,
    executionProviderCleared,
    realtimePipelineErrorReceived,
} = realtimeSlice.actions;
