// Run: node src/components/realtime-processing/run-realtime-processing-tests.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import '@/store';
import {LegacyExecutionProviderNotice} from './legacy-execution-provider-notice';

const PACK = {key: 'pack-ep', label: 'Pack EP', description: 'Needs a pack.', usable: false,
    install_hint: 'Run `install pack-ep`.', uses_gpu: true, devices: [], checks: []};
const CPU = {key: 'cpu', label: 'CPU', description: 'Runs on the processor.', usable: true, install_hint: null, uses_gpu: false, devices: [], checks: []};
const text = (html: string) => html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
const notice = (migration: Parameters<typeof LegacyExecutionProviderNotice>[0]['migration']) =>
    text(renderToStaticMarkup(<LegacyExecutionProviderNotice migration={migration} providers={[PACK, CPU]} onDismiss={() => {}}/>));

test('a replacement that is not installed: replaced by its label, with the EP menu\'s not-usable text (G4)', () => {
    assert.equal(notice({saved: 'old-ep', status: 'replaced', replacement: 'pack-ep'}),
        'The execution provider old-ep saved by an earlier FreeMoCap version was replaced by Pack EP. Not usable here. Run `install pack-ep`.Dismiss');
});

test('a usable replacement, Auto (G3), and pending', () => {
    assert.equal(notice({saved: 'old-ep', status: 'replaced', replacement: 'cpu'}),
        'The execution provider old-ep saved by an earlier FreeMoCap version was replaced by CPU.Dismiss');
    assert.match(notice({saved: 'old-ep', status: 'replaced', replacement: null}), /replaced by Auto: SkellyTracker has no usable replacement/);
    assert.match(notice({saved: 'old-ep', status: 'pending'}), /^Checking the execution provider old-ep/);
});
