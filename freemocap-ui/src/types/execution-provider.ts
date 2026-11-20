/** A skellytracker EP key, as the server lists it. null = Auto, the server's recommendation. */
export type ExecutionProviderName = string;

/** A GPU that an EP can use, as skellytracker gives it. */
export interface ExecutionProviderDevice {
    key: string;
    name: string | null;
    vram_total_bytes: number | null;
}

/** skellytracker's check of an EP on one GPU of the server's host. The menu offers the pair only when it is `usable`. */
export interface ExecutionProviderCheck {
    device_key: string;
    certified: boolean;
    /** The last quick check of the EP on this GPU model here; null with none. */
    local_result: 'passed' | 'failed' | null;
    usable: boolean;
    /** 'unclean-exits': the local failure is two unclean exits in a row, not a failed quick check; null otherwise. */
    local_cause: 'unclean-exits' | null;
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
    /** One per GPU that passes the EP's floors; none for cpu and for an EP no GPU here can use. */
    checks: ExecutionProviderCheck[];
    /** skellytracker's `PackStatus.source` (`windows-ml` for an EP of the Windows ML catalog) and `state`; the server
     *  always sends both, optional so other uses of this type need not name them. */
    source?: string;
    state?: string;
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
