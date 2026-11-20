import {createHttpClient} from '@freemocap/client/http';
import type {Certification, components} from '@freemocap/client';
import {describeError} from '@/store/slices/thunk-helpers';

export type HandInList = components['schemas']['HandInList'];
export type HandInReport = components['schemas']['HandInReport'];
export type ReportFile = components['schemas']['ReportFile'];
type RelayError = components['schemas']['RelayError'];
type SendOutcome = components['schemas']['SendOutcome'];
export type PendingReport = Certification['pending_reports'][number];

/** skellycertify's issue form (its README, "Send a report in 3 steps"); the permanent fallback for a hand-in. */
export const ISSUE_FORM_URL = 'https://github.com/domisjustanumber/skellycertify/issues/new?template=certify-report.yml';
const ISSUE_URL = /^https:\/\/github\.com\/domisjustanumber\/skellycertify\/issues\/[1-9][0-9]*$/;

/** Every text of the Certification button and dialog, in one place ("system" for the computer in this dialog). */
export const CERTIFICATION_TEXT = {
    button: 'Certification',
    title: 'Certify FreeMoCap on this system',
    invitation: "We'd love your help to know this is a good configuration for FreeMoCap to run on in the future. If you'd "
        + 'like to submit your anonymous certification report, click the Submit report button below. If you want to see '
        + "what we'll get before it sends, click the View report button first.",
    fullBenchmark: 'Full benchmark',
    fullBenchmarkInvitation: "If you have the time (approx 5 to 10 mins), we'd really appreciate the results from a full "
        + 'benchmark run on your system.',
    notAvailableYet: 'Not available yet',
    reports: 'Help FreeMoCap by sharing your (anonymous) results',
    nothingPending: 'Nothing to share right now.',
    noteLabel: "Anything you'd like to tell us?",
    privacy: 'The note becomes part of the report, which is public. Do not write your name, contact details or other '
        + 'personal details. Paths and this system\'s user and host names are removed.',
    viewReport: 'View report',
    submitReport: 'Submit report',
    submitReports: 'Submit reports',
    resultsLater: 'Your results appear here when the checks are done.',
    startNow: 'Start now',
    issueForm: 'Save file and open issue form',
    issueFormHelp: 'Attach the saved file to the issue form. If GitHub does not accept the .md file, rename it to .txt.',
    relayNotSetUp: 'Sending is not set up in this build; use the issue form.',
    tooLarge: 'The report is too large to send; use the issue form.',
    relayOff: 'The relay is off. Use the issue form.',
    fileChanged: 'The report changed after you viewed it. View it again.',
    couldNotView: 'Could not build the report: ',
    couldNotSend: 'Could not send: ',
    couldNotMark: 'Could not record that the report was shared: ',
    issueFormOpened: 'Issue form opened',
    openIssueFormAgain: 'Open the issue form again',
    notSent: 'Not sent',
    runningCheck: 'Running check',
    cancelCheck: 'Cancel check',
    fileReport: 'File report',
    recordWaits: 'A recording can start once the quick check ends. ',
    close: 'Close',
    continue: 'Continue',
} as const;

/** "Submit report", or "Submit reports" when the server lists more than one pending report. */
export type SendPhase = 'idle' | 'submitting' | 'sent';

/** The send button's label: "Submitting..." while this window's send is in flight, "Sent!" just after it was accepted. */
export const submitText = (phase: SendPhase, pendingCount: number) =>
    phase === 'submitting' ? 'Submitting...' : phase === 'sent' ? 'Sent!' : submitLabel(pendingCount);

export const submitLabel = (pendingCount: number) => pendingCount > 1 ? CERTIFICATION_TEXT.submitReports : CERTIFICATION_TEXT.submitReport;

/** The reports to share show once no check runs and the start check, when required, has ended (passed, failed or
 * cancelled), from the server's current state. */
export const reportsReady = (certification: Certification | null): boolean =>
    Boolean(certification && !certification.run && (!certification.start_required || certification.start_results?.length));

/** The report pop-up's right-hand button: Submit while the relay can take this file, else the issue form; a send answer
 * that offers the issue form (the relay refused, or gave up) switches to it too. None when nothing is pending. */
export function reportFooterAction(list: HandInList | null, file: ReportFile, message: HandInMessage | null, pendingCount: number):
    'submit' | 'issue-form' | null {
    if (!pendingCount) return null;
    return list?.relay_enabled === false || !file.fits_relay || message?.offerIssueForm ? 'issue-form' : 'submit';
}

