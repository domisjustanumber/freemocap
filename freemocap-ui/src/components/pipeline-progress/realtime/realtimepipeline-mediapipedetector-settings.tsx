import React, {useCallback} from 'react';
import TrackerSettingsDialog from '@/components/mocap-setup/tracker-settings-dialog';
import ValueSelector from '@/components/ui-components/ValueSelector';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import {CONFIDENCE_INFO, MODEL_INFO} from '@/components/mocap-setup/detector-setting-rows';
import { useRealtimePipelineSync } from '@/hooks/useRealtimePipelineSync';
import { useExecutionProviderOptions } from '@/hooks/useExecutionProviderOptions';
import { DetectorType, ExecutionProviderName, RTMPOSE_MODELS, RTMPoseModelName } from '@/store/slices/mocap';
import { CameraNodeConfig } from '@/store/slices/realtime/realtime-types';
import { DETECTOR_OPTIONS } from '@/components/mocap-setup/detector-options';
import {RTMW_CONFIDENCE_THRESHOLD} from '@/types/rtmw-confidence';
import './realtime-settings.css';

interface RTPSkeletonSetupProps {
    open: boolean;
    onClose: () => void;
}

const DETECTOR_INFO = {
    title: 'Skeleton detector',
    text: <>
        <p><strong>RTMW</strong> — 133 keypoints (body, hands, face) via YOLOX + RTMW.</p>
        <p><strong>MediaPipe</strong> — body, hands and face.</p>
        <p><em>The detector decides which settings below apply.</em></p>
    </>,
};

const RTPSkeletonSetup: React.FC<RTPSkeletonSetupProps> = ({ open, onClose }) => {
    const { pipelineConfig, cameraNodeConfig, applyOrUpdatePipelineConfig } = useRealtimePipelineSync();

    const executionProvider = pipelineConfig.skeleton_inference_node_config?.execution_provider ?? null;
    const executionProviderOptions = useExecutionProviderOptions(executionProvider);

    const handleExecutionProviderChange = useCallback(
        (provider: ExecutionProviderName | null) => {
            applyOrUpdatePipelineConfig({
                ...pipelineConfig,
                skeleton_inference_node_config: { ...pipelineConfig.skeleton_inference_node_config, execution_provider: provider, execution_device: null },
            });
        },
        [applyOrUpdatePipelineConfig, pipelineConfig]
    );

    const detectorType: DetectorType = cameraNodeConfig.detector_type ?? "rtmpose";

    const handleCameraNodeUpdate = useCallback(
        (updates: Partial<CameraNodeConfig>) => {
            applyOrUpdatePipelineConfig({
                ...pipelineConfig,
                camera_node_config: { ...cameraNodeConfig, ...updates },
            });
        },
        [applyOrUpdatePipelineConfig, pipelineConfig, cameraNodeConfig]
    );

    if (!open) return null;

    return (
        <TrackerSettingsDialog title="Skeleton Setup" onClose={onClose}>
            <div className="realtime-skeleton-setup">
                {/* The detector reframes every row beneath it, so it leads. */}
                <SettingRow promoted label="Skeleton detector" info={DETECTOR_INFO}
                    control={<SettingSelectInput label="Skeleton detector" value={detectorType}
                        options={DETECTOR_OPTIONS}
                        onChange={(value: DetectorType) => handleCameraNodeUpdate({ detector_type: value })}/>}/>

                {executionProviderOptions.takesExecutionProvider(detectorType) &&
                    <SettingRow label="Execution provider" info={executionProviderOptions.info}
                        control={<SettingSelectInput label="Execution provider" value={executionProvider ?? 'auto'}
                            options={executionProviderOptions.options.map(option => ({...option, value: option.value ?? 'auto' as const}))}
                            onChange={(value: ExecutionProviderName | 'auto') => handleExecutionProviderChange(value === 'auto' ? null : value)}/>}/>}
                {detectorType === 'rtmpose' && <>
                    <SettingRow label="Model" info={MODEL_INFO}
                        control={<SettingSelectInput label="RTMPose model" value={cameraNodeConfig.rtmpose_model_name ?? "rtmw-x-l_256x192"}
                            options={RTMPOSE_MODELS}
                            onChange={(value: RTMPoseModelName) => handleCameraNodeUpdate({ rtmpose_model_name: value })}/>}/>
                    <SettingRow label="Confidence threshold" info={CONFIDENCE_INFO}
                        control={<ValueSelector ariaLabel="Confidence threshold" value={cameraNodeConfig.rtmpose_confidence_threshold ?? RTMW_CONFIDENCE_THRESHOLD}
                            min={0} max={1} step={0.0005} unit=""
                            onChange={(v) => handleCameraNodeUpdate({ rtmpose_confidence_threshold: v })}/>}/>
                </>}
            </div>
        </TrackerSettingsDialog>
    );
};

export default RTPSkeletonSetup;
