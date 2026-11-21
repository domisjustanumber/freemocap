import React, {useCallback, useEffect, useRef, useState} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import {serverUrls} from '@/services';
import {useAppSelector} from '@/store';
import {QUICK_CHECK_TEXT, quickCheckProgressText, requestQuickCheckCancel} from '@/services/server/execution-providers';
import {CERTIFICATION_TEXT, REPORTS_SECTION_ID} from '@/services/server/certification-hand-in';
import {
    type PackagePlan, planDetail, requestStartCheck, requestStartCheckPlan, START_CHECK_PACKAGES, START_CHECK_TEXT, startCheckRowStatus,
} from '@/services/server/start-check';

/**
 * The start check in the Certification dialog (decisions 14, 17, 27): a table with one row per package (its plan and
 * its status: waiting, running with a moving icon, done, passed, failed, cancelled, not run), the running check's
 * progress, the server's refusal of this window's start, "Start now" and "Cancel check". The table's rows and
 * the message lines keep their place whatever the state, so the dialog does not jump. The plan and the refusal belong
 * to one server identity; the rest is the server's current state. The buttons never change label or disable; Cancel
 * is hidden (its space kept) while nothing runs.
 */
export function StartCheckSection() {
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

    const running = certification?.run?.level === 'quick' ? certification.run : undefined;  // the full benchmark has its own section
    const packages = mine.plans?.map(plan => plan.package) ?? [...START_CHECK_PACKAGES];
    const statuses = startCheckRowStatus(packages, running, certification?.start_results ?? [],
        certification?.start_required === true);
    const detail = (name: string) => {
        const plan = mine.plans?.find(item => item.package === name);
        return plan ? planDetail(plan) : mine.planError ? START_CHECK_TEXT.couldNotReadPlan + mine.planError : START_CHECK_TEXT.loadingPlan;
    };
    // A failed package's report is in the hand-in list below (freemocap's own and skellytracker's, J13).
    const fileReport = () => document.getElementById(REPORTS_SECTION_ID)?.scrollIntoView({block: 'nearest'});
    const cell = {padding: '4px 6px', height: 36, verticalAlign: 'middle' as const};

    return <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
        <SubactionHeader text={START_CHECK_TEXT.heading} className="text-gray"/>
        <table className="certify-table text sm" style={{width: '100%', tableLayout: 'fixed', borderCollapse: 'collapse'}}>
            <thead>
            <tr className="text-darkgray" style={{textAlign: 'left'}}>
                <th style={{...cell, width: '24%', height: 'auto'}}>Package</th>
                <th style={{...cell, width: '38%', height: 'auto'}}>What it checks</th>
                <th style={{...cell, height: 'auto'}}>Status</th>
            </tr>
            </thead>
            <tbody>
            {packages.map((name, index) => {
                const status = statuses[index];
                return <tr key={name} className="border-1" title={mine.plans?.find(item => item.package === name)?.checks.join(', ')}>
                    <td style={cell} className="text-white">{name}</td>
                    <td style={cell} className="text-gray">{detail(name)}</td>
                    <td style={cell} role="status">
                        <span className="flex flex-row items-center gap-1">
                            {status.kind === 'running' && <span className="icon loader-icon icon-size-20" role="img" aria-label="Running"/>}
                            <span className={status.kind === 'failed' ? 'settings-note-error' : status.kind === 'passed' || status.kind === 'running'
                                ? 'text-white' : 'text-gray'}>{status.text}</span>
                            {status.kind === 'failed' && <ButtonSm text={CERTIFICATION_TEXT.fileReport} buttonType="secondary" onClick={fileReport}/>}
                        </span>
                    </td>
                </tr>;
            })}
            </tbody>
        </table>
        <div className="flex flex-row gap-2">
            <ButtonSm text={CERTIFICATION_TEXT.startNow} textColor="text-white" className="primary accent" onClick={run}/>
            <span style={{visibility: running ? 'visible' : 'hidden'}}>
                <ButtonSm text={CERTIFICATION_TEXT.cancelCheck} buttonType="secondary" onClick={() =>
                    requestQuickCheckCancel(endpoint).catch(error => console.warn("Could not cancel the quick check:", error))}/>
            </span>
            {/* One line beside the buttons (truncated, full text as its title), so nothing sits between them and the next section. */}
            <p className="text sm" style={{flex: 1, minWidth: 0, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', alignSelf: 'center'}}
               title={mine.refusal ? QUICK_CHECK_TEXT.couldNotStart + mine.refusal : undefined}>
                {mine.refusal ? <span className="settings-note-error" role="alert">{QUICK_CHECK_TEXT.couldNotStart}{mine.refusal}</span>
                    // An EP pair's check is not in the table; the start check's progress is in its status cells.
                    : running?.items.length ? <span className="text-gray">{quickCheckProgressText(running, certification?.items)}</span> : null}
            </p>
        </div>
    </div>;
}
