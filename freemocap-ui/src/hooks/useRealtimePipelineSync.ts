import {useCallback} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {store} from '@/store/store';
import {
    cancelQueuedRealtimeApply,
    closePipeline,
    pipelineConfigUpdated,
    REALTIME_RESTART_REQUIRED_MESSAGE,
    realtimePipelineRestartRequired,
    requestCoordinatedRealtimeApply,
    selectAggregatorConfig,
    selectCameraNodeConfig,
    selectCanConnectPipeline,
    selectCanDisconnectPipeline,
    selectIsPipelineConnected,
    selectIsPipelineLoading,
    selectPipelineConfig,
} from '@/store/slices/realtime';
import type {RealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';

export type RealtimePipelineConfigUpdate =
    | RealtimePipelineConfig
    | ((current: RealtimePipelineConfig) => RealtimePipelineConfig);

function resolveRealtimeConfigUpdate(update: RealtimePipelineConfigUpdate): RealtimePipelineConfig {
    const current = selectPipelineConfig(store.getState());
    return typeof update === 'function' ? update(current) : update;
}

/**
 * Shared realtime-pipeline sync logic used by the Realtime Pipeline sidebar panel,
 * the streaming-view settings overlay, and the RTP settings modals.
 */
export function useRealtimePipelineSync() {
    const dispatch = useAppDispatch();

    const isConnected = useAppSelector(selectIsPipelineConnected);
    const isLoading = useAppSelector(selectIsPipelineLoading);
    const canConnect = useAppSelector(selectCanConnectPipeline);
    const canDisconnect = useAppSelector(selectCanDisconnectPipeline);
    const pipelineConfig = useAppSelector(selectPipelineConfig);
    const cameraNodeConfig = useAppSelector(selectCameraNodeConfig);
    const aggregatorConfig = useAppSelector(selectAggregatorConfig);

    const applyOrUpdatePipelineConfig = useCallback(
        (update: RealtimePipelineConfigUpdate) => {
            const newConfig = resolveRealtimeConfigUpdate(update);
            dispatch(pipelineConfigUpdated(newConfig));
            if (selectIsPipelineConnected(store.getState())) {
                dispatch(realtimePipelineRestartRequired({message: REALTIME_RESTART_REQUIRED_MESSAGE}));
            }
        },
        [dispatch],
    );

    const triggerRealtimeApply = useCallback(() => {
        if (selectIsPipelineConnected(store.getState())) {
            dispatch(realtimePipelineRestartRequired({message: REALTIME_RESTART_REQUIRED_MESSAGE}));
            return;
        }
        cancelQueuedRealtimeApply();
        requestCoordinatedRealtimeApply(dispatch, () => store.getState());
    }, [dispatch]);

    const toggleConnection = useCallback(async () => {
        if (selectIsPipelineLoading(store.getState())) return;
        cancelQueuedRealtimeApply();
        if (selectIsPipelineConnected(store.getState())) {
            await dispatch(closePipeline());
        } else {
            requestCoordinatedRealtimeApply(dispatch, () => store.getState());
        }
    }, [dispatch]);

    const restartPipeline = useCallback(async () => {
        cancelQueuedRealtimeApply();
        if (selectIsPipelineConnected(store.getState())) {
            await dispatch(closePipeline());
        }
        requestCoordinatedRealtimeApply(dispatch, () => store.getState());
    }, [dispatch]);

    return {
        isConnected,
        isLoading,
        canConnect,
        canDisconnect,
        pipelineConfig,
        cameraNodeConfig,
        aggregatorConfig,
        applyOrUpdatePipelineConfig,
        triggerRealtimeApply,
        toggleConnection,
        restartPipeline,
    };
}
