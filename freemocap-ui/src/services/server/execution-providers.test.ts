// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {
    checkIntentOutcome, detectorShowsExecutionProvider, executionProviderOptions, menuPairs, offeredDevices, PAIR_MARKERS, pairState, pairToCheck,
    quickCheckProgressText, quickCheckResultText, requestExecutionProviders, requestExecutionProviderSuggestion, requestQuickCheck, requestQuickCheckCancel,
} from './execution-providers';
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
        /Runs on a GPU\. Second GPU: passed on this machine, not yet reviewed\./);
    assert.doesNotMatch(text([ep([pair(null, true, true)])]), /passed on this machine|Not usable/);
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

// ── The uncertified-EP flow (F15 step 2) ────────────────────────────────────────────────────────────────────────────
type Item = Parameters<typeof menuPairs>[1] extends readonly (infer T)[] | undefined ? T : never;
const item = (device_key: string, facts: Partial<Item>): Item => ({execution_provider: 'gpu-ep', label: 'GPU EP', device_key,
    device_name: `${device_key} name`, certified: false, usable: false, reason_code: 'quick-check-needed', ...facts});

test('F12: five states of a pair, worded with "machine"', () => {
    assert.equal(pairState({certified: true, usable: true}), 'reviewed');
    assert.equal(pairState({certified: false, local_result: 'passed', usable: true}), 'passed-here');
    assert.equal(pairState({certified: false, usable: false}), 'not-checked');
    assert.equal(pairState({certified: true, local_result: 'failed', usable: false}), 'failed');
    assert.equal(pairState({certified: false, local_result: 'failed', local_cause: 'unclean-exits', usable: false}), 'unclean-exits');
    assert.deepEqual(Object.values(PAIR_MARKERS), ['', 'passed on this machine, not yet reviewed', 'not checked on this machine',
        'check failed on this machine', 'exited uncleanly twice']);
    assert.ok(Object.values(PAIR_MARKERS).every(marker => !/\bPC\b|device/.test(marker)));
});

test('the menu shows usable pairs and the ones a check would let run; a pair of an EP that is not ready stays hidden', () => {
    const provider = ep([pair(null, false, false), pair(null, false, false, 'gpu:1')]);
    const keys = (items: Item[]) => menuPairs(provider, items).map(({device_key, needsCheck}) => [device_key, needsCheck]);
    assert.deepEqual(keys([item('gpu:0', {}), item('gpu:1', {local_result: 'failed', reason_code: 'quick-check-failed'})]),
        [['gpu:0', true], ['gpu:1', true]]);
    assert.deepEqual(keys([item('gpu:0', {reason_code: 'ep-not-installed'}), item('gpu:1', {reason_code: 'ep-not-installed'})]), [], 'not installed');
    // The EP runs on one GPU (its row has no reason code): the other GPU waits for a check.
    assert.deepEqual(keys([item('gpu:0', {usable: true, certified: true, reason_code: undefined}), item('gpu:1', {reason_code: undefined})]),
        [['gpu:0', false], ['gpu:1', true]]);
    assert.deepEqual(keys([item('gpu:0', {}), {...item('gpu:1', {}), execution_provider: 'other-ep'}]), [['gpu:0', true]], 'only its own items');
});

test('a choice asks for the check of one pair only when it cannot run now (F1, F9)', () => {
    const provider = ep([pair(null, false, false), pair('passed', false, true, 'gpu:1')]);
    const items = [item('gpu:0', {}), item('gpu:1', {local_result: 'passed', usable: true, reason_code: undefined})];
    assert.equal(pairToCheck(provider, null, items), undefined, 'Auto device runs on the usable GPU');
    assert.equal(pairToCheck(provider, 'gpu:0', items)?.device_key, 'gpu:0');
    assert.equal(pairToCheck(provider, 'gpu:1', items), undefined);
    assert.equal(pairToCheck(provider, null, [item('gpu:0', {}), item('gpu:1', {})])?.device_key, 'gpu:0', 'none usable: the first GPU');
    assert.equal(pairToCheck(CPU, null, items), undefined, 'an EP with no GPU checks');
    assert.equal(pairToCheck(undefined, null, items), undefined, 'Auto');
    assert.deepEqual(executionProviderOptions(null, [provider, CPU], items).map(({label}) => label),
        ['Auto', 'GPU EP (passed on this machine, not yet reviewed)', 'CPU']);
});

test('the six result lines, a cancel included, from last_result', () => {
    assert.equal(quickCheckResultText({result: 'pass'}), 'Quick check passed');
    assert.equal(quickCheckResultText({result: 'fail', reason: 'probe-l3-failed'}), 'Quick check failed: probe-l3-failed');
    assert.equal(quickCheckResultText({result: 'not-run', reason: 'models-missing'}), 'Quick check did not run: models-missing');
    assert.equal(quickCheckResultText({result: 'crashed', reason: 'exit-code-3'}), 'Quick check stopped unexpectedly');
    assert.equal(quickCheckResultText({result: 'error', reason: 'ValueError'}), 'Quick check could not start: ValueError');
    assert.equal(quickCheckResultText({result: 'not-run', reason: 'cancelled'}), 'Quick check cancelled');
});

