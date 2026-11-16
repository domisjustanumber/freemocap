// The skeleton detector's setting rows, shared by the posthoc Mocap processing window and the realtime processing
// controls. Everything arrives through props: the caller owns the store and the server's provider list.
import type {ReactNode} from 'react';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import ValueSelector from '@/components/ui-components/ValueSelector';
import {type DetectorType, RTMPOSE_MODELS, type RTMPoseModelName} from '@/store/slices/mocap';
import type {ExecutionProviderName} from '@/types/execution-provider';

export const DETECTOR_INFO = {
    title: "Skeleton detector",
    text: <>
        <p><strong>RTMW</strong> — body, hand and face keypoints from the wholebody model, following YOLOX person detection.</p>
        <p><strong>MediaPipe</strong> — separate pose, cropped hand and face detectors.</p>
        <p><em>The detector decides which parameters below apply.</em></p>
    </>,
};

export const EXECUTION_PROVIDER_INFO = {
    title: 'Execution provider',
    text: 'Auto retains the pipeline default. Choices are advertised by the server runtime; session startup verifies the selected provider can load.',
};

export const MODEL_INFO = {
    title: "Model",
    text: <>
        <p><strong>High Res</strong> estimates from a larger input crop: more accurate on small or distant people, and slower.</p>
        <p><strong>Fast</strong> trades accuracy for runtime. <strong>Default</strong> sits between the two.</p>
    </>,
};

export const CONFIDENCE_INFO = {
    title: "Confidence threshold",
    text: <>
        <p>Keypoints detected below this confidence are <strong>discarded before triangulation</strong>, so they never contribute to a 3D estimate.</p>
        <p><em>Raise it to reject noisy detections; lower it to keep sparse ones and rely on outlier rejection instead.</em></p>
    </>,
};

export const CHARUCO_INFO = {
    title: "Charuco board detection settings",
    text: <>
        <p><strong>Board layout and square size</strong> come from Charuco Board Settings.</p>
        <p><strong>AUTO</strong> selects the layout. You must still enter the <em>measured square size.</em></p>
    </>,
};

export const BOARD_GROUP_INFO = {
    title: "Board",
    text: <>
        <p>A Charuco board detected alongside the skeleton, reconstructed as its own rigid object in the same capture volume.</p>
        <p><em>Useful as a known reference for the ground plane and for checking reconstruction accuracy against a real measured object.</em></p>
    </>,
};

interface Info {title: string; text: ReactNode}

/**
 * What the realtime Skeleton Setup dialog said under its detector choice, word for word. The realtime rows show the
 * selected detector's note in the explanations of the rows it is about: the detector and, where the detector has one,
 * the execution provider. The posthoc explanations stay as they are.
 */
const REALTIME_DETECTOR_NOTES = {
    rtmpose: '133 keypoints (body, hands, face) via YOLOX + RTMW. Uses GPU batched inference when available.',
    mediapipe: 'Body + hands + face via MediaPipe. CPU-only; runs per-camera without GPU batching.',
} satisfies Partial<Record<DetectorType, string>>;

/** An explanation with a note as one more paragraph after its own. */
const withNote = (info: Info, note: string): Info =>
    ({title: info.title, text: <>{typeof info.text === 'string' ? <p>{info.text}</p> : info.text}<p>{note}</p></>});
/** An explanation with each detector's note, by detector. */
const withDetectorNotes = (info: Info): Map<string, Info> =>
    new Map(Object.entries(REALTIME_DETECTOR_NOTES).map(([detector, note]) => [detector, withNote(info, note)]));

// Built once, so a row's explanation is the same object on every render.
const REALTIME_DETECTOR_INFO = withDetectorNotes(DETECTOR_INFO);
const REALTIME_PROVIDER_INFO = withDetectorNotes(EXECUTION_PROVIDER_INFO);

export interface DetectorSettingsValue {
    detector: DetectorType; model: RTMPoseModelName; provider: ExecutionProviderName | null; confidence: number;
}

interface DetectorSettingRowsProps {
    value: DetectorSettingsValue;
    /** Receives only the fields a control changes. */
    onChange: (change: Partial<DetectorSettingsValue>) => void;
    detectors: readonly {label: string; value: DetectorType}[];
    /** The execution providers to offer; the one with no value is Auto. */
    providerOptions: readonly {label: string; value: ExecutionProviderName | null}[];
    context: 'posthoc' | 'realtime';
    /** 'key' is the detector and, for RTMW, its model row. 'all' is every row the detector has. */
    rows: 'all' | 'key';
    /** What the rows belong to is switched off: they stay on screen, dimmed. */
    inactive?: boolean;
}

export function DetectorSettingRows({value, onChange, detectors, providerOptions, context, rows, inactive = false}: DetectorSettingRowsProps) {
    const {detector} = value;
    const all = rows === 'all';
    const rtmw = detector === 'rtmpose';
    const realtime = context === 'realtime';
    const detectorInfo = (realtime && REALTIME_DETECTOR_INFO.get(detector)) || DETECTOR_INFO;
    const providerInfo = (realtime && REALTIME_PROVIDER_INFO.get(detector)) || EXECUTION_PROVIDER_INFO;

    return <>
        {/* In the posthoc section the detector reframes every row beneath it, so it leads the section. */}
        <SettingRow promoted={context === 'posthoc'} inactive={inactive} label="Skeleton detector" info={detectorInfo}
            control={<SettingSelectInput label="Skeleton detector" value={detector} options={detectors}
                onChange={(selected: DetectorType) => onChange({detector: selected})}/>}/>

        {all && rtmw && <SettingRow inactive={inactive} label="Execution provider" info={providerInfo}
            control={<SettingSelectInput label="Execution provider" value={value.provider ?? 'auto'}
                options={providerOptions.map(option => ({...option, value: option.value ?? 'auto' as const}))}
                onChange={(provider: ExecutionProviderName | 'auto') => onChange({provider: provider === 'auto' ? null : provider})}/>}/>}

        {rtmw && <SettingRow inactive={inactive} label="Model" info={MODEL_INFO}
            control={<SettingSelectInput label="RTMPose model" value={value.model}
                options={RTMPOSE_MODELS} onChange={(model: RTMPoseModelName) => onChange({model})}/>}/>}

        {all && rtmw && <SettingRow inactive={inactive} label="Confidence threshold" info={CONFIDENCE_INFO}
            control={<ValueSelector ariaLabel="Confidence threshold" value={value.confidence} min={0} max={1}
                step={realtime ? 0.0005 : 0.001} unit="" onChange={confidence => onChange({confidence})}/>}/>}
    </>;
}
