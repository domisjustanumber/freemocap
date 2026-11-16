/** The skellytracker 2.0 EP keys. null = Auto, the server's recommendation; trt is retained only for saved-config migration. */
export type ExecutionProviderName = "cpu" | "coreml" | "cuda" | "trt-rtx" | "trt";

export const EXECUTION_PROVIDERS: { label: string; value: ExecutionProviderName | null }[] = [
    { label: "Auto", value: null },
    { label: "CUDA", value: "cuda" },
    { label: "TensorRT RTX", value: "trt-rtx" },
    { label: "CoreML", value: "coreml" },
    { label: "CPU", value: "cpu" },
];