/** The dialog's bottom button from the current server state: none while the start check is required, "Continue" once a
 * start check of this server session has ended and released the app, else "Close". */
export function bottomButtonLabel(certification: Certification | null): string | null {
    if (certification?.start_required) return null;
    // As the server releases the app: a start check of this server session ended, and not by a cancel.
    const results = certification?.run ? [] : certification?.start_results ?? [];
    return results.length && results.every(row => row.reason !== 'cancelled') ? CERTIFICATION_TEXT.continue : CERTIFICATION_TEXT.close;
}

/** Opens the Certification dialog from anywhere (the button, a failed check's "File report"; decisions 23, 25 to 27). */
export const openCertification = () => window.dispatchEvent(new CustomEvent('open-certification'));

/** The id of the dialog's "Reports to hand in" part, which a start check's "File report" scrolls to. */
export const REPORTS_SECTION_ID = 'certification-reports';

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

/** Whether the backend runs on this machine; a remote one is named on the button (decision 25). */
export const isLocalHost = (host: string) => ['localhost', '127.0.0.1', '::1', '[::1]'].includes(host.toLowerCase());

/**
 * The button's suffix from the current server state only (decisions 25, F10): the running check's progress, else
 * the reports to file (failures named first), and `@ <host>` for a remote backend. Empty while nothing is known.
 */
export function certificationButtonSuffix(certification: Certification | null, remote: boolean): string {
    if (!certification) return '';
    const {run, pending_reports: pending, host} = certification;
    const failures = pending.filter(report => report.has_failure).length;
    const parts = [run ? `· quick check${run.total === undefined ? '' : ` ${run.done} of ${run.total}`}`
        : failures ? `· ${plural(failures, 'failure')} to file` : pending.length ? `· ${pending.length} to file` : ''];
    if (remote) parts.push(`@ ${host.name}`);
    return parts.filter(Boolean).join(' ');
}

/** "Share N reports with FreeMoCap, F with a failure". */
export function pendingSummary(pending: readonly PendingReport[]): string {
    const failures = pending.filter(report => report.has_failure).length;
    return `Share ${plural(pending.length, 'report')} with FreeMoCap${failures ? `, ${failures} with a failure` : ''}`;
}

/** The pending reports, failures first, each with the facts the hand-in list gives (package, time, kind) when it has them. */
export function pendingRows(pending: readonly PendingReport[], list: HandInList | null): (PendingReport & {text: string})[] {
    const facts = new Map(list?.reports.map(report => [report.report_id, report]));
    return [...pending].sort((a, b) => Number(b.has_failure) - Number(a.has_failure)).map(report => {
        const row = facts.get(report.report_id);
        return {...report, text: [row?.package, row?.created_utc ?? report.report_id, row?.kind, report.has_failure ? 'with a failure' : 'no failure']
            .filter(Boolean).join(' · ')};
    });
}

/** The hand-ins already made, one per issue (covered) or one for every report handed in through the issue form. */
export function handedIn(list: HandInList | null): {issueUrl: string | null; reportIds: string[]}[] {
    const groups = new Map<string, string[]>();
    for (const report of list?.reports ?? []) {
        if (report.state === 'pending') continue;
        const key = report.state === 'covered' && report.reference ? report.reference : '';
        groups.set(key, [...groups.get(key) ?? [], report.report_id]);
    }
    return [...groups].map(([url, reportIds]) => ({issueUrl: safeIssueUrl(url), reportIds}));
}

/** The address only when it is an issue of skellycertify on github.com; a link is never made from anything else. */
export const safeIssueUrl = (url: string | null | undefined) => url && ISSUE_URL.test(url) ? url : null;

const issueNumber = (url: string) => url.slice(url.lastIndexOf('/') + 1);
export const issueLabel = (url: string) => `issue #${issueNumber(url)}`;

const relayErrorText = (error: RelayError | null) => !error ? 'unknown error'
    : error.error === 'privacy-rule' ? `privacy rule ${error.detail ?? '?'}`
        : `${error.error}${error.detail ? ` (${error.detail})` : ''}`;

/** A kept file's line (F20): waiting to be sent again, or given up with the issue form offered. */
export function outboxLine(entry: HandInList['outbox'][number]): string {
    const error = relayErrorText(entry.last_error);
    return entry.offer_issue_form ? `Not shared: ${entry.file_name} (${error}). Use the issue form.`
        : `Waiting to be sent again at the next backend start: ${entry.file_name} (${plural(entry.failed_attempts, 'failed attempt')}; last: ${error}).`;
}

