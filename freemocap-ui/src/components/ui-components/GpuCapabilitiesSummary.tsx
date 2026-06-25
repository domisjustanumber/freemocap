import React from 'react';
import {useAppSelector} from '@/store/hooks';
import {selectDisplayedExecutionProvider, selectGpuCapabilities} from '@/store/slices/realtime';
import {
    executionProviderDisplayLabel,
    executionProviderShortLabel,
    formatVramBytes,
    GpuInfoDto,
} from '@/types/gpu-capabilities';

export function DetectedGpuList({gpus}: {gpus: GpuInfoDto[]}): React.ReactNode {
    if (!gpus.length) {
        return <p className="text sm text-gray">No GPUs detected</p>;
    }

    return gpus.map((gpu) => (
        <div key={gpu.id} className="flex flex-col gap-0">
            <p className="text sm text-white">{gpu.name}</p>
            <p className="text sm text-gray">
                Vendor: {gpu.vendor}
                {gpu.vram_bytes != null ? ` · VRAM: ${formatVramBytes(gpu.vram_bytes)}` : ''}
            </p>
            {gpu.driver_version && (
                <p className="text sm text-gray">Driver: {gpu.driver_version}</p>
            )}
            {gpu.vendor === 'nvidia' && gpu.cuda_driver_max && (
                <p className="text sm text-gray">
                    CUDA max: {gpu.cuda_driver_max}
                    {gpu.cuda_required_min ? ` (required ≥ ${gpu.cuda_required_min})` : ''}
                </p>
            )}
        </div>
    ));
}

interface GpuCapabilitiesSummaryProps {
    showExecutionProvider?: boolean;
}

export const GpuCapabilitiesSummary: React.FC<GpuCapabilitiesSummaryProps> = ({
    showExecutionProvider = true,
}) => {
    const gpuCapabilities = useAppSelector(selectGpuCapabilities);
    const displayedProvider = useAppSelector(selectDisplayedExecutionProvider);

    if (!gpuCapabilities) {
        return <p className="text sm text-gray p-1">Loading GPU info…</p>;
    }

    const epFullLabel = executionProviderDisplayLabel(displayedProvider);
    const epShortLabel = executionProviderShortLabel(displayedProvider);

    return (
        <div className="flex flex-col gap-1 p-1">
            {showExecutionProvider && (
                <p className="text sm text-white">
                    Execution provider: {epFullLabel}
                    {epShortLabel !== epFullLabel ? ` (${epShortLabel})` : ''}
                </p>
            )}
            <p className="text bg text-white">Detected GPUs</p>
            <DetectedGpuList gpus={gpuCapabilities.gpus} />
        </div>
    );
};

export default GpuCapabilitiesSummary;
