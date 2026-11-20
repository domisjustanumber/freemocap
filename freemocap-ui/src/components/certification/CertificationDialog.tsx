import React, {useCallback, useEffect, useRef, useState} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import IconButton from '@/components/ui-components/IconButton';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import {serverUrls} from '@/services';
import {useAppSelector} from '@/store';
import {useHandIn} from '@/hooks/useHandIn';
import {
    bottomButtonLabel, certificationButtonSuffix, footerActionText, reportFooterAction, reportsReady, submitText, CERTIFICATION_TEXT, handedIn, ISSUE_FORM_URL, issueFormProminent, issueLabel, isLocalHost,
    openCertification, outboxLine, pendingRows, pendingSummary, REPORTS_SECTION_ID, submitLabel,
} from '@/services/server/certification-hand-in';
import {START_CHECK_TEXT} from '@/services/server/start-check';
import {ReportMarkdown} from './ReportMarkdown';
import {StartCheckSection} from './StartCheckSection';

/** The button after the Streaming and Playback tabs, clear of the pages' toolbars at the right: a fixed label with a suffix from the server state (25). */
export function CertificationButton() {
    const {isConnected, certification} = useAppSelector(state => state.connection);
    const suffix = certificationButtonSuffix(certification, !isLocalHost(serverUrls.getHost()));
    // Dimmed by opacity: the quaternary button's own rule sets its text colour, so a colour class has no effect.
    return <div style={isConnected ? undefined : {opacity: 0.5}}>
        <ButtonSm text={suffix ? `${CERTIFICATION_TEXT.button} ${suffix}` : CERTIFICATION_TEXT.button} buttonType="quaternary"
                  onClick={openCertification}/>
    </div>;
}

const link = (url: string, text: string) => <a href={url} target="_blank" rel="noreferrer">{text}</a>;

/**
 * The Certification dialog (decision 26, the SettingsModal pattern; the owner's notes of 2026-11-20): the title, the
 * start check's table with its run and cancel, and the reports to hand in: the invitation, note, "Submit Report",
 * "View report" with the exact file, "Save file and open issue form", the hand-ins already made and the kept files,
 * each with "Not sent", and the full benchmark (not available yet). Everything shown comes from the current server
 * state and the answers to this window's requests; no label changes with history and no working button is greyed out.
 * `required` (the server's `start_required`, decision 14): the start check is needed, so the dialog has no dismiss and
 * no overlay; the layout greys out the rest of the UI except the server connection and the log terminal.
 */
