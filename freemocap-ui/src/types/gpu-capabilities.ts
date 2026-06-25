export type ExecutionProviderName =
    | 'trt-trx'
    | 'trt'
    | 'cuda'
    | 'directml'
    | 'coreml'
    | 'cpu';

export interface GpuInfoDto {
    id: string;
    name: string;
    vendor: string;
    vram_bytes: number | null;
    online: boolean;
    driver_version: string | null;
    cuda_driver_max: string | null;
    cuda_required_min: string | null;
    cuda_meets_nvidia_eps: boolean | null;
}

export interface ExecutionProviderCapabilitiesDto {
    fixed_batch_sizes: boolean;
    downcasting: boolean;
    quantization: boolean;
}

export interface ExecutionProviderInfoDto {
    id: ExecutionProviderName;
    display_name: string;
    available: boolean;
    recommended: boolean;
    optimal: boolean;
    install_recommended: boolean;
    driver_cuda_compatible: boolean | null;
    capabilities: ExecutionProviderCapabilitiesDto;
    doc_url: string;
}

export interface ExecutionProvidersInfoDto {
    providers: ExecutionProviderInfoDto[];
    recommended_provider_id: ExecutionProviderName | null;
    optimal_provider_id: ExecutionProviderName | null;
    install_recommended_provider_id: ExecutionProviderName | null;
}

export interface ModelCatalogEntryDto {
    id: string;
    display_name: string;
}

export interface PoseModelInfoDto extends ModelCatalogEntryDto {
    requires_detector: boolean;
}

export interface ModeDefaultsDto {
    detector_model: string;
    pose_model: string;
}

export interface GpuCapabilitiesResponse {
    gpus: GpuInfoDto[];
    execution_providers: ExecutionProvidersInfoDto;
    detection_models: ModelCatalogEntryDto[];
    pose_models: PoseModelInfoDto[];
    mode_defaults: Record<string, ModeDefaultsDto>;
}

/** Full UI labels — TensorRT RTX is distinct from legacy TensorRT (`trt`). */
export const EXECUTION_PROVIDER_DISPLAY_LABELS: Record<ExecutionProviderName, string> = {
    'trt-trx': 'TensorRT RTX',
    trt: 'TensorRT',
    cuda: 'CUDA',
    directml: 'DirectML',
    coreml: 'CoreML',
    cpu: 'CPU',
};

export const EXECUTION_PROVIDER_SHORT_LABELS: Record<ExecutionProviderName, string> = {
    'trt-trx': 'RTX',
    trt: 'TRT',
    cuda: 'CUDA',
    directml: 'DirectML',
    coreml: 'CoreML',
    cpu: 'CPU',
};

export function executionProviderDisplayLabel(id: string | null | undefined): string {
    if (!id) return 'Auto';
    return EXECUTION_PROVIDER_DISPLAY_LABELS[id as ExecutionProviderName] ?? id;
}

export function executionProviderShortLabel(id: string | null | undefined): string {
    if (!id) return 'Auto';
    return EXECUTION_PROVIDER_SHORT_LABELS[id as ExecutionProviderName] ?? id.toUpperCase();
}

export function formatVramBytes(vramBytes: number | null): string {
    if (vramBytes == null || vramBytes <= 0) return 'unknown';
    const gib = vramBytes / (1024 ** 3);
    return `${gib.toFixed(1)} GiB`;
}
