// Bundle with esbuild --bundle --platform=node --format=cjs, then node --test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import type {Certification} from '@freemocap/client';
import {
    bottomButtonLabel, certificationButtonSuffix, handedIn, type HandInList, isLocalHost, issueFormProminent, outboxLine, pendingRows, pendingSummary,
    requestHandIn, requestNotSent, requestOpened, requestReportFile, requestSend, safeIssueUrl, sendAnswerMessage, viewIsCurrent,
    type ViewedReport,
} from './certification-hand-in';

const ISSUE = 'https://github.com/domisjustanumber/skellycertify/issues/42';
const BASE: Certification = {host: {name: 'lab-machine', os: 'Windows 11'}, items: [], gpu_held_by: [], pending_reports: []};
const pending = (...failures: boolean[]) => failures.map((has_failure, index) => ({report_id: `r${index}`, has_failure}));
const report = (report_id: string, state: 'pending' | 'opened' | 'covered', reference: string | null = null) =>
    ({report_id, package: 'freemocap', kind: 'quick', created_utc: `2026-11-19T12:0${report_id.slice(1)}:00Z`, has_failure: false, evidence_valid: true, state, reference});
const LIST: HandInList = {relay_enabled: true, reports: [], outbox: []};
const FILE = {file_name: 'certify-report-x.md', sha256: 'a'.repeat(64), size_bytes: 10, fits_relay: true, content: '# report'};
const VIEW: ViewedReport = {reportIds: ['r0', 'r1'], note: '', file: FILE};

test('the button suffix follows the server state: progress, then failures, then the count, and a remote host', () => {
    assert.equal(certificationButtonSuffix(null, true), '', 'nothing known (disconnected)');
    assert.equal(certificationButtonSuffix(BASE, false), '');
    assert.equal(certificationButtonSuffix({...BASE, pending_reports: pending(false, false)}, false), '· 2 to file');
    assert.equal(certificationButtonSuffix({...BASE, pending_reports: pending(true, false)}, false), '· 1 failure to file');
    assert.equal(certificationButtonSuffix({...BASE, pending_reports: pending(true, true)}, false), '· 2 failures to file');
    const run = {level: 'quick', items: [], state: 'running', done: 1, total: 3};
    assert.equal(certificationButtonSuffix({...BASE, run, pending_reports: pending(true)}, false), '· quick check 1 of 3');
    assert.equal(certificationButtonSuffix({...BASE, run: {...run, total: undefined}}, false), '· quick check');
    assert.equal(certificationButtonSuffix({...BASE, pending_reports: pending(false)}, true), '· 1 to file @ lab-machine');
    assert.equal(certificationButtonSuffix(BASE, true), '@ lab-machine');
    assert.deepEqual(['localhost', '127.0.0.1', '::1', 'LOCALHOST', '192.168.1.5', 'lab'].map(isLocalHost), [true, true, true, true, false, false]);
});

test('the pending reports are summed up and listed failures first, with the list facts (package first) when known', () => {
    assert.equal(pendingSummary(pending(false)), '1 report to hand in');
    assert.equal(pendingSummary(pending(false, true, true)), '3 reports to hand in, 2 with a failure');
    const rows = pendingRows(pending(false, true), {...LIST, reports: [report('r0', 'pending')]});
    assert.deepEqual(rows.map(row => row.text), ['r1 · with a failure', 'freemocap · 2026-11-19T12:00:00Z · quick · no failure']);
});

test('hand-ins made are grouped by issue, the issue form ones together, and only safe issue links are kept', () => {
    const list = {...LIST, reports: [report('r0', 'covered', ISSUE), report('r1', 'covered', ISSUE), report('r2', 'opened'),
        report('r3', 'pending'), report('r4', 'opened')]};
    assert.deepEqual(handedIn(list), [{issueUrl: ISSUE, reportIds: ['r0', 'r1']}, {issueUrl: null, reportIds: ['r2', 'r4']}]);
    assert.deepEqual(handedIn(null), []);
    for (const url of ['javascript:alert(1)', 'https://github.com/other/repo/issues/1', `${ISSUE}/x`, 'http://github.com/domisjustanumber/skellycertify/issues/1']) {
        assert.equal(safeIssueUrl(url), null, url);
    }
    assert.equal(safeIssueUrl(ISSUE), ISSUE);
});

test('a kept file says whether it waits for the next start or the issue form is needed', () => {
    const entry = {sha256: 'b'.repeat(64), file_name: 'f.md', report_ids: ['r0'], failed_attempts: 1, retry_pending: true, offer_issue_form: false,
        last_error: {status: 503, error: 'github-unavailable', retry: true, detail: null}};
    assert.equal(outboxLine(entry), 'Waiting to be sent again at the next backend start: f.md (1 failed attempt; last: github-unavailable).');
    assert.equal(outboxLine({...entry, offer_issue_form: true, last_error: {status: 422, error: 'privacy-rule', retry: false, detail: '7'}}),
        'Not handed in: f.md (privacy rule 7). Use the issue form.');
});

