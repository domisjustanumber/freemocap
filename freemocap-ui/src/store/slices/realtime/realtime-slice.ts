import {createSlice, PayloadAction} from '@reduxjs/toolkit';
import {defaultRealtimePipelineConfig, PipelineState, RealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';
import {applyRealtimePipeline, closePipeline, fetchGpuCapabilities} from '@/store/slices/realtime/realtime-thunks';

const initialState: PipelineState = {
    pipelineConfig: defaultRealtimePipelineConfig,
    cameraGroupId: null,
    pipelineId: null,
    isConnected: false,
    isLoading: false,
    error: null,
    gpuCapabilities: null,
    gpuCapabilitiesLoading: false,
    gpuCapabilitiesError: null,
    activeExecutionProvider: null,
};

export const realtimeSlice = createSlice({
    name: 'realtime',
    initialState,
    reducers: {
        pipelineStateReset: () => initialState,

        pipelineConfigUpdated: (state, action: PayloadAction<RealtimePipelineConfig>) => {
            state.pipelineConfig = action.payload;
        },

        activeExecutionProviderCleared: (state) => {
            state.activeExecutionProvider = null;
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
                            fallback_on_missing_provider:
                                state.pipelineConfig.skeleton_inference_node_config?.fallback_on_missing_provider ?? true,
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

            // ========== Apply Pipeline (POST /realtime/apply) ==========
            .addCase(applyRealtimePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(applyRealtimePipeline.fulfilled, (state, action) => {
                state.cameraGroupId = action.payload.camera_group_id;
                state.pipelineId = action.payload.pipeline_id;
                state.pipelineConfig = action.meta.arg;
                state.activeExecutionProvider = action.payload.active_execution_provider ?? null;
                state.isConnected = true;
                state.isLoading = false;
            })
            .addCase(applyRealtimePipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to apply pipeline';
            })

            // ========== Close Pipeline (DELETE /realtime/all/close) ==========
            .addCase(closePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(closePipeline.fulfilled, (state) => {
                state.cameraGroupId = null;
                state.pipelineId = null;
                state.isConnected = false;
                state.activeExecutionProvider = null;
                state.isLoading = false;
            })
            .addCase(closePipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to close pipeline';
            });
    },
});

export const {pipelineStateReset, pipelineConfigUpdated, activeExecutionProviderCleared} = realtimeSlice.actions;
