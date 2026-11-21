// Bundled by tools/test-sdk-integration.mjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import {Provider} from 'react-redux';
import {configureStore} from '@reduxjs/toolkit';
import '@/store';  // the store's modules load before the section's imports of them
import {FullBenchmarkConsent, FullBenchmarkSection} from './FullBenchmarkSection';
import {FULL_BENCHMARK_TEXT} from '@/services/server/full-benchmark';

const PLAN = {package: 'skellytracker', seconds_estimate: 333, total: 38, risks: [], system_changes: [], checks: [],
    downloads: [{name: 'test-video.mp4', bytes: 12_340_000, source: 'https://media.example.org/v.mp4'}]};
const consent = (plans: typeof PLAN[], removeData = true) => renderToStaticMarkup(<FullBenchmarkConsent plans={plans}
    removeData={removeData} onRemoveData={() => {}} onStart={() => {}} onCancel={() => {}}/>);
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

test('the consent step shows the plan\'s downloads, total and estimate, and the clean-up box is on by default', () => {
    const html = consent([PLAN]);
    assert.match(text(html), /test-video\.mp4 media\.example\.org 12\.3 MB Total 12\.3 MB/);
    assert.match(text(html), /skellytracker: 38 checks, about 6 minutes/);
    const box = html.match(/<label[^>]*>.*?Remove benchmark data after a successful run.*?<\/label>/s)?.[0] ?? '';
    assert.ok(/<input[^>]*checked=""/.test(box), box);
    assert.ok(!/disabled/.test(html), 'Start, Cancel and the box are never disabled');
    assert.match(text(html), new RegExp(`${FULL_BENCHMARK_TEXT.start} ${FULL_BENCHMARK_TEXT.cancel}`));
});

test('with nothing to download the consent step says so', () => {
    assert.match(text(consent([{...PLAN, downloads: []}])), /Nothing is downloaded\./);
    assert.ok(!/checked=""/.test(consent([PLAN], false)), 'the box shows the choice it is given');
});

test('the "Full benchmark" button keeps its label and is never disabled, also while a full benchmark runs', () => {
    for (const run of [undefined, {level: 'full', items: [], state: 'running', done: 2, package: 'skellytracker',
        rows: [{name: 'cpu', package: 'skellytracker', execution_provider: 'cpu', state: 'running'}]}]) {
        const certification = {host: {name: 'h', os: 'o'}, items: [], gpu_held_by: [], pending_reports: [], run,
            full_results: [{package: 'skellytracker', result: 'fail', reason: 'start-check-not-passed'}]};
        const store = configureStore({reducer: () => ({connection: {isConnected: false, serverPid: null, certification}})});
        const html = renderToStaticMarkup(<Provider store={store}><FullBenchmarkSection/></Provider>);
        assert.match(html, />Full benchmark<\/p>/);
        assert.ok(!/disabled/.test(html), html);
        if (run) assert.match(text(html), /CPU Running Cancel check 2 checks finished/);
    }
});

test('after a full benchmark ends its rows stay with how each ended, from the server, with no Cancel check', () => {
    const certification = {host: {name: 'h', os: 'o'}, items: [], gpu_held_by: [], pending_reports: [],
        full_results: [{package: 'skellytracker', result: 'not-run', reason: 'cancelled'}],
        full_rows: [{name: 'cpu', package: 'skellytracker', execution_provider: 'cpu', state: 'done', result: 'pass'}]};
    const store = configureStore({reducer: () => ({connection: {isConnected: false, serverPid: null, certification}})});
    const html = text(renderToStaticMarkup(<Provider store={store}><FullBenchmarkSection/></Provider>));
    assert.match(html, /CPU Passed skellytracker: cancelled/);
    assert.ok(!/Cancel check/.test(html), html);
});

test('the rows of one pair stay apart: each package\'s rows come under its name', () => {
    const run = {level: 'full', items: [], state: 'running', done: 3, package: 'freemocap', rows: [
        {name: 'cpu', package: 'skellytracker', execution_provider: 'cpu', state: 'done', result: 'pass'},
        {name: 'posthoc:cpu', package: 'freemocap', execution_provider: 'cpu', state: 'running'},
        {name: 'blender', package: 'freemocap', state: 'waiting'}]};
    const certification = {host: {name: 'h', os: 'o'}, items: [], gpu_held_by: [], pending_reports: [], run};
    const store = configureStore({reducer: () => ({connection: {isConnected: false, serverPid: null, certification}})});
    const html = renderToStaticMarkup(<Provider store={store}><FullBenchmarkSection/></Provider>);
    assert.match(text(html), /skellytracker CPU Passed freemocap CPU Running /);
    assert.equal(html.match(/<th /g)?.length, 2, 'one heading per package');
});
