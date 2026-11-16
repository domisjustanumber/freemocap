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

/** The server's EPs in skellytracker's order, and whether the pipeline of each detector takes an EP. */
export interface ExecutionProviderCatalog {
    providers: ExecutionProviderOption[];
    detectorTakesExecutionProvider: Record<string, boolean>;
}
