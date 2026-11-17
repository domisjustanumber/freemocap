import {useState} from 'react';
import {RTMW_CONFIDENCE_THRESHOLD} from '@/types/rtmw-confidence';
import {useRealtimePipelineSync} from '@/hooks/useRealtimePipelineSync';
import {useExecutionProviderOptions} from '@/hooks/useExecutionProviderOptions';
import {DetectorSettingRows, type DetectorSettingsValue} from '@/components/mocap-setup/detector-setting-rows';
import {DETECTOR_OPTIONS} from '@/components/mocap-setup/detector-options';
import TrackerSettingsDialog from '@/components/mocap-setup/tracker-settings-dialog';
import ProcessingOutline from '@/components/mocap-setup/processing-outline';
import StageSection from '@/components/mocap-setup/stage-section';
import type {ProcessingSection} from '@/components/mocap-setup/processing-sections';
import SkeletonAnchorSetting from '@/components/mocap-setup/skeleton-anchor-setting';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import {TemporalFilterControls} from '@/components/control-panels/realtime-panel/TemporalFilterControls';
import {StreamingOutputsPanel} from '@/components/control-panels/streaming-outputs/StreamingOutputsPanel';
import './realtime-processing.css';
import '@/components/mocap-setup/mocap-processing.css';

type Section = 'tracking' | 'triangulation' | 'filtering' | 'reconstruction' | 'outputs';

/** Presentation reuses posthoc sections; all commands and observations use the existing realtime interfaces. */
export default function RealtimeProcessingSettings({onClose}: {onClose: () => void}) {
    const [active, setActive] = useState<Section>('tracking');
    const {pipelineConfig, cameraNodeConfig: camera, aggregatorConfig: aggregator, applyOrUpdatePipelineConfig} = useRealtimePipelineSync();
    const provider = pipelineConfig.skeleton_inference_node_config.execution_provider ?? null;
    const device = pipelineConfig.skeleton_inference_node_config.execution_device ?? null;
    const providers = useExecutionProviderOptions(provider);
    const value: DetectorSettingsValue = {
        detector: camera.detector_type ?? 'rtmpose', model: camera.rtmpose_model_name ?? 'rtmw-x-l_256x192',
        provider, confidence: camera.rtmpose_confidence_threshold ?? RTMW_CONFIDENCE_THRESHOLD, device,
    };
    const changeDetector = (change: Partial<DetectorSettingsValue>) => applyOrUpdatePipelineConfig({
        ...pipelineConfig,
        camera_node_config: {...camera,
            detector_type: change.detector ?? camera.detector_type,
            rtmpose_model_name: change.model ?? camera.rtmpose_model_name,
            rtmpose_confidence_threshold: change.confidence ?? camera.rtmpose_confidence_threshold},
        skeleton_inference_node_config: {...pipelineConfig.skeleton_inference_node_config,
            execution_provider: change.provider !== undefined ? change.provider : provider,
            execution_device: change.device !== undefined ? change.device : device},
    });
    const toggle = (label: string, enabled: boolean, update: (enabled: boolean) => void) =>
        <SettingToggleSwitch label={label} isToggled={enabled} onToggle={update}/>;
    const sections: ProcessingSection<Section>[] = [
        {id: 'tracking', number: 1, title: '2D tracking', stage: null, summary: null,
            content: <>
                <SettingRow label="Track person" info={{title: 'Track person', text: 'Run the selected person detector on camera images.'}} control={toggle('Track person', camera.skeleton_tracking_enabled,
                    enabled => applyOrUpdatePipelineConfig({...pipelineConfig, camera_node_config: {...camera, skeleton_tracking_enabled: enabled}}))}/>
                <DetectorSettingRows value={value} onChange={changeDetector} detectors={DETECTOR_OPTIONS}
                    providers={providers} context="realtime" rows="all"/>
                {import.meta.env.DEV && value.detector === 'rtmpose' && <SettingRow label="Legacy tracker (benchmark)" info={{title: 'Legacy tracker (benchmark)', // Deleted at skellytracker stage 2.4 (legacy tracker benchmark).
                    text: 'Development only. Run the old skellytracker Tracker (YOLOX and RTMW x-l 256x192) instead of the 2.0 pipeline, to compare their timing in the pipeline metrics window. It runs on CPU or CUDA: Auto and TensorRT RTX use CUDA when it is usable, else CPU. Its scores are the old raw scores.'}} // Deleted at skellytracker stage 2.4 (legacy tracker benchmark).
                    control={toggle('Legacy tracker (benchmark)', pipelineConfig.skeleton_inference_node_config.legacy_tracker_benchmark ?? false, enabled => applyOrUpdatePipelineConfig({ // Deleted at skellytracker stage 2.4 (legacy tracker benchmark).
                        ...pipelineConfig, skeleton_inference_node_config: {...pipelineConfig.skeleton_inference_node_config, legacy_tracker_benchmark: enabled}}))}/>} {/* Deleted at skellytracker stage 2.4 (legacy tracker benchmark). */}
                <SettingRow label="Track Charuco board" info={{title: 'Track Charuco board', text: 'Detect the configured Charuco board alongside the person tracker.'}} control={toggle('Track Charuco board', camera.charuco_tracking_enabled,
                    enabled => applyOrUpdatePipelineConfig({...pipelineConfig, camera_node_config: {...camera, charuco_tracking_enabled: enabled}}))}/>
            </>},
        {id: 'triangulation', number: 2, title: 'Triangulation', stage: null, summary: null,
            toggle: toggle('Triangulation', aggregator.triangulation_enabled, enabled => applyOrUpdatePipelineConfig({
                ...pipelineConfig, aggregator_config: {...aggregator, triangulation_enabled: enabled}})),
            content: <p className="settings-note">Reconstruct 3D points from matching camera observations using the capture-volume calibration. Configure the calibration in the camera sidebar.</p>},
        {id: 'filtering', number: 3, title: 'Filtering and gap recovery', stage: null, summary: null,
            content: <TemporalFilterControls/>},
        {id: 'reconstruction', number: 4, title: 'Skeleton reconstruction', stage: null, summary: null,
            toggle: toggle('Fit skeleton', aggregator.skeleton_fitting_enabled, enabled => applyOrUpdatePipelineConfig({
                ...pipelineConfig, aggregator_config: {...aggregator, skeleton_fitting_enabled: enabled}})),
            content: <SkeletonAnchorSetting value={aggregator.anchor_segment_name} onChange={anchor_segment_name =>
                applyOrUpdatePipelineConfig({...pipelineConfig, aggregator_config: {...aggregator, anchor_segment_name}})}/>},
        {id: 'outputs', number: null, title: 'Streaming outputs', stage: null, after: true, summary: null,
            content: active === 'outputs' ? <StreamingOutputsPanel/> : null},
    ];
    const selected = sections.find(section => section.id === active)!;
    return <TrackerSettingsDialog title="Real-time processing settings" onClose={onClose}>
        <div className="realtime-processing-layout">
            <ProcessingOutline sections={sections} active={active} playback={false} states={null}
                label="Real-time processing stages" afterTitle="Outputs" onPick={setActive}/>
            <div className="realtime-processing-detail" key={active}>
                <StageSection section={selected} playback={false}>{selected.content}</StageSection>
            </div>
        </div>
    </TrackerSettingsDialog>;
}
