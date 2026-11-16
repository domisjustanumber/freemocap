import ButtonSm from '@/components/ui-components/ButtonSm';
import type {ExecutionProviderMigration} from '@/store/slices/mocap';
import type {ExecutionProviderOption} from '@/types/execution-provider';
import {NotUsableNote} from './execution-provider-info';

/**
 * The notice of an EP key saved by an earlier FreeMoCap version (user G1, G3, G4): while skellytracker's suggestion is
 * pending, and then which key replaced it, with the EP menu's not-usable text for a replacement that is not installed.
 */
export function LegacyExecutionProviderNotice({migration, providers, onDismiss}: {
    migration: ExecutionProviderMigration; providers: readonly ExecutionProviderOption[]; onDismiss: () => void;
}) {
    if (migration.status === 'pending') {
        return <p className="settings-note" role="status">
            Checking the execution provider <strong>{migration.saved}</strong> saved by an earlier FreeMoCap version;
            processing waits for the server.</p>;
    }
    const replacement = providers.find(({key}) => key === migration.replacement);
    return <div role="status" className="settings-note settings-note-dismissable">
        <span>The execution provider <strong>{migration.saved}</strong> saved by an earlier FreeMoCap version was
            replaced by <strong>{replacement?.label ?? migration.replacement ?? 'Auto'}</strong>
            {migration.replacement === null ? ': SkellyTracker has no usable replacement on this computer' : ''}.
            {replacement && !replacement.usable && <> <NotUsableNote provider={replacement}/></>}</span>
        <ButtonSm text="Dismiss" className="setting-action-button" onClick={onDismiss}/>
    </div>;
}
