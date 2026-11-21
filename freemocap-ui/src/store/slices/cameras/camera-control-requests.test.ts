import assert from 'node:assert/strict';
import {store} from '../../index';
import type {Certification} from '@freemocap/client';
import {camerasConnectOrUpdate, pauseUnpauseCameras} from './cameras-thunks';
import {createDefaultCameraConfig} from './cameras-types';
import {stopRecording} from '../recording/recording-thunks';
import {serverStateReceived} from '../connection/connection-slice';

async function checkControls() {
    const original = globalThis.fetch;
    const calls: string[] = [];
    try {
        globalThis.fetch = async (input, init) => {
            const path = new URL(String(input)).pathname;
            calls.push(`${init?.method} ${path}`);
            if (path.endsWith('/pause')) {
                const {paused} = JSON.parse(String(init?.body));
                assert.equal(typeof paused, 'boolean');
                // The pushed state can arrive before the HTTP response.
                store.dispatch(serverStateReceived({server_pid: 1, state: {camera_groups: {
                    group: {id: 'group', backend: 'python', configs: {}, cameras: {}, alive: true,
                        recording_in_progress: false, paused},
                }, realtime_pipelines: []}}));
                return new Response(JSON.stringify({paused}));
            }
            return new Response('[]');
        };
        await store.dispatch(pauseUnpauseCameras()).unwrap();
        assert.equal(store.getState().cameras.isPaused, true);
        await store.dispatch(pauseUnpauseCameras()).unwrap();
        assert.equal(store.getState().cameras.isPaused, false);
        assert.equal(await store.dispatch(stopRecording()).unwrap(), null);
        assert.deepEqual(calls, ['PUT /skellycam/camera/group/all/pause',
            'PUT /skellycam/camera/group/all/pause', 'POST /skellycam/camera/group/all/record/stop']);
        console.log('Camera control requests and pushed-state race passed');
    } finally {
        globalThis.fetch = original;
    }
}
/** A refusal for the required start check shows until the server's state no longer requires it; other errors stay. */
async function checkStartCheckRefusal() {
    const original = globalThis.fetch;
    const certification = (start_required: boolean) =>
        ({host: {name: 'h', os: 'o'}, items: [], gpu_held_by: [], pending_reports: [], start_required}) as Certification;
    const snapshot = (start_required: boolean) => serverStateReceived({server_pid: 1, state: {camera_groups: {},
        realtime_pipelines: [], certification: certification(start_required)}});
    const sentence = 'FreeMoCap must finish its system checks before cameras can start.';
    let answer = () => new Response(JSON.stringify({detail: {code: 'start-check-required', message: sentence}}), {status: 409});
    try {
        globalThis.fetch = async () => answer();
        store.dispatch(serverStateReceived({server_pid: 1, state: {camera_groups: {group: {id: 'group', backend: 'python',
            configs: {'camera-A': createDefaultCameraConfig('camera-A', 0, 'Camera')}, cameras: {}, alive: true,
            recording_in_progress: false, paused: false}}, realtime_pipelines: []}}));
        store.dispatch(snapshot(true));
        await store.dispatch(camerasConnectOrUpdate());
        assert.equal(store.getState().cameras.error, sentence);
        store.dispatch(snapshot(true));
        assert.equal(store.getState().cameras.error, sentence, 'the refusal shows while the check is still required');
        store.dispatch(snapshot(false));
        assert.equal(store.getState().cameras.error, null, 'the refusal goes once the server no longer requires the check');
        answer = () => new Response(JSON.stringify({detail: 'Camera busy'}), {status: 500});
        await store.dispatch(camerasConnectOrUpdate());
        store.dispatch(snapshot(false));
        assert.equal(store.getState().cameras.error, 'Camera busy', 'any other error stays until dismissed or a new request');
        console.log('Start-check camera refusal reconciliation passed');
    } finally {
        globalThis.fetch = original;
    }
}
void checkControls().then(checkStartCheckRefusal).catch(error => {console.error(error); process.exitCode = 1;});
