import assert from 'node:assert/strict';
import {test} from 'node:test';
import {encode} from 'cbor-x';
import {TransportService} from '@/services/server/transport/TransportService';
import type {PipelineTimingEvent, PipelineTimingMessage} from '@/services/server/transport/message-contract';
import {feedPipelineTimingStore, frameTimings, PipelineTimingStore, toStoredEvent} from './pipeline-timing-store';

const MS = 1_000_000;

function event(frame: number, stage: string, startMs: number, endMs: number, overrides: Partial<PipelineTimingEvent> = {}): PipelineTimingEvent {
    return {task_id: `${frame}:batch:skeleton_inference:${stage}`, parent_task_ids: [], stage, node_kind: 'skeleton_inference',
        camera_id: null, frame_number: frame, start_time_ns: startMs * MS, end_time_ns: endMs * MS, duration_ms: endMs - startMs,
        batch_index: null, batch_size: 2, ...overrides};
}

function message(overrides: Partial<PipelineTimingMessage> = {}): PipelineTimingMessage {
    return {kind: 'pipeline_timing', version: 0, timestamp: 0, sequence: 1, mode: 'realtime', pipeline_id: 'p1',
        camera_group_id: 'group1', recording_name: null, realtime_pipeline_active: true, log_pipeline_times_enabled: true,
        configured_camera_fps_hz: 30, per_node: {}, per_camera: {}, events: [], clock_domain: 'perf_counter',
        relay_perf_counter_ns: 0, dropped_timing_events: 0, node_lag: {}, incomplete_frames: [], stale_nodes: [],
        ...overrides} as PipelineTimingMessage;
}

// Frame 7: charuco on cam0 (10-14 ms) runs beside frame read (11-12) and predict batch (12-30).
const frame7 = [
    event(7, 'charuco_detection', 10, 14, {task_id: '7:cam0:camera:charuco_detection', node_kind: 'camera', camera_id: 'cam0'}),
    event(7, 'frame_read', 11, 12),
    event(7, 'predict_batch', 12, 30),
];

test('each complete frame takes its end-to-end time from its own events, and incomplete frames are skipped', () => {
    const timings = frameTimings([...frame7, event(8, 'frame_read', 40, 41), event(9, 'frame_read', 70, 75)].map(toStoredEvent), [9]);
    assert.deepEqual([...timings.keys()], [7, 8]);
    assert.equal(timings.get(7)!.endToEndMs, 20, 'first start (charuco, 10 ms) to last end (predict batch, 30 ms)');
    assert.equal(timings.get(8)!.endToEndMs, 1);
    assert.deepEqual([...timings.get(7)!.stageMs], [['camera:cam0:charuco_detection', 4], ['skeleton_inference:frame_read', 1], ['skeleton_inference:predict_batch', 18]]);
});

test('per-stage ms/frame pairs with FPS over the sampled frames, and a frame sent twice counts once', () => {
    const store = new PipelineTimingStore();
    store.ingest(message({events: frame7}), 0);
    // The next message repeats frame 7 and adds frame 8: frame 7 must not be counted twice.
    store.ingest(message({events: [...frame7, event(8, 'frame_read', 44, 47), event(8, 'predict_batch', 47, 57)]}), 250);
    const [run] = store.runs(250);
    assert.deepEqual(run.endToEnd, {meanMs: 16.5, minMs: 13, maxMs: 20, frames: 2});
    const predict = run.stages.find(stage => stage.sourceKey === 'skeleton_inference:predict_batch')!;
    assert.deepEqual([predict.meanMs, predict.minMs, predict.maxMs, predict.frames, predict.fps], [14, 10, 18, 2, 1000 / 14]);
    const charuco = run.stages.find(stage => stage.sourceKey === 'camera:cam0:charuco_detection')!;
    assert.deepEqual([charuco.frames, charuco.cameraId, charuco.nodeKind], [1, 'cam0', 'camera']);
});

test('runs are keyed by mode and pipeline id, each message replaces its run, and silent runs expire', () => {
    const store = new PipelineTimingStore();
    store.ingest(message({pipeline_id: 'p1', events: frame7, dropped_timing_events: 2}), 0);
    store.ingest(message({pipeline_id: 'p2', camera_group_id: 'group2'}), 0);
    store.ingest(message({mode: 'posthoc', pipeline_id: 'p1'}), 0);
    assert.deepEqual(store.runs(0).map(run => [run.key, run.cameraGroupId]),
        [['posthoc:p1', 'group1'], ['realtime:p1', 'group1'], ['realtime:p2', 'group2']]);

    store.ingest(message({pipeline_id: 'p1', events: [], log_pipeline_times_enabled: false, dropped_timing_events: 3}), 1000);
    const p1 = store.runs(1000).find(run => run.key === 'realtime:p1')!;
    assert.deepEqual([p1.events.length, p1.timingEnabled, p1.droppedInLastMessage, p1.droppedSinceOpened], [0, false, 3, 5],
        'events replace; dropped events are per message, with a labelled sum since the window opened');
    assert.deepEqual(store.runs(2500).map(run => run.key), ['realtime:p1'], 'the runs that stopped reporting are gone');
});

test('a posthoc run keeps its recording name and has no camera group', () => {
    const store = new PipelineTimingStore();
    store.ingest(message({mode: 'posthoc', pipeline_id: 'run1', camera_group_id: null, recording_name: 'session_1',
        configured_camera_fps_hz: null, events: frame7}), 0);
    const [run] = store.runs(0);
    assert.deepEqual([run.key, run.cameraGroupId, run.recordingName, run.endToEnd?.frames], ['posthoc:run1', null, 'session_1', 1]);
});

class Socket {
    readyState = 0; binaryType = ''; sent: string[] = [];
    onopen: ((event: object) => void) | null = null; onclose: ((event: object) => void) | null = null;
    onerror: ((event: object) => void) | null = null; onmessage: ((event: {data: unknown}) => void) | null = null;
    send(value: string) {this.sent.push(value);}
    close() {this.readyState = 3;}
    open() {this.readyState = 1; this.onopen?.({});}
    drop() {this.readyState = 3; this.onclose?.({code: 1006});}
    packet(value: object) {const bytes = encode(value); this.onmessage?.({data: bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)});}
}

test('a dropped connection or server restart empties the store, and fresh messages alone rebuild it', async () => {
    const sockets: Socket[] = [];
    const transport = new TransportService({url: 'ws://server.invalid/websocket/connect', socketFactory: () => {
        const socket = new Socket(); sockets.push(socket); return socket as unknown as WebSocket;}});
    transport['connection']['config'].reconnectDelay = 1;
    const store = new PipelineTimingStore();
    const stop = feedPipelineTimingStore(transport, store);
    transport.connect(); sockets[0].open();
    assert.ok(sockets[0].sent.includes(JSON.stringify({pipelineTiming: true})));
    sockets[0].packet(message({events: frame7, dropped_timing_events: 4}));
    assert.equal(store.runs()[0].droppedSinceOpened, 4);

    sockets[0].drop();
    assert.deepEqual(store.runs(), [], 'nothing of the old server survives the disconnect');
    await new Promise(resolve => setTimeout(resolve, 20));
    sockets[1].open();
    assert.ok(sockets[1].sent.includes(JSON.stringify({pipelineTiming: true})), 'the new connection asks again');
    sockets[1].packet(message({pipeline_id: 'restarted', dropped_timing_events: 1}));
    assert.deepEqual(store.runs().map(run => [run.key, run.droppedSinceOpened, run.endToEnd]), [['realtime:restarted', 1, null]]);
    stop();
    transport.disconnect();
});