export function CertificationDialog({open, onClose, required = false}: {open: boolean; onClose: () => void; required?: boolean}) {
    const {isConnected, serverPid, certification} = useAppSelector(state => state.connection);
    const endpoint = serverUrls.getHttpUrl();
    const handIn = useHandIn(endpoint, `${endpoint}:${serverPid}:${isConnected}`, open, certification);
    const {list, view, message} = handIn;
    // The report pop-up: opened by "View report", or by Submit Report's issue-form fallback; closed for this file only.
    const [reportAsked, setReportAsked] = useState(false);
    const [closedView, setClosedView] = useState<typeof handIn.shownView>(null);
    const viewButton = useRef<HTMLSpanElement>(null);
    const shown = handIn.shownView;
    const showReport = Boolean(shown && shown !== closedView && (reportAsked || message?.offerIssueForm));
    const closeReport = useCallback(() => {
        setReportAsked(false);
        setClosedView(shown);
        viewButton.current?.querySelector('button')?.focus();
    }, [shown]);

    // "Sent!" shows for 1.5 s, then the pop-ups close so the app is in view; the timer goes with the dialog.
    const {phase, clearPhase} = handIn;
    useEffect(() => {
        if (phase !== 'sent') return;
        const timer = setTimeout(() => { clearPhase(); setReportAsked(false); setClosedView(shown); if (!required) onClose(); }, 1500);
        return () => clearTimeout(timer);
    }, [phase, clearPhase, shown, required, onClose]);

    useEffect(() => {
        if (!open || (required && !showReport)) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key !== 'Escape') return;
            if (showReport) closeReport(); else onClose();
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [open, onClose, required, showReport, closeReport]);

    if (!open) return null;
    const pending = certification?.pending_reports ?? [];
    const prominent = issueFormProminent(list, message, view);
    const bottom = required ? null : bottomButtonLabel(certification);
    const ready = reportsReady(certification);
    const footer = shown ? reportFooterAction(list, shown.file, message, pending.length) : null;
    const section = 'flex flex-col gap-2 bg-secondary p-2 br-1';

    return <>
        {!required && <div className="pos-fixed inset-0 bg-surface-overlay z-10" onClick={onClose}/>}
        <Centred zIndex={1000}>
        <div className="settings-modal bg-primary border-1 border-black elevated-sharp p-1 flex flex-col br-2" role="dialog"
             aria-label={CERTIFICATION_TEXT.title} style={{...UNTRANSFORMED, width: 560, height: '80vh'}}>
            <div className="flex flex-col p-2 gap-2 bg-middark br-1">
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text={CERTIFICATION_TEXT.title}/>
                    {!required && <IconButton icon="close-icon" onClick={onClose}/>}
                </div>
                <p className="text sm text-white">{required ? START_CHECK_TEXT.required : START_CHECK_TEXT.optional}</p>

                <StartCheckSection/>

                <div className={section} id={REPORTS_SECTION_ID}>
                    <SubactionHeader text={CERTIFICATION_TEXT.reports} className="text-gray"/>
                    {!ready && <p className="text sm text-gray">{CERTIFICATION_TEXT.resultsLater}</p>}
                    {ready && !pending.length && <p className="text sm text-gray">{CERTIFICATION_TEXT.nothingPending}</p>}
                    {ready && pending.length > 0 && <>
                        <p className="text sm text-white">{CERTIFICATION_TEXT.invitation}</p>
                        <p className="text sm text-white">{pendingSummary(pending)}</p>
                        <ul className="text sm text-gray">
                            {pendingRows(pending, list).map(row => <li key={row.report_id}>{row.text}</li>)}
                        </ul>
                        <label className="text sm text-gray flex flex-col gap-1">
                            {CERTIFICATION_TEXT.noteLabel}
                            <textarea className="setting-text-input" rows={3} value={handIn.note}
                                      onChange={event => handIn.setNote(event.target.value)}/>
                        </label>
                        <div className="flex flex-row gap-2 flex-wrap">
                            <SendButton phase={phase} text={submitText(phase, pending.length)} className={prominent ? '' : 'primary accent'}
                                        buttonType={prominent ? 'secondary' : ''} onClick={() => { setClosedView(null); handIn.submit(); }}/>
                            <span ref={viewButton}>
                                <ButtonSm text={CERTIFICATION_TEXT.viewReport} buttonType="secondary" onClick={() => {
                                    setReportAsked(true);
                                    setClosedView(null);
                                    handIn.viewReport();
                                }}/>
                            </span>
                        </div>
                        <p className="text sm text-darkgray">{CERTIFICATION_TEXT.privacy}</p>
                    </>}
                    {message && <p className={`text sm ${message.error ? 'settings-note-error' : 'text-white'}`} role="status">
                        {message.text}{message.issueUrl && <>: {link(message.issueUrl, message.issueUrl)}</>}</p>}
                    {view && !showReport && message?.offerIssueForm && <div className="flex flex-row">
                        <ButtonSm text={CERTIFICATION_TEXT.issueForm} textColor="text-white" className="primary accent" onClick={handIn.issueForm}/>
                    </div>}
                    {list?.outbox.map(entry => <div key={entry.sha256} className="settings-note settings-note-dismissable">
                        <span>{outboxLine(entry)}</span>
                        <ButtonSm text={CERTIFICATION_TEXT.notSent} buttonType="secondary" onClick={() => handIn.notSent(entry.report_ids)}/>
                    </div>)}
                    {handedIn(list).map(group => <div key={group.issueUrl ?? 'opened'} className="settings-note settings-note-dismissable">
                        <span>{group.issueUrl ? <>Shared as {link(group.issueUrl, issueLabel(group.issueUrl))}</>
                            : <>{CERTIFICATION_TEXT.issueFormOpened} ({link(ISSUE_FORM_URL, CERTIFICATION_TEXT.openIssueFormAgain)})</>}
                            {' '}· {group.reportIds.length} report{group.reportIds.length === 1 ? '' : 's'}</span>
                        <ButtonSm text={CERTIFICATION_TEXT.notSent} buttonType="secondary" onClick={() => handIn.notSent(group.reportIds)}/>
                    </div>)}
                </div>

                <div className={section}>
                    <p className="text sm text-white">{CERTIFICATION_TEXT.fullBenchmarkInvitation}</p>
                    <div className="flex flex-row">
                        {/* shortcut: the full benchmark is not built yet; enable and wire it when its route exists. */}
                        <ButtonSm text={CERTIFICATION_TEXT.fullBenchmark} buttonType="secondary" disabled tooltip
                                  tooltipText={CERTIFICATION_TEXT.notAvailableYet} title={CERTIFICATION_TEXT.notAvailableYet}/>
                    </div>
                </div>

                {/* Sticky: the dialog scrolls at 80vh, and Continue must stay in sight. */}
                {bottom && <div className="flex flex-row gap-2 bg-middark pt-1" style={{justifyContent: 'flex-end', position: 'sticky', bottom: 0}}>
                    <ButtonSm text={bottom} textColor="text-white" className={bottom === CERTIFICATION_TEXT.continue ? 'primary accent' : ''}
                              buttonType={bottom === CERTIFICATION_TEXT.continue ? '' : 'secondary'} onClick={onClose}/>
                </div>}
            </div>
        </div>
        </Centred>

        {showReport && shown && <>
            <div className="pos-fixed inset-0 bg-surface-overlay" style={{zIndex: 1001}} onClick={closeReport}/>
            <Centred zIndex={1002}>
            <div className="settings-modal bg-primary border-1 border-black elevated-sharp p-1 flex flex-col br-2" role="dialog"
                 aria-label={CERTIFICATION_TEXT.viewReport} style={{...UNTRANSFORMED, width: 800, maxHeight: '90vh'}}>
                <div className="flex flex-col p-2 gap-2 bg-middark br-1">
                    <div className="flex justify-content-space-between items-center">
                        <p className="text sm text-gray">{shown.file.file_name} ({shown.file.size_bytes} bytes)</p>
                        <IconButton icon="close-icon" onClick={closeReport}/>
                    </div>
                    {/* The exact file the server returned, read as Markdown; never rebuilt here. */}
                    <ReportMarkdown text={shown.file.content}/>
                    {/* Sticky footer: the answer line (reserved, so nothing jumps), then Close left and the action right. */}
                    <div className="flex flex-col gap-1 bg-middark pt-1" style={{position: 'sticky', bottom: 0}}>
                        {footer && <div>
                            <p className="text sm text-white"><strong>{CERTIFICATION_TEXT.reports}</strong></p>
                            <p className="text sm text-gray">{footerActionText(footer, pending.length)}</p>
                        </div>}
                        <p className={`text sm ${message?.error ? 'settings-note-error' : 'text-white'}`} role="status" style={{minHeight: '3em'}}>
                            {message ? <>{message.text}{message.issueUrl && <>: {link(message.issueUrl, message.issueUrl)}</>}</>
                                : footer === 'issue-form' ? (list?.relay_enabled === false ? CERTIFICATION_TEXT.relayNotSetUp
                                    : !shown.file.fits_relay ? CERTIFICATION_TEXT.tooLarge : '') : ''}</p>
                        <div className="flex flex-row gap-2" style={{justifyContent: 'space-between'}}>
                            <ButtonSm text={CERTIFICATION_TEXT.close} buttonType="secondary" textColor="text-white" onClick={closeReport}/>
                            {footer === 'submit' && <SendButton phase={phase} text={submitText(phase, pending.length)} className="primary accent"
                                                                buttonType="" onClick={handIn.submit}/>}
                            {footer === 'issue-form' && <ButtonSm text={CERTIFICATION_TEXT.issueForm} textColor="text-white"
                                                                  className="primary accent" onClick={handIn.issueForm}/>}
                        </div>
                    </div>
                </div>
            </div>
            </Centred>
        </>}
    </>;
}

