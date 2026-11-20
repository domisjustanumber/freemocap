import {createHttpClient} from '@freemocap/client/http';
import type {Certification, components} from '@freemocap/client';
import {describeError} from '@/store/slices/thunk-helpers';
import {QUICK_CHECK_TEXT, quickCheckResultText} from '@/services/server/execution-providers';

export type PackagePlan = components['schemas']['PackagePlan'];
export type StartCheckResult = NonNullable<Certification['start_results']>[number];

/** Every text of the start check (decisions 13 to 17), in one place; "machine" for the computer (G1). */
export const START_CHECK_TEXT = {
    heading: 'Quick check of this machine',
    required: 'This machine has no checked result for this version of freemocap. Run the quick check before you use the '
        + 'app; it takes about a minute. Cancel keeps the app waiting; any finished check, passed or failed, releases it.',
    optional: 'freemocap\'s own checks and every GPU execution provider that has no reviewed result on this machine.',
    run: 'Run quick check',
    loadingPlan: 'Reading what the check runs…',
    couldNotReadPlan: 'Could not read what the check runs: ',
    progressName: 'this machine',
    crashed: 'The check',
} as const;

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

/** One line per package: its checks, its one-off estimate, and any download or system change it would make. */
export function planLines(plans: readonly PackagePlan[]): string[] {
    return plans.map(plan => {
        const megabytes = plan.downloads.reduce((sum, download) => sum + (Number(download.bytes) || 0), 0) / 1e6;
        return [`${plan.package}: ${plan.checks.length ? plural(plan.checks.length, 'check') : 'nothing to check'}`,
            `up to about ${plan.seconds_estimate} seconds`, megabytes ? `downloads about ${Math.ceil(megabytes)} MB` : '',
            ...plan.system_changes].filter(Boolean).join(', ');
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

/** Start the start check. Null when accepted, else the server's reason (other work runs, a check runs). */
export async function requestStartCheck(baseUrl: string, request: typeof fetch = fetch): Promise<string | null> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses
        .start_start_check_freemocap_certify_start_check_post({});
    if (response.ok) return null;
    const body: unknown = await response.json().catch(() => null);
    return describeError(body) || `HTTP ${response.status}`;
}
