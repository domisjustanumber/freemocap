import {createHttpClient, type OperationData} from '@freemocap/client/http';
import {ConnectionState} from '@/services/server/server-helpers/websocket-connection';
import type {TransportService} from '@/services/server/transport/TransportService';

/** skellytracker's host, GPUs, runtime, EP status and the models of each live run, as the server gives them. */
export type SystemInformation = OperationData<'get_system_information_freemocap_onnx_system_information_get'>;

export async function requestSystemInformation(baseUrl: string, signal?: AbortSignal,
    request: typeof fetch = fetch): Promise<SystemInformation> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses
        .get_system_information_freemocap_onnx_system_information_get({signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (typeof data?.host !== 'object' || data.host === null || typeof data.runtime !== 'object' || data.runtime === null
        || typeof data.execution_providers !== 'object' || data.execution_providers === null
        || !Array.isArray(data.gpus) || !Array.isArray(data.runs)) {
        throw new Error('Invalid system information');
    }
    return data;
}

export interface SystemInformationState {
    info: SystemInformation | null;
    loading: boolean;
    /** The last request's failure, shown as a diagnostic; it never disables a refresh. */
    error: string | null;
}

/**
 * Fetch the system information on every connect, so a restarted server answers for itself, and on `refresh()`.
 * A disconnect empties it and makes an answer still on its way obsolete: only the newest request is kept.
 */
export function watchSystemInformation(transport: Pick<TransportService, 'on' | 'off' | 'getState'>,
    load: (signal: AbortSignal) => Promise<SystemInformation>,
    onState: (state: SystemInformationState) => void): {refresh: () => void; stop: () => void} {
    let state: SystemInformationState = {info: null, loading: false, error: null};
    let controller: AbortController | null = null;
    const set = (next: Partial<SystemInformationState>) => { state = {...state, ...next}; onState(state); };
    const cancel = () => { controller?.abort(); controller = null; };
    const refresh = () => {
        cancel();
        const current = controller = new AbortController();
        set({loading: true, error: null});
        load(current.signal).then(
            info => { if (controller === current) { controller = null; set({info, loading: false}); } },
            (error: unknown) => {
                if (controller === current) { controller = null; set({loading: false, error: error instanceof Error ? error.message : String(error)}); }
            });
    };
    const onConnection = (connection: ConnectionState) => {
        if (connection === ConnectionState.CONNECTED) refresh();
        else { cancel(); set({info: null, loading: false, error: null}); }
    };
    transport.on('state-change', onConnection);
    if (transport.getState() === ConnectionState.CONNECTED) refresh();
    return {refresh, stop: () => { cancel(); transport.off('state-change', onConnection); }};
}
