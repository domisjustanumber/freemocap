import {describe, expect, it, vi} from 'vitest';

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

import {configureStore} from '@reduxjs/toolkit';
import {realtimeSlice, realtimePipelineErrorReceived} from './realtime-slice';
import {REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE} from './realtime-messages';
import {formatApplyErrorDetail} from './formatApplyErrorDetail';
import {countRealtimeApplyCameras} from './realtime-apply-camera-count';
import {guardRealtimeApply} from './guardRealtimeApply';
import {
    pipelineErrorDismissed,
    realtimeApplyBlocked,
    realtimeApplyBlockedDismissed,
    realtimePipelineRestartRequired,
    realtimePipelineRestartRequiredDismissed,
} from './realtime-notify-actions';

const applyPendingType = 'realtime/apply/pending';
const applyFulfilledType = 'realtime/apply/fulfilled';
const applyRejectedType = 'realtime/apply/rejected';
const closePendingType = 'realtime/close/pending';
const closeFulfilledType = 'realtime/close/fulfilled';
const closeRejectedType = 'realtime/close/rejected';

function makeStore(preloadedState?: Partial<ReturnType<typeof realtimeSlice.reducer>>) {
    return configureStore({
        reducer: {
            realtime: realtimeSlice.reducer,
            cameras: (state = {cameras: []}) => state,
        },
        preloadedState: preloadedState ? {realtime: {...realtimeSlice.getInitialState(), ...preloadedState}} : undefined,
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware({serializableCheck: false}),
    });
}

describe('formatApplyErrorDetail', () => {
    it('returns string detail', () => {
        expect(formatApplyErrorDetail({detail: 'bad request'}, 422)).toBe('bad request');
    });

    it('joins validation array detail', () => {
        expect(formatApplyErrorDetail({detail: [{msg: 'a'}, {msg: 'b'}]}, 422)).toBe('a; b');
    });
});

