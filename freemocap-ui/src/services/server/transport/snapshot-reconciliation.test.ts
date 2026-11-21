import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {decodeMessage} from './cbor-codec';
import {TransportService} from './TransportService';
import {ModelDefinitionSchema} from './message-contract';

test('frame contents replace stale definitions despite an unchanged model revision', () => {
    const message = decodeMessage(readFileSync('src/services/server/transport/__fixtures__/message_frame_golden.bin'));
    assert.ok(message?.kind === 'frame');
    const model = ModelDefinitionSchema.parse({model_id: 'tracked-object', segments: [], landmarks: [], connections: []});
    const frame = {...message, models: [model], instances: [], trackers: [], image: undefined};
    const service = new TransportService({url: 'ws://localhost/websocket/connect'});
    let updates = 0;
    service.subscribeToModels(() => {updates++;});
    service['handleFrame']({...frame, models: []});
    service['handleFrame'](frame);
    assert.ok(frame.models.length > 0);
    assert.equal(updates, 2);
    const retained = service.getModels();
    service['handleFrame'](structuredClone(frame));
    assert.equal(updates, 2);
    assert.equal(service.getModels(), retained);
    service['handleFrame']({...frame, models: []});
    assert.deepEqual(service.getModels(), []);
    assert.equal(updates, 3);
});

test('the app-state golden with its certification field passes the transport validation', () => {
    const message = decodeMessage(readFileSync('src/services/server/transport/__fixtures__/message_app_state_golden.bin'));
    assert.ok(message?.kind === 'app_state');
    // The field is kept, not stripped, and a null value of the server is an absent key.
    const certification = message.state.certification;
    assert.ok(certification);
    assert.deepEqual(certification.run, {level: 'quick', items: [{execution_provider: 'golden-ep', device_key: 'gpu:10de:2484:0'}],
        state: 'running', done: 2, total: 5, seconds_estimate: 45, rows: []});
    assert.deepEqual(certification.full_results, []);
    assert.deepEqual(certification.full_rows, []);
    assert.deepEqual(certification.last_result,
        {execution_provider: 'other-ep', device_key: 'gpu:10de:2484:0', result: 'fail', reason: 'probe-l3-failed'});
    assert.equal(certification.items[0].label, 'Golden EP');
    assert.equal(certification.items[0].local_result, undefined);
    assert.equal(certification.auto?.execution_provider, 'cpu-ep');
    assert.deepEqual(certification.gpu_held_by, [{kind: 'posthoc', id: 'abc123'}]);
    assert.deepEqual(certification.pack_run, {action: 'install', execution_provider: 'golden-ml-ep', phase: 'download', fraction: 0.25});
    assert.deepEqual(certification.last_pack_result,
        {action: 'remove', execution_provider: 'golden-ml-ep', result: 'failed', reason: 'package-not-removed'});
});
