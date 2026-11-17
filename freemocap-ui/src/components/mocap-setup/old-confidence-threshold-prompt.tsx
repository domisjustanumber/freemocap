import ButtonSm from '@/components/ui-components/ButtonSm';
import {RTMW_CONFIDENCE_THRESHOLD} from '@/types/rtmw-confidence';

/**
 * Asks about an RTMW confidence threshold saved before the calibrated score (user M1). Nothing changes until the user
 * answers; the saved value stays in force meanwhile.
 */
export function OldConfidenceThresholdPrompt({saved, onAnswer}: {saved: number; onAnswer: (answer: 'reset' | 'keep') => void}) {
    return <div role="alert" className="settings-note settings-note-dismissable">
        <span>The keypoint confidence score changed to a probability from 0 to 1. Your saved threshold <strong>{saved}</strong> is
            on the old scale and lets almost every point through. The new default is {RTMW_CONFIDENCE_THRESHOLD}.</span>
        <ButtonSm text={`Reset to ${RTMW_CONFIDENCE_THRESHOLD}`} className="setting-action-button" onClick={() => onAnswer('reset')}/>
        <ButtonSm text={`Keep ${saved}`} className="setting-action-button" onClick={() => onAnswer('keep')}/>
    </div>;
}
