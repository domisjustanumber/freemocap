import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';

vi.mock('./realtime-thunks', () => {
    const makeAsync = (type: string) =>
        Object.assign(() => ({type}), {
            type,
            match: (action: {type: string}) => action.type === type,
        });
    return {
        applyRealtimePipeline: {
            pending: makeAsync('realtime/apply/pending'),
            fulfilled: makeAsync('realtime/apply/fulfilled'),
            rejected: makeAsync('realtime/apply/rejected'),
        },
        closePipeline: {
            pending: makeAsync('realtime/close/pending'),
            fulfilled: makeAsync('realtime/close/fulfilled'),
            rejected: makeAsync('realtime/close/rejected'),
        },
        fetchGpuCapabilities: {
            pending: makeAsync('realtime/fetchGpuCapabilities/pending'),
            fulfilled: makeAsync('realtime/fetchGpuCapabilities/fulfilled'),
            rejected: makeAsync('realtime/fetchGpuCapabilities/rejected'),
        },
    };
});

const coordinatedApply = vi.fn();
const cancelQueued = vi.fn();
const getCurrentInFlightRequestId = vi.fn(() => null as string | null);
const requestRealtimeApplyReconciliation = vi.fn();

vi.mock('@/store/slices/realtime/realtime-apply-coordinator', () => ({
    cancelQueuedRealtimeApply: () => cancelQueued(),
    getCurrentInFlightRequestId: () => getCurrentInFlightRequestId(),
    requestCoordinatedRealtimeApply: (...args: unknown[]) => coordinatedApply(...args),
    requestRealtimeApplyReconciliation: () => requestRealtimeApplyReconciliation(),
}));

import {configureStore} from '@reduxjs/toolkit';
import {realtimeSlice} from './realtime-slice';
import {realtimeApplyListenerMiddleware} from '@/store/realtime-apply-listener';

function makeStore(connected: boolean) {
    return configureStore({
        reducer: {
            realtime: realtimeSlice.reducer,
            cameras: (state = {cameras: []}) => state,
        },
        preloadedState: connected
            ? {
                  realtime: {
                      ...realtimeSlice.getInitialState(),
                      isConnected: true,
                      pipelineId: 'pipe-1',
                  },
              }
            : undefined,
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware({serializableCheck: false}).prepend(
                realtimeApplyListenerMiddleware.middleware,
            ),
    });
}

describe('realtimeApplyListenerMiddleware', () => {
    beforeEach(() => {
        coordinatedApply.mockClear();
        cancelQueued.mockClear();
        requestRealtimeApplyReconciliation.mockClear();
        getCurrentInFlightRequestId.mockReturnValue(null);
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    it('reconciles stale fulfilled responses while still connected', () => {
        const store = makeStore(true);
        store.dispatch({
            type: 'realtime/apply/fulfilled',
            meta: {requestId: 'stale-req'},
            payload: {pipeline_id: 'pipe-1', execution_provider: 'cuda'},
        });
        expect(coordinatedApply).toHaveBeenCalledTimes(1);
    });

    it('does not reconcile stale responses after disconnect', () => {
        const store = makeStore(false);
        store.dispatch({
            type: 'realtime/apply/fulfilled',
            meta: {requestId: 'stale-req'},
            payload: {pipeline_id: 'pipe-1', execution_provider: 'cuda'},
        });
        expect(coordinatedApply).not.toHaveBeenCalled();
    });

    it('requests reconciliation when stale response arrives during in-flight apply', () => {
        getCurrentInFlightRequestId.mockReturnValue('current-req');
        const store = makeStore(true);
        store.dispatch({
            type: 'realtime/apply/rejected',
            meta: {requestId: 'stale-req'},
            payload: 'failed',
        });
        expect(requestRealtimeApplyReconciliation).toHaveBeenCalledTimes(1);
        expect(coordinatedApply).not.toHaveBeenCalled();
    });

    it('cancels queued applies on close pending', () => {
        const store = makeStore(true);
        store.dispatch({
            type: 'realtime/close/pending',
            meta: {requestId: 'close-1'},
        });
        expect(cancelQueued).toHaveBeenCalledTimes(1);
    });
});
