import React, {useCallback, useEffect, useRef, useState} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import Checkbox from '@/components/ui-components/Checkbox';
import {serverUrls} from '@/services';
import {useAppSelector} from '@/store';
import {requestQuickCheckCancel} from '@/services/server/execution-providers';
import {CERTIFICATION_TEXT} from '@/services/server/certification-hand-in';
import type {PackagePlan} from '@/services/server/start-check';
import {
    downloadRows, estimateLine, finishedText, FULL_BENCHMARK_TEXT, fullResultLines, fullRowName, fullRowStatus, invitationText,
    requestFullBenchmark, requestFullBenchmarkPlan,
} from '@/services/server/full-benchmark';

const cell = {padding: '4px 6px', verticalAlign: 'middle' as const};
const table = {width: '100%', tableLayout: 'fixed' as const, borderCollapse: 'collapse' as const};

/** The consent step (fifth grilling): the downloads with their total, each package's time estimate, the risks, the
 * clean-up choice, Start and Cancel, and the server's refusal of this window's start beside them. */
export function FullBenchmarkConsent({plans, removeData, onRemoveData, onStart, onCancel, refusal}: {
    plans: readonly PackagePlan[]; removeData: boolean; onRemoveData: (value: boolean) => void; onStart: () => void;
    onCancel: () => void; refusal?: string;
}) {
    const downloads = downloadRows(plans);
    return <div className="flex flex-col gap-2">
        <p className="text sm text-gray">{FULL_BENCHMARK_TEXT.downloadsHeading}</p>
        {downloads.rows.length ? <table className="certify-table text sm" style={table}>
            <thead><tr className="text-darkgray" style={{textAlign: 'left'}}>
                <th style={{...cell, width: '45%'}}>Name</th><th style={cell}>Source</th><th style={{...cell, width: '20%'}}>Size</th>
            </tr></thead>
            <tbody>
            {downloads.rows.map((row, index) => <tr key={index} className="border-1">
                <td style={cell} className="text-white">{row.name}</td><td style={cell} className="text-gray">{row.source}</td>
                <td style={cell} className="text-gray">{row.size}</td>
            </tr>)}
            <tr className="border-1"><td style={cell} className="text-white">{FULL_BENCHMARK_TEXT.total}</td><td style={cell}/>
                <td style={cell} className="text-white">{downloads.total}</td></tr>
            </tbody>
        </table> : <p className="text sm text-white">{FULL_BENCHMARK_TEXT.nothingDownloaded}</p>}
        <p className="text sm text-gray">{FULL_BENCHMARK_TEXT.estimatesHeading}</p>
        <ul className="text sm text-white">{plans.map(plan => <li key={plan.package}>{estimateLine(plan)}</li>)}</ul>
        {plans.flatMap(plan => plan.risks).map(risk => <p key={risk} className="text sm settings-note-error">{risk}</p>)}
        <Checkbox label={FULL_BENCHMARK_TEXT.removeData} checked={removeData} onChange={event => onRemoveData(event.target.checked)}/>
        <p className="text sm text-darkgray">{FULL_BENCHMARK_TEXT.removeDataHelp}</p>
        <div className="flex flex-row gap-2 items-center">
            <ButtonSm text={FULL_BENCHMARK_TEXT.start} textColor="text-white" className="primary accent" onClick={onStart}/>
            <ButtonSm text={FULL_BENCHMARK_TEXT.cancel} buttonType="secondary" onClick={onCancel}/>
            {refusal && <p className="text sm settings-note-error" role="alert">{FULL_BENCHMARK_TEXT.couldNotStart}{refusal}</p>}
        </div>
    </div>;
}

/**
 * The full benchmark in the Certification dialog: the invitation with the total of the plans' estimates, the "Full
 * benchmark" button (never disabled or relabelled), its consent step, the running benchmark's rows (one per EP and GPU,
 * with a turning icon while it runs), its count of finished checks and "Cancel check", then how the last one ended.
 * The plan and the refusal belong to one server identity; the rest is the server's current state.
 */
