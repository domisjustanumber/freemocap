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

const guardRealtimeApply = vi.fn(() => true);

vi.mock('./guardRealtimeApply', () => ({
    guardRealtimeApply: (...args: unknown[]) => guardRealtimeApply(...args),
}));

import {configureStore} from '@reduxjs/toolkit';
import {realtimeSlice} from './realtime-slice';
import {REALTIME_RESTART_REQUIRED_MESSAGE} from './realtime-messages';
import {realtimePipelineRestartRequired} from './realtime-notify-actions';
import {
    cancelScheduledRealtimeCameraApply,
    scheduleRealtimeRestartRequiredAfterCameraToggle,
} from './realtime-camera-apply-scheduler';

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
            getDefaultMiddleware({serializableCheck: false}),
    });
}

describe('scheduleRealtimeRestartRequiredAfterCameraToggle', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        guardRealtimeApply.mockReturnValue(true);
    });

    afterEach(() => {
        cancelScheduledRealtimeCameraApply();
        vi.useRealTimers();
    });

    it('marks restart required after the debounce delay while connected', () => {
        const store = makeStore(true);
        const dispatch = vi.fn(store.dispatch);

        scheduleRealtimeRestartRequiredAfterCameraToggle(dispatch as never, store.getState, 2000);
        vi.advanceTimersByTime(1999);
        expect(dispatch).not.toHaveBeenCalled();

        vi.advanceTimersByTime(1);
        expect(dispatch).toHaveBeenCalledWith(
            realtimePipelineRestartRequired({message: REALTIME_RESTART_REQUIRED_MESSAGE}),
        );
    });

    it('debounces multiple toggles into one restart-required mark', () => {
        const store = makeStore(true);
        const dispatch = vi.fn(store.dispatch);

        scheduleRealtimeRestartRequiredAfterCameraToggle(dispatch as never, store.getState, 2000);
        vi.advanceTimersByTime(1000);
        scheduleRealtimeRestartRequiredAfterCameraToggle(dispatch as never, store.getState, 2000);
        vi.advanceTimersByTime(1999);
        expect(dispatch).not.toHaveBeenCalled();
        vi.advanceTimersByTime(1);
        expect(dispatch).toHaveBeenCalledTimes(1);
    });

    it('does nothing when disconnected before the timer fires', () => {
        const store = makeStore(false);
        const dispatch = vi.fn(store.dispatch);

        scheduleRealtimeRestartRequiredAfterCameraToggle(dispatch as never, store.getState, 2000);
        vi.advanceTimersByTime(2000);
        expect(dispatch).not.toHaveBeenCalled();
    });

    it('clears pending timer via cancelScheduledRealtimeCameraApply', () => {
        const store = makeStore(true);
        const dispatch = vi.fn(store.dispatch);

        scheduleRealtimeRestartRequiredAfterCameraToggle(dispatch as never, store.getState, 2000);
        cancelScheduledRealtimeCameraApply();
        vi.advanceTimersByTime(2000);
        expect(dispatch).not.toHaveBeenCalled();
    });

    it('does not mark restart required when guard fails at fire time', () => {
        guardRealtimeApply.mockReturnValue(false);
        const store = makeStore(true);
        const dispatch = vi.fn(store.dispatch);

        scheduleRealtimeRestartRequiredAfterCameraToggle(dispatch as never, store.getState, 2000);
        vi.advanceTimersByTime(2000);
        expect(dispatch).not.toHaveBeenCalledWith(
            realtimePipelineRestartRequired({message: REALTIME_RESTART_REQUIRED_MESSAGE}),
        );
    });
});
