// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {quickCheckProgressText} from './execution-providers';
import {planLines, requestStartCheck, requestStartCheckPlan, START_CHECK_TEXT, startCheckRowStatus, startResultLines} from './start-check';

test('each package\'s plan is one line with its checks, estimate, downloads and changes', () => {
    assert.deepEqual(planLines([
        {package: 'freemocap', seconds_estimate: 30, total: 2, risks: [], downloads: [], system_changes: [], checks: ['a', 'b']},
        {package: 'skellytracker', seconds_estimate: 75, total: 6, risks: [], downloads: [{name: 'x.whl', bytes: 1_500_000}], system_changes: ['Installs X.'], checks: ['ep@1']},
        {package: 'skellytracker', seconds_estimate: 0, total: 0, risks: [], downloads: [], system_changes: [], checks: []},
    ]), ['freemocap: 2 checks, up to about 30 seconds', 'skellytracker: 6 checks, up to about 75 seconds, downloads about 2 MB, Installs X.',
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
        seconds_estimate: 120}), 'Quick check of this system (freemocap): 2 of 6 checks done, up to about 120 seconds.');
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

test("each package's status cell follows the current run, else how its part of the last start check ended", () => {
    const packages = ['freemocap', 'skellytracker'];
    const run = {level: 'quick', items: [], state: 'running', done: 1, total: 4};
    assert.deepEqual(startCheckRowStatus(packages, undefined, []).map(row => row.text), ['Waiting', 'Waiting']);
    assert.deepEqual(startCheckRowStatus(packages, undefined, [], false).map(row => row.text), ['Not run in this session', 'Not run in this session']);
    assert.deepEqual(startCheckRowStatus(packages, {...run, total: undefined}, []).map(row => row.text), ['Starting', 'Waiting']);
    assert.deepEqual(startCheckRowStatus(packages, {...run, package: 'skellytracker'}, [{package: 'freemocap', result: 'pass'}])
        .map(row => [row.kind, row.text]), [['done', 'Done'], ['running', 'Running, 1 of 4']]);
    assert.deepEqual(startCheckRowStatus(packages, undefined, [{package: 'freemocap', result: 'record-only'},
        {package: 'skellytracker', result: 'fail', reason: 'dml@x-0'}]).map(row => [row.kind, row.text]),
    [['passed', 'Passed'], ['failed', 'Failed: dml@x-0']]);
    assert.deepEqual(startCheckRowStatus(packages, undefined, [{package: 'freemocap', result: 'not-run', reason: 'no-check'},
        {package: 'skellytracker', result: 'not-run', reason: 'cancelled'}]).map(row => row.text), ['Nothing to check', 'Cancelled']);
    assert.deepEqual(startCheckRowStatus(packages, undefined, [{package: 'freemocap', result: 'not-run', reason: 'over-budget'},
        {package: 'skellytracker', result: 'not-run', reason: 'models-missing'}]).map(row => row.text),
    ['Not run: it did not fit in the time the quick check allows', 'Not run: a model file it needs is not on this system']);
    assert.deepEqual(startCheckRowStatus(packages, undefined, [{package: 'freemocap', result: 'pass'}, {result: 'crashed', reason: 'exit-code-3'}])
        .map(row => row.kind), ['passed', 'failed']);
    // An EP pair's quick check (a run with items) is not the start check: the rows keep the last start check's results.
    assert.deepEqual(startCheckRowStatus(packages, {...run, items: [{execution_provider: 'dml'}]}, []).map(row => row.text), ['Waiting', 'Waiting']);
    assert.ok(Object.values(START_CHECK_TEXT).every(text => !/machine/.test(text)), 'this dialog says "system"');
});