export function FullBenchmarkSection() {
    const {isConnected, serverPid, certification} = useAppSelector(state => state.connection);
    const endpoint = serverUrls.getHttpUrl();
    const serverKey = `${endpoint}:${serverPid}:${isConnected}`;
    const [local, setLocal] = useState<{key: string; plans?: PackagePlan[]; planError?: string; refusal?: string; consent?: boolean}>(
        {key: serverKey});
    const [removeData, setRemoveData] = useState(true);
    const current = useRef(serverKey);
    current.current = serverKey;
    const mine = local.key === serverKey ? local : {key: serverKey} as typeof local;
    const update = useCallback((key: string, change: Partial<typeof local>) =>
        setLocal(previous => ({...(previous.key === key ? previous : {key}), ...change})), []);

    useEffect(() => {
        if (!isConnected) return;
        const controller = new AbortController();
        requestFullBenchmarkPlan(endpoint, controller.signal)
            .then(plans => update(serverKey, {plans}))
            .catch(error => controller.signal.aborted || update(serverKey, {planError: String(error)}));
        return () => controller.abort();
    }, [endpoint, serverKey, isConnected, update]);

    const start = useCallback(async () => {
        const key = serverKey;
        update(key, {refusal: undefined});
        const refusal = await requestFullBenchmark(endpoint, removeData).catch(error => String(error));
        if (current.current === key) update(key, refusal ? {refusal} : {refusal: undefined, consent: false});
    }, [endpoint, serverKey, removeData, update]);

    const run = certification?.run?.level === 'full' ? certification.run : undefined;
    return <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
        <p className="text sm text-white">{invitationText(mine.plans)}</p>
        <div className="flex flex-row">
            <ButtonSm text={FULL_BENCHMARK_TEXT.button} buttonType="secondary" onClick={() => update(serverKey, {consent: true})}/>
        </div>
        {mine.consent && (mine.plans
            ? <FullBenchmarkConsent plans={mine.plans} removeData={removeData} onRemoveData={setRemoveData} onStart={start}
                                    onCancel={() => update(serverKey, {consent: false, refusal: undefined})} refusal={mine.refusal}/>
            : <p className="text sm text-gray">{mine.planError ? FULL_BENCHMARK_TEXT.couldNotReadPlan + mine.planError : FULL_BENCHMARK_TEXT.loadingPlan}</p>)}
        {run && <>
            <table className="certify-table text sm" style={table}>
                <tbody>
                {(run.rows ?? []).map(row => {
                    const status = fullRowStatus(row);
                    return <tr key={`${row.package}:${row.name}`} className="border-1">
                        <td style={{...cell, width: '62%'}} className="text-white">{fullRowName(row, certification?.items)}</td>
                        <td style={cell} role="status">
                            <span className="flex flex-row items-center gap-1">
                                {status.kind === 'running' && <span className="icon loader-icon icon-size-20" role="img" aria-label="Running"/>}
                                <span className={status.kind === 'failed' ? 'settings-note-error' : status.kind === 'waiting' ? 'text-gray'
                                    : 'text-white'}>{status.text}</span>
                            </span>
                        </td>
                    </tr>;
                })}
                </tbody>
            </table>
            <div className="flex flex-row gap-2 items-center">
                <ButtonSm text={CERTIFICATION_TEXT.cancelCheck} buttonType="secondary" onClick={() =>
                    requestQuickCheckCancel(endpoint).catch(error => console.warn('Could not cancel the full benchmark:', error))}/>
                <p className="text sm text-gray" role="status">{finishedText(run)}</p>
            </div>
        </>}
        {!run && fullResultLines(certification?.full_results ?? []).map(line =>
            <p key={line.text} className={`text sm ${line.failed ? 'settings-note-error' : 'text-white'}`}>{line.text}</p>)}
    </div>;
}