test('each answer to "send" gives its message: accepted, kept, given up, refused, relay off, file changed, other', () => {
    const outcome = {state: 'covered', issue_url: ISSUE, issue_number: 42, duplicate: false, error: null, offer_issue_form: false};
    assert.deepEqual(sendAnswerMessage(200, outcome), {text: 'Handed in as issue #42', issueUrl: ISSUE, error: false, offerIssueForm: false});
    assert.equal(sendAnswerMessage(200, {...outcome, duplicate: true}).text, 'Already handed in as issue #42');
    const error = {status: 503, error: 'github-unavailable', retry: true, detail: 'try later'};
    const kept = sendAnswerMessage(200, {...outcome, state: 'kept', issue_url: null, error});
    assert.equal(kept.text, 'Not handed in yet: github-unavailable (try later). The file is kept and sent again at the next backend start.');
    assert.equal(kept.offerIssueForm, false);
    assert.deepEqual(sendAnswerMessage(200, {...outcome, state: 'kept', issue_url: null, error, offer_issue_form: true}),
        {text: 'Not handed in: github-unavailable (try later). Use the issue form.', error: true, offerIssueForm: true});
    assert.deepEqual(sendAnswerMessage(200, {...outcome, state: 'refused', issue_url: null, offer_issue_form: true,
        error: {status: 422, error: 'privacy-rule', retry: false, detail: '3'}}),
    {text: 'The relay refused the report: privacy rule 3. Use the issue form.', error: true, offerIssueForm: true});
    assert.deepEqual(sendAnswerMessage(409, {detail: {code: 'relay-off', detail: 'the relay is off; use the issue form'}}),
        {text: 'The relay is off. Use the issue form.', error: true, offerIssueForm: true});
    assert.equal(sendAnswerMessage(409, {detail: {code: 'file-changed', detail: 'x'}}).viewAgain, true);
    assert.equal(sendAnswerMessage(422, {detail: {code: 'unknown-report', detail: "'r9' is not a report of this host"}}).text,
        "Could not send: 'r9' is not a report of this host");
    assert.equal(sendAnswerMessage(502, null).text, 'Could not send: HTTP 502');
});

test('the viewed file counts only for the same pending reports and note', () => {
    assert.equal(viewIsCurrent(VIEW, pending(false, true), ''), true);
    assert.equal(viewIsCurrent(VIEW, pending(false, true), 'a note'), false, 'note changed');
    assert.equal(viewIsCurrent(VIEW, pending(false, true, false), ''), false, 'a new report arrived');
    assert.equal(viewIsCurrent(null, pending(false), ''), false);
});

test('the issue form is the main choice when the relay cannot take the file', () => {
    assert.equal(issueFormProminent(LIST, null, VIEW), false);
    assert.equal(issueFormProminent({...LIST, relay_enabled: false}, null, VIEW), true, 'no relay address');
    assert.equal(issueFormProminent(LIST, {text: '', error: true, offerIssueForm: true}, VIEW), true, 'relay off or refused');
    assert.equal(issueFormProminent(LIST, null, {...VIEW, file: {...FILE, fits_relay: false}}), true, 'too large');
    assert.equal(issueFormProminent({...LIST, outbox: [{sha256: 'c', file_name: 'f', report_ids: [], failed_attempts: 4, last_error: null,
        retry_pending: false, offer_issue_form: true}]}, null, VIEW), true, 'given up after the retries');
});

test('the requests name the routes, the reports, the note and the viewed SHA-256; an empty note is sent as null', async () => {
    const requests: {url: string; method: string; body: unknown}[] = [];
    const answer = (response: Response): typeof fetch => async (url, init) => {
        requests.push({url: String(url), method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined});
        return response;
    };
    assert.deepEqual(await requestHandIn('http://server.invalid', undefined, answer(Response.json(LIST))), LIST);
    assert.deepEqual(await requestReportFile('http://server.invalid', ['r0'], '  ', answer(Response.json(FILE))), FILE);
    assert.equal((await requestSend('http://server.invalid', {...VIEW, note: 'n'}, answer(Response.json(
        {detail: {code: 'relay-off', detail: 'off'}}, {status: 409})))).text, 'The relay is off. Use the issue form.');
    await requestOpened('http://server.invalid', VIEW, answer(Response.json(LIST)));
    await requestNotSent('http://server.invalid', ['r0'], answer(Response.json(LIST)));
    assert.deepEqual(requests, [
        {url: 'http://server.invalid/freemocap/certify/hand_in', method: 'GET', body: undefined},
        {url: 'http://server.invalid/freemocap/certify/hand_in/file', method: 'POST', body: {report_ids: ['r0'], note: null}},
        {url: 'http://server.invalid/freemocap/certify/hand_in/send', method: 'POST', body: {report_ids: ['r0', 'r1'], note: 'n', sha256: FILE.sha256}},
        {url: 'http://server.invalid/freemocap/certify/hand_in/opened', method: 'POST', body: {report_ids: ['r0', 'r1'], note: null, sha256: FILE.sha256}},
        {url: 'http://server.invalid/freemocap/certify/hand_in/not_sent', method: 'POST', body: {report_ids: ['r0']}},
    ]);
    await assert.rejects(requestOpened('http://server.invalid', VIEW, answer(Response.json(
        {detail: {code: 'file-changed', detail: 'the report file is not the file that was viewed; view it again'}}, {status: 409}))),
    /view it again/);
});

test('the bottom button follows the server state: none while required, Continue once a start check ended, else Close', () => {
    const run = {level: 'quick', items: [], state: 'running', done: 0};
    assert.equal(bottomButtonLabel(null), 'Close');
    assert.equal(bottomButtonLabel(BASE), 'Close');
    assert.equal(bottomButtonLabel({...BASE, start_required: true, start_results: [{package: 'freemocap', result: 'pass'}]}), null);
    assert.equal(bottomButtonLabel({...BASE, start_results: [{package: 'freemocap', result: 'fail'}]}), 'Continue');
    assert.equal(bottomButtonLabel({...BASE, run, start_results: [{package: 'freemocap', result: 'pass'}]}), 'Close');
    assert.equal(bottomButtonLabel({...BASE, start_results: [{package: 'freemocap', result: 'pass'},
        {package: 'skellytracker', result: 'not-run', reason: 'cancelled'}]}), 'Close');
});
