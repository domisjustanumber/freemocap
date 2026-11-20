// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {quickCheckProgressText} from './execution-providers';
import {planLines, requestStartCheck, requestStartCheckPlan, START_CHECK_TEXT, startResultLines} from './start-check';

test('each package\'s plan is one line with its checks, estimate, downloads and changes', () => {
    assert.deepEqual(planLines([
        {package: 'freemocap', seconds_estimate: 30, downloads: [], system_changes: [], checks: ['a', 'b']},
        {package: 'skellytracker', seconds_estimate: 90, downloads: [{name: 'x.whl', bytes: 1_500_000}], system_changes: ['Installs X.'], checks: ['ep@1']},
        {package: 'skellytracker', seconds_estimate: 0, downloads: [], system_changes: [], checks: []},
    ]), ['freemocap: 2 checks, up to about 30 seconds', 'skellytracker: 1 check, up to about 90 seconds, downloads about 2 MB, Installs X.',
        'skellytracker: nothing to check, up to about 0 seconds']);
});

test('how the start check ended uses the quick check\'s result texts, per package', () => {
    assert.deepEqual(startResultLines([
        {package: 'freemocap', result: 'pass'}, {package: 'skellytracker', result: 'fail', reason: 'dml@x-0'},
        {package: 'skellytracker', result: 'not-run', reason: 'cancelled'}, {package: 'skellytracker', result: 'not-run', reason: 'no-check'},
        {result: 'crashed', reason: 'exit-code-3'},
    ]), [{text: 'freemocap: Quick check passed', failed: false}, {text: 'skellytracker: Quick check failed: dml@x-0', failed: true},
        {text: 'skellytracker: Quick check cancelled', failed: false}, {text: 'skellytracker: nothing to check', failed: false},
        {text: 'The check: Quick check stopped unexpectedly', failed: false}]);
});

test('a start check\'s progress names this machine and the package that runs now', () => {
    assert.equal(quickCheckProgressText({level: 'quick', items: [], state: 'running', done: 2, total: 6, package: 'freemocap',
        seconds_estimate: 120}), 'Quick check of this machine (freemocap): 2 of 6 checks done, up to about 120 seconds.');
    assert.ok(Object.values(START_CHECK_TEXT).every(text => !/\bPC\b|\bdevice\b/.test(text)), 'G1: machine, never PC or device');
});

test('the start check\'s requests: the plan, an accepted start, and a refusal with the server\'s reason', async () => {
    const calls: string[] = [];
    const answer = (response: Response) => (async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push(`${init?.method ?? (input instanceof Request ? input.method : 'GET')} ${String(input instanceof Request ? input.url : input)}`);
        return response;
    }) as typeof fetch;
    assert.deepEqual(await requestStartCheckPlan('http://server.invalid', undefined, answer(Response.json({packages: []}))), []);
    assert.equal(await requestStartCheck('http://server.invalid', answer(Response.json({}, {status: 202}))), null);
    const sent: string[] = [];
    await requestStartCheck('http://server.invalid', (async (input: RequestInfo | URL, init?: RequestInit) => {
        sent.push(String(init?.body ?? (input instanceof Request ? await input.text() : '')));
        return Response.json({}, {status: 202});
    }) as typeof fetch, 'C:/Blender/blender.exe');
    assert.deepEqual(JSON.parse(sent[0]), {blenderExePath: 'C:/Blender/blender.exe'});
    assert.equal(await requestStartCheck('http://server.invalid', answer(Response.json({detail: {code: 'pipelines-running',
        message: 'A quick check cannot start while other work runs: cameras g1. Stop it first.'}}, {status: 409}))),
    'A quick check cannot start while other work runs: cameras g1. Stop it first.');
    assert.deepEqual(calls.map(call => call.replace(/^(GET|POST) /, '')), Array(3).fill(0).map((_, index) =>
        `http://server.invalid/freemocap/certify/start_check${index ? '' : '/plan'}`));
});
