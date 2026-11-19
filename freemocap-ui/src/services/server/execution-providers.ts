import {createHttpClient} from '@freemocap/client/http';
import type {ExecutionProviderCatalog, ExecutionProviderDevice, ExecutionProviderName, ExecutionProviderOption} from '@/types/execution-provider';

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
    && Array.isArray(row.devices) && row.devices.every(isDevice) && Array.isArray(row.checks) && row.checks.every(isCheck);
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

/** Auto, then the server's offered EPs in its order; a saved key that is not offered stays visible as itself. */
export function executionProviderOptions(selected: ExecutionProviderName | null,
    providers: readonly ExecutionProviderOption[]): {label: string; value: ExecutionProviderName | null}[] {
    const usable = providers.filter(isOffered);
    const options = [{label: 'Auto', value: null}, ...usable.map(({key, label}) => ({label, value: key}))];
    return selected === null || usable.some(({key}) => key === selected)
        ? options : [...options, {label: providers.find(({key}) => key === selected)?.label ?? selected, value: selected}];
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
