// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import type {Certification} from '@freemocap/client';
import {
    appLocked, checkText, downloadRows, durationText, estimateLine, finishedText, FULL_BENCHMARK_TEXT, fullBenchmarkLocks, fullResultLines, fullRowName,
    fullRowStatus, invitationText, requestFullBenchmark, requestFullBenchmarkPlan,
} from './full-benchmark';
import type {PackagePlan} from './start-check';

const TRACKER: PackagePlan = {package: 'skellytracker', seconds_estimate: 333, total: 38, risks: [], system_changes: [], checks: ['dml@1-0'],
    downloads: [{name: 'test-video.mp4', bytes: 12_340_000, source: 'https://media.example.org/v/test-video.mp4', sha256: 'ab'},
        {name: 'frames.zip', bytes: 660_000}]};
const OWN: PackagePlan = {package: 'freemocap', seconds_estimate: 0, total: 0, risks: [], downloads: [], system_changes: [], checks: []};

test('the consent step shows each download with its source host and size, the total, and each package\'s estimate', () => {
    assert.deepEqual(downloadRows([TRACKER, OWN]), {rows: [
        {name: 'test-video.mp4', source: 'media.example.org', size: '12.3 MB'},
        {name: 'frames.zip', source: FULL_BENCHMARK_TEXT.sourceNotGiven, size: '0.7 MB'}], total: '13.0 MB'});
    assert.deepEqual(downloadRows([{...TRACKER, downloads: []}, OWN]).rows, [], 'no rows: the step says "Nothing is downloaded."');
    assert.deepEqual([TRACKER, OWN].map(estimateLine), ['skellytracker: 38 checks, about 6 minutes', 'freemocap: nothing to check']);
    assert.equal(durationText(45), '45 seconds');
});

test('the invitation names the total of the plans\' estimates, not a fixed span', () => {
    assert.equal(invitationText([TRACKER, OWN]),
        "If you have the time (about 6 minutes), we'd really appreciate the results from a full benchmark run on your system.");
    assert.equal(invitationText(), "If you have the time, we'd really appreciate the results from a full benchmark run on your system.");
    assert.ok(Object.values(FULL_BENCHMARK_TEXT).every(text => !/machine/i.test(text)), '"system", never "machine"');
});

test('the progress has one row per EP and GPU with its state, and a count of finished checks with no percentage', () => {
    const items = [{execution_provider: 'dml', label: 'DirectML', device_key: 'gpu:1:2:0', device_name: 'GPU A', certified: false, usable: true}];
    assert.equal(fullRowName({name: 'dml@1-2-0', package: 'skellytracker', execution_provider: 'dml', device_key: 'gpu:1:2:0', state: 'running'}, items),
        'DirectML on GPU A');
    assert.equal(fullRowName({name: 'cpu', package: 'skellytracker', execution_provider: 'cpu', state: 'waiting'}), 'CPU');
    assert.equal(fullRowName({name: 'freemocap', package: 'freemocap', state: 'waiting'}), 'freemocap');
    assert.deepEqual(['waiting', 'running'].map(state => fullRowStatus({name: 'x', package: 'p', state}).kind), ['waiting', 'running']);
    assert.deepEqual(fullRowStatus({name: 'cpu', package: 'p', state: 'partly-done'}), {kind: 'waiting', text: 'Partly done'});
    assert.deepEqual(['pass', 'fail', 'not-run'].map(result => fullRowStatus({name: 'x', package: 'p', state: 'done', result}).text),
        ['Passed', 'Failed', 'Not run']);
    assert.equal(finishedText({level: 'full', items: [], state: 'running', done: 1, rows: []}), '1 check finished');
});

