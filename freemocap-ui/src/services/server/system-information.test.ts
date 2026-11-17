// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ConnectionState} from '@/services/server/server-helpers/websocket-connection';
import {requestSystemInformation, type SystemInformation, type SystemInformationState, watchSystemInformation} from './system-information';

const INFO = {host: {}, gpus: [], runtime: {}, execution_providers: {}, runs: []} as unknown as SystemInformation;

class FakeTransport {
    state = ConnectionState.DISCONNECTED;
    listeners = new Set<(state: ConnectionState) => void>();
    on(_event: string, callback: (state: ConnectionState) => void) { this.listeners.add(callback); }
    off(_event: string, callback: (state: ConnectionState) => void) { this.listeners.delete(callback); }
    getState() { return this.state; }
    emit(state: ConnectionState) { this.state = state; for (const callback of [...this.listeners]) callback(state); }
}

const settle = () => new Promise(resolve => setTimeout(resolve, 0));

test('the static groups are fetched on every connect, emptied on disconnect, and an obsolete answer is ignored', async () => {
    const transport = new FakeTransport();
    const pending: {resolve: (info: SystemInformation) => void; signal: AbortSignal}[] = [];
    const states: SystemInformationState[] = [];
    const watch = watchSystemInformation(transport, signal => new Promise(resolve => pending.push({resolve, signal})), state => states.push(state));
    assert.equal(pending.length, 0, 'nothing is asked before a connection');

    transport.emit(ConnectionState.CONNECTED);
    assert.equal(pending.length, 1);
    assert.equal(states.at(-1)?.loading, true);
    // The server goes away before it answers; the answer that arrives later is obsolete.
    transport.emit(ConnectionState.RECONNECTING);
    assert.ok(pending[0].signal.aborted);
    assert.deepEqual(states.at(-1), {info: null, loading: false, error: null});
    pending[0].resolve(INFO);
    await settle();
    assert.equal(states.at(-1)?.info, null);

    // A restarted server is asked again on reconnect.
    transport.emit(ConnectionState.CONNECTED);
    assert.equal(pending.length, 2);
    const fresh = {...INFO, runs: [{mode: 'realtime', pipeline_id: 'new', requested_provider: null, models: []}]} as SystemInformation;
    pending[1].resolve(fresh);
    await settle();
    assert.equal(states.at(-1)?.info, fresh);

    watch.refresh();
    assert.equal(pending.length, 3, 'refresh asks again');
    assert.equal(states.at(-1)?.info, fresh, 'the shown information stays while a refresh loads');
    watch.stop();
    assert.ok(pending[2].signal.aborted);
    transport.emit(ConnectionState.CONNECTED);
    assert.equal(pending.length, 3, 'a stopped watch asks nothing');
});

test('a failed request is a diagnostic and the next refresh asks again', async () => {
    const transport = new FakeTransport();
    transport.state = ConnectionState.CONNECTED;
    let calls = 0;
    const states: SystemInformationState[] = [];
    const watch = watchSystemInformation(transport, async () => { calls++; if (calls === 1) throw new Error('HTTP 500'); return INFO; },
        state => states.push(state));
    await settle();
    assert.deepEqual(states.at(-1), {info: null, loading: false, error: 'HTTP 500'});
    watch.refresh();
    await settle();
    assert.deepEqual(states.at(-1), {info: INFO, loading: false, error: null});
    watch.stop();
});

test('the request goes to the system information route and checks its groups', async () => {
    const urls: string[] = [];
    const request = (async (url: RequestInfo | URL) => { urls.push(String(url)); return Response.json(urls.length === 1 ? INFO : {host: {}}); }) as typeof fetch;
    assert.deepEqual(await requestSystemInformation('http://server.invalid', undefined, request), INFO);
    await assert.rejects(requestSystemInformation('http://server.invalid', undefined, request), /Invalid system information/);
    assert.deepEqual(urls, ['http://server.invalid/freemocap/onnx/system_information', 'http://server.invalid/freemocap/onnx/system_information']);
});
