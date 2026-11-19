// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {detectorShowsExecutionProvider, requestExecutionProviders, executionProviderOptions, offeredDevices, requestExecutionProviderSuggestion} from './execution-providers';
import {executionProviderInfo} from '@/components/mocap-setup/execution-provider-info';
import {renderToStaticMarkup} from 'react-dom/server';

const CPU = {key: 'cpu', label: 'CPU', description: 'Runs on the processor.', usable: true, install_hint: null, uses_gpu: false, devices: [], checks: []};
const GPU = {key: 'gpu-ep', label: 'GPU EP', description: 'Runs on a GPU.', usable: true, install_hint: null, uses_gpu: true,
    devices: [{key: 'gpu:0', name: 'Some GPU', vram_total_bytes: 8 * 2 ** 30}],
    checks: [{device_key: 'gpu:0', certified: true, local_result: null, usable: true, local_cause: null}]};
const PACK = {key: 'pack-ep', label: 'Pack EP', description: 'Needs a pack.', usable: false,
    install_hint: 'Run `install pack-ep`.', uses_gpu: true, devices: [], checks: []};
const TAKES = {rtmpose: true, mediapipe: false};
const OFFER = {kind: 'add-pack', ep_key: 'pack-ep', download_bytes: 110_000_000, disk_bytes: 286_000_000,
    licence_url: null, note: 'Run `install pack-ep`.'};
const answer = (providers: unknown[], auto_offers: unknown[] = [OFFER]) => ({providers, detector_takes_execution_provider: TAKES, auto_offers});

test('the options are Auto and the usable server rows in their order, with their labels', () => {
    assert.deepEqual(executionProviderOptions(null, []), [{label: 'Auto', value: null}]);
    assert.deepEqual(executionProviderOptions(null, [GPU, PACK, CPU]),
        [{label: 'Auto', value: null}, {label: 'GPU EP', value: 'gpu-ep'}, {label: 'CPU', value: 'cpu'}]);
});

// skellytracker's per-GPU checks (decision 17): a pair is offered only when its check is usable.
const TWO = [{key: 'gpu:0', name: 'First GPU', vram_total_bytes: 8 * 2 ** 30}, {key: 'gpu:1', name: 'Second GPU', vram_total_bytes: 4 * 2 ** 30}];
const pair = (local_result: 'passed' | 'failed' | null, certified: boolean, usable: boolean, device_key = 'gpu:0') =>
    ({device_key, certified, local_result, usable, local_cause: null});
const ep = (checks: ReturnType<typeof pair>[]) => ({...GPU, devices: TWO.slice(0, checks.length), checks});

test('an EP and GPU pair is offered from its own check, not from the EP-wide flag', () => {
    const offered = (provider: ReturnType<typeof ep>) => [executionProviderOptions(null, [provider, CPU]).map(option => option.value),
        offeredDevices(provider).map(({key}) => key)];
    assert.deepEqual(offered(ep([pair(null, true, true)])), [[null, 'gpu-ep', 'cpu'], ['gpu:0']], 'certified');
    assert.deepEqual(offered(ep([pair('passed', false, true)])), [[null, 'gpu-ep', 'cpu'], ['gpu:0']], 'passed here, not reviewed');
    assert.deepEqual(offered(ep([pair(null, false, false)])), [[null, 'cpu'], []], 'not reviewed, not checked here');
    assert.deepEqual(offered(ep([pair('failed', true, false)])), [[null, 'cpu'], []], 'a local failure on a reviewed pair');
    assert.deepEqual(offered(ep([pair(null, false, false), pair('passed', false, true, 'gpu:1')])), [[null, 'gpu-ep', 'cpu'], ['gpu:1']],
        'two GPUs, only the second usable');
    assert.deepEqual(offered({...CPU, key: 'no-check-ep'}), [[null, 'no-check-ep', 'cpu'], []], 'no device checks: the EP flag');
    assert.deepEqual(offeredDevices({...GPU, checks: []}).map(({key}) => key), ['gpu:0'], 'no device checks: the devices as given');
});

test('a saved EP that is no longer usable on any GPU stays visible as itself, with the same label', () => {
    assert.deepEqual(executionProviderOptions('gpu-ep', [ep([pair('failed', true, false)]), CPU]),
        [{label: 'Auto', value: null}, {label: 'CPU', value: 'cpu'}, {label: 'GPU EP', value: 'gpu-ep'}]);
});

test('the explanation marks a pair that passed here and has no reviewed row, and an EP offered on no GPU as not usable', () => {
    const text = (providers: ReturnType<typeof ep>[]) => renderToStaticMarkup(executionProviderInfo(providers).text)
        .replace(/<[^>]+>/g, '').replace(/\s+/g, ' ');
    assert.match(text([ep([pair(null, true, true), pair('passed', false, true, 'gpu:1')])]),
        /Runs on a GPU\. Second GPU: passed on this device, not yet reviewed\./);
    assert.doesNotMatch(text([ep([pair(null, true, true)])]), /passed on this device|Not usable/);
    assert.match(text([ep([pair('failed', true, false)])]), /Runs on a GPU\. Not usable here\./);
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

test('a local failure from two unclean exits keeps its cause', async () => {
    const failed = {...GPU, checks: [{device_key: 'gpu:0', certified: true, local_result: 'failed', usable: false, local_cause: 'unclean-exits'}]};
    assert.deepEqual((await requestExecutionProviders('http://providers.invalid', undefined,
        (async () => Response.json(answer([failed, CPU]))) as typeof fetch)).providers, [failed, CPU]);
});

test('HTTP failures and malformed provider lists are not advertised as support', async () => {
    for (const response of [new Response('', {status: 503}), Response.json({available: [CPU]}),
        Response.json(answer([{key: 'cpu', label: 'CPU'}])), Response.json({providers: [CPU]}),
        Response.json(answer([{...GPU, devices: [{key: 'gpu:0'}]}])), Response.json(answer([{...GPU, checks: undefined}])),
        Response.json(answer([{...GPU, checks: [{device_key: 'gpu:0', certified: true, local_result: 'unknown', usable: true, local_cause: null}]}])),
        Response.json(answer([{...GPU, checks: [{device_key: 'gpu:0', certified: true, local_result: 'failed', usable: false, local_cause: 'crash'}]}])),
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
