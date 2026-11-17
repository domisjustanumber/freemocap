// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {detectorShowsExecutionProvider, requestExecutionProviders, executionProviderOptions, requestExecutionProviderSuggestion} from './execution-providers';

const CPU = {key: 'cpu', label: 'CPU', description: 'Runs on the processor.', usable: true, install_hint: null, uses_gpu: false, devices: []};
const GPU = {key: 'gpu-ep', label: 'GPU EP', description: 'Runs on a GPU.', usable: true, install_hint: null, uses_gpu: true,
    devices: [{key: 'gpu:0', name: 'Some GPU', vram_total_bytes: 8 * 2 ** 30}]};
const PACK = {key: 'pack-ep', label: 'Pack EP', description: 'Needs a pack.', usable: false,
    install_hint: 'Run `install pack-ep`.', uses_gpu: true, devices: []};
const TAKES = {rtmpose: true, mediapipe: false};
const OFFER = {kind: 'add-pack', ep_key: 'pack-ep', download_bytes: 110_000_000, disk_bytes: 286_000_000,
    licence_url: null, note: 'Run `install pack-ep`.'};
const answer = (providers: unknown[], auto_offers: unknown[] = [OFFER]) => ({providers, detector_takes_execution_provider: TAKES, auto_offers});

test('the options are Auto and the usable server rows in their order, with their labels', () => {
    assert.deepEqual(executionProviderOptions(null, []), [{label: 'Auto', value: null}]);
    assert.deepEqual(executionProviderOptions(null, [GPU, PACK, CPU]),
        [{label: 'Auto', value: null}, {label: 'GPU EP', value: 'gpu-ep'}, {label: 'CPU', value: 'cpu'}]);
});

test('before the server answers RTMW shows the provider row with Auto and the saved key; then the server decides', () => {
    assert.equal(detectorShowsExecutionProvider(null, 'rtmpose'), true);
    assert.equal(detectorShowsExecutionProvider(null, 'mediapipe'), false);
    assert.deepEqual(executionProviderOptions('saved-ep', []), [{label: 'Auto', value: null}, {label: 'saved-ep', value: 'saved-ep'}]);
    assert.equal(detectorShowsExecutionProvider({rtmpose: false, mediapipe: true}, 'rtmpose'), false, 'the answer decides');
    assert.equal(detectorShowsExecutionProvider({rtmpose: true, mediapipe: true}, 'mediapipe'), true);
    assert.equal(detectorShowsExecutionProvider({}, 'rtmpose'), false, 'a detector the answer does not list');
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
        {providers: [GPU, CPU], detectorTakesExecutionProvider: TAKES, autoOffers: [OFFER]});
    assert.deepEqual((await requestExecutionProviders('http://second.invalid', controller.signal, request)).providers, [CPU]);
    assert.deepEqual(calls, ['http://first.invalid/freemocap/onnx/execution_providers', 'http://second.invalid/freemocap/onnx/execution_providers']);
});

test('HTTP failures and malformed provider lists are not advertised as support', async () => {
    for (const response of [new Response('', {status: 503}), Response.json({available: [CPU]}),
        Response.json(answer([{key: 'cpu', label: 'CPU'}])), Response.json({providers: [CPU]}),
        Response.json(answer([{...GPU, devices: [{key: 'gpu:0'}]}])),
        Response.json({providers: [CPU], detector_takes_execution_provider: TAKES}), Response.json(answer([CPU], [{kind: 'add-pack'}])), Response.json(answer([CPU], [{...OFFER, note: null}]))]) {
        await assert.rejects(requestExecutionProviders('http://providers.invalid', undefined, (async () => response) as typeof fetch));
    }
});

test('the suggestion for a legacy key is asked with the saved key and is a key or null (Auto)', async () => {
    const calls: string[] = [];
    for (const suggested of ['new-ep', null]) {
        const request = (async url => {
            calls.push(String(url));
            return Response.json({saved: 'old-ep', suggested});
        }) as typeof fetch;
        assert.equal(await requestExecutionProviderSuggestion('http://server.invalid', 'old-ep', undefined, request), suggested);
    }
    assert.deepEqual(calls, Array(2).fill('http://server.invalid/freemocap/onnx/execution_providers/suggestion?saved=old-ep'));
    for (const response of [new Response('', {status: 503}), Response.json({saved: 'other', suggested: null}),
        Response.json({saved: 'old-ep', suggested: 3})]) {
        await assert.rejects(requestExecutionProviderSuggestion('http://server.invalid', 'old-ep', undefined, (async () => response) as typeof fetch));
    }
});
