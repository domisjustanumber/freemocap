import {createListenerMiddleware} from '@reduxjs/toolkit';
import {
    cancelQueuedRealtimeApply,
    getCurrentInFlightRequestId,
    requestCoordinatedRealtimeApply,
    requestRealtimeApplyReconciliation,
} from '@/store/slices/realtime/realtime-apply-coordinator';
import {cancelScheduledRealtimeCameraApply} from '@/store/slices/realtime/realtime-camera-apply-scheduler';
import {selectIsPipelineConnected, selectPipelineConfig} from '@/store/slices/realtime/realtime-selectors';

export const realtimeApplyListenerMiddleware = createListenerMiddleware();

const applyFulfilledType = 'realtime/apply/fulfilled';
const applyRejectedType = 'realtime/apply/rejected';
const closePendingType = 'realtime/close/pending';

realtimeApplyListenerMiddleware.startListening({
    predicate: (action) =>
        action.type === applyFulfilledType || action.type === applyRejectedType,
    effect: (action, listenerApi) => {
        const inFlightId = getCurrentInFlightRequestId();
        if (inFlightId !== null && action.meta.requestId === inFlightId) {
            return;
        }
        if (!selectIsPipelineConnected(listenerApi.getState())) {
            return;
        }
        if (inFlightId !== null) {
            requestRealtimeApplyReconciliation();
            return;
        }
        requestCoordinatedRealtimeApply(
            listenerApi.dispatch,
            listenerApi.getState,
            () => selectPipelineConfig(listenerApi.getState()),
        );
    },
});

realtimeApplyListenerMiddleware.startListening({
    predicate: (action) => action.type === closePendingType,
    effect: () => {
        cancelQueuedRealtimeApply();
        cancelScheduledRealtimeCameraApply();
    },
});
