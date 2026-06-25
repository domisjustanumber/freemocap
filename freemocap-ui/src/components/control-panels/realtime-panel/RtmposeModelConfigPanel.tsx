import React, {useCallback, useMemo} from 'react';
import NameDropdownSelector from '@/components/ui-components/NameDropdownSelector';
import {useAppSelector} from '@/store/hooks';
import {selectGpuCapabilities, selectRtmposeDetectorConfig} from '@/store/slices/realtime';
import {RtmposeDetectorConfig, RtmposeMode} from '@/store/slices/realtime/realtime-types';

interface RtmposeModelConfigPanelProps {
    updateDetectorConfig: (updates: Partial<RtmposeDetectorConfig>) => void;
}

function effectiveModelId(
    explicit: string | null | undefined,
    mode: RtmposeMode,
    modeDefaults: Record<string, { detector_model: string; pose_model: string }> | undefined,
    field: 'detector_model' | 'pose_model',
): string {
    if (explicit) return explicit;
    const defaults = modeDefaults?.[mode];
    return defaults?.[field] ?? '';
}

export const RtmposeModelConfigPanel: React.FC<RtmposeModelConfigPanelProps> = ({
    updateDetectorConfig,
}) => {
    const detectorConfig = useAppSelector(selectRtmposeDetectorConfig);
    const gpuCapabilities = useAppSelector(selectGpuCapabilities);

    const mode = detectorConfig?.mode ?? 'balanced';
    const modeDefaults = gpuCapabilities?.mode_defaults;

    const detectionModels = gpuCapabilities?.detection_models ?? [];
    const poseModels = gpuCapabilities?.pose_models ?? [];

    const selectedDetector = useMemo(
        () => effectiveModelId(detectorConfig?.detector_model, mode, modeDefaults, 'detector_model'),
        [detectorConfig?.detector_model, mode, modeDefaults],
    );

    const selectedPose = useMemo(
        () => effectiveModelId(detectorConfig?.pose_model, mode, modeDefaults, 'pose_model'),
        [detectorConfig?.pose_model, mode, modeDefaults],
    );

    const detectorOptions = useMemo(
        () => detectionModels.map((m) => m.display_name),
        [detectionModels],
    );
    const poseOptions = useMemo(
        () => poseModels.map((m) => m.display_name),
        [poseModels],
    );

    const detectorLabelToId = useMemo(
        () => Object.fromEntries(detectionModels.map((m) => [m.display_name, m.id])),
        [detectionModels],
    );
    const poseLabelToId = useMemo(
        () => Object.fromEntries(poseModels.map((m) => [m.display_name, m.id])),
        [poseModels],
    );

    const selectedDetectorLabel =
        detectionModels.find((m) => m.id === selectedDetector)?.display_name ?? '';
    const selectedPoseLabel =
        poseModels.find((m) => m.id === selectedPose)?.display_name ?? '';

    const handleDetectorChange = useCallback(
        (label: string) => {
            const id = detectorLabelToId[label];
            if (id) updateDetectorConfig({detector_model: id});
        },
        [detectorLabelToId, updateDetectorConfig],
    );

    const handlePoseChange = useCallback(
        (label: string) => {
            const id = poseLabelToId[label];
            if (id) updateDetectorConfig({pose_model: id});
        },
        [poseLabelToId, updateDetectorConfig],
    );

    return (
        <div className="flex flex-col gap-1">
            <p className="text sm text-gray p-1">RTMPose models</p>

            <div className="flex flex-col gap-1 p-1">
                <span className="text sm text-gray">Detector model</span>
                <NameDropdownSelector
                    key={selectedDetectorLabel}
                    options={detectorOptions}
                    initialValue={selectedDetectorLabel}
                    onChange={handleDetectorChange}
                    className="w-full"
                />
            </div>

            <div className="flex flex-col gap-1 p-1">
                <span className="text sm text-gray">Pose model</span>
                <NameDropdownSelector
                    key={selectedPoseLabel}
                    options={poseOptions}
                    initialValue={selectedPoseLabel}
                    onChange={handlePoseChange}
                    className="w-full"
                />
            </div>

            {!gpuCapabilities && (
                <p className="text sm text-gray p-1">
                    Connect to the server to load model catalog.
                </p>
            )}
        </div>
    );
};
