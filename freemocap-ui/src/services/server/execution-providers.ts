import {createHttpClient} from '@freemocap/client/http';
import type {Certification} from '@freemocap/client';
import type {ExecutionProviderCatalog, ExecutionProviderDevice, ExecutionProviderName, ExecutionProviderOption} from '@/types/execution-provider';
import {describeError} from '@/store/slices/thunk-helpers';

export type CertificationItem = Certification['items'][number];
export type CertificationRun = NonNullable<Certification['run']>;

const isDevice = (device: Record<string, unknown> | null) => typeof device?.key === 'string'
    && (device.name === null || typeof device.name === 'string')
    && (device.vram_total_bytes === null || typeof device.vram_total_bytes === 'number');
const isCheck = (check: Record<string, unknown> | null) => typeof check?.device_key === 'string'
    && typeof check.certified === 'boolean' && typeof check.usable === 'boolean'
    && (check.local_result === null || check.local_result === 'passed' || check.local_result === 'failed')
    && (check.local_cause === null || check.local_cause === 'unclean-exits');
const isProvider = (row: Record<string, unknown> | null) => typeof row?.key === 'string' && typeof row.label === 'string'
    && typeof row.description === 'string' && typeof row.usable === 'boolean' && typeof row.uses_gpu === 'boolean'
    && (row.install_hint === null || typeof row.install_hint === 'string')
    && Array.isArray(row.devices) && row.devices.every(isDevice) && Array.isArray(row.checks) && row.checks.every(isCheck)
    && (row.source === undefined || typeof row.source === 'string') && (row.state === undefined || typeof row.state === 'string');
const isNumberOrNull = (value: unknown) => value === null || typeof value === 'number';
const isStringOrNull = (value: unknown) => value === null || typeof value === 'string';
const isOffer = (offer: Record<string, unknown> | null) => typeof offer?.kind === 'string' && isStringOrNull(offer.ep_key)
    && isNumberOrNull(offer.download_bytes) && isNumberOrNull(offer.disk_bytes) && isStringOrNull(offer.licence_url)
    && typeof offer.note === 'string';

