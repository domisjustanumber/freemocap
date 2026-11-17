// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test (tools/test-sdk-integration.mjs).
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {oldScaleConfidenceThreshold, savedMocapConfig} from '@/store/export-settings-migration';
import {RTMW_CONFIDENCE_THRESHOLD} from '@/types/rtmw-confidence';
import type {MocapState} from './mocap-slice';

// A settings file from before T1 (version 1) in the browser storage the store reads when it is created.
const files = new Map<string, string>([['freemocap:mocap.config',
    JSON.stringify({detectorType: 'rtmpose', rtmPoseConfidenceThreshold: 0.004, exportTallCsv: false, settingsVersion: 1})]]);
Object.assign(globalThis, {localStorage: {getItem: (key: string) => files.get(key) ?? null,
    setItem: (key: string, value: string) => files.set(key, value), removeItem: (key: string) => files.delete(key)}});
const saved = () => JSON.parse(files.get('freemocap:mocap.config')!);
const settle = () => new Promise(resolve => setTimeout(resolve, 400)); // past the 300 ms save debounce

test('an old file opens the prompt and keeps its value until the answer; reset saves 0.5 with the new version', async () => {
    const {store} = await import('@/store');
    const slice = await import('./mocap-slice');
    assert.equal(store.getState().mocap.oldConfidenceThreshold, 0.004);
    assert.equal(store.getState().mocap.config.rtmPoseConfidenceThreshold, 0.004);
    // Another setting changed while the prompt is open is saved, with the old version so the prompt survives a restart.
    store.dispatch(slice.exportTallCsvUpdated(true));
    await settle();
    assert.deepEqual([saved().rtmPoseConfidenceThreshold, saved().settingsVersion, saved().exportTallCsv], [0.004, 1, true]);
    store.dispatch(slice.oldConfidenceThresholdAnswered('reset'));
    await settle();
    assert.equal(store.getState().mocap.oldConfidenceThreshold, null);
    assert.deepEqual([saved().rtmPoseConfidenceThreshold, saved().settingsVersion], [RTMW_CONFIDENCE_THRESHOLD, 2]);
});

test('keep, or an edit of the field, closes the prompt and saves that value with the new version', async () => {
    const {mocapSlice, oldConfidenceThresholdAnswered, mocapRtmPoseConfidenceThresholdChanged} = await import('./mocap-slice');
    const initial = mocapSlice.getInitialState();
    const pending: MocapState = {...initial, config: {...initial.config, rtmPoseConfidenceThreshold: 0.004}, oldConfidenceThreshold: 0.004};
    assert.equal(savedMocapConfig(pending)!.settingsVersion, 1);
    const kept = mocapSlice.reducer(pending, oldConfidenceThresholdAnswered('keep'));
    assert.deepEqual([kept.oldConfidenceThreshold, savedMocapConfig(kept)!.rtmPoseConfidenceThreshold, savedMocapConfig(kept)!.settingsVersion],
        [null, 0.004, 2]);
    const edited = mocapSlice.reducer(pending, mocapRtmPoseConfidenceThresholdChanged(0.3));
    assert.deepEqual([edited.oldConfidenceThreshold, savedMocapConfig(edited)!.rtmPoseConfidenceThreshold, savedMocapConfig(edited)!.settingsVersion],
        [null, 0.3, 2]);
    // A late answer after the edit changes nothing.
    assert.equal(mocapSlice.reducer(edited, oldConfidenceThresholdAnswered('reset')).config.rtmPoseConfidenceThreshold, 0.3);
});

test('a new-version file, no file, no saved key or a value at or above 0.5 gets no prompt; any detector gets one', () => {
    assert.equal(oldScaleConfidenceThreshold({rtmPoseConfidenceThreshold: 0.004, settingsVersion: 2}), null);
    assert.equal(oldScaleConfidenceThreshold({}), null);
    assert.equal(oldScaleConfidenceThreshold({detectorType: 'rtmpose', settingsVersion: 1}), null);
    assert.equal(oldScaleConfidenceThreshold({rtmPoseConfidenceThreshold: RTMW_CONFIDENCE_THRESHOLD, settingsVersion: 1}), null);
    assert.equal(oldScaleConfidenceThreshold({rtmPoseConfidenceThreshold: 0.7, settingsVersion: 1}), null);
    assert.equal(oldScaleConfidenceThreshold({rtmPoseConfidenceThreshold: 0.004}), 0.004, 'pre-skellytracker-2 file');
    assert.equal(oldScaleConfidenceThreshold({detectorType: 'mediapipe', rtmPoseConfidenceThreshold: 0.004, settingsVersion: 1}), 0.004);
});