/** The single send action's button: dimmed, busy and not clickable with the turning icon while the send is in flight. */
const SendButton = ({phase, text, className, buttonType, onClick}: {phase: string; text: string; className: string; buttonType: string;
                     onClick: () => void}) =>
    <span className="certify-busy" aria-busy={phase === 'submitting'} style={phase === 'submitting' ? {opacity: 0.6} : undefined}>
        <ButtonSm text={text} textColor="text-white" className={className} buttonType={buttonType} disabled={phase !== 'idle'}
                  iconClass={phase === 'submitting' ? 'loader-icon' : ''} onClick={onClick}/>
    </span>;

/** The settings-modal centres itself with translate(-50%, -50%), which puts the text on half pixels (blurred) whenever
 * the height or the display scale makes the half odd; these dialogs are centred by a flex layer instead. */
const UNTRANSFORMED: React.CSSProperties = {position: 'relative', top: 'auto', left: 'auto', transform: 'none', maxWidth: 'calc(100vw - 32px)',
    minWidth: 0, pointerEvents: 'auto'};
const Centred = ({zIndex, children}: {zIndex: number; children: React.ReactNode}) =>
    <div className="pos-fixed inset-0 flex items-center justify-center" style={{zIndex, pointerEvents: 'none'}}>{children}</div>;
