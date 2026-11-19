import {useEffect} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import type {ExecutionProviderChoices} from '@/hooks/useExecutionProviderOptions';
import {
    PAIR_MARKERS, pairLabel, QUICK_CHECK_TEXT, quickCheckProgressText, quickCheckResultText,
} from '@/services/server/execution-providers';
import type {DetectorSettingsValue} from './detector-setting-rows';

/**
 * The quick check beside the EP setting (F3 to F10): the running check with its progress and cancel, the two-choice
 * prompt, the offer for a selection that needs a check, Auto's notice, the server's refusal of a start, and how the
 * last check ended. Shown from the server's `certification` state; the buttons never change label or disable.
 */
export function QuickCheckPanel({value, onChange, providers}: {
    value: DetectorSettingsValue; onChange: (change: Partial<DetectorSettingsValue>) => void; providers: ExecutionProviderChoices;
}) {
    const {certification, quickCheck} = providers;
    const items = certification?.items;
    const {passed, settle} = quickCheck;
    // A pass makes the choice the selection (F6), with the rows' current change handler.
    useEffect(() => {
        if (!passed) return;
        onChange(passed);
        settle();
    }, [passed, onChange, settle]);

    const detector = {detector_type: value.detector, rtmpose_model_name: value.model};
    const {prompt} = quickCheck;
    const selected = prompt ? undefined : providers.pairToCheck(value.provider, value.device);
    const faster = value.provider === null
        ? certification?.auto?.needs_check.find((pair): pair is {execution_provider: string; device_key: string} => pair.device_key !== undefined)
        : undefined;
    const run = certification?.run;
    const result = certification?.last_result;
    const action = (text: string, onClick: () => void) => <ButtonSm text={text} className="setting-action-button" onClick={onClick}/>;

    return <>
        {run && <div className="settings-note settings-note-dismissable" role="status">
            <span>{quickCheckProgressText(run, items)}</span>
            {action('Cancel check', quickCheck.cancel)}
        </div>}
        {prompt && <div className="settings-note settings-note-dismissable" role="alert">
            <span><strong>{pairLabel(prompt.pair, items)}</strong>: {PAIR_MARKERS[prompt.pair.state]}. A quick check on this
                machine decides whether it can run here.</span>
            {action('Run quick check', () => quickCheck.run(prompt.pair, prompt.change, detector))}
            {action('Not now', quickCheck.notNow)}
        </div>}
        {selected && <div className="settings-note settings-note-dismissable" role="status">
            <span><strong>{pairLabel(selected, items)}</strong>: {PAIR_MARKERS[selected.state]}. A start with it is refused
                until a quick check passes.</span>
            {action('Run quick check', () => quickCheck.run(selected, null, detector))}
        </div>}
        {faster && <div className="settings-note settings-note-dismissable" role="status">
            <span>A faster option needs a quick check on this machine: {pairLabel(faster, items)}.</span>
            {action('Run quick check', () => quickCheck.run(faster, null, detector))}
        </div>}
        {quickCheck.refusal && <p className="settings-note settings-note-error" role="alert">
            {QUICK_CHECK_TEXT.couldNotStart}{quickCheck.refusal}</p>}
        {result && quickCheck.showsResult && <p className="settings-note" role="status">
            {pairLabel(result, items)}: {quickCheckResultText(result)}</p>}
    </>;
}
