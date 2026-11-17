import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import {formatBytes, formatHz, LiveLoadGroup, MISSING, runAwaitingModels, SystemInformationPanel} from './SystemInformationPanel';
import type {SystemInformation} from '@/services/server/system-information';
import type {RunTimingSnapshot} from '@/services/server/server-helpers/pipeline-timing-types';
import type {LiveLoad} from '@/services/server/transport/message-contract';

const DEVICE = 'gpu:10de:2484:0';
const INFO: SystemInformation = {
    host: {os_name: 'Windows', os_release: '11', os_version: '10.0.26300', os_build: '26300', arch: 'AMD64', cpu_name: 'Some CPU',
        cpu_physical_cores: null, cpu_logical_cores: 16, cpu_max_frequency_hz: 3_418_000_000, memory_total_bytes: 64 * 2 ** 30,
        is_wsl: false, is_vm: false, hypervisor: null, container_runtime: null, probe_errors: []},
    gpus: [{device_key: DEVICE, name: 'Some NVIDIA GPU', vendor: 'nvidia', driver_version: '610.88', vram_total_bytes: 8 * 2 ** 30,
        is_integrated: null, compute_capability: '8.6', brand: 'geforce'},
        {device_key: null, name: null, vendor: 'other', driver_version: null, vram_total_bytes: null, is_integrated: null,
            compute_capability: null, brand: null}],
    runtime: {python_implementation: 'CPython', python_version: '3.13.18', python_build: 'main', python_compiler: 'MSC',
        skellytracker_version: '2.0.0', skellytracker_commit: '0a50c719', ort_version: '1.31.1', ort_packages: ['onnxruntime'],
        ort_ep_names: ['CpuEp'], mediapipe_version: null, driver_supported_cuda_version: '13.3',
        loaded_libraries: [{name: 'cudnn', version: '9.1', source: 'module:cudnn64_9'}], probe_errors: []},
    execution_providers: {ort_version: '1.31.1', core_matches_pin: true, warnings: ['VIRTUAL_ENV is not the environment of this Python.'],
        providers: [{key: 'gpu-ep', label: 'NVIDIA CUDA', state: 'ready', usable: true, install_hint: null,
            devices: [{key: DEVICE, name: 'Some NVIDIA GPU', vram_total_bytes: 8 * 2 ** 30}]},
            {key: 'pack-ep', label: 'TensorRT RTX', state: 'not_installed', usable: false, install_hint: 'Run `skellytracker-eps install pack-ep`.', devices: []}],
        recommendation: {hardware_class: 'nvidia-cc80', precision: 'fp16',
            chosen: {ep_key: 'gpu-ep', device_key: DEVICE, status: 'ready', reason: null},
            skipped: [{ep_key: 'pack-ep', device_key: null, status: 'not_installed', reason: 'the pack is not installed'}],
            offers: [{kind: 'add-pack', ep_key: 'pack-ep', download_bytes: 1, disk_bytes: 2, licence_url: null, note: 'Install the TensorRT pack.'}]}},
    runs: [{mode: 'realtime', pipeline_id: 'p1', requested_provider: 'gpu-ep', models: [
        {node: 'wholebody', key: 'rtmw-wholebody', version: '1', size: 'm', precision: 'fp16', engine: null, execution_provider: 'gpu-ep',
            device: DEVICE, device_names: ['Some NVIDIA GPU']}]}],
};

function run(overrides: Partial<RunTimingSnapshot> = {}): RunTimingSnapshot {
    return {key: 'realtime:p1', mode: 'realtime', pipelineId: 'p1', cameraGroupId: 'group1', recordingName: null, active: true,
        timingEnabled: true, configuredCameraFpsHz: 30, events: [], incompleteFrames: [], nodeLag: {}, staleNodes: [],
        droppedInLastMessage: 0, droppedSinceOpened: 0, endToEnd: null, stages: [], liveLoad: null, receivedAtMs: 0, ...overrides};
}

function load(overrides: Partial<LiveLoad> = {}): LiveLoad {
    return {sample_perf_counter_ns: 1, interval_s: 1, memory_used_bytes: 40 * 2 ** 30, memory_available_bytes: 24 * 2 ** 30,
        cpu_utilization: null, process_cpu_utilization: null, process_rss_bytes: 512 * 2 ** 20, process_vram_used_bytes: null,
        gpus: [{device_key: DEVICE, name: 'Some NVIDIA GPU', utilization: 0.09, vram_used_bytes: null, vram_free_bytes: 5 * 2 ** 30,
            process_vram_used_bytes: null}], sample_errors: [], ...overrides};
}

