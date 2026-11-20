import React, {useCallback, useEffect, useRef, useState} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import {serverUrls} from '@/services';
import {useAppSelector} from '@/store';
import {QUICK_CHECK_TEXT} from '@/services/server/execution-providers';
import {
    type PackagePlan, planLines, requestStartCheck, requestStartCheckPlan, START_CHECK_TEXT, startResultLines,
} from '@/services/server/start-check';

/**
 * The start check in the Certification dialog (decisions 14, 17, 27): each package's plan, "Run quick check", the
 * server's refusal of this window's start, and how each package's part of the last start check ended. Its progress and
 * cancel are the dialog's running check. The plan and the refusal belong to one server identity; the rest is the
 * server's current state. The button never changes label or disables.
 */
export function StartCheckSection({required}: {required: boolean}) {
    const {isConnected, serverPid, certification} = useAppSelector(state => state.connection);
    const endpoint = serverUrls.getHttpUrl();
    const serverKey = `${endpoint}:${serverPid}:${isConnected}`;
    const [local, setLocal] = useState<{key: string; plans?: PackagePlan[]; planError?: string; refusal?: string}>({key: serverKey});
    const current = useRef(serverKey);
    current.current = serverKey;
    const mine = local.key === serverKey ? local : {key: serverKey};

    useEffect(() => {
        if (!isConnected) return;
        const controller = new AbortController();
        requestStartCheckPlan(endpoint, controller.signal)
            .then(plans => setLocal(previous => ({...(previous.key === serverKey ? previous : {key: serverKey}), plans})))
            .catch(error => controller.signal.aborted
                || setLocal(previous => ({...(previous.key === serverKey ? previous : {key: serverKey}), planError: String(error)})));
        return () => controller.abort();
    }, [endpoint, serverKey, isConnected]);

    const run = useCallback(async () => {
        const key = serverKey;
        setLocal(previous => ({...(previous.key === key ? previous : {key}), refusal: undefined}));
        const refusal = await requestStartCheck(endpoint).catch(error => String(error));
        if (current.current === key) setLocal(previous => ({...(previous.key === key ? previous : {key}), refusal: refusal ?? undefined}));
    }, [endpoint, serverKey]);

    const results = certification?.run ? [] : startResultLines(certification?.start_results ?? []);
    return <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
        <SubactionHeader text={START_CHECK_TEXT.heading} className="text-gray"/>
        <p className={`text sm ${required ? 'text-white' : 'text-gray'}`}>{required ? START_CHECK_TEXT.required : START_CHECK_TEXT.optional}</p>
        {mine.plans ? <ul className="text sm text-gray">{planLines(mine.plans).map(line => <li key={line}>{line}</li>)}</ul>
            : <p className="text sm text-darkgray">{mine.planError ? START_CHECK_TEXT.couldNotReadPlan + mine.planError : START_CHECK_TEXT.loadingPlan}</p>}
        <div className="flex flex-row">
            <ButtonSm text={START_CHECK_TEXT.run} textColor="text-white" className="primary accent" onClick={run}/>
        </div>
        {mine.refusal && <p className="text sm settings-note-error" role="alert">{QUICK_CHECK_TEXT.couldNotStart}{mine.refusal}</p>}
        {results.map(line => <p key={line.text} className={`text sm ${line.failed ? 'settings-note-error' : 'text-white'}`} role="status">
            {line.text}</p>)}
    </div>;
}
