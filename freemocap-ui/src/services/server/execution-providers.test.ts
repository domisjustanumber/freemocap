// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {requestExecutionProviders, executionProviderOptions} from './execution-providers';

const CPU = {key: 'cpu', label: 'CPU'};
const GPU = {key: 'gpu-ep', label: 'GPU EP'};

test('the options are Auto and the server rows in their order, with their labels', () => {
    assert.deepEqual(executionProviderOptions(null, []), [{label: 'Auto', value: null}]);
    assert.deepEqual(executionProviderOptions(null, [GPU, CPU]),
        [{label: 'Auto', value: null}, {label: 'GPU EP', value: 'gpu-ep'}, {label: 'CPU', value: 'cpu'}]);
});

test('a saved key that the server does not list stays visible as itself', () => {
    assert.deepEqual(executionProviderOptions('old-ep', [CPU]).map(option => option.value), [null, 'cpu', 'old-ep']);
    assert.deepEqual(executionProviderOptions('cpu', [CPU]).map(option => option.value), [null, 'cpu']);
});

test('reconnected or different servers are queried again and preserve abort signals', async () => {
    const calls: string[] = [];
    const controller = new AbortController();
    const request = (async (url, options) => {
        calls.push(String(url));
        assert.equal(options?.signal, controller.signal);
        return Response.json({available: calls.length === 1 ? [GPU, CPU] : [CPU]});
    }) as typeof fetch;
    assert.deepEqual(await requestExecutionProviders('http://first.invalid', controller.signal, request), [GPU, CPU]);
    assert.deepEqual(await requestExecutionProviders('http://second.invalid', controller.signal, request), [CPU]);
    assert.deepEqual(calls, ['http://first.invalid/freemocap/onnx/execution_providers', 'http://second.invalid/freemocap/onnx/execution_providers']);
});

test('HTTP failures and malformed provider lists are not advertised as support', async () => {
    for (const response of [new Response('', {status: 503}), Response.json({available: ['cpu']}),
        Response.json({available: [{key: 'cpu'}]}), Response.json({})]) {
        await assert.rejects(requestExecutionProviders('http://providers.invalid', undefined, (async () => response) as typeof fetch));
    }
});
