import {createHttpClient} from '@freemocap/client/http';
import type {Certification} from '@freemocap/client';
import {describeError} from '@/store/slices/thunk-helpers';
import {type CertificationItem, type CertificationRun, pairLabel, reasonText} from '@/services/server/execution-providers';
import type {PackagePlan, StartCheckResult} from '@/services/server/start-check';

export type FullRunRow = NonNullable<CertificationRun['rows']>[number];

/** Every text of the full benchmark (fifth grilling, "Full benchmark"), in one place; "system" for the computer. */
export const FULL_BENCHMARK_TEXT = {
    button: 'Full benchmark',
    invitationStart: "If you have the time",
    invitationEnd: ", we'd really appreciate the results from a full benchmark run on your system.",
    downloadsHeading: 'Downloads',
    nothingDownloaded: 'Nothing is downloaded.',
    estimatesHeading: 'Time estimate',
    removeData: 'Remove benchmark data after a successful run',
    removeDataHelp: 'The report, the bundled test images and files that were there before are kept. After a failed or '
        + 'cancelled run nothing is removed.',
    start: 'Start',
    cancel: 'Cancel',
    couldNotStart: 'Full benchmark could not start: ',
    couldNotReadPlan: 'Could not read what the full benchmark runs: ',
    loadingPlan: 'Reading what the full benchmark runs…',
    sourceNotGiven: 'not given',
    total: 'Total',
} as const;

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

/** A one-off estimate in words: seconds under a minute, else whole minutes rounded up. */
export const durationText = (seconds: number): string => seconds < 60 ? plural(seconds, 'second') : plural(Math.ceil(seconds / 60), 'minute');

/** The invitation with the total of the plans' estimates once they arrived. */
export const invitationText = (plans?: readonly PackagePlan[]): string => FULL_BENCHMARK_TEXT.invitationStart
    + (plans ? ` (about ${durationText(plans.reduce((sum, plan) => sum + plan.seconds_estimate, 0))})` : '')
    + FULL_BENCHMARK_TEXT.invitationEnd;

const megabytes = (bytes: number) => `${(bytes / 1e6).toFixed(1)} MB`;
const host = (source: unknown): string => {
    if (typeof source !== 'string' || !source) return FULL_BENCHMARK_TEXT.sourceNotGiven;
    try { return new URL(source).host || source; } catch { return source; }
};

/** The consent step's downloads table: name, source host and size of each package's download, then the total; no rows
 * when nothing is downloaded. */
export function downloadRows(plans: readonly PackagePlan[]): {rows: {name: string; source: string; size: string}[]; total: string} {
    const downloads = plans.flatMap(plan => plan.downloads);
    const rows = downloads.map(download => ({name: String(download.name ?? ''), source: host(download.source),
        size: megabytes(Number(download.bytes) || 0)}));
    return {rows, total: megabytes(downloads.reduce((sum, download) => sum + (Number(download.bytes) || 0), 0))};
}

/** Each package's line of the consent step: its count of checks and its time estimate. */
export const estimateLine = (plan: PackagePlan): string =>
    `${plan.package}: ${plan.total ? `${plural(plan.total, 'check')}, about ${durationText(plan.seconds_estimate)}` : 'nothing to check'}`;

/** freemocap's own full benchmark checks in words, where the rows and the result lines print them; the report file
 * keeps the names. Its `posthoc:<label>` checks read "post-hoc processing on <pair>". */
const CHECK_TEXT: Readonly<Record<string, string>> = {
    'data-folder': 'data folder write access',
    'recording': 'sample recording download and preparation',
    'blender': 'Blender export',
};
const POSTHOC = 'posthoc:';

/** A check's name, or a reason code, in words: a freemocap pair by its progress row when the server still has it. */
export function checkText(name: string, items: readonly CertificationItem[] = [], rows: readonly FullRunRow[] = []): string {
    if (!name.startsWith(POSTHOC)) return CHECK_TEXT[name] ?? reasonText(name);
    const row = rows.find(row => row.package === 'freemocap' && row.name === name && row.execution_provider);
    const label = name.slice(POSTHOC.length);
    return `post-hoc processing on ${row ? fullRowName(row, items) : label === 'cpu' ? 'CPU' : label}`;
}

