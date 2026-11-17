// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test (tools/test-sdk-integration.mjs).
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {MOCAP_SETTINGS_VERSION} from '@/store/export-settings-migration';

// A settings file saved with timing on, in the browser storage the store reads when it is created (an app restart).
const files = new Map<string, string>([['freemocap:mocap.config',
    JSON.stringify({detectorType: 'rtmpose', logPipelineTimes: true, settingsVersion: MOCAP_SETTINGS_VERSION})]]);
Object.assign(globalThis, {localStorage: {getItem: (key: string) => files.get(key) ?? null,
    setItem: (key: string, value: string) => files.set(key, value), removeItem: (key: string) => files.delete(key)}});
const saved = () => JSON.parse(files.get('freemocap:mocap.config')!);
const settle = () => new Promise(resolve => setTimeout(resolve, 400)); // past the 300 ms save debounce

test('the timing setting survives a restart, reaches the posthoc request, and its change is saved', async () => {
    const {store} = await import('@/store');
    const slice = await import('./mocap-slice');
    const {mocapProcessingConfig} = await import('./mocap-thunks');
    assert.equal(store.getState().mocap.config.logPipelineTimes, true);
    assert.equal(mocapProcessingConfig(store.getState()).logPipelineTimes, true);
    store.dispatch(slice.logPipelineTimesChanged(false));
    await settle();
    assert.deepEqual([saved().logPipelineTimes, saved().settingsVersion], [false, MOCAP_SETTINGS_VERSION]);
    assert.equal(mocapProcessingConfig(store.getState()).logPipelineTimes, false);
});