describe('realtime slice apply branches', () => {
    it('pending sets latestApplyRequestId and clears error', () => {
        const store = makeStore({error: 'old', latestApplyRequestId: null});
        store.dispatch({
            type: applyPendingType,
            meta: {requestId: 'req-1', arg: store.getState().realtime.pipelineConfig},
        });
        const state = store.getState().realtime;
        expect(state.latestApplyRequestId).toBe('req-1');
        expect(state.error).toBeNull();
        expect(state.isLoading).toBe(true);
    });

    it('ignores stale fulfilled', () => {
        const store = makeStore({latestApplyRequestId: 'new-req', pipelineId: 'keep'});
        store.dispatch({
            type: applyFulfilledType,
            meta: {requestId: 'old-req', arg: store.getState().realtime.pipelineConfig},
            payload: {pipeline_id: 'changed', execution_provider: 'cuda'},
        });
        expect(store.getState().realtime.pipelineId).toBe('keep');
    });

    it('ignores stale rejected', () => {
        const store = makeStore({latestApplyRequestId: 'new-req', error: null, isLoading: true});
        store.dispatch({
            type: applyRejectedType,
            meta: {
                requestId: 'old-req',
                arg: store.getState().realtime.pipelineConfig,
                requestStatus: 'rejected',
            },
            error: {message: 'stale failure'},
        });
        const state = store.getState().realtime;
        expect(state.error).toBeNull();
        expect(state.isLoading).toBe(true);
    });

    it('current fulfilled sets executionProvider and connected fields', () => {
        const store = makeStore({latestApplyRequestId: 'req-1'});
        const config = store.getState().realtime.pipelineConfig;
        store.dispatch({
            type: applyFulfilledType,
            meta: {requestId: 'req-1', arg: config},
            payload: {pipeline_id: 'pipe-1', execution_provider: 'cuda'},
        });
        const state = store.getState().realtime;
        expect(state.pipelineId).toBe('pipe-1');
        expect(state.executionProvider).toBe('cuda');
        expect(state.isConnected).toBe(true);
        expect(state.latestApplyRequestId).toBeNull();
        expect(state.realtimeApplyBlockedMessage).toBeNull();
    });

    it('guard rejectWithValue sets blocked message only', () => {
        const store = makeStore({isConnected: true, pipelineId: 'p1', latestApplyRequestId: 'req-1'});
        store.dispatch({
            type: applyRejectedType,
            meta: {
                requestId: 'req-1',
                arg: store.getState().realtime.pipelineConfig,
                requestStatus: 'rejected',
                rejectedWithValue: true,
            },
            payload: REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE,
            error: {message: 'Rejected'},
        });
        const state = store.getState().realtime;
        expect(state.realtimeApplyBlockedMessage).toBe(REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE);
        expect(state.isConnected).toBe(true);
        expect(state.pipelineId).toBe('p1');
    });

    it('pipeline start failure deactivates pipeline fields', () => {
        const store = makeStore({latestApplyRequestId: 'req-1', isConnected: true, pipelineId: 'p1'});
        store.dispatch({
            type: applyRejectedType,
            meta: {
                requestId: 'req-1',
                arg: store.getState().realtime.pipelineConfig,
                requestStatus: 'rejected',
                rejectedWithValue: true,
            },
            payload: 'ORT startup failed',
            error: {message: 'Rejected'},
        });
        const state = store.getState().realtime;
        expect(state.error).toBe('ORT startup failed');
        expect(state.isConnected).toBe(false);
        expect(state.pipelineId).toBeNull();
    });

    it('closePipeline.pending clears latestApplyRequestId', () => {
        const store = makeStore({latestApplyRequestId: 'req-1'});
        store.dispatch({type: closePendingType, meta: {requestId: 'close-1'}});
        expect(store.getState().realtime.latestApplyRequestId).toBeNull();
    });

    it('closePipeline.fulfilled clears connected pipeline fields', () => {
        const store = makeStore({
            latestApplyRequestId: 'req-1',
            isConnected: true,
            pipelineId: 'p1',
            executionProvider: 'cuda',
            error: 'old',
            realtimeApplyBlockedMessage: 'blocked',
            restartRequired: true,
            restartRequiredMessage: 'restart',
        });
        store.dispatch({type: closeFulfilledType, meta: {requestId: 'close-1'}});
        const state = store.getState().realtime;
        expect(state.pipelineId).toBeNull();
        expect(state.isConnected).toBe(false);
        expect(state.executionProvider).toBeNull();
        expect(state.error).toBeNull();
        expect(state.realtimeApplyBlockedMessage).toBeNull();
        expect(state.restartRequired).toBe(false);
    });

    it('closePipeline.rejected keeps pipeline identity and sets error', () => {
        const store = makeStore({
            isConnected: true,
            pipelineId: 'p1',
            isLoading: true,
        });
        store.dispatch({
            type: closeRejectedType,
            meta: {requestId: 'close-1'},
            error: {message: 'close failed'},
        });
        const state = store.getState().realtime;
        expect(state.pipelineId).toBe('p1');
        expect(state.isConnected).toBe(true);
        expect(state.error).toBe('close failed');
        expect(state.isLoading).toBe(false);
    });

    it('pipelineErrorDismissed clears error only', () => {
        const store = makeStore({error: 'worker failed', isConnected: true, pipelineId: 'p1'});
        store.dispatch(pipelineErrorDismissed());
        const state = store.getState().realtime;
        expect(state.error).toBeNull();
        expect(state.isConnected).toBe(true);
        expect(state.pipelineId).toBe('p1');
    });

    it('realtimeApplyBlockedDismissed clears blocked message only', () => {
        const store = makeStore({
            realtimeApplyBlockedMessage: REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE,
            pipelineId: 'p1',
            isConnected: true,
        });
        store.dispatch(realtimeApplyBlockedDismissed());
        const state = store.getState().realtime;
        expect(state.realtimeApplyBlockedMessage).toBeNull();
        expect(state.pipelineId).toBe('p1');
    });

    it('realtimePipelineRestartRequiredDismissed clears restart fields only', () => {
        const store = makeStore({
            restartRequired: true,
            restartRequiredMessage: 'restart',
            pipelineId: 'p1',
            isConnected: true,
        });
        store.dispatch(realtimePipelineRestartRequiredDismissed());
        const state = store.getState().realtime;
        expect(state.restartRequired).toBe(false);
        expect(state.restartRequiredMessage).toBeNull();
        expect(state.pipelineId).toBe('p1');
    });

    it('thrown network error deactivates pipeline fields', () => {
        const store = makeStore({
            latestApplyRequestId: 'req-1',
            isConnected: true,
            pipelineId: 'p1',
            executionProvider: 'cuda',
        });
        store.dispatch({
            type: applyRejectedType,
            meta: {
                requestId: 'req-1',
                arg: store.getState().realtime.pipelineConfig,
                requestStatus: 'rejected',
            },
            error: {message: 'Network Error'},
        });
        const state = store.getState().realtime;
        expect(state.error).toBe('Network Error');
        expect(state.isConnected).toBe(false);
        expect(state.pipelineId).toBeNull();
        expect(state.executionProvider).toBeNull();
    });

    it('restart required action keeps pipeline identity', () => {
        const store = makeStore({pipelineId: 'p1', isConnected: true});
        store.dispatch(realtimePipelineRestartRequired({message: 'restart'}));
        const state = store.getState().realtime;
        expect(state.restartRequired).toBe(true);
        expect(state.pipelineId).toBe('p1');
    });

    it('worker error clears connected fields', () => {
        const store = makeStore({isConnected: true, pipelineId: 'p1', realtimeApplyBlockedMessage: 'blocked'});
        store.dispatch(realtimePipelineErrorReceived('worker failed'));
        const state = store.getState().realtime;
        expect(state.error).toBe('worker failed');
        expect(state.isConnected).toBe(false);
        expect(state.realtimeApplyBlockedMessage).toBeNull();
    });
});

describe('guardRealtimeApply', () => {
    it('dispatches blocked action when zero cameras', () => {
        const store = makeStore();
        const dispatch = vi.fn();
        const getState = store.getState;
        const allowed = guardRealtimeApply(dispatch as never, getState);
        expect(allowed).toBe(false);
        expect(dispatch).toHaveBeenCalledWith(
            realtimeApplyBlocked({message: REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE}),
        );
    });
});

describe('countRealtimeApplyCameras', () => {
    it('returns zero with default camera state absent', () => {
        const store = makeStore();
        expect(countRealtimeApplyCameras(store.getState() as never)).toBe(0);
    });

    it('counts selected realtime-enabled cameras', () => {
        const store = configureStore({
            reducer: {
                realtime: realtimeSlice.reducer,
                cameras: (state = {
                    cameras: [
                        {
                            id: 'cam_a',
                            selected: true,
                            realtimeEnabled: true,
                            desiredConfig: {name: 'A'},
                        },
                        {
                            id: 'cam_b',
                            selected: true,
                            realtimeEnabled: false,
                            desiredConfig: {name: 'B'},
                        },
                    ],
                }) => state,
            },
            middleware: (getDefaultMiddleware) =>
                getDefaultMiddleware({serializableCheck: false}),
        });
        expect(countRealtimeApplyCameras(store.getState() as never)).toBe(1);
    });
});
