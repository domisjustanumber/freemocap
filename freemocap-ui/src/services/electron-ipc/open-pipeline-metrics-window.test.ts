import assert from 'node:assert/strict';
import {test} from 'node:test';
import superjson from 'superjson';
import {requestedRunKey} from '@/components/pipeline-metrics/pipelineMetricsState';
import {openPipelineMetricsWindow, pipelineMetricsHash} from './open-pipeline-metrics-window';

const global = globalThis as unknown as {window?: object};

test('the opener names the run in the hash the window reads back', () => {
    assert.equal(pipelineMetricsHash(), '#/pipeline-metrics');
    assert.equal(requestedRunKey(pipelineMetricsHash()), null);
    assert.equal(requestedRunKey(pipelineMetricsHash('posthoc:3f2a-run')), 'posthoc:3f2a-run');
});

test('in a browser the opener reuses the named window at the run hash', async () => {
    const opened: string[][] = [];
    global.window = {location: {origin: 'http://localhost:5173', pathname: '/'},
        open: (...args: string[]) => { opened.push(args); return {focus() {}}; }};
    try {
        await openPipelineMetricsWindow('posthoc:run1');
        assert.deepEqual(opened, [['http://localhost:5173/#/pipeline-metrics?pipeline=posthoc%3Arun1',
            'freemocap-pipeline-metrics', 'width=1100,height=760']]);
    } finally {
        delete global.window;
    }
});

test('in Electron the opener passes the run to the openPipelineMetrics mutation', async () => {
    const calls: unknown[][] = [];
    global.window = {electronAPI: {invoke: async (...args: unknown[]) => { calls.push(args); return superjson.serialize(undefined); }}};
    try {
        await openPipelineMetricsWindow('posthoc:run1');
        await openPipelineMetricsWindow();
        assert.deepEqual(calls, [['windows.openPipelineMetrics', {pipeline: 'posthoc:run1'}], ['windows.openPipelineMetrics', undefined]]);
    } finally {
        delete global.window;
    }
});
