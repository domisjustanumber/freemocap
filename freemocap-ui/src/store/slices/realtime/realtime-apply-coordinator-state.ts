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

export function getCoordinatorInFlight(): Promise<unknown> | null {
    return inFlight;
}

export function setCoordinatorInFlight(value: Promise<unknown> | null): void {
    inFlight = value;
}

export function setCurrentInFlightRequestId(value: string | null): void {
    currentInFlightRequestId = value;
}

export function takeQueuedUpdate(): RealtimePipelineConfigUpdate | null {
    const update = queuedUpdate;
    queuedUpdate = null;
    return update;
}

export function setQueuedUpdate(update: RealtimePipelineConfigUpdate | null): void {
    queuedUpdate = update;
}

export function peekQueuedUpdate(): RealtimePipelineConfigUpdate | null {
    return queuedUpdate;
}

export function requestRealtimeApplyReconciliation(): void {
    reconcileAfterStaleResponse = true;
}

export function consumeReconcileAfterStaleResponse(): boolean {
    if (!reconcileAfterStaleResponse) return false;
    reconcileAfterStaleResponse = false;
    return true;
}

export function cancelQueuedRealtimeApply(): void {
    queuedUpdate = null;
    reconcileAfterStaleResponse = false;
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