/** The answer to one request of this window, shown until the next view, a new server or a closed dialog. */
export interface HandInMessage {text: string; issueUrl?: string; error: boolean; offerIssueForm: boolean; viewAgain?: boolean}

/** The message for the backend's answer to "send" (R1, R2, relay off): accepted with its link, kept, refused, or not sent. */
export function sendAnswerMessage(status: number, body: unknown): HandInMessage {
    if (status === 200 && body !== null && typeof body === 'object') {
        const outcome = body as SendOutcome;
        const url = safeIssueUrl(outcome.issue_url);
        if (outcome.state === 'covered') {
            const text = `${outcome.duplicate ? 'Already shared' : 'Shared'}${url ? ` as ${issueLabel(url)}` : ''}`;
            return {text, issueUrl: url ?? undefined, error: false, offerIssueForm: false};
        }
        const error = relayErrorText(outcome.error);
        if (outcome.state === 'refused') {
            return {text: `The relay refused the report: ${error}. Use the issue form.`, error: true, offerIssueForm: true};
        }
        return outcome.offer_issue_form
            ? {text: `Not shared: ${error}. Use the issue form.`, error: true, offerIssueForm: true}
            : {text: `Not shared yet: ${error}. The file is kept and sent again at the next backend start.`, error: true,
                offerIssueForm: false};
    }
    const code = (body as {detail?: {code?: unknown}} | null)?.detail?.code;
    if (code === 'relay-off') return {text: CERTIFICATION_TEXT.relayOff, error: true, offerIssueForm: true};
    if (code === 'file-changed') return {text: CERTIFICATION_TEXT.fileChanged, error: true, offerIssueForm: false, viewAgain: true};
    return {text: CERTIFICATION_TEXT.couldNotSend + (describeError(body) || `HTTP ${status}`), error: true, offerIssueForm: false};
}

/** The file the person viewed, for these reports and this note; a send or the issue form uses only this file (R1). */
export interface ViewedReport {reportIds: string[]; note: string; file: ReportFile}

/** Whether the viewed file is still everything pending with the current note; otherwise it must be viewed again. */
export const viewIsCurrent = (view: ViewedReport | null, pending: readonly PendingReport[], note: string): view is ViewedReport =>
    view !== null && view.note === note && view.reportIds.join('\n') === pending.map(report => report.report_id).join('\n');

/** The issue form is the main choice when the relay cannot take this file (R1, R5, decision 26). */
export function issueFormProminent(list: HandInList | null, message: HandInMessage | null, view: ViewedReport | null): boolean {
    return Boolean(message?.offerIssueForm || list?.relay_enabled === false || (view && !view.file.fits_relay)
        || list?.outbox.some(entry => entry.offer_issue_form));
}

const client = (baseUrl: string, request: typeof fetch) => createHttpClient({baseUrl, fetch: request}).responses;

async function json<T>(response: Response): Promise<T> {
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) throw new Error(describeError(body) || `HTTP ${response.status}`);
    return body as T;
}

export const requestHandIn = async (baseUrl: string, signal?: AbortSignal, request: typeof fetch = fetch) =>
    json<HandInList>(await client(baseUrl, request).get_hand_in_freemocap_certify_hand_in_get({signal}));

const noteOrNull = (note: string) => note.trim() ? note : null;

export const requestReportFile = async (baseUrl: string, reportIds: string[], note: string, request: typeof fetch = fetch) =>
    json<ReportFile>(await client(baseUrl, request).get_hand_in_file_freemocap_certify_hand_in_file_post(
        {body: {report_ids: reportIds, note: noteOrNull(note)}}));

const accepted = ({reportIds, note, file}: ViewedReport) => ({report_ids: reportIds, note: noteOrNull(note), sha256: file.sha256});

export async function requestSend(baseUrl: string, view: ViewedReport, request: typeof fetch = fetch): Promise<HandInMessage> {
    const response = await client(baseUrl, request).send_hand_in_freemocap_certify_hand_in_send_post({body: accepted(view)});
    return sendAnswerMessage(response.status, await response.json().catch(() => null));
}

export const requestOpened = async (baseUrl: string, view: ViewedReport, request: typeof fetch = fetch) =>
    json<HandInList>(await client(baseUrl, request).mark_hand_in_opened_freemocap_certify_hand_in_opened_post({body: accepted(view)}));

export const requestNotSent = async (baseUrl: string, reportIds: string[], request: typeof fetch = fetch) =>
    json<HandInList>(await client(baseUrl, request).mark_hand_in_not_sent_freemocap_certify_hand_in_not_sent_post(
        {body: {report_ids: reportIds}}));
