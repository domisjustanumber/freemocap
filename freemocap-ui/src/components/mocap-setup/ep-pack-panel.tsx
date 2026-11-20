import {useCallback, useRef, useState} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import type {ExecutionProviderChoices} from '@/hooks/useExecutionProviderOptions';
import type {ExecutionProviderOption} from '@/types/execution-provider';
import {serverUrls} from '@/services';
import {useAppSelector} from '@/store/hooks';
import {describeError} from '@/store/slices/thunk-helpers';
import {
    EP_PACK_TEXT, type EpPackAction, packControls, packProgressText, packResultText, packStateText, requestEpPack,
    requestEpPackCancel,
} from '@/services/server/ep-packs';

interface Local {
    /** The EP whose Remove asks first (F16). */
    confirm: string | null;
    /** The server's refusal of this window's last start; the answer to that request only. */
    refusal: {action: EpPackAction; text: string} | null;
}
const NONE: Local = {confirm: null, refusal: null};

/**
 * Install and Remove of each Windows ML EP of the server's host (F15 step 5), beside the EP setting: its state, the running
 * install's progress with "Cancel install", the confirmation before a remove, the server's refusal, and how the last
 * install or remove ended. Everything shown comes from the server; the buttons never change label or disable.
 */
export function EpPackPanel({providers}: {providers: ExecutionProviderChoices}) {
    const rows = providers.providers.flatMap(provider => {
        const controls = packControls(provider);
        return controls ? [{provider, controls}] : [];
    });
    return rows.length ? <EpPackRows providers={providers} rows={rows}/> : null;
}

function EpPackRows({providers, rows}: {
    providers: ExecutionProviderChoices; rows: {provider: ExecutionProviderOption; controls: {install: boolean}}[];
}) {
    const {isConnected, serverPid} = useAppSelector(state => state.connection);
    const endpoint = serverUrls.getHttpUrl();
    const serverKey = `${endpoint}:${serverPid}:${isConnected}`;
    const [state, setState] = useState<Local & {key: string}>({key: serverKey, ...NONE});
    const local: Local = state.key === serverKey ? state : NONE;
    const update = useCallback((patch: Partial<Local>) => setState(previous =>
        ({...(previous.key === serverKey ? previous : {key: serverKey, ...NONE}), ...patch})), [serverKey]);
    // A start answered after a newer request, or by a server that is no longer this one, is obsolete.
    const generation = useRef(0);
    const current = useRef(serverKey);
    current.current = serverKey;

    const start = useCallback(async (action: EpPackAction, key: string) => {
        const started = ++generation.current, server = serverKey;
        update({confirm: null, refusal: null});
        const text = await requestEpPack(endpoint, action, key).catch(error => describeError(error) || String(error));
        if (generation.current !== started || current.current !== server) return;
        update({refusal: text === null ? null : {action, text}});
    }, [endpoint, serverKey, update]);
    const cancel = useCallback(() => {
        requestEpPackCancel(endpoint).catch(error => console.warn('Could not cancel the install:', error));
    }, [endpoint]);

    const run = providers.certification?.pack_run;
    const result = providers.certification?.last_pack_result;
    const labelOf = (key: string) => providers.providers.find(provider => provider.key === key)?.label ?? key;
    const action = (text: string, onClick: () => void) => <ButtonSm text={text} className="setting-action-button" onClick={onClick}/>;

    return <>
        {rows.map(({provider, controls}) => <div key={provider.key} className="settings-note settings-note-dismissable" role="status">
            <span><strong>{provider.label}</strong> (Windows ML): {packStateText(provider.state ?? '')}</span>
            {controls.install && action(EP_PACK_TEXT.install, () => void start('install', provider.key))}
            {action(EP_PACK_TEXT.remove, () => update({confirm: provider.key, refusal: null}))}
        </div>)}
        {local.confirm && <div className="settings-note settings-note-dismissable" role="alert">
            <span>{EP_PACK_TEXT.confirmRemove(labelOf(local.confirm))}</span>
            {action(EP_PACK_TEXT.remove, () => void start('remove', local.confirm as string))}
            {action(EP_PACK_TEXT.keep, () => update({confirm: null}))}
        </div>}
        {run && <div className="settings-note settings-note-dismissable" role="status">
            <span>{packProgressText(run, labelOf(run.execution_provider))}</span>
            {run.action === 'install' && action(EP_PACK_TEXT.cancel, cancel)}
        </div>}
        {local.refusal && <p className="settings-note settings-note-error" role="alert">
            {EP_PACK_TEXT.couldNotStart(local.refusal.action)}{local.refusal.text}</p>}
        {result && !run && <p className="settings-note" role="status">
            {packResultText(result, labelOf(result.execution_provider))}</p>}
    </>;
}
