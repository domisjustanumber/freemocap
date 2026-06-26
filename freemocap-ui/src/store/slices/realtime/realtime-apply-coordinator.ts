import type {AppDispatch, RootState} from '@/store/types';
import {applyRealtimePipeline} from './realtime-thunks';
import {guardRealtimeApply} from './guardRealtimeApply';
import {realtimePipelineRestartRequired} from './realtime-notify-actions';
import {selectPipelineConfig} from './realtime-selectors';
import type {RealtimePipelineConfig} from './realtime-types';
import {
    cancelQueuedRealtimeApply,
    consumeReconcileAfterStaleResponse,
    getCoordinatorInFlight,
    getCurrentInFlightRequestId,
    peekQueuedUpdate,
    requestRealtimeApplyReconciliation,
    resetCoordinatorForTesting,
    setCoordinatorInFlight,
    setCurrentInFlightRequestId,
    setQueuedUpdate,
    takeQueuedUpdate,
    type RealtimePipelineConfigUpdate,
} from './realtime-apply-coordinator-state';

export type {RealtimePipelineConfigUpdate};
export {
    cancelQueuedRealtimeApply,
    getCurrentInFlightRequestId,
    requestRealtimeApplyReconciliation,
    resetCoordinatorForTesting,
};

function resolveConfig(
    getState: () => RootState,
    update: RealtimePipelineConfigUpdate,
): RealtimePipelineConfig {
    const current = selectPipelineConfig(getState());
    return typeof update === 'function' ? update(current) : update;
}

export function requestCoordinatedRealtimeApply(
    dispatch: AppDispatch,
    getState: () => RootState,
    update: RealtimePipelineConfigUpdate = () => selectPipelineConfig(getState()),
): void {
    if (!guardRealtimeApply(dispatch, getState)) return;
    setQueuedUpdate(update);
    if (getCoordinatorInFlight()) return;
    void drainRealtimeApplyQueue(dispatch, getState);
}

async function drainRealtimeApplyQueue(
    dispatch: AppDispatch,
    getState: () => RootState,
): Promise<void> {
    while (peekQueuedUpdate()) {
        const update = takeQueuedUpdate();
        if (!update) break;
        const config = resolveConfig(getState, update);
        const thunkAction = dispatch(applyRealtimePipeline(config));
        setCurrentInFlightRequestId(thunkAction.requestId);
        setCoordinatorInFlight(thunkAction);
        await thunkAction;
        setCoordinatorInFlight(null);
        setCurrentInFlightRequestId(null);

        if (consumeReconcileAfterStaleResponse()) {
            setQueuedUpdate(() => selectPipelineConfig(getState()));
        }
    }
}

export function markRealtimePipelineRestartRequired(
    dispatch: AppDispatch,
    message: string,
): void {
    dispatch(realtimePipelineRestartRequired({message}));
}
