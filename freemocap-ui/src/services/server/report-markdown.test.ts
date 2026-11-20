// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {parseInline, parseReportMarkdown} from './report-markdown';

const FILE = [
    '# Certify report', '',
    'Schema `skellycertify.report/1.1.0`, app freemocap 2.0.0, created 2026-11-20T03:32:53Z (UTC).', '',
    '**freemocap 2.0.0:** valid as evidence.',
    '**skellytracker 2.0.0:** not valid as evidence: cancelled.', '',
    '- OS: macOS 15.2', '- GPU: Apple M2 Pro', '',
    '| Module | Section | Result | Reason |', '|---|---|---|---|', '| skellycam | a \\| b | fail | |', '',
    '> <b>not html</b>', '',
    '## Data', '',
    '````json', '{"note": "```"}', '````', '',
].join('\n');

test('the report file reads as headings, lines, lists, tables, quotes and one fenced block', () => {
    assert.deepEqual(parseReportMarkdown(FILE), [
        {kind: 'heading', level: 1, text: 'Certify report'},
        {kind: 'paragraph', lines: ['Schema `skellycertify.report/1.1.0`, app freemocap 2.0.0, created 2026-11-20T03:32:53Z (UTC).']},
        {kind: 'paragraph', lines: ['**freemocap 2.0.0:** valid as evidence.', '**skellytracker 2.0.0:** not valid as evidence: cancelled.']},
        {kind: 'list', items: ['OS: macOS 15.2', 'GPU: Apple M2 Pro']},
        {kind: 'table', header: ['Module', 'Section', 'Result', 'Reason'], rows: [['skellycam', 'a | b', 'fail', '']]},
        {kind: 'quote', lines: ['<b>not html</b>']},
        {kind: 'heading', level: 2, text: 'Data'},
        {kind: 'code', language: 'json', text: '{"note": "```"}'},
    ]);
});

test('inline bold and code; anything else, HTML included, stays text', () => {
    assert.deepEqual(parseInline('**a b:** x `c` <i>y</i>'), [{kind: 'bold', text: 'a b:'}, {kind: 'text', text: ' x '},
        {kind: 'code', text: 'c'}, {kind: 'text', text: ' <i>y</i>'}]);
});
