// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
// The store import follows the application entry order, as the slice's imports expect.
import {store} from '@/store';
import {
    mocapSlice, legacyExecutionProviderResolved, executionProviderNoticeDismissed, mocapExecutionProviderChanged,
    selectCanProcessMocapRecording, type MocapState,
} from './mocap-slice';
import type {RootState} from '@/store/root-state-types';

const pending = (): MocapState => ({...mocapSlice.getInitialState(),
    config: {...mocapSlice.getInitialState().config, executionProvider: null, executionDevice: null},
    executionProviderMigration: {saved: 'old-ep', status: 'pending'}});
const reduce = mocapSlice.reducer;

test('the suggestion replaces the held-back key and the notice names both (G1); null is Auto (G3)', () => {
    for (const suggested of ['new-ep', null]) {
        const state = reduce(pending(), legacyExecutionProviderResolved({saved: 'old-ep', suggested}));
        assert.equal(state.config.executionProvider, suggested);
        assert.deepEqual(state.executionProviderMigration, {saved: 'old-ep', status: 'replaced', replacement: suggested});
        assert.equal(reduce(state, executionProviderNoticeDismissed()).executionProviderMigration, null);
    }
});

test('an answer for another key, or after the user chose, changes nothing', () => {
    assert.deepEqual(reduce(pending(), legacyExecutionProviderResolved({saved: 'other', suggested: 'new-ep'})), pending());
    const chosen = reduce(pending(), mocapExecutionProviderChanged('cpu'));
    assert.equal(chosen.executionProviderMigration, null);
    assert.equal(reduce(chosen, legacyExecutionProviderResolved({saved: 'old-ep', suggested: 'new-ep'})).config.executionProvider, 'cpu');
});

test('processing waits while a legacy key is pending', () => {
    const state = store.getState();
    const root = (mocap: MocapState) => ({...state, mocap,
        activeRecording: {...state.activeRecording, baseDirectory: '/data', recordingName: 'recording', origin: 'browsed'}}) as RootState;
    const ready = reduce(pending(), legacyExecutionProviderResolved({saved: 'old-ep', suggested: null}));
    assert.equal(selectCanProcessMocapRecording(root(ready)), true);
    assert.equal(selectCanProcessMocapRecording(root(pending())), false);
});