/** A progress row's name: the EP on its GPU by the server's item names, the CPU, or freemocap's check in words, else its name. */
export function fullRowName(row: FullRunRow, items: readonly CertificationItem[] = []): string {
    if (row.execution_provider === 'cpu') return 'CPU';
    if (row.execution_provider) return pairLabel({execution_provider: row.execution_provider, device_key: row.device_key}, items);
    const text = CHECK_TEXT[row.name];
    return text ? text[0].toUpperCase() + text.slice(1) : row.name;
}

/** A progress row's status: waiting, running (with the turning icon), partly done (some checks ended, the rest come later
 * in the run, as the CPU's timings after the pairs), or how it ended; a check that a cancel stopped reads "Cancelled". */
export function fullRowStatus(row: FullRunRow): {kind: 'waiting' | 'running' | 'passed' | 'failed' | 'done'; text: string} {
    if (row.state === 'running') return {kind: 'running', text: 'Running'};
    if (row.state === 'partly-done') return {kind: 'waiting', text: 'Partly done'};
    if (row.state !== 'done') return {kind: 'waiting', text: 'Waiting'};
    if (row.result === 'pass') return {kind: 'passed', text: 'Passed'};
    if (row.result === 'fail') return {kind: 'failed', text: 'Failed'};
    return {kind: 'done', text: row.result !== 'not-run' ? 'Done' : row.reason === 'cancelled' ? 'Cancelled' : 'Not run'};
}

/** The count of finished checks; no percentage and no time remaining. */
export const finishedText = (run: CertificationRun): string => `${plural(run.done, 'check')} finished`;

/** How each package's part of the last full benchmark ended (a crash of the whole run names no package); a failed
 * check is named in words, by the server's items and the run's rows. */
export function fullResultLines(results: readonly StartCheckResult[], items: readonly CertificationItem[] = [],
    rows: readonly FullRunRow[] = []): {text: string; failed: boolean}[] {
    return results.map(({package: name, result, reason}) => {
        const why = checkText(reason ?? result, items, rows);
        const ended = result === 'crashed' || reason === 'crashed' ? 'stopped unexpectedly'
            : result === 'pass' || result === 'record-only' ? 'finished'
                : result === 'fail' ? `finished with failed checks: ${why}`
                    : result === 'not-run' ? (reason === 'cancelled' ? 'cancelled' : `not run: ${why}`) : `could not run: ${why}`;
        return {text: `${name ?? FULL_BENCHMARK_TEXT.button}: ${ended}`, failed: result !== 'pass' && result !== 'record-only' && result !== 'not-run'};
    });
}

/** The app is locked while a full benchmark runs, as during the required start check; a cancel unlocks it at once. */
export const fullBenchmarkLocks = (certification: Certification | null): boolean =>
    certification?.run?.level === 'full' && certification.run.state !== 'cancelling';

/** The app's lock from the current server state: the required start check or a running full benchmark. The dialog
 * stays usable; everything else, keyboard shortcuts and the native menu's actions included, waits. */
export const appLocked = (certification: Certification | null): boolean =>
    certification?.start_required === true || fullBenchmarkLocks(certification);

/** What the full benchmark runs on this system, per package in the run order, with the Blender path chosen in settings. */
export async function requestFullBenchmarkPlan(baseUrl: string, signal?: AbortSignal, request: typeof fetch = fetch,
    blenderExePath: string | null = null): Promise<PackagePlan[]> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses
        .get_full_benchmark_plan_freemocap_certify_full_benchmark_plan_get({query: blenderExePath ? {blenderExePath} : {}, signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.packages)) throw new Error('Invalid full benchmark plan');
    return data.packages;
}

/** Start the full benchmark with the clean-up choice and the Blender path chosen in settings (null: the server's best
 * guess). Null when accepted, else the server's one sentence. */
export async function requestFullBenchmark(baseUrl: string, removeData: boolean, request: typeof fetch = fetch,
    blenderExePath: string | null = null): Promise<string | null> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses
        .start_full_benchmark_freemocap_certify_full_benchmark_post({body: {remove_data: removeData, blenderExePath}});
    if (response.ok) return null;
    const body: unknown = await response.json().catch(() => null);
    return describeError(body) || `HTTP ${response.status}`;
}
