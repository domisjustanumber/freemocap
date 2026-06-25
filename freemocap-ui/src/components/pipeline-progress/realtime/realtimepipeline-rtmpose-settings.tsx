import React, {useEffect, useRef} from 'react';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import IconButton from '@/components/ui-components/IconButton';
import GpuCapabilitiesSummary from '@/components/ui-components/GpuCapabilitiesSummary';
import {ExecutionProviderConfigPanel} from '@/components/control-panels/realtime-panel/ExecutionProviderConfigPanel';
import {RtmposeModelConfigPanel} from '@/components/control-panels/realtime-panel/RtmposeModelConfigPanel';
import {useRealtimePipelineSync} from '@/hooks/useRealtimePipelineSync';
import {defaultRtmposeDetectorConfig, RtmposeDetectorConfig} from '@/store/slices/realtime/realtime-types';

interface RTPRtmposeSkeletonSettingsProps {
    open: boolean;
    onClose: () => void;
}

const RTPRtmposeSkeletonSettings: React.FC<RTPRtmposeSkeletonSettingsProps> = ({open, onClose}) => {
    const modalRef = useRef<HTMLDivElement>(null);
    const {applyOrUpdatePipelineConfig, pipelineConfig, cameraNodeConfig} = useRealtimePipelineSync();

    const handleUpdateRtmposeDetectorConfig = (updates: Partial<RtmposeDetectorConfig>) => {
        const current = cameraNodeConfig.skeleton_detector_config ?? defaultRtmposeDetectorConfig;
        applyOrUpdatePipelineConfig({
            ...pipelineConfig,
            camera_node_config: {
                ...cameraNodeConfig,
                skeleton_detector_config: {
                    ...current,
                    ...updates,
                },
            },
        });
    };

    useEffect(() => {
        if (!open) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };

        const handleClickOutside = (e: MouseEvent) => {
            if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
                onClose();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        document.addEventListener('mousedown', handleClickOutside);

        return () => {
            window.removeEventListener('keydown', handleKeyDown);
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div
            ref={modalRef}
            className="RTP-settings-flyout RTP-skeleton-settings-flyout pos-abs top-5 right-0 draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1"
        >
            <div className="gap-1 flex flex-col right-0 p-2 bg-middark br-1 z-1">
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text="Skeleton Settings" />
                    <IconButton icon="close-icon" onClick={onClose} />
                </div>

                <ExecutionProviderConfigPanel onConfigChange={applyOrUpdatePipelineConfig} />

                <div
                    style={{
                        height: 1,
                        backgroundColor: 'var(--color-border-secondary)',
                    }}
                />

                <GpuCapabilitiesSummary showExecutionProvider={false} />

                <div
                    style={{
                        height: 1,
                        backgroundColor: 'var(--color-border-secondary)',
                    }}
                />

                <RtmposeModelConfigPanel updateDetectorConfig={handleUpdateRtmposeDetectorConfig} />
            </div>
        </div>
    );
};

export default RTPRtmposeSkeletonSettings;
