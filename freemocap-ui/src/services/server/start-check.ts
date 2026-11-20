import {createHttpClient} from '@freemocap/client/http';
import type {Certification, components} from '@freemocap/client';
import {describeError} from '@/store/slices/thunk-helpers';
import {type CertificationRun, QUICK_CHECK_TEXT, quickCheckResultText} from '@/services/server/execution-providers';

export type PackagePlan = components['schemas']['PackagePlan'];
export type StartCheckResult = NonNullable<Certification['start_results']>[number];

/** Every text of the start check (decisions 13 to 17), in one place; "system" for the computer in this dialog. */
export const START_CHECK_TEXT = {
    heading: 'Quick check of this system',
    required: 'FreeMoCap has not run on this type of system before, so we need to run a check to confirm things work before launching.',
    optional: "freemocap's own checks and every GPU execution provider that has no reviewed result on this system.",
    run: 'Run quick check',
    loadingPlan: 'Reading what the check runs…',
    couldNotReadPlan: 'Could not read what the check runs: ',
    progressName: 'this system',
    crashed: 'The check',
} as const;

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

/** A package's checks, its one-off estimate, and any download or system change it would make. */
export function planDetail(plan: PackagePlan): string {
    const megabytes = plan.downloads.reduce((sum, download) => sum + (Number(download.bytes) || 0), 0) / 1e6;
    return [plan.checks.length ? plural(plan.checks.length, 'check') : 'nothing to check',
        `up to about ${plan.seconds_estimate} seconds`, megabytes ? `downloads about ${Math.ceil(megabytes)} MB` : '',
        ...plan.system_changes].filter(Boolean).join(', ');
}

/** One line per package: its name and its plan detail. */
export const planLines = (plans: readonly PackagePlan[]): string[] => plans.map(plan => `${plan.package}: ${planDetail(plan)}`);

/** The start check's packages, in the order they run; the table shows them before the plan arrives. */
export const START_CHECK_PACKAGES = ['freemocap', 'skellytracker'] as const;

export type RowStatus = {kind: 'waiting' | 'running' | 'done' | 'passed' | 'failed' | 'cancelled' | 'not-run'; text: string};

/**
 * Each package's status cell from the current server state only. While a start check runs (a run without items),
 * packages before the running one are done, it runs with "N of M", later ones wait; the server sends only
 * package-level progress. Otherwise each package shows how its part of the last start check ended (a crash of the
 * whole check, which names no package, stands for every package without its own result), or waits.
 */
export function startCheckRowStatus(packages: readonly string[], run: CertificationRun | undefined,
                                    results: readonly StartCheckResult[]): RowStatus[] {
    if (run && !run.items.length) {
        const running = Math.max(0, run.package ? packages.indexOf(run.package) : 0);
        return packages.map((_, index) => index < running ? {kind: 'done', text: 'Done'}
            : index > running ? {kind: 'waiting', text: 'Waiting'}
                : {kind: 'running', text: run.total === undefined ? 'Starting' : `Running, ${run.done} of ${run.total}`});
    }
    return packages.map(name => {
        const ended = results.find(result => result.package === name) ?? results.find(result => result.package === undefined);
        if (!ended) return {kind: 'waiting', text: 'Waiting'};
        const {result, reason} = ended;
        if (result === 'pass' || result === 'record-only') return {kind: 'passed', text: 'Passed'};
        if (result === 'fail') return {kind: 'failed', text: `Failed: ${reason ?? result}`};
        if (result === 'not-run') return reason === 'cancelled' ? {kind: 'cancelled', text: 'Cancelled'}
            : {kind: 'not-run', text: reason === 'no-check' ? 'Nothing to check' : `Not run: ${reason ?? result}`};
        return {kind: 'failed', text: quickCheckResultText({result, reason})};
    });
}

/** How each package's part of the last start check ended, with the six result texts of the EP quick check (H3). */
export function startResultLines(results: readonly StartCheckResult[]): {text: string; failed: boolean}[] {
    return results.map(({package: name, result, reason}) => ({
        text: `${name ?? START_CHECK_TEXT.crashed}: ${result === 'record-only' ? QUICK_CHECK_TEXT.passed
            : result === 'not-run' && reason === 'no-check' ? 'nothing to check' : quickCheckResultText({result, reason})}`,
        failed: result === 'fail',
    }));
}

/** What the start check runs on this machine, per package. */
export async function requestStartCheckPlan(baseUrl: string, signal?: AbortSignal, request: typeof fetch = fetch): Promise<PackagePlan[]> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses
        .get_start_check_plan_freemocap_certify_start_check_plan_get({signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.packages)) throw new Error('Invalid start check plan');
    return data.packages;
}

/** Start the start check, with the Blender path chosen in Blender settings (null: the server's best guess). Null when
 * accepted, else the server's reason (other work runs, a check runs). */
export async function requestStartCheck(baseUrl: string, request: typeof fetch = fetch, blenderExePath: string | null = null): Promise<string | null> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses
        .start_start_check_freemocap_certify_start_check_post({body: {blenderExePath}});
    if (response.ok) return null;
    const body: unknown = await response.json().catch(() => null);
    return describeError(body) || `HTTP ${response.status}`;
}
