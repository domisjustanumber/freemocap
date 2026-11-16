import {createHttpClient} from '@freemocap/client/http';
import type {ExecutionProviderName, ExecutionProviderOption} from '@/types/execution-provider';

export async function requestExecutionProviders(baseUrl: string, signal?: AbortSignal,
    request: typeof fetch = fetch): Promise<ExecutionProviderOption[]> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses.get_available_execution_providers_freemocap_onnx_execution_providers_get({signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.available) || data.available.some((row: {key?: unknown; label?: unknown} | null) =>
        typeof row?.key !== 'string' || typeof row?.label !== 'string')) {
        throw new Error('Invalid provider response');
    }
    return data.available.map(({key, label}: ExecutionProviderOption) => ({key, label}));
}

/** Auto, then the server's EPs in its order; a saved key that the server does not list stays visible as itself. */
export function executionProviderOptions(selected: ExecutionProviderName | null,
    available: readonly ExecutionProviderOption[]): {label: string; value: ExecutionProviderName | null}[] {
    const options = [{label: 'Auto', value: null}, ...available.map(({key, label}) => ({label, value: key}))];
    return selected === null || available.some(({key}) => key === selected)
        ? options : [...options, {label: selected, value: selected}];
}
