/** A skellytracker EP key, as the server lists it. null = Auto, the server's recommendation. */
export type ExecutionProviderName = string;

/** A GPU that an EP can use, as skellytracker gives it. */
export interface ExecutionProviderDevice {
    key: string;
    name: string | null;
    vram_total_bytes: number | null;
}

/** An EP of the server's host, as skellytracker gives it. */
export interface ExecutionProviderOption {
    key: ExecutionProviderName;
    label: string;
    description: string;
    usable: boolean;
    install_hint: string | null;
    uses_gpu: boolean;
    devices: ExecutionProviderDevice[];
}

/** An offer of skellytracker's Auto recommendation for the server's host (install a pack, update a driver), as it gives it. */
export interface ExecutionProviderOffer {
    kind: string;
    ep_key: ExecutionProviderName | null;
    download_bytes: number | null;
    disk_bytes: number | null;
    licence_url: string | null;
    note: string;
}

/** The server's EPs in skellytracker's order, whether the pipeline of each detector takes an EP, and the Auto offers. */
export interface ExecutionProviderCatalog {
    providers: ExecutionProviderOption[];
    detectorTakesExecutionProvider: Record<string, boolean>;
    autoOffers: ExecutionProviderOffer[];
}
