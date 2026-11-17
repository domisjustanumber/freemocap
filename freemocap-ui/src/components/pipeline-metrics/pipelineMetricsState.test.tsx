import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import {RunSummary, StateNotice} from './PipelineMetricsWindowPage';
import {requestedRunKey, runLabel} from './pipelineMetricsState';
import type {RunTimingSnapshot} from '@/services/server/server-helpers/pipeline-timing-types';

function run(overrides: Partial<RunTimingSnapshot> = {}): RunTimingSnapshot {
    return {key: 'realtime:p1', mode: 'realtime', pipelineId: 'p1', cameraGroupId: 'group1', recordingName: null,
        active: true, timingEnabled: true, configuredCameraFpsHz: 30, events: [], incompleteFrames: [],
        nodeLag: {aggregator: 2}, staleNodes: ['skeleton_inference'], droppedInLastMessage: 0, droppedSinceOpened: 0,
        endToEnd: null, stages: [], receivedAtMs: 0, ...overrides};
}

test('a posthoc run is labelled by its recording, else its pipeline id', () => {
    assert.equal(runLabel(run()), 'Real-time · camera group group1');
    assert.equal(runLabel(run({mode: 'posthoc', cameraGroupId: null, recordingName: 'session_1'})), 'Posthoc · session_1');
    assert.equal(runLabel(run({mode: 'posthoc', cameraGroupId: null})), 'Posthoc · p1');
});

test('lag and stall show for a realtime run and are hidden for a posthoc run', () => {
    const realtime = renderToStaticMarkup(<RunSummary run={run()}/>);
    assert.match(realtime, /aggregator \+2/);
    assert.match(realtime, /stalled: skeleton_inference/);
    const posthoc = renderToStaticMarkup(<RunSummary run={run({mode: 'posthoc', key: 'posthoc:p1', cameraGroupId: null})}/>);
    assert.doesNotMatch(posthoc, /aggregator \+2|stalled/);
    assert.match(posthoc, /whole posthoc run/);
});

test('the window reads the run to preselect from its hash', () => {
    assert.equal(requestedRunKey('#/pipeline-metrics?pipeline=posthoc%3Aabc-1'), 'posthoc:abc-1');
    assert.equal(requestedRunKey('#/pipeline-metrics'), null);
});

test('timing off says how to turn it on, and that real-time processing must restart', () => {
    const realtime = renderToStaticMarkup(<StateNotice state="timing-disabled" run={run({timingEnabled: false})}/>);
    assert.match(realtime, /off for this real-time pipeline/);
    assert.match(realtime, /gear next to the Real-time processing button/);
    assert.match(realtime, /Log pipeline times/);
    assert.match(realtime, /stop and start Real-time processing/);
    const posthoc = renderToStaticMarkup(<StateNotice state="timing-disabled" run={run({mode: 'posthoc', timingEnabled: false})}/>);
    assert.match(posthoc, /off when this recording started processing/);
    assert.match(posthoc, /next recording you process is timed/);
});

test('a posthoc run says its dropped timing events are not counted', () => {
    const posthoc = renderToStaticMarkup(<RunSummary run={run({mode: 'posthoc', key: 'posthoc:p1', cameraGroupId: null, droppedSinceOpened: 0})}/>);
    assert.match(posthoc, /not counted for a posthoc run/);
    assert.doesNotMatch(posthoc, /since this window opened/);
    assert.match(renderToStaticMarkup(<RunSummary run={run()}/>), /since this window opened/);
});
