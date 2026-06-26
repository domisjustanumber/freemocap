import {describe, expect, it, vi} from 'vitest';
import {realtimeSlice} from './realtime-slice';
import {pipelineErrorDismissed, realtimeApplyBlocked} from './realtime-notify-actions';
import {applyRealtimePipeline} from './realtime-thunks';
import {REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE} from './realtime-messages';
import {formatApplyErrorDetail} from './formatApplyErrorDetail';
import {countRealtimeApplyCameras} from './realtime-apply-camera-count';
import {guardRealtimeApply} from './guardRealtimeApply';

const reducer = realtimeSlice.reducer;

function pending(requestId = 'test') {
    return {
        type: applyRealtimePipeline.pending.type,
        meta: {
            requestStatus: 'pending' as const,
            requestId,
            arg: {} as never,
        },
    };
}

function rejectedWithValue(payload: string, requestId = 'test') {
    return {
        type: applyRealtimePipeline.rejected.type,
        payload,
        error: {message: 'Rejected'},
        meta: {
            rejectedWithValue: true,
            requestStatus: 'rejected' as const,
            requestId,
            arg: {} as never,
            aborted: false,
            condition: false,
        },
    };
}

function fulfilled(requestId = 'test') {
    return {
        type: applyRealtimePipeline.fulfilled.type,
        payload: {
            pipeline_id: 'pipe_1',
            execution_provider: 'cuda',
        },
        meta: {
            requestStatus: 'fulfilled' as const,
            requestId,
            arg: {} as never,
        },
    };
}

function camerasState(selectedRealtime: Array<{id: string; selected: boolean; realtimeEnabled: boolean}>) {
    return {
        cameras: selectedRealtime.map((c, index) => ({
            id: c.id,
            index,
            name: c.id,
            selected: c.selected,
            realtimeEnabled: c.realtimeEnabled,
            connectionStatus: 'connected' as const,
            desiredConfig: {},
            actualConfig: {},
            hasConfigMismatch: false,
        })),
        isPaused: false,
        isLoading: false,
        autoApply: false,
        error: null,
    };
}

describe('realtime slice apply branches', () => {
    it('pending sets latestApplyRequestId and clears stale messages', () => {
        let state = reducer(undefined, pending('req-1'));
        expect(state.latestApplyRequestId).toBe('req-1');
        expect(state.error).toBeNull();
        expect(state.realtimeApplyBlockedMessage).toBeNull();
        expect(state.isLoading).toBe(true);
    });

    it('ignores stale fulfilled actions', () => {
        let state = reducer(undefined, pending('new'));
        state = reducer(state, fulfilled('old'));
        expect(state.pipelineId).toBeNull();
        expect(state.isConnected).toBe(false);
    });

    it('guard reject sets blocked message only', () => {
        let state = reducer(undefined, pending('guard'));
        state = reducer(state, rejectedWithValue(REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE, 'guard'));
        expect(state.realtimeApplyBlockedMessage).toBe(REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE);
        expect(state.isConnected).toBe(false);
        expect(state.pipelineId).toBeNull();
    });

    it('pipeline start failure deactivates pipeline fields', () => {
        let state = reducer(undefined, pending('failure'));
        state = reducer(state, rejectedWithValue('OOM during TRT compile', 'failure'));
        expect(state.error).toBe('OOM during TRT compile');
        expect(state.isConnected).toBe(false);
        expect(state.pipelineId).toBeNull();
    });

    it('pipelineErrorDismissed clears error only', () => {
        let state = reducer(undefined, pending('failure'));
        state = reducer(state, rejectedWithValue('boom', 'failure'));
        state = reducer(state, pipelineErrorDismissed());
        expect(state.error).toBeNull();
        expect(state.isConnected).toBe(false);
    });
});

describe('formatApplyErrorDetail', () => {
    it('returns string detail', () => {
        expect(formatApplyErrorDetail({detail: 'nope'}, 422)).toBe('nope');
    });

    it('joins validation array detail', () => {
        expect(
            formatApplyErrorDetail({detail: [{msg: 'a'}, {msg: 'b'}]}, 422),
        ).toBe('a; b');
    });

    it('falls back to status message', () => {
        expect(formatApplyErrorDetail({}, 500)).toBe('Failed to apply realtime (500)');
    });
});

describe('countRealtimeApplyCameras', () => {
    it('counts selected and realtime-enabled cameras', () => {
        const state = {
            cameras: camerasState([
                {id: 'a', selected: true, realtimeEnabled: true},
                {id: 'b', selected: true, realtimeEnabled: false},
            ]),
        };
        expect(countRealtimeApplyCameras(state as never)).toBe(1);
    });
});

describe('guardRealtimeApply', () => {
    it('dispatches blocked action when zero cameras', () => {
        const dispatch = vi.fn();
        const getState = () =>
            ({
                cameras: camerasState([]),
            });
        const allowed = guardRealtimeApply(dispatch, getState as never);
        expect(allowed).toBe(false);
        expect(dispatch).toHaveBeenCalledWith(
            realtimeApplyBlocked({message: REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE}),
        );
    });
});
