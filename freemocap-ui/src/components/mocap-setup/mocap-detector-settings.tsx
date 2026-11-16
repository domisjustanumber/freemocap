import {useExecutionProviderOptions} from "@/hooks/useExecutionProviderOptions";
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import ButtonSm from '@/components/ui-components/ButtonSm';
import {mocapCharucoTrackingChanged, executionProviderNoticeDismissed, selectExecutionProviderMigration} from '@/store/slices/mocap';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingsGroupHeading from '@/components/common/settings-layout/settings-group-heading';
import SettingToggleSwitch from '@/components/common/settings-layout/setting-toggle-switch';
import {useMocap} from '@/hooks/useMocap';
import {DETECTOR_OPTIONS} from './detector-options';
import {BOARD_GROUP_INFO, CHARUCO_INFO, DetectorSettingRows, type DetectorSettingsValue} from './detector-setting-rows';

export default function MocapDetectorSettings() {
    const dispatch = useAppDispatch();
    const detectBoard = useAppSelector(state => state.mocap.config.charucoTrackingEnabled);
    const migration = useAppSelector(selectExecutionProviderMigration);
    const {
        detectorType,
        rtmPoseModelName,
        rtmPoseConfidenceThreshold,
        executionProvider,
        executionDevice,
        setDetectorType,
        setRtmPoseModelName,
        setRtmPoseConfidenceThreshold,
        setExecutionProvider,
        setExecutionDevice,
    } = useMocap();
    const executionProviderOptions = useExecutionProviderOptions(executionProvider);

    const detector = detectorType ?? "rtmpose";
    const value: DetectorSettingsValue = {
        detector,
        model: rtmPoseModelName ?? "rtmw-x-l_256x192",
        provider: executionProvider ?? null,
        device: executionDevice ?? null,
        confidence: rtmPoseConfidenceThreshold ?? 0.4,
    };
    /** Each field the rows report goes to its own setting in the store. */
    const applyChange = (change: Partial<DetectorSettingsValue>) => {
        if (change.detector !== undefined) setDetectorType(change.detector);
        if (change.provider !== undefined) setExecutionProvider(change.provider);
        if (change.device !== undefined) setExecutionDevice(change.device);
        if (change.model !== undefined) setRtmPoseModelName(change.model);
        if (change.confidence !== undefined) setRtmPoseConfidenceThreshold(change.confidence);
    };

    const labelOf = (key: string | null) => executionProviderOptions.options.find(({value}) => value === key)?.label ?? key ?? 'Auto';
    return <>
        {migration?.status === 'pending' && <p className="settings-note" role="status">
            Checking the execution provider <strong>{migration.saved}</strong> saved by an earlier FreeMoCap version;
            processing waits for the server.</p>}
        {migration?.status === 'replaced' && <div role="status" className="settings-note settings-note-dismissable">
            <span>The execution provider <strong>{migration.saved}</strong> saved by an earlier FreeMoCap version was
                replaced by <strong>{labelOf(migration.replacement)}</strong>
                {migration.replacement === null ? ': SkellyTracker has no usable replacement on this computer' : ''}.
                {executionProviderOptions.installHintOf(migration.replacement) && <> {executionProviderOptions.installHintOf(migration.replacement)}</>}</span>
            <ButtonSm text="Dismiss" className="setting-action-button" onClick={() => dispatch(executionProviderNoticeDismissed())}/>
        </div>}
        <DetectorSettingRows value={value} onChange={applyChange} detectors={DETECTOR_OPTIONS}
            providers={executionProviderOptions} context="posthoc" rows="all"/>

        <SettingsGroupHeading text="Board" info={BOARD_GROUP_INFO}/>
        <SettingRow label="Detect and reconstruct Charuco board" info={CHARUCO_INFO}
            control={<SettingToggleSwitch label="Detect and reconstruct Charuco board" isToggled={detectBoard}
                onToggle={enabled => dispatch(mocapCharucoTrackingChanged(enabled))}/>}/>
    </>;
}
