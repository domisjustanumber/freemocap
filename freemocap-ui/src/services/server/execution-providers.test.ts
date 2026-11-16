// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {requestExecutionProviders, executionProviderOptions} from './execution-providers';

const CPU = {key: 'cpu', label: 'CPU', description: 'Runs on the processor.', usable: true, install_hint: null, uses_gpu: false, devices: []};
const GPU = {key: 'gpu-ep', label: 'GPU EP', description: 'Runs on a GPU.', usable: true, install_hint: null, uses_gpu: true,
    devices: [{key: 'gpu:0', name: 'Some GPU', vram_total_bytes: 8 * 2 ** 30}]};
const PACK = {key: 'pack-ep', label: 'Pack EP', description: 'Needs a pack.', usable: false,
    install_hint: 'Run `install pack-ep`.', uses_gpu: true, devices: []};
const TAKES = {rtmpose: true, mediapipe: false};
const answer = (providers: unknown[]) => ({providers, detector_takes_execution_provider: TAKES});

test('the options are Auto and the usable server rows in their order, with their labels', () => {
    assert.deepEqual(executionProviderOptions(null, []), [{label: 'Auto', value: null}]);
    assert.deepEqual(executionProviderOptions(null, [GPU, PACK, CPU]),
        [{label: 'Auto', value: null}, {label: 'GPU EP', value: 'gpu-ep'}, {label: 'CPU', value: 'cpu'}]);
});

test('a saved key that is not offered stays visible, with its label when the server lists it', () => {
    assert.deepEqual(executionProviderOptions('old-ep', [CPU]).map(option => option.value), [null, 'cpu', 'old-ep']);
    assert.deepEqual(executionProviderOptions('pack-ep', [CPU, PACK]).at(-1), {label: 'Pack EP', value: 'pack-ep'});
    assert.deepEqual(executionProviderOptions('cpu', [CPU]).map(option => option.value), [null, 'cpu']);
});

test('reconnected or different servers are queried again and preserve abort signals', async () => {
    const calls: string[] = [];
    const controller = new AbortController();
    const request = (async (url, options) => {
        calls.push(String(url));
        assert.equal(options?.signal, controller.signal);
        return Response.json(answer(calls.length === 1 ? [GPU, CPU] : [CPU]));
    }) as typeof fetch;
    assert.deepEqual(await requestExecutionProviders('http://first.invalid', controller.signal, request),
        {providers: [GPU, CPU], detectorTakesExecutionProvider: TAKES});
    assert.deepEqual((await requestExecutionProviders('http://second.invalid', controller.signal, request)).providers, [CPU]);
    assert.deepEqual(calls, ['http://first.invalid/freemocap/onnx/execution_providers', 'http://second.invalid/freemocap/onnx/execution_providers']);
});

test('HTTP failures and malformed provider lists are not advertised as support', async () => {
    for (const response of [new Response('', {status: 503}), Response.json({available: [CPU]}),
        Response.json(answer([{key: 'cpu', label: 'CPU'}])), Response.json({providers: [CPU]}),
        Response.json(answer([{...GPU, devices: [{key: 'gpu:0'}]}]))]) {
        await assert.rejects(requestExecutionProviders('http://providers.invalid', undefined, (async () => response) as typeof fetch));
    }
});