test('a running full benchmark locks the app until a cancel is asked; how it ended is one line per package', () => {
    const base = {host: {name: 'h', os: 'o'}, items: [], gpu_held_by: [], pending_reports: []} as Certification;
    const run = {level: 'full', items: [], state: 'running', done: 0};
    assert.equal(fullBenchmarkLocks({...base, run}), true);
    assert.equal(fullBenchmarkLocks({...base, run: {...run, state: 'cancelling'}}), false);
    assert.equal(fullBenchmarkLocks({...base, run: {...run, level: 'quick'}}), false);
    assert.equal(fullBenchmarkLocks(null), false);
    // The one gate of the inert layer, the keyboard shortcuts and the native menu's actions (Shift+Space, Connect).
    assert.deepEqual([{...base, run}, {...base, start_required: true}, {...base, run: {...run, state: 'cancelling'}}, {...base}, null]
        .map(appLocked), [true, true, false, false, false]);
    assert.deepEqual(fullResultLines([{package: 'skellytracker', result: 'pass'}, {package: 'skellytracker', result: 'not-run', reason: 'cancelled'},
        {package: 'skellytracker', result: 'fail', reason: 'crashed'}, {result: 'crashed', reason: 'exit-code-3'}]).map(line => line.text),
    ['skellytracker: finished', 'skellytracker: cancelled', 'skellytracker: stopped unexpectedly', 'Full benchmark: stopped unexpectedly']);
});

test('the full benchmark\'s requests: the plan, a start with the clean-up choice, and the server\'s one-sentence refusal', async () => {
    const sent: unknown[] = [];
    const answer = (response: Response) => (async (input: RequestInfo | URL, init?: RequestInit) => {
        const request = input instanceof Request ? input : new Request(String(input), init);
        sent.push(`${request.method} ${new URL(request.url).pathname}`, request.method === 'POST' ? await request.json() : null);
        return response;
    }) as typeof fetch;
    assert.deepEqual(await requestFullBenchmarkPlan('http://server.invalid', undefined, answer(Response.json({packages: [OWN]}))), [OWN]);
    assert.equal(await requestFullBenchmark('http://server.invalid', true, answer(Response.json({}, {status: 202}))), null);
    const sentence = 'The full benchmark can start once the start check has passed on this system.';
    assert.equal(await requestFullBenchmark('http://server.invalid', false,
        answer(Response.json({detail: {code: 'start-check-not-passed', message: sentence}}, {status: 409}))), sentence);
    assert.deepEqual(sent, ['GET /freemocap/certify/full_benchmark/plan', null, 'POST /freemocap/certify/full_benchmark', {remove_data: true},
        'POST /freemocap/certify/full_benchmark', {remove_data: false}]);
});

test('freemocap\'s check names and the reason codes of its benchmark read as words; other names show as sent', () => {
    const items = [{execution_provider: 'dml', label: 'DirectML', device_key: 'gpu:1:2:0', device_name: 'GPU A', certified: false, usable: true}];
    const rows = [{name: 'posthoc:dml@1-2-0', package: 'freemocap', execution_provider: 'dml', device_key: 'gpu:1:2:0', state: 'done', result: 'fail'}];
    assert.deepEqual(['recording', 'data-folder', 'blender', 'posthoc:cpu', 'posthoc:dml@1-2-0'].map(name => checkText(name, items, rows)), [
        'sample recording download and preparation', 'data folder write access', 'Blender export', 'post-hoc processing on CPU',
        'post-hoc processing on DirectML on GPU A']);
    assert.equal(checkText('posthoc:dml@1-2-0'), 'post-hoc processing on dml@1-2-0', 'after a restart the server has no rows');
    assert.deepEqual(['bad-hash', 'recording-missing', 'ep-not-passed', 'not-installed', 'cancelled', 'interrupted', 'reason-lost',
        'dml@1-2-0:video'].map(code => checkText(code)), [
        'the sample recording is not the expected file, so it was not used', 'the sample recording was not ready, so it did not run',
        'its execution provider did not pass its checks on this system in this run', 'it is not installed on this system',
        'it was cancelled before it ended', 'the run was interrupted before it ended',
        'it ended before the run was interrupted, and its reason was not kept', 'dml@1-2-0:video']);
    assert.deepEqual([{name: 'recording', package: 'freemocap', state: 'done'}, {name: 'blender', package: 'freemocap', state: 'waiting'},
        ...rows].map(row => fullRowName(row, items)), ['Sample recording download and preparation', 'Blender export', 'DirectML on GPU A']);
    assert.deepEqual(fullResultLines([{package: 'freemocap', result: 'fail', reason: 'posthoc:dml@1-2-0'},
        {package: 'freemocap', result: 'fail', reason: 'recording'}], items, rows).map(line => line.text), [
        'freemocap: finished with failed checks: post-hoc processing on DirectML on GPU A',
        'freemocap: finished with failed checks: sample recording download and preparation']);
});
