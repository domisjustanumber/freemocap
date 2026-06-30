import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';

const applyMocks = vi.hoisted(() => {
    const applyPendingResolvers: Array<(value: {type: string}) => void> = [];
    let applyRequestCounter = 0;
    return {
        applyPendingResolvers,
        resetApplyMocks() {
            applyRequestCounter = 0;
            applyPendingResolvers.length = 0;
        },
        createApplyThunk() {
            const requestId = `req-${++applyRequestCounter}`;
            const promise = new Promise<{type: string}>((resolve) => {
                applyPendingResolvers.push(resolve);
            });
            const thunkResult = Object.assign(promise, {requestId});
            return () => thunkResult;
        },
        resolveLatestApply(type = 'realtime/apply/fulfilled') {
            const resolve = applyPendingResolvers.shift();
            if (!resolve) throw new Error('No pending apply to resolve');
            resolve({type});
        },
    };
});

vi.mock('./realtime-thunks', () => ({
    applyRealtimePipeline: Object.assign(vi.fn(() => applyMocks.createApplyThunk()), {
        pending: {type: 'realtime/apply/pending'},
        fulfilled: {type: 'realtime/apply/fulfilled'},
        rejected: {type: 'realtime/apply/rejected'},
    }),
    closePipeline: {
        pending: {type: 'realtime/close/pending'},
        fulfilled: {type: 'realtime/close/fulfilled'},
        rejected: {type: 'realtime/close/rejected'},
    },
    fetchGpuCapabilities: {
        pending: {type: 'realtime/fetchGpuCapabilities/pending'},
        fulfilled: {type: 'realtime/fetchGpuCapabilities/fulfilled'},
        rejected: {type: 'realtime/fetchGpuCapabilities/rejected'},
    },
}));

vi.mock('./guardRealtimeApply', () => ({
    guardRealtimeApply: vi.fn(() => true),
}));

import {configureStore} from '@reduxjs/toolkit';
import {defaultRealtimePipelineConfig} from './realtime-types';
import {realtimeSlice} from './realtime-slice';
import {applyRealtimePipeline} from './realtime-thunks';
import {guardRealtimeApply} from './guardRealtimeApply';
import {
    cancelQueuedRealtimeApply,
    requestCoordinatedRealtimeApply,
    resetCoordinatorForTesting,
} from './realtime-apply-coordinator';

function makeStore() {
    return configureStore({
        reducer: {
            realtime: realtimeSlice.reducer,
            cameras: (state = {cameras: []}) => state,
        },
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware({serializableCheck: false}),
    });
}

function resolveLatestApply(type = 'realtime/apply/fulfilled') {
    applyMocks.resolveLatestApply(type);
}

describe('requestCoordinatedRealtimeApply', () => {
    beforeEach(() => {
        resetCoordinatorForTesting();
        applyMocks.resetApplyMocks();
        vi.mocked(applyRealtimePipeline).mockClear();
        vi.mocked(guardRealtimeApply).mockReturnValue(true);
    });

    afterEach(() => {
        resetCoordinatorForTesting();
    });

    it('dispatches exactly one apply immediately', async () => {
        const store = makeStore();
        requestCoordinatedRealtimeApply(store.dispatch, store.getState);
        expect(applyRealtimePipeline).toHaveBeenCalledTimes(1);
        await resolveLatestApply();
    });

    it('does not dispatch a second apply while the first is in flight', async () => {
        const store = makeStore();
        requestCoordinatedRealtimeApply(store.dispatch, store.getState);
        requestCoordinatedRealtimeApply(store.dispatch, store.getState, (current) => ({
            ...current,
            log_pipeline_times: false,
        }));
        expect(applyRealtimePipeline).toHaveBeenCalledTimes(1);
        await resolveLatestApply();
        await Promise.resolve();
        expect(applyRealtimePipeline).toHaveBeenCalledTimes(2);
    });

    it('replaces queued update with the latest config', async () => {
        const store = makeStore();
        requestCoordinatedRealtimeApply(store.dispatch, store.getState);
        requestCoordinatedRealtimeApply(store.dispatch, store.getState, (current) => ({
            ...current,
            log_pipeline_times: false,
        }));
        requestCoordinatedRealtimeApply(store.dispatch, store.getState, (current) => ({
            ...current,
            log_pipeline_times: true,
        }));
        await resolveLatestApply();
        await Promise.resolve();
        expect(applyRealtimePipeline).toHaveBeenCalledTimes(2);
        const secondArg = vi.mocked(applyRealtimePipeline).mock.calls[1]?.[0];
        expect(secondArg?.log_pipeline_times).toBe(true);
    });

    it('resolves queued config from fresh store state at drain time', async () => {
        const store = makeStore();
        requestCoordinatedRealtimeApply(store.dispatch, store.getState);
        requestCoordinatedRealtimeApply(store.dispatch, store.getState, (current) => ({
            ...current,
            log_pipeline_times: false,
        }));
        store.dispatch(
            realtimeSlice.actions.pipelineConfigUpdated({
                ...defaultRealtimePipelineConfig,
                log_pipeline_times: true,
            }),
        );
        await resolveLatestApply();
        await Promise.resolve();
        const secondArg = vi.mocked(applyRealtimePipeline).mock.calls[1]?.[0];
        expect(secondArg?.log_pipeline_times).toBe(false);
    });

    it('drops queued apply after cancelQueuedRealtimeApply', async () => {
        const store = makeStore();
        requestCoordinatedRealtimeApply(store.dispatch, store.getState);
        requestCoordinatedRealtimeApply(store.dispatch, store.getState, (current) => ({
            ...current,
            log_pipeline_times: false,
        }));
        cancelQueuedRealtimeApply();
        await resolveLatestApply();
        await Promise.resolve();
        expect(applyRealtimePipeline).toHaveBeenCalledTimes(1);
    });

    it('does not apply when guardRealtimeApply rejects', () => {
        vi.mocked(guardRealtimeApply).mockReturnValue(false);
        const store = makeStore();
        requestCoordinatedRealtimeApply(store.dispatch, store.getState);
        expect(applyRealtimePipeline).not.toHaveBeenCalled();
    });
});
