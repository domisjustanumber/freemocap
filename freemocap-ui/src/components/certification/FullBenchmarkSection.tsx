import React, {useCallback, useEffect, useRef, useState} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import Checkbox from '@/components/ui-components/Checkbox';
import {serverUrls} from '@/services';
import {useAppSelector} from '@/store';
import {requestQuickCheckCancel} from '@/services/server/execution-providers';
import {CERTIFICATION_TEXT} from '@/services/server/certification-hand-in';
import type {PackagePlan} from '@/services/server/start-check';
import {
    consentPlan, downloadRows, estimateLine, finishedText, FULL_BENCHMARK_TEXT, fullResultLines, fullRowName, fullRowStatus, invitationText,
    planReadKey, requestFullBenchmark, requestFullBenchmarkPlan,
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
 * with a turning icon while it runs), its count of finished checks and "Cancel check", then how the last one ended with
 * its rows as they ended (the server keeps them until the next one starts).
 * The plan and the refusal belong to one server identity; the consent step shows only the plan read for its opening and
 * the current full-run state (`planReadKey`); the rest is the server's current state.
 */
export function FullBenchmarkSection() {
    const {isConnected, serverPid, certification} = useAppSelector(state => state.connection);
    const blenderExePath = useAppSelector(state => state.blender?.blenderExePath ?? null);
    const endpoint = serverUrls.getHttpUrl();
    const serverKey = `${endpoint}:${serverPid}:${isConnected}`;
    type Local = {key: string; plans?: PackagePlan[]; planError?: string; readFor?: string; opened?: number; refusal?: string;
        consent?: boolean};
    const [local, setLocal] = useState<Local>({key: serverKey});
    const [removeData, setRemoveData] = useState(true);
    const current = useRef(serverKey);
    current.current = serverKey;
    const mine: Local = local.key === serverKey ? local : {key: serverKey};
    const update = useCallback((key: string, change: Partial<Local> | ((previous: Local) => Partial<Local>)) =>
        setLocal(previous => {
            const base = previous.key === key ? previous : {key};
            return {...base, ...(typeof change === 'function' ? change(base) : change)};
        }), []);
    const readKey = planReadKey(mine.opened ?? 0, certification);
    const shown = consentPlan(mine, readKey);

    useEffect(() => {
        if (!isConnected) return;
        const controller = new AbortController();
        requestFullBenchmarkPlan(endpoint, controller.signal, fetch, blenderExePath)
            .then(plans => controller.signal.aborted || update(serverKey, {plans, planError: undefined, readFor: readKey}))
            .catch(error => controller.signal.aborted || update(serverKey, {plans: undefined, planError: String(error), readFor: readKey}));
        return () => controller.abort();
    }, [endpoint, serverKey, isConnected, update, blenderExePath, readKey]);

    const start = useCallback(async () => {
        const key = serverKey;
        update(key, {refusal: undefined});
        const refusal = await requestFullBenchmark(endpoint, removeData, fetch, blenderExePath, shown.plans).catch(error => String(error));
        // A refusal reads the plan again: the step then shows what a Start would download now, with the sentence beside it.
        if (current.current === key) update(key, refusal ? previous => ({refusal, opened: (previous.opened ?? 0) + 1})
            : {refusal: undefined, consent: false});
    }, [endpoint, serverKey, removeData, update, blenderExePath, shown.plans]);

    const run = certification?.run?.level === 'full' ? certification.run : undefined;
    const rows = run ? run.rows ?? [] : certification?.full_rows ?? [];
    return <div className="flex flex-col gap-2 bg-secondary p-2 br-1">
        <p className="text sm text-white">{invitationText(mine.plans)}</p>
        <div className="flex flex-row">
            <ButtonSm text={FULL_BENCHMARK_TEXT.button} buttonType="secondary" onClick={() =>
                update(serverKey, previous => ({consent: true, opened: (previous.opened ?? 0) + 1}))}/>
        </div>
        {mine.consent && (shown.plans
            ? <FullBenchmarkConsent plans={shown.plans} removeData={removeData} onRemoveData={setRemoveData} onStart={start}
                                    onCancel={() => update(serverKey, {consent: false, refusal: undefined})} refusal={mine.refusal}/>
            : <p className="text sm text-gray">{shown.planError ? FULL_BENCHMARK_TEXT.couldNotReadPlan + shown.planError : FULL_BENCHMARK_TEXT.loadingPlan}</p>)}
        {rows.length > 0 && <table className="certify-table text sm" style={table}>
            <tbody>
            {rows.map((row, index) => {
                const status = fullRowStatus(row);
                // Each package's rows under its name: skellytracker's checks and freemocap's benchmark of one pair stay apart.
                return <React.Fragment key={`${row.package}:${row.name}`}>
                {row.package !== rows[index - 1]?.package && <tr><th colSpan={2} style={{...cell, textAlign: 'left'}}
                    className="text-gray">{row.package}</th></tr>}
                <tr className="border-1">
                    <td style={{...cell, width: '62%'}} className="text-white">{fullRowName(row, certification?.items)}</td>
                    <td style={cell} role="status">
                        <span className="flex flex-row items-center gap-1">
                            {status.kind === 'running' && <span className="icon loader-icon icon-size-20" role="img" aria-label="Running"/>}
                            <span className={status.kind === 'failed' ? 'settings-note-error' : status.kind === 'waiting' ? 'text-gray'
                                : 'text-white'}>{status.text}</span>
                        </span>
                    </td>
                </tr>
                </React.Fragment>;
            })}
            </tbody>
        </table>}
        {run && <div className="flex flex-row gap-2 items-center">
            <ButtonSm text={CERTIFICATION_TEXT.cancelCheck} buttonType="secondary" onClick={() =>
                requestQuickCheckCancel(endpoint).catch(error => console.warn('Could not cancel the full benchmark:', error))}/>
            <p className="text sm text-gray" role="status">{finishedText(run)}</p>
        </div>}
        {!run && fullResultLines(certification?.full_results ?? [], certification?.items, rows).map(line =>
            <p key={line.text} className={`text sm ${line.failed ? 'settings-note-error' : 'text-white'}`}>{line.text}</p>)}
    </div>;
}
