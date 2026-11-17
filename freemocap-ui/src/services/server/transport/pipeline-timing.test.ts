import assert from 'node:assert/strict';
import {test} from 'node:test';
import {encode} from 'cbor-x';
import {decodeMessage} from './cbor-codec';
import {TransportService} from './TransportService';
import type {PipelineTimingMessage} from './message-contract';

// As the server encodes it: null fields left out, nanoseconds past 2^32 as CBOR uint64.
function timing(overrides: object = {}): object {
    return {kind: 'pipeline_timing', version: 0, timestamp: 0, sequence: 4, mode: 'realtime', pipeline_id: 'abc123',
        camera_group_id: 'group1', realtime_pipeline_active: true, log_pipeline_times_enabled: true,
        per_node: {aggregator: {triangulate: [1.5]}}, per_camera: {cam0: {read: [2, 2.5]}},
        events: [{task_id: 'abc123:7:camera:cam0:read', parent_task_ids: [], stage: 'read', node_kind: 'camera', camera_id: 'cam0',
            frame_number: 7, start_time_ns: 5_000_000_000n, end_time_ns: 5_002_000_000n, duration_ms: 2}],
        clock_domain: 'perf_counter', relay_perf_counter_ns: 1n << 40n, dropped_timing_events: 3,
        node_lag: {skeleton_inference: 2}, incomplete_frames: [8], stale_nodes: [], ...overrides};
}

test('a pipeline timing message decodes on its own, with defaults for the fields the server leaves out', () => {
    const message = decodeMessage(encode(timing()));
    assert.ok(message?.kind === 'pipeline_timing');
    assert.equal(message.configured_camera_fps_hz, null);
    assert.deepEqual(message.events[0], {task_id: 'abc123:7:camera:cam0:read', parent_task_ids: [], stage: 'read',
        node_kind: 'camera', camera_id: 'cam0', frame_number: 7, start_time_ns: 5_000_000_000, end_time_ns: 5_002_000_000,
        duration_ms: 2, batch_index: null, batch_size: null});
    assert.equal(message.relay_perf_counter_ns, 2 ** 40);
    assert.deepEqual([message.pipeline_id, message.camera_group_id, message.mode, message.dropped_timing_events],
        ['abc123', 'group1', 'realtime', 3]);
});

test('a malformed pipeline timing message is rejected, an unknown version is skipped', () => {
    for (const bad of [{mode: 'replay'}, {events: [{task_id: 'x'}]}, {dropped_timing_events: -1}, {pipeline_id: undefined}]) {
        assert.throws(() => decodeMessage(encode(timing(bad))));
    }
    assert.equal(decodeMessage(encode(timing({version: 1}))), null);
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

test('a timing subscriber asks on every connect, receives the messages, and the last one stops them', async () => {
    const sockets: Socket[] = [];
    const service = new TransportService({url: 'ws://server.invalid/websocket/connect', socketFactory: () => {
        const socket = new Socket(); sockets.push(socket); return socket as unknown as WebSocket;}});
    service['connection']['config'].reconnectDelay = 1;
    const interest = (socket: Socket) => socket.sent.filter(text => text.includes('pipelineTiming')).map(text => JSON.parse(text));
    service.connect(); sockets[0].open();
    assert.deepEqual(interest(sockets[0]), [], 'nothing is asked without a subscriber');
    const received: PipelineTimingMessage[] = [], other: PipelineTimingMessage[] = [];
    const stop = service.subscribeToPipelineTiming(message => received.push(message));
    const stopOther = service.subscribeToPipelineTiming(message => other.push(message));
    assert.deepEqual(interest(sockets[0]), [{pipelineTiming: true}]);
    sockets[0].packet(timing());
    assert.equal(received.length, 1); assert.deepEqual(received, other);

    // The server forgets the declaration with its connection (or restart): the new connection asks again.
    sockets[0].drop();
    await new Promise(resolve => setTimeout(resolve, 20));
    sockets[1].open();
    assert.deepEqual(interest(sockets[1]), [{pipelineTiming: true}]);
    sockets[1].packet(timing({sequence: 5}));
    assert.deepEqual(received.map(message => message.sequence), [4, 5]);

    stopOther();
    assert.deepEqual(interest(sockets[1]), [{pipelineTiming: true}]);
    stop();
    assert.deepEqual(interest(sockets[1]), [{pipelineTiming: true}, {pipelineTiming: false}]);
    service.disconnect();
});