test('a started check ends from the server state only: a pass selects its choice; anything else, a restart included, does not (F6)', () => {
    const before = {execution_provider: 'gpu-ep', device_key: 'gpu:0', result: 'fail', reason: 'probe-l3-failed'};
    const intent = {pair: {execution_provider: 'gpu-ep', device_key: 'gpu:0'}, change: {provider: 'gpu-ep', device: null},
        before: JSON.stringify(before), sawRun: false};
    const state = (more: object) => ({host: {name: 'h', os: 'o'}, items: [], gpu_held_by: [], pending_reports: [], ...more});
    const run = {level: 'quick', items: [intent.pair], state: 'running', done: 1, total: 5};
    assert.equal(checkIntentOutcome(intent, state({last_result: before})), 'running', 'accepted, the state not yet sent');
    assert.equal(checkIntentOutcome(intent, state({run, last_result: before})), 'running');
    const seen = {...intent, sawRun: true};
    assert.equal(checkIntentOutcome(seen, state({last_result: before})), 'ended', 'the same ending again after a run');
    assert.equal(checkIntentOutcome(intent, state({last_result: {...intent.pair, result: 'pass'}})), 'passed');
    assert.equal(checkIntentOutcome(intent, state({last_result: {...intent.pair, result: 'not-run', reason: 'cancelled'}})), 'ended');
    assert.equal(checkIntentOutcome(intent, state({last_result: {...intent.pair, device_key: 'gpu:1', result: 'pass'}})), 'ended',
        'a pass of another pair');
    assert.equal(checkIntentOutcome(seen, state({})), 'ended', 'a restarted server with no result');
    assert.equal(checkIntentOutcome(intent, null), 'ended', 'disconnected');
});

test('progress is done of total with the one-off estimate', () => {
    const run = {level: 'quick', items: [{execution_provider: 'gpu-ep', device_key: 'gpu:0'}], state: 'running', done: 1, total: 3};
    assert.equal(quickCheckProgressText(run, [item('gpu:0', {})]), 'Quick check of GPU EP on gpu:0 name: 1 of 3 checks done.');
    assert.equal(quickCheckProgressText({...run, seconds_estimate: 45}), 'Quick check of gpu-ep on gpu:0: 1 of 3 checks done, up to about 45 seconds.');
});

test('the check start sends one pair with the detector; a refusal is the server\'s message; cancel is a DELETE', async () => {
    const requests: {url: string; method?: string; body?: unknown}[] = [];
    const answer = (response: Response) => (async (url, init) => {
        requests.push({url: String(url), method: init?.method, body: init?.body && JSON.parse(String(init.body))});
        return response;
    }) as typeof fetch;
    const pairKeys = {execution_provider: 'gpu-ep', device_key: 'gpu:0'};
    const detector = {detector_type: 'rtmpose' as const, rtmpose_model_name: 'rtmw-x-l_256x192' as const};
    assert.equal(await requestQuickCheck('http://server.invalid', pairKeys, detector, undefined,
        answer(Response.json({level: 'quick'}, {status: 202}))), null);
    assert.deepEqual(requests[0], {url: 'http://server.invalid/freemocap/certify/quick_check', method: 'POST', body: {...pairKeys, ...detector}});
    for (const [status, detail, message] of [
        [409, {code: 'pipelines-running', message: 'Something is running: cameras abc. Stop it first.', gpu_held_by: [{kind: 'cameras', id: 'abc'}]},
            'Something is running: cameras abc. Stop it first.'],
        [409, {code: 'quick-check-running', message: 'A quick check of cuda on gpu:0 is already running.'}, 'A quick check of cuda on gpu:0 is already running.'],
        [409, {code: 'cannot-run', reason_code: 'ep-not-installed', message: 'cannot run here: ep-not-installed.'}, 'cannot run here: ep-not-installed.'],
    ] as const) {
        assert.equal(await requestQuickCheck('http://server.invalid', pairKeys, detector, undefined, answer(Response.json({detail}, {status}))), message);
    }
    assert.equal(await requestQuickCheck('http://server.invalid', pairKeys, detector, undefined, answer(new Response('', {status: 502}))), 'HTTP 502');
    await requestQuickCheckCancel('http://server.invalid', answer(Response.json({run: null})));
    assert.deepEqual([requests.at(-1)?.url, requests.at(-1)?.method], ['http://server.invalid/freemocap/certify/quick_check', 'DELETE']);
});
