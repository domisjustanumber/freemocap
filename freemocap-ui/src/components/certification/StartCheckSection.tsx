import React, {useCallback, useEffect, useRef, useState} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import {serverUrls} from '@/services';
import {useAppSelector} from '@/store';
import {QUICK_CHECK_TEXT} from '@/services/server/execution-providers';
import {CERTIFICATION_TEXT, openCertification, REPORTS_SECTION_ID} from '@/services/server/certification-hand-in';
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
    const blenderExePath = useAppSelector(state => state.blender.blenderExePath);
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
        const refusal = await requestStartCheck(endpoint, fetch, blenderExePath).catch(error => String(error));
        if (current.current === key) setLocal(previous => ({...(previous.key === key ? previous : {key}), refusal: refusal ?? undefined}));
    }, [endpoint, serverKey, blenderExePath]);

    const results = certification?.run ? [] : startResultLines(certification?.start_results ?? []);
    const fileReport = () => {
        openCertification();
        document.getElementById(REPORTS_SECTION_ID)?.scrollIntoView({block: 'nearest'});
    };
    return <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
        <SubactionHeader text={START_CHECK_TEXT.heading} className="text-gray"/>
        <p className={`text sm ${required ? 'text-white' : 'text-gray'}`}>{required ? START_CHECK_TEXT.required : START_CHECK_TEXT.optional}</p>
        {mine.plans ? <ul className="text sm text-gray">{planLines(mine.plans).map(line => <li key={line}>{line}</li>)}</ul>
            : <p className="text sm text-darkgray">{mine.planError ? START_CHECK_TEXT.couldNotReadPlan + mine.planError : START_CHECK_TEXT.loadingPlan}</p>}
        <div className="flex flex-row">
            <ButtonSm text={START_CHECK_TEXT.run} textColor="text-white" className="primary accent" onClick={run}/>
        </div>
        {mine.refusal && <p className="text sm settings-note-error" role="alert">{QUICK_CHECK_TEXT.couldNotStart}{mine.refusal}</p>}
        {results.map(line => line.failed
            // A failed package's report is in the hand-in list below (freemocap's own and skellytracker's, J13).
            ? <div key={line.text} className="settings-note settings-note-dismissable" role="status">
                <span className="settings-note-error">{line.text}</span>
                <ButtonSm text={CERTIFICATION_TEXT.fileReport} className="setting-action-button" onClick={fileReport}/>
            </div>
            : <p key={line.text} className="text sm text-white" role="status">{line.text}</p>)}
    </div>;
}
