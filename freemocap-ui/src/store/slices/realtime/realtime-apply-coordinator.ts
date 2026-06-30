import type {AppDispatch, RootState} from '@/store/types';
import {applyRealtimePipeline} from './realtime-thunks';
import {guardRealtimeApply} from './guardRealtimeApply';
import {selectPipelineConfig} from './realtime-selectors';
import type {RealtimePipelineConfig} from './realtime-types';

export type RealtimePipelineConfigUpdate =
    | RealtimePipelineConfig
    | ((current: RealtimePipelineConfig) => RealtimePipelineConfig);

let inFlight: Promise<unknown> | null = null;
let currentInFlightRequestId: string | null = null;
let queuedUpdate: RealtimePipelineConfigUpdate | null = null;
let reconcileAfterStaleResponse = false;

export function getCurrentInFlightRequestId(): string | null {
    return currentInFlightRequestId;
}

export function resetCoordinatorForTesting(): void {
    inFlight = null;
    currentInFlightRequestId = null;
    queuedUpdate = null;
    reconcileAfterStaleResponse = false;
}

if (import.meta.hot) {
    import.meta.hot.dispose(() => {
        resetCoordinatorForTesting();
    });
}

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
    queuedUpdate = update;
    if (inFlight) return;
    void drainRealtimeApplyQueue(dispatch, getState);
}

async function drainRealtimeApplyQueue(
    dispatch: AppDispatch,
    getState: () => RootState,
): Promise<void> {
    while (queuedUpdate) {
        const update = queuedUpdate;
        queuedUpdate = null;
        const config = resolveConfig(getState, update);
        const thunkAction = dispatch(applyRealtimePipeline(config));
        currentInFlightRequestId = thunkAction.requestId;
        inFlight = thunkAction;
        const action = await inFlight;
        inFlight = null;
        currentInFlightRequestId = null;

        if (reconcileAfterStaleResponse) {
            reconcileAfterStaleResponse = false;
            queuedUpdate = () => selectPipelineConfig(getState());
        }

        void action;
    }
}

export function cancelQueuedRealtimeApply(): void {
    queuedUpdate = null;
    reconcileAfterStaleResponse = false;
}

export function requestRealtimeApplyReconciliation(): void {
    reconcileAfterStaleResponse = true;
}
