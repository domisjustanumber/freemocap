import assert from 'node:assert/strict';
import {test} from 'node:test';
import {PipelineTimingStore, toStoredEvent} from '@/services/server/server-helpers/pipeline-timing-store';
import type {PipelineTimingMessage} from '@/services/server/transport/message-contract';
import {realtimeFrame} from './__fixtures__/realtime-frame';
import {metricsState, runLabel, sortStages} from './pipelineMetricsState';
import {
    barWidthPercentInViewport,
    buildTimelineViewModel,
    estimateFrameDurationFromFrameAnchors,
    formatBarDuration,
    formatDurationPrecise,
    resolveVisibleTimelineWindow,
    zoomTimelineAtPointer,
} from './pipelineTimelineModel';

const frames = (from: number, to: number) => Array.from({length: to - from + 1}, (_, i) => realtimeFrame(from + i, (from + i) * 33)).flat();

test('the timeline keeps the newest five frames, nests rows under their parent span, and links them', () => {
    const model = buildTimelineViewModel({events: frames(1, 7).map(toStoredEvent), configuredCameraFpsHz: 30, incompleteFrames: []});
    assert.deepEqual([model.frameStart, model.frameEnd], [3, 7]);
    assert.ok(model.rows.every(row => row.frameNumber! >= 3));
    assert.equal(model.windowStartMs, 3 * 33, 'the window starts at the first shown frame earliest event');
    assert.equal(model.windowDurationMs, (1000 / 30) * 5, 'five frame times, while the frames fit');

    const person = model.rows.find(row => row.taskId === 'p1:7:batch:skeleton_inference:person.inference')!;
    assert.deepEqual([person.engine, person.indentLevel, person.parentSpanStartMs, person.parentSpanEndMs], ['2.0', 2, 7 * 33 + 3, 7 * 33 + 19]);
    const edgeTo = (taskId: string) => model.edges.filter(edge => edge.toTaskId === taskId).map(edge => edge.fromTaskId);
    assert.deepEqual(edgeTo('p1:7:batch:skeleton_inference:pipeline.run'), ['7:batch:skeleton_inference:predict_batch']);
});

test('bars shorter than 0.5 ms are not rows, and no edge points at a hidden row', () => {
    const run = 'p1:9:batch:skeleton_inference:pipeline.run';
    const short = (stage: string, startMs: number, endMs: number, parents: string[]) => ({...realtimeFrame(9)[0],
        task_id: `p1:9:batch:skeleton_inference:${stage}`, parent_task_ids: parents, stage, node_kind: 'skeleton_inference',
        camera_id: null, start_time_ns: startMs * 1_000_000, end_time_ns: endMs * 1_000_000, duration_ms: endMs - startMs});
    // A 0.2 ms middle row with a child of its own, and a 0.4 ms leaf under pipeline.run (3-19 ms).
    const events = [...realtimeFrame(9), short('box.run', 5, 5.2, [run]), short('box.child', 5.05, 5.15, ['p1:9:batch:skeleton_inference:box.run']),
        short('trigger.run', 3.1, 3.5, [run])].map(toStoredEvent);
    const model = buildTimelineViewModel({events, configuredCameraFpsHz: 30});
    const ids = new Set(model.rows.map(row => row.taskId));
    assert.ok(!['box.run', 'box.child', 'trigger.run'].some(stage => ids.has(`p1:9:batch:skeleton_inference:${stage}`)));
    assert.ok(ids.has(run) && ids.has('p1:9:batch:skeleton_inference:crop.run'), 'pipeline.run and a 1 ms bar stay');
    assert.ok(model.edges.every(edge => ids.has(edge.fromTaskId) && ids.has(edge.toTaskId)
        && model.rows[edge.fromRowIndex].taskId === edge.fromTaskId && model.rows[edge.toRowIndex].taskId === edge.toTaskId));
});

test('a frame slower than the window widens it by whole window steps', () => {
    const slow = realtimeFrame(9).map(event => event.stage === 'predict_batch' ? {...event, end_time_ns: 400 * 1_000_000} : event);
    const model = buildTimelineViewModel({events: slow.map(toStoredEvent), configuredCameraFpsHz: 30});
    assert.equal(model.windowDurationMs, 3 * ((1000 / 30) * 5), 'a 400 ms frame needs three steps of 167 ms');
});

test('without a configured rate the frame time comes from the frame anchors', () => {
    const events = frames(1, 4).map(toStoredEvent);
    assert.equal(estimateFrameDurationFromFrameAnchors(events), 33);
    assert.equal(buildTimelineViewModel({events, configuredCameraFpsHz: null}).frameDurationMs, 33);
    assert.equal(estimateFrameDurationFromFrameAnchors(frames(1, 2).map(toStoredEvent)), null, 'two frames are not enough');
});

test('zoom keeps the pointer in place, and bars clip to the visible window', () => {
    const window = resolveVisibleTimelineWindow(100, 200, 4, 30);
    assert.deepEqual([window.visibleStartMs, window.visibleDurationMs], [130, 50]);
    const zoomed = zoomTimelineAtPointer(0, 100, 1, 0, 0.5, true);
    const visible = resolveVisibleTimelineWindow(0, 100, zoomed.zoomLevel, zoomed.panMs);
    assert.ok(Math.abs(visible.visibleStartMs + visible.visibleDurationMs / 2 - 50) < 1e-9);
    assert.deepEqual(barWidthPercentInViewport({barStartMs: 90, barEndMs: 150}, 100, 100), {leftPct: 0, widthPct: 50, visible: true});
    assert.equal(barWidthPercentInViewport({barStartMs: 0, barEndMs: 10}, 100, 100).visible, false);
    assert.deepEqual([formatBarDuration(0.4), formatBarDuration(12.6), formatDurationPrecise(3.14159)], ['<1 ms', '13 ms', '3.14 ms']);
});

function message(overrides: Partial<PipelineTimingMessage>): PipelineTimingMessage {
    return {kind: 'pipeline_timing', version: 0, timestamp: 0, sequence: 1, mode: 'realtime', pipeline_id: 'p1',
        camera_group_id: 'group1', realtime_pipeline_active: true, log_pipeline_times_enabled: true,
        configured_camera_fps_hz: 30, per_node: {}, per_camera: {}, events: [], clock_domain: 'perf_counter',
        relay_perf_counter_ns: 0, dropped_timing_events: 0, node_lag: {}, incomplete_frames: [], stale_nodes: [],
        ...overrides} as PipelineTimingMessage;
}

test('the window state comes from the connection and the newest message only', () => {
    const store = new PipelineTimingStore();
    store.ingest(message({events: realtimeFrame(7)}), 0);
    const [run] = store.runs(0);
    assert.equal(metricsState(false, run), 'disconnected');
    assert.equal(metricsState(true, null), 'no-pipeline');
    assert.equal(metricsState(true, run), 'ready');
    assert.equal(metricsState(true, {...run, timingEnabled: false}), 'timing-disabled');
    assert.equal(metricsState(true, {...run, active: false}), 'not-running');
    assert.equal(runLabel(run), 'Real-time · camera group group1');
    assert.equal(runLabel({mode: 'posthoc', pipelineId: 'job9', cameraGroupId: null, recordingName: null}), 'Posthoc · job9');
    assert.deepEqual(sortStages(run.stages).map(stage => stage.stage), [
        'charuco_detection', 'frame_read', 'predict_batch', 'pipeline.run', 'wholebody.inference', 'person.inference', 'crop.run']);
});
