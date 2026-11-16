/** A skellytracker EP key, as the server lists it. null = Auto, the server's recommendation. */
export type ExecutionProviderName = string;

/** An EP that the server can use now, with skellytracker's label. */
export interface ExecutionProviderOption {
    key: ExecutionProviderName;
    label: string;
}
