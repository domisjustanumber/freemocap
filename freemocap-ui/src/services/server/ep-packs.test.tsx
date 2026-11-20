// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import {EP_PACK_TEXT, packControls, packProgressText, packResultText, requestEpPack, requestEpPackCancel} from './ep-packs';

const row = (source: string, state: string) => ({key: 'amdgpu', label: 'AMD GPU', description: 'Runs on an AMD GPU.', usable: false,
    install_hint: null, uses_gpu: true, devices: [], checks: [], source, state});

test('the controls are only for a Windows ML EP that a GPU here runs and that is offered; install only adds a missing one', () => {
    assert.deepEqual(packControls(row('windows-ml', 'not_installed')), {install: true});
    assert.deepEqual(packControls(row('windows-ml', 'ready')), {install: false});
    assert.deepEqual(packControls(row('windows-ml', 'not_ready')), {install: false});
    assert.equal(packControls(row('windows-ml', 'unsupported')), null);
    assert.equal(packControls(row('windows-ml', 'field_test')), null);
    assert.equal(packControls(row('azure', 'not_installed')), null);
    assert.equal(packControls(row('builtin', 'builtin')), null);
    const {source: _source, state: _state, ...older} = row('windows-ml', 'not_installed');
    assert.equal(packControls(older), null);
});

test('progress and results say what the server says, with "machine" for the computer', () => {
    assert.equal(packProgressText({action: 'install', execution_provider: 'amdgpu'}, 'AMD GPU'), 'Installing AMD GPU: starting');
    assert.equal(packProgressText({action: 'install', execution_provider: 'amdgpu', phase: 'download', fraction: 0.256}, 'AMD GPU'),
        'Installing AMD GPU: 26%');
    assert.equal(packProgressText({action: 'remove', execution_provider: 'amdgpu'}, 'AMD GPU'), 'Removing AMD GPU…');
    const result = (action: string, outcome: string, reason?: string, message?: string) =>
        packResultText({action, execution_provider: 'amdgpu', result: outcome, reason, message}, 'AMD GPU');
    assert.equal(result('install', 'done'), 'AMD GPU installed');
    assert.equal(result('install', 'cancelled'), 'Install of AMD GPU cancelled. Remove takes away anything it added.');
    assert.equal(result('install', 'failed', 'failed', 'The Windows ML package did not install'),
        'Install of AMD GPU failed: The Windows ML package did not install');
    assert.equal(result('install', 'error', 'OSError'), 'Install of AMD GPU could not run: OSError');
    assert.equal(result('remove', 'done'), 'AMD GPU removed');
    assert.equal(result('remove', 'done', 'was-present'),
        'AMD GPU removed from this app; its package was on this machine before and stays');
    assert.equal(result('remove', 'failed', 'no-record'), 'Nothing to remove: no install of AMD GPU by this app is recorded');
    assert.equal(result('remove', 'failed', 'package-not-removed'), 'Remove of AMD GPU failed: package-not-removed');
    const every = [EP_PACK_TEXT.confirmRemove('AMD GPU'), result('remove', 'done', 'was-present')].join(' ');
    assert.ok(!/\bPC\b|\bdevice\b/.test(every));
    assert.ok(renderToStaticMarkup(<p>{EP_PACK_TEXT.confirmRemove('AMD GPU')}</p>).includes('Remove AMD GPU?'));
});

test('a start posts to its route and gives the server reason of a refusal; cancel deletes', async () => {
    const calls: {url: string; method: string; body: unknown}[] = [];
    const answers = [new Response(JSON.stringify({action: 'install', execution_provider: 'amdgpu', phase: null, fraction: null}), {status: 202}),
        new Response(JSON.stringify({detail: {code: 'pipelines-running', message: 'The remove of amdgpu cannot start while other work runs.'}}),
            {status: 409}),
        new Response(JSON.stringify({run: null}), {status: 200})];
    const request = (async (input: RequestInfo | URL, init?: RequestInit) => {
        const call = input instanceof Request ? input : new Request(input, init);
        calls.push({url: call.url, method: call.method, body: call.method === 'DELETE' ? null : await call.json()});
        return answers.shift() as Response;
    }) as typeof fetch;
    assert.equal(await requestEpPack('http://server', 'install', 'amdgpu', request), null);
    assert.equal(await requestEpPack('http://server', 'remove', 'amdgpu', request), 'The remove of amdgpu cannot start while other work runs.');
    await requestEpPackCancel('http://server', request);
    assert.deepEqual(calls, [
        {url: 'http://server/freemocap/certify/ep_pack/install', method: 'POST', body: {execution_provider: 'amdgpu'}},
        {url: 'http://server/freemocap/certify/ep_pack/remove', method: 'POST', body: {execution_provider: 'amdgpu'}},
        {url: 'http://server/freemocap/certify/ep_pack', method: 'DELETE', body: null}]);
});
