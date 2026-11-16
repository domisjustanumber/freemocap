import {createHttpClient} from '@freemocap/client/http';
import type {ExecutionProviderCatalog, ExecutionProviderName, ExecutionProviderOption} from '@/types/execution-provider';

const isDevice = (device: Record<string, unknown> | null) => typeof device?.key === 'string'
    && (device.name === null || typeof device.name === 'string')
    && (device.vram_total_bytes === null || typeof device.vram_total_bytes === 'number');
const isProvider = (row: Record<string, unknown> | null) => typeof row?.key === 'string' && typeof row.label === 'string'
    && typeof row.description === 'string' && typeof row.usable === 'boolean' && typeof row.uses_gpu === 'boolean'
    && (row.install_hint === null || typeof row.install_hint === 'string')
    && Array.isArray(row.devices) && row.devices.every(isDevice);

export async function requestExecutionProviders(baseUrl: string, signal?: AbortSignal,
    request: typeof fetch = fetch): Promise<ExecutionProviderCatalog> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses.get_available_execution_providers_freemocap_onnx_execution_providers_get({signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const takes = data.detector_takes_execution_provider;
    if (!Array.isArray(data.providers) || !data.providers.every(isProvider) || typeof takes !== 'object' || takes === null
        || !Object.values(takes).every(value => typeof value === 'boolean')) {
        throw new Error('Invalid provider response');
    }
    return {providers: data.providers, detectorTakesExecutionProvider: takes};
}

/** Auto, then the server's usable EPs in its order; a saved key that is not offered stays visible as itself. */
export function executionProviderOptions(selected: ExecutionProviderName | null,
    providers: readonly ExecutionProviderOption[]): {label: string; value: ExecutionProviderName | null}[] {
    const usable = providers.filter(({usable}) => usable);
    const options = [{label: 'Auto', value: null}, ...usable.map(({key, label}) => ({label, value: key}))];
    return selected === null || usable.some(({key}) => key === selected)
        ? options : [...options, {label: providers.find(({key}) => key === selected)?.label ?? selected, value: selected}];
}
