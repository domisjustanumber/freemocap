import {createListenerMiddleware, isAnyOf} from '@reduxjs/toolkit';
import {requestCoordinatedRealtimeApply} from '@/store/slices/realtime/realtime-apply-coordinator';
import {
    getCurrentInFlightRequestId,
    requestRealtimeApplyReconciliation,
} from '@/store/slices/realtime/realtime-apply-coordinator-state';
import {selectIsPipelineConnected, selectPipelineConfig} from '@/store/slices/realtime/realtime-selectors';

const APPLY_FULFILLED = 'realtime/apply/fulfilled';
const APPLY_REJECTED = 'realtime/apply/rejected';

export const realtimeApplyListenerMiddleware = createListenerMiddleware();

realtimeApplyListenerMiddleware.startListening({
    matcher: isAnyOf(APPLY_FULFILLED, APPLY_REJECTED),
    effect: (action, listenerApi) => {
        const inFlightId = getCurrentInFlightRequestId();
        const requestId = (action as {meta?: {requestId?: string}}).meta?.requestId;
        const isStale = inFlightId !== null && requestId !== inFlightId;
        if (!isStale) return;

        const state = listenerApi.getState();
        if (!selectIsPipelineConnected(state)) return;

        if (inFlightId !== null) {
            requestRealtimeApplyReconciliation();
            return;
        }

        requestCoordinatedRealtimeApply(
            listenerApi.dispatch,
            () => listenerApi.getState(),
            () => selectPipelineConfig(listenerApi.getState()),
        );
    },
});
