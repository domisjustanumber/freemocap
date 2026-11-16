// The skeleton detector's setting rows, shared by the posthoc Mocap processing window and the realtime processing
// controls. Everything arrives through props: the caller owns the store and the server's provider list.
import type {ReactNode} from 'react';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import ValueSelector from '@/components/ui-components/ValueSelector';
import {type DetectorType, RTMPOSE_MODELS, type RTMPoseModelName} from '@/store/slices/mocap';
import type {ExecutionProviderName} from '@/types/execution-provider';
import type {ExecutionProviderChoices} from '@/hooks/useExecutionProviderOptions';

export const DETECTOR_INFO = {
    title: "Skeleton detector",
    text: <>
        <p><strong>RTMW</strong> — body, hand and face keypoints from the wholebody model, following YOLOX person detection.</p>
        <p><strong>MediaPipe</strong> — separate pose, cropped hand and face detectors.</p>
        <p><em>The detector decides which parameters below apply.</em></p>
    </>,
};

export const DEVICE_INFO = {
    title: 'Device',
    text: <p>The GPU that the chosen execution provider runs on. <strong>Auto</strong> lets SkellyTracker choose.</p>,
};

/** A device as the select shows it: its name and VRAM, as skellytracker gives them. */
const deviceLabel = ({key, name, vram_total_bytes}: {key: string; name: string | null; vram_total_bytes: number | null}) =>
    `${name ?? key}${vram_total_bytes === null ? '' : ` (${(vram_total_bytes / 2 ** 30).toFixed(1)} GiB)`}`;

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
 * What the realtime Skeleton Setup dialog said under its detector choice. The realtime detector row shows the
 * selected detector's note in its explanation; what runs on which hardware comes from SkellyTracker's EP sentences.
 */
export const REALTIME_DETECTOR_NOTES = {
    rtmpose: '133 keypoints (body, hands, face) via YOLOX + RTMW.',
    mediapipe: 'Body + hands + face via MediaPipe.',
} satisfies Partial<Record<DetectorType, string>>;

/** An explanation with a note as one more paragraph after its own. */
const withNote = (info: Info, note: string): Info =>
    ({title: info.title, text: <>{typeof info.text === 'string' ? <p>{info.text}</p> : info.text}<p>{note}</p></>});
/** An explanation with each detector's note, by detector. */
const withDetectorNotes = (info: Info): Map<string, Info> =>
    new Map(Object.entries(REALTIME_DETECTOR_NOTES).map(([detector, note]) => [detector, withNote(info, note)]));

// Built once, so a row's explanation is the same object on every render.
const REALTIME_DETECTOR_INFO = withDetectorNotes(DETECTOR_INFO);

export interface DetectorSettingsValue {
    detector: DetectorType; model: RTMPoseModelName; provider: ExecutionProviderName | null; confidence: number;
    /** A skellytracker device key of the chosen EP; null = skellytracker's choice. */
    device: string | null;
}

interface DetectorSettingRowsProps {
    value: DetectorSettingsValue;
    /** Receives only the fields a control changes. */
    onChange: (change: Partial<DetectorSettingsValue>) => void;
    detectors: readonly {label: string; value: DetectorType}[];
    /** The server's execution provider choices (the one with no value is Auto), their explanation, and which detectors take one. */
    providers: ExecutionProviderChoices;
    context: 'posthoc' | 'realtime';
    /** 'key' is the detector and, for RTMW, its model row. 'all' is every row the detector has. */
    rows: 'all' | 'key';
    /** What the rows belong to is switched off: they stay on screen, dimmed. */
    inactive?: boolean;
}

export function DetectorSettingRows({value, onChange, detectors, providers, context, rows, inactive = false}: DetectorSettingRowsProps) {
    const {detector} = value;
    const all = rows === 'all';
    const rtmw = detector === 'rtmpose';
    const realtime = context === 'realtime';
    const detectorInfo = (realtime && REALTIME_DETECTOR_INFO.get(detector)) || DETECTOR_INFO;
    const takesProvider = all && providers.takesExecutionProvider(detector);
    const devices = takesProvider ? providers.devicesOf(value.provider) : [];

    return <>
        {/* In the posthoc section the detector reframes every row beneath it, so it leads the section. */}
        <SettingRow promoted={context === 'posthoc'} inactive={inactive} label="Skeleton detector" info={detectorInfo}
            control={<SettingSelectInput label="Skeleton detector" value={detector} options={detectors}
                onChange={(selected: DetectorType) => onChange({detector: selected})}/>}/>

        {takesProvider && <SettingRow inactive={inactive} label="Execution provider" info={providers.info}
            control={<SettingSelectInput label="Execution provider" value={value.provider ?? 'auto'}
                options={providers.options.map(option => ({...option, value: option.value ?? 'auto' as const}))}
                onChange={(provider: ExecutionProviderName | 'auto') => onChange({provider: provider === 'auto' ? null : provider, device: null})}/>}/>}

        {devices.length > 1 && <SettingRow inactive={inactive} label="Device" info={DEVICE_INFO}
            control={<SettingSelectInput label="Device" value={value.device ?? 'auto'}
                options={[{label: 'Auto', value: 'auto'}, ...devices.map(device => ({label: deviceLabel(device), value: device.key}))]}
                onChange={(device: string) => onChange({device: device === 'auto' ? null : device})}/>}/>}

        {rtmw && <SettingRow inactive={inactive} label="Model" info={MODEL_INFO}
            control={<SettingSelectInput label="RTMPose model" value={value.model}
                options={RTMPOSE_MODELS} onChange={(model: RTMPoseModelName) => onChange({model})}/>}/>}

        {all && rtmw && <SettingRow inactive={inactive} label="Confidence threshold" info={CONFIDENCE_INFO}
            control={<ValueSelector ariaLabel="Confidence threshold" value={value.confidence} min={0} max={1}
                step={realtime ? 0.0005 : 0.001} unit="" onChange={confidence => onChange({confidence})}/>}/>}
    </>;
}