export async function requestExecutionProviders(baseUrl: string, signal?: AbortSignal,
    request: typeof fetch = fetch): Promise<ExecutionProviderCatalog> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses.get_available_execution_providers_freemocap_onnx_execution_providers_get({signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const takes = data.detector_takes_execution_provider;
    if (!Array.isArray(data.providers) || !data.providers.every(isProvider) || typeof takes !== 'object' || takes === null
        || !Object.values(takes).every(value => typeof value === 'boolean')
        || !Array.isArray(data.auto_offers) || !data.auto_offers.every(isOffer)) {
        throw new Error('Invalid provider response');
    }
    return {providers: data.providers, detectorTakesExecutionProvider: takes, autoOffers: data.auto_offers};
}

/** The GPUs of an EP that the menu offers: each with a usable check of skellytracker; all of them for an EP with no checks. */
export function offeredDevices(provider: ExecutionProviderOption | undefined): ExecutionProviderDevice[] {
    if (!provider) return [];
    const {devices, checks} = provider;
    return checks.length ? devices.filter(({key}) => checks.some(check => check.device_key === key && check.usable)) : devices;
}

/** Whether the menu offers an EP: usable, and for an EP with GPU checks usable on at least one GPU. */
export const isOffered = ({usable, checks}: ExecutionProviderOption) => usable && (!checks.length || checks.some(check => check.usable));

/**
 * Auto, then the server's offered EPs in its order; a saved key that is not offered stays visible as itself.
 * With the server's certification items (F1, F2), an EP with GPU checks is offered from its menu pairs instead, its
 * label marked with the state of the pair that a device choice of Auto would take.
 */
export function executionProviderOptions(selected: ExecutionProviderName | null,
    providers: readonly ExecutionProviderOption[], items?: readonly CertificationItem[]): {label: string; value: ExecutionProviderName | null}[] {
    const byPairs = (provider: ExecutionProviderOption) => items !== undefined && provider.checks.length > 0;
    const shown = providers.filter(provider => byPairs(provider) ? menuPairs(provider, items).length > 0 : isOffered(provider));
    const label = (provider: ExecutionProviderOption) => {
        const marker = byPairs(provider) ? PAIR_MARKERS[autoPair(menuPairs(provider, items))?.state ?? 'reviewed'] : '';
        return marker ? `${provider.label} (${marker})` : provider.label;
    };
    const options = [{label: 'Auto', value: null}, ...shown.map(provider => ({label: label(provider), value: provider.key}))];
    return selected === null || shown.some(({key}) => key === selected)
        ? options : [...options, {label: providers.find(({key}) => key === selected)?.label ?? selected, value: selected}];
}

/** F12's five states of one EP on one GPU, worded with "machine" for the computer (G1). A reviewed pair has no marker. */
export const PAIR_MARKERS = {
    'reviewed': '',
    'passed-here': 'passed on this system, not yet reviewed',
    'not-checked': 'not checked on this system',
    'failed': 'check failed on this system',
    'unclean-exits': 'exited uncleanly twice',
} as const;
export type PairState = keyof typeof PAIR_MARKERS;

/** The state of a pair from skellytracker's facts (`DeviceCheck`). */
export function pairState({certified, local_result, local_cause, usable}: {
    certified: boolean; local_result?: string | null; local_cause?: string | null; usable: boolean;
}): PairState {
    if (usable) return certified ? 'reviewed' : 'passed-here';
    if (local_result === 'failed') return local_cause === 'unclean-exits' ? 'unclean-exits' : 'failed';
    return 'not-checked';
}

// skellytracker's reason codes of an EP that is ready but refused by its check rule (ADR-ER5X).
const CHECK_RULE_CODES: ReadonlySet<string> = new Set(['quick-check-needed', 'quick-check-failed', 'unclean-exits']);

/** One EP on one GPU as the menu shows it. `needsCheck`: choosing it opens the quick-check prompt. */
export interface MenuPair {execution_provider: string; device_key: string; name: string; state: PairState; needsCheck: boolean}

/**
 * The pairs of an EP that the menu shows, in skellytracker's order (most VRAM first): the usable ones and, from the
 * server's certification items, the ones a quick check would let run (unchecked or failed here; F1, F2). A pair of an
 * EP that is not installed or not ready stays hidden. Without the items (before the first status read): the usable
 * checks. Each item's reason code is its GPU's (absent when usable).
 */
export function menuPairs(provider: ExecutionProviderOption, items?: readonly CertificationItem[]): MenuPair[] {
    const name = (key: string, given?: string) => given ?? provider.devices.find(device => device.key === key)?.name ?? key;
    if (!items) {
        return provider.checks.filter(check => check.usable).map(check => ({execution_provider: provider.key,
            device_key: check.device_key, name: name(check.device_key), state: pairState(check), needsCheck: false}));
    }
    return items.filter(item => item.execution_provider === provider.key
        && (item.usable || CHECK_RULE_CODES.has(item.reason_code ?? '')))
        .map(item => ({execution_provider: provider.key, device_key: item.device_key, name: name(item.device_key, item.device_name),
            state: pairState(item), needsCheck: !item.usable}));
}

/** The pair a device choice of Auto runs on: the first usable one, else the first one shown. */
const autoPair = (pairs: readonly MenuPair[]): MenuPair | undefined => pairs.find(pair => !pair.needsCheck) ?? pairs[0];

/** The Device row's GPUs of an EP, each with its marker; without the items, or for an EP with no checks, `offeredDevices`. */
export function menuDevices(provider: ExecutionProviderOption | undefined,
    items?: readonly CertificationItem[]): (ExecutionProviderDevice & {marker?: string})[] {
    if (!provider || !items || !provider.checks.length) return offeredDevices(provider);
    return menuPairs(provider, items).map(pair => ({key: pair.device_key, name: pair.name, marker: PAIR_MARKERS[pair.state],
        vram_total_bytes: provider.devices.find(device => device.key === pair.device_key)?.vram_total_bytes ?? null}));
}

/**
 * The pair whose quick check a choice asks for (F1, F9): with no device (Auto), the EP's pair when none of its pairs
 * is usable; with a device, that pair when it is not usable. Undefined when the choice can run now.
 */
export function pairToCheck(provider: ExecutionProviderOption | undefined, device: string | null,
    items?: readonly CertificationItem[]): MenuPair | undefined {
    if (!provider) return undefined;
    const pairs = menuPairs(provider, items);
    const pair = device === null ? autoPair(pairs) : pairs.find(({device_key}) => device_key === device);
    return pair?.needsCheck ? pair : undefined;
}

/** "<EP> on <GPU>" by the server's item names, else by the keys. */
export function pairLabel(pair: {execution_provider: string; device_key?: string}, items: readonly CertificationItem[] = []): string {
    const item = items.find(({execution_provider, device_key}) => execution_provider === pair.execution_provider && device_key === pair.device_key);
    return `${item?.label ?? pair.execution_provider} on ${item?.device_name ?? pair.device_key ?? 'its device'}`;
}

/** The running check as F10 words it: checks done of total, and the plan's one-off estimate; no countdown. */
export function quickCheckProgressText(run: CertificationRun, items?: readonly CertificationItem[], machine = 'this system'): string {
    const done = run.total === undefined ? 'starting' : `${run.done} of ${run.total} checks done`;
    const estimate = run.seconds_estimate === undefined ? '' : `, up to about ${run.seconds_estimate} seconds`;
    // A start check has no items: it checks this machine, one package after the other.
    const what = run.items[0] ? pairLabel(run.items[0], items) : `${machine}${run.package ? ` (${run.package})` : ''}`;
    return `Quick check of ${what}: ${done}${estimate}.`;
}

/** The six lines saying how a quick check ended (user-confirmed wording, 2026-11-19), in one place. */
export const QUICK_CHECK_TEXT = {
    passed: 'Quick check passed',
    failed: 'Quick check failed: ',
    notRun: 'Quick check did not run: ',
    crashed: 'Quick check stopped unexpectedly',
    couldNotStart: 'Quick check could not start: ',
    cancelled: 'Quick check cancelled',
} as const;

/** Plain sentences for skellytracker's reason codes (its REASON_CODES.md) that a person sees, and for freemocap's checks
 * (a failed freemocap module names its failed check); any other code shows as sent. */
const REASON_TEXT: Readonly<Record<string, string>> = {
    'models-missing': 'a model file it needs is not on this system',
    'test-media-missing': 'its test images are missing or damaged',
    'over-budget': 'it did not fit in the time the quick check allows',
    'video-not-passed': 'the video check did not pass',
    'cpu-reference-missing': 'the CPU reference check did not pass',
    'posthoc-session': 'a post-hoc processing session did not start and run on this system',
    'crashed': 'it stopped unexpectedly while it ran and is not run again by itself',
};
export const reasonText = (reason: string): string => REASON_TEXT[reason] ?? reason;

/**
 * How the last check ended, from `certification.last_result`. A cancel is skellytracker's `not-run` with the reason
 * `cancelled`; `error` (certify() raised; the reason is the exception class) and any new result say it could not start.
 */
export function quickCheckResultText({result, reason}: {result: string; reason?: string}): string {
    if (result === 'pass') return QUICK_CHECK_TEXT.passed;
    if (result === 'fail') return QUICK_CHECK_TEXT.failed + reasonText(reason ?? result);
    if (result === 'not-run') return reason === 'cancelled' ? QUICK_CHECK_TEXT.cancelled : QUICK_CHECK_TEXT.notRun + reasonText(reason ?? result);
    if (result === 'crashed') return QUICK_CHECK_TEXT.crashed;
    return QUICK_CHECK_TEXT.couldNotStart + reasonText(reason ?? result);
}

/** A check this window started for a choice, and the choice that a pass makes the selection (F6). */
export interface CheckIntent {
    pair: {execution_provider: string; device_key: string};
    change: {provider: ExecutionProviderName; device: string | null};
    /** `last_result` as the server gave it when the start was accepted, to tell the end of this check from it. */
    before: string | undefined;
    /** The server has shown this check running. */
    sawRun: boolean;
}

/**
 * Where a started check stands, from the server's current state only: running; passed for its pair (the choice becomes
 * the selection); or ended any other way, also when the server is gone (the selection stays what it was: F6).
 */
export function checkIntentOutcome(intent: CheckIntent, certification: Certification | null): 'running' | 'passed' | 'ended' {
    if (!certification) return 'ended';
    const {run, last_result: result} = certification;
    if (run) return 'running';
    if (!intent.sawRun && JSON.stringify(result) === intent.before) return 'running'; // accepted, not yet in a state message
    return result?.result === 'pass' && result.execution_provider === intent.pair.execution_provider
        && result.device_key === intent.pair.device_key ? 'passed' : 'ended';
}

/** What a window keeps of its quick-check requests besides the started check. */
export interface QuickCheckLines {
    /** The server's refusal of this window's last start, and whether the server has since shown work running. */
    refusal: {text: string; sawBusy: boolean} | null;
    /** The `last_result` the person moved on from by a new choice. */
    dismissed: string | null;
}

/**
 * The lines after a new server state, so that neither outlives the state it answered: a refusal goes once the work
 * that refused it (a check, or anything in `gpu_held_by`) is seen to end; a result moved on from may show again only
 * after an EP quick check ran, since a start check leaves `last_result` as it was. Returns `lines` when nothing changes.
 */
export function settleQuickCheckLines<T extends QuickCheckLines>(lines: T, certification: Certification | null): T {
    const busy = Boolean(certification?.run || certification?.gpu_held_by.length);
    const held = lines.refusal;
    const refusal = !held ? null : busy ? (held.sawBusy ? held : {...held, sawBusy: true}) : held.sawBusy ? null : held;
    const dismissed = certification?.run?.items.length ? null : lines.dismissed;
    return refusal === held && dismissed === lines.dismissed ? lines : {...lines, refusal, dismissed};
}

/** The last check's ending shows unless a check runs or the person moved on from it. */
export function quickCheckResultShows(certification: Certification | null, dismissed: string | null): boolean {
    const result = certification?.last_result;
    return Boolean(result) && !certification?.run && JSON.stringify(result) !== dismissed;
}

/** Start the quick check of one pair with the person's detector (F9). Null when accepted, else the server's reason. */
export async function requestQuickCheck(baseUrl: string, pair: {execution_provider: string; device_key: string},
    detector: {detector_type: 'rtmpose' | 'mediapipe'; rtmpose_model_name: 'rtmw-x-l_256x192' | 'rtmw-x-l_384x288' | 'rtmw-l-m_256x192'},
    signal?: AbortSignal, request: typeof fetch = fetch): Promise<string | null> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses
        .start_quick_check_freemocap_certify_quick_check_post({body: {...pair, ...detector}, signal});
    if (response.ok) return null;
    const body: unknown = await response.json().catch(() => null);
    return describeError(body) || `HTTP ${response.status}`;
}

/** Ask the running check to stop; the server's state shows when and how it ended. */
export async function requestQuickCheckCancel(baseUrl: string, request: typeof fetch = fetch): Promise<void> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses.cancel_quick_check_freemocap_certify_quick_check_delete({});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
}

/** Whether a detector shows the Execution provider row: the server's flag once it has answered; before that (also
 *  while disconnected or after a failed query) the RTMW detector shows it with Auto and the saved key, as upstream sfn26. */
export function detectorShowsExecutionProvider(answer: Readonly<Record<string, boolean>> | null, detector: string): boolean {
    return answer ? answer[detector] ?? false : detector === 'rtmpose';
}

/** skellytracker's replacement for an EP key saved before skellytracker 2 (null = Auto). */
export async function requestExecutionProviderSuggestion(baseUrl: string, saved: string, signal?: AbortSignal,
    request: typeof fetch = fetch): Promise<string | null> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses
        .get_execution_provider_suggestion_freemocap_onnx_execution_providers_suggestion_get({query: {saved}, signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (data.saved !== saved || !(data.suggested === null || typeof data.suggested === 'string')) {
        throw new Error('Invalid provider suggestion');
    }
    return data.suggested;
}
