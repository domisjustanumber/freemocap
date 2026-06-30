import React, {useCallback, useMemo} from 'react';
import NameDropdownSelector from '@/components/ui-components/NameDropdownSelector';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    pipelineConfigUpdated,
    REALTIME_RESTART_REQUIRED_MESSAGE,
    realtimePipelineRestartRequired,
    selectGpuCapabilities,
    selectIsPipelineConnected,
    selectPipelineConfig,
    selectSkeletonInferenceNodeConfig,
} from '@/store/slices/realtime';
import {ExecutionProviderName, RealtimePipelineConfig, SkeletonInferenceNodeConfig} from '@/store/slices/realtime/realtime-types';
import {executionProviderDisplayLabel} from '@/types/gpu-capabilities';

interface ExecutionProviderConfigPanelProps {
    onConfigChange?: (config: RealtimePipelineConfig) => void;
}

function providerOptionLabel(
    providerId: string,
    flags: {recommended?: boolean; optimal?: boolean},
): string {
    let label = executionProviderDisplayLabel(providerId);
    if (flags.recommended) label += ' (Recommended)';
    else if (flags.optimal) label += ' (Optimal)';
    return label;
}

export const ExecutionProviderConfigPanel: React.FC<ExecutionProviderConfigPanelProps> = ({
    onConfigChange,
}) => {
    const dispatch = useAppDispatch();
    const pipelineConfig = useAppSelector(selectPipelineConfig);
    const isConnected = useAppSelector(selectIsPipelineConnected);
    const skeletonInfConfig = useAppSelector(selectSkeletonInferenceNodeConfig);
    const gpuCapabilities = useAppSelector(selectGpuCapabilities);

    const availableProviders = useMemo(
        () => gpuCapabilities?.execution_providers.providers.filter((p) => p.available) ?? [],
        [gpuCapabilities],
    );

    const recommendedId = gpuCapabilities?.execution_providers.recommended_provider_id ?? null;

    const {optionLabels, labelToValue} = useMemo(() => {
        const labels: string[] = [];
        const toValue: Record<string, string> = {};

        for (const provider of availableProviders) {
            const label = providerOptionLabel(provider.id, {
                recommended: provider.recommended,
                optimal: provider.optimal,
            });
            labels.push(label);
            toValue[label] = provider.id;
        }

        return {optionLabels: labels, labelToValue: toValue};
    }, [availableProviders]);

    const effectiveSelectedId: ExecutionProviderName | null =
        skeletonInfConfig?.execution_provider
        ?? recommendedId
        ?? (availableProviders[0]?.id as ExecutionProviderName | undefined)
        ?? null;

    const selectedLabel = useMemo(() => {
        if (!effectiveSelectedId) return '';
        const provider = availableProviders.find((p) => p.id === effectiveSelectedId);
        return provider
            ? providerOptionLabel(provider.id, {
                  recommended: provider.recommended,
                  optimal: provider.optimal,
              })
            : executionProviderDisplayLabel(effectiveSelectedId);
    }, [effectiveSelectedId, availableProviders]);

    const cudaDriverWarning = useMemo(() => {
        if (!gpuCapabilities) return null;

        const nvidiaGpuBelowRequired = gpuCapabilities.gpus.some(
            (g) => g.vendor === 'nvidia' && g.cuda_meets_nvidia_eps === false,
        );
        if (nvidiaGpuBelowRequired) {
            const gpu = gpuCapabilities.gpus.find(
                (g) => g.vendor === 'nvidia' && g.cuda_meets_nvidia_eps === false,
            );
            return (
                `NVIDIA driver CUDA max ${gpu?.cuda_driver_max ?? '?'} is below required ` +
                `${gpu?.cuda_required_min ?? '?'} for RTMPose NVIDIA extras. Update your GPU drivers.`
            );
        }

        const selectedEpId = effectiveSelectedId;
        const selectedEp = gpuCapabilities.execution_providers.providers.find(
            (p) => p.id === selectedEpId,
        );
        if (
            selectedEp &&
            ['cuda', 'trt', 'trt-trx'].includes(selectedEp.id) &&
            selectedEp.driver_cuda_compatible === false
        ) {
            return (
                `Selected execution provider (${executionProviderDisplayLabel(selectedEp.id)}) requires a newer NVIDIA ` +
                `driver CUDA version. Update your GPU drivers.`
            );
        }

        return null;
    }, [gpuCapabilities, effectiveSelectedId]);

    const applyConfig = useCallback(
        (execution_provider: ExecutionProviderName) => {
            const nextSkeletonInf: SkeletonInferenceNodeConfig = {
                ...pipelineConfig.skeleton_inference_node_config,
                execution_provider,
            };

            const newConfig: RealtimePipelineConfig = {
                ...pipelineConfig,
                skeleton_inference_node_config: nextSkeletonInf,
            };

            if (onConfigChange) {
                onConfigChange(newConfig);
                return;
            }

            dispatch(pipelineConfigUpdated(newConfig));
            if (isConnected) {
                dispatch(realtimePipelineRestartRequired({message: REALTIME_RESTART_REQUIRED_MESSAGE}));
            }
        },
        [dispatch, isConnected, onConfigChange, pipelineConfig],
    );

    const handleChange = (label: string) => {
        const raw = labelToValue[label];
        if (!raw) return;
        applyConfig(raw as ExecutionProviderName);
    };

    const installHint = gpuCapabilities?.execution_providers.install_recommended_provider_id;
    const optimalEp = gpuCapabilities?.execution_providers.providers.find(
        (p) => p.id === gpuCapabilities.execution_providers.optimal_provider_id,
    );

    return (
        <div className="flex flex-col gap-1 mb-1">
            {gpuCapabilities && optionLabels.length > 0 ? (
                <div className="flex flex-col gap-1 p-1">
                    <span className="text sm text-gray">Execution provider</span>
                    <NameDropdownSelector
                        key={selectedLabel}
                        options={optionLabels}
                        initialValue={selectedLabel}
                        onChange={handleChange}
                        className="w-full"
                    />
                </div>
            ) : (
                <p className="text sm text-gray p-1">
                    Connect to the server to load execution providers.
                </p>
            )}

            {installHint && optimalEp && (
                <p className="text sm text-gray p-1">
                    Hardware-optimal provider: {executionProviderDisplayLabel(optimalEp.id)}
                    {installHint !== optimalEp.id ? ` (${installHint})` : ''} — install matching skellytracker extra for best performance.
                </p>
            )}

            {cudaDriverWarning && (
                <p className="text sm text-warning p-2 border-1 border-warning br-1 text-wrap">
                    {cudaDriverWarning}
                </p>
            )}

            <div
                style={{
                    height: 1,
                    backgroundColor: 'var(--color-border-secondary)',
                    marginTop: 4,
                }}
            />
        </div>
    );
};