const panel = (props: Partial<Parameters<typeof SystemInformationPanel>[0]> = {}) => renderToStaticMarkup(<SystemInformationPanel
    state={{info: INFO, loading: false, error: null}} run={run()} liveLoad={load()} connected onRefresh={() => {}} {...props}/>);

test('the panel renders the six groups from the endpoint and the message', () => {
    const html = panel();
    for (const group of ['Host', 'GPUs', 'Runtime &amp; libraries', 'Execution providers', 'Models of this run', 'Live load']) {
        assert.match(html, new RegExp(`<summary>${group}`), group);
    }
    assert.match(html, /3\.42 GHz/);
    assert.match(html, /64\.0 GiB/);
    assert.match(html, /gpu:10de:2484:0/);
    assert.match(html, /8\.6 \(geforce\)/);
    assert.match(html, /2\.0\.0 @ 0a50c719/);
    assert.match(html, /cudnn 9\.1/);
    assert.match(html, /gpu-ep on Some NVIDIA GPU, fp16/);
    assert.match(html, /pack-ep: the pack is not installed/);
    assert.match(html, /Install the TensorRT pack\./);
    assert.match(html, /VIRTUAL_ENV is not the environment/);
    assert.match(html, /rtmw-wholebody 1/);
    assert.match(html, /Refresh system information/);
});

test('missing values show as a dash, never as 0', () => {
    const html = panel();
    assert.match(html, new RegExp(`${MISSING} physical, 16 logical`));
    assert.match(html, new RegExp(`MediaPipe</td><td>${MISSING}`));
    assert.match(html, new RegExp(`CPU \\(all cores\\)</td><td>${MISSING}`), 'the first sample has no CPU value');
    assert.match(html, new RegExp(`CPU ${MISSING}, RAM 512\\.0 MiB, VRAM ${MISSING}`));
    assert.doesNotMatch(html, /0 %|0 B/);
    assert.equal(formatBytes(null), MISSING);
    assert.equal(formatBytes(0), '0 B');
    assert.equal(formatHz(undefined), MISSING);
});

test('models are those of the selected run, and a run without models says so', () => {
    assert.match(panel(), /Some NVIDIA GPU<\/td><\/tr><\/tbody><\/table><\/div><\/details>/);
    const other = panel({run: run({key: 'posthoc:p2', mode: 'posthoc', pipelineId: 'p2'})});
    assert.match(other, /This run reports no models yet/);
    assert.match(panel({run: null}), /No run is selected/);
});

test('live load updates from the newest message and needs a pipeline', () => {
    assert.match(renderToStaticMarkup(<LiveLoadGroup load={load({cpu_utilization: 0.25})}/>), /25 %/);
    assert.match(renderToStaticMarkup(<LiveLoadGroup load={load({cpu_utilization: 0.5})}/>), /50 %/);
    assert.match(renderToStaticMarkup(<LiveLoadGroup load={null}/>), /needs a pipeline/);
});

test('without information the panel shows its state, the live load, and a refresh that stays enabled', () => {
    const loading = panel({state: {info: null, loading: true, error: null}});
    assert.match(loading, /Loading…/);
    assert.doesNotMatch(loading, /<summary>Host/);
    assert.match(loading, /<summary>Live load/);
    const failed = panel({state: {info: null, loading: false, error: 'HTTP 500'}});
    assert.match(failed, /Could not load: HTTP 500/);
    assert.doesNotMatch(failed, /disabled/);
    assert.match(panel({connected: false, state: {info: null, loading: false, error: null}}), /Not connected/);
});

test('the panel shows no absolute path or host name', () => {
    assert.doesNotMatch(panel(), /[A-Za-z]:\\|\/home\/|\/Users\//);
});

test('a run is awaiting models until the shown answer lists some for it, and never while an answer loads', () => {
    const run = {key: 'posthoc:new', mode: 'posthoc', pipelineId: 'new'} as RunTimingSnapshot;
    const listed = {...INFO, runs: [...INFO.runs, {mode: 'posthoc', pipeline_id: 'new', requested_provider: null,
        models: INFO.runs[0].models}]} as SystemInformation;
    assert.equal(runAwaitingModels({info: INFO, loading: false, error: null}, run), 'posthoc:new');
    assert.equal(runAwaitingModels({info: INFO, loading: true, error: null}, run), null);
    assert.equal(runAwaitingModels({info: null, loading: false, error: 'HTTP 500'}, run), null);
    assert.equal(runAwaitingModels({info: listed, loading: false, error: null}, run), null);
    assert.equal(runAwaitingModels({info: INFO, loading: false, error: null}, null), null);
});
