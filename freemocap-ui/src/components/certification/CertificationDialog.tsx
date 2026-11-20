import React, {useEffect} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import IconButton from '@/components/ui-components/IconButton';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import {serverUrls} from '@/services';
import {useAppSelector} from '@/store';
import {useHandIn} from '@/hooks/useHandIn';
import {
    certificationButtonSuffix, CERTIFICATION_TEXT, handedIn, ISSUE_FORM_URL, issueFormProminent, issueLabel, isLocalHost, openCertification, outboxLine,
    pendingRows, pendingSummary, REPORTS_SECTION_ID,
} from '@/services/server/certification-hand-in';
import {quickCheckProgressText, requestQuickCheckCancel} from '@/services/server/execution-providers';
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
 * The Certification dialog (decision 26, the SettingsModal pattern): the running check with its cancel, and the
 * reports to hand in: summary, note, the exact file, "Send report", "Save file and open issue form", the hand-ins
 * already made and the kept files, each with "Not sent". Everything shown comes from the current server state and
 * the answers to this window's requests; no label changes with history and no button is greyed out.
 * `required` (the server's `start_required`, decision 14): the start check is needed, so the dialog has no dismiss and
 * no overlay; the layout greys out the rest of the UI except the server connection and the log terminal.
 */
export function CertificationDialog({open, onClose, required = false}: {open: boolean; onClose: () => void; required?: boolean}) {
    const {isConnected, serverPid, certification} = useAppSelector(state => state.connection);
    const endpoint = serverUrls.getHttpUrl();
    const handIn = useHandIn(endpoint, `${endpoint}:${serverPid}:${isConnected}`, open, certification);

    useEffect(() => {
        if (!open || required) return;
        const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [open, onClose, required]);

    if (!open) return null;
    const {list, view, message} = handIn;
    const pending = certification?.pending_reports ?? [];
    const run = certification?.run;
    const prominent = issueFormProminent(list, message, view);
    const section = 'flex flex-col gap-2 bg-secondary p-2 br-1';

    return <>
        {!required && <div className="pos-fixed inset-0 bg-surface-overlay z-10" onClick={onClose}/>}
        <div className="settings-modal bg-primary border-1 border-black pos-fixed elevated-sharp p-1 flex flex-col br-2" role="dialog"
             aria-label={CERTIFICATION_TEXT.button}>
            <div className="flex flex-col p-2 gap-2 bg-middark br-1">
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text={certification ? `${CERTIFICATION_TEXT.button} · ${certification.host.name}` : CERTIFICATION_TEXT.button}/>
                    {!required && <IconButton icon="close-icon" onClick={onClose}/>}
                </div>

                {run && <div className={section} role="status">
                    <SubactionHeader text={CERTIFICATION_TEXT.runningCheck} className="text-gray"/>
                    <p className="text sm text-gray">{quickCheckProgressText(run, certification?.items)}</p>
                    <div className="flex flex-row">
                        <ButtonSm text={CERTIFICATION_TEXT.cancelCheck} buttonType="quaternary" onClick={() =>
                            requestQuickCheckCancel(endpoint).catch(error => console.warn("Could not cancel the quick check:", error))}/>
                    </div>
                </div>}

                <StartCheckSection required={required}/>

                <div className={section} id={REPORTS_SECTION_ID}>
                    <SubactionHeader text={CERTIFICATION_TEXT.reports} className="text-gray"/>
                    {!pending.length && <p className="text sm text-gray">{CERTIFICATION_TEXT.nothingPending}</p>}
                    {pending.length > 0 && <>
                        <p className="text sm text-white">{pendingSummary(pending)}</p>
                        <ul className="text sm text-gray">
                            {pendingRows(pending, list).map(row => <li key={row.report_id}>{row.text}</li>)}
                        </ul>
                        <label className="text sm text-gray flex flex-col gap-1">
                            {CERTIFICATION_TEXT.noteLabel}
                            <textarea className="setting-text-input" rows={3} value={handIn.note}
                                      onChange={event => handIn.setNote(event.target.value)}/>
                        </label>
                        <p className="text sm text-darkgray">{CERTIFICATION_TEXT.privacy}</p>
                        <div className="flex flex-row">
                            <ButtonSm text={CERTIFICATION_TEXT.viewReport} buttonType="quaternary" onClick={handIn.viewReport}/>
                        </div>
                    </>}
                    {view && <>
                        <p className="text sm text-gray">{view.file.file_name} ({view.file.size_bytes} bytes)</p>
                        <pre className="text sm text-white bg-dark p-1 br-1"
                             style={{maxHeight: '40vh', overflow: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)'}}>
                            {view.file.content}</pre>
                        {list?.relay_enabled === false && <p className="text sm text-gray">{CERTIFICATION_TEXT.relayNotSetUp}</p>}
                        {!view.file.fits_relay && <p className="text sm text-gray">{CERTIFICATION_TEXT.tooLarge}</p>}
                        <div className="flex flex-row gap-2 flex-wrap">
                            {list?.relay_enabled !== false && <ButtonSm text={CERTIFICATION_TEXT.sendReport} textColor="text-white"
                                className={prominent ? '' : 'primary accent'} buttonType={prominent ? 'quaternary' : ''} onClick={handIn.send}/>}
                            <ButtonSm text={CERTIFICATION_TEXT.issueForm} textColor={prominent ? 'text-white' : 'text-gray'}
                                      className={prominent ? 'primary accent' : ''} buttonType={prominent ? '' : 'quaternary'}
                                      onClick={handIn.issueForm}/>
                        </div>
                    </>}
                    {message && <p className={`text sm ${message.error ? 'settings-note-error' : 'text-white'}`} role="status">
                        {message.text}{message.issueUrl && <>: {link(message.issueUrl, message.issueUrl)}</>}</p>}
                    {list?.outbox.map(entry => <div key={entry.sha256} className="settings-note settings-note-dismissable">
                        <span>{outboxLine(entry)}</span>
                        <ButtonSm text={CERTIFICATION_TEXT.notSent} className="setting-action-button" onClick={() => handIn.notSent(entry.report_ids)}/>
                    </div>)}
                    {handedIn(list).map(group => <div key={group.issueUrl ?? 'opened'} className="settings-note settings-note-dismissable">
                        <span>{group.issueUrl ? <>Handed in as {link(group.issueUrl, issueLabel(group.issueUrl))}</>
                            : <>{CERTIFICATION_TEXT.issueFormOpened} ({link(ISSUE_FORM_URL, CERTIFICATION_TEXT.openIssueFormAgain)})</>}
                            {' '}· {group.reportIds.length} report{group.reportIds.length === 1 ? '' : 's'}</span>
                        <ButtonSm text={CERTIFICATION_TEXT.notSent} className="setting-action-button" onClick={() => handIn.notSent(group.reportIds)}/>
                    </div>)}
                </div>

                {!required && <div className="flex flex-row gap-2" style={{justifyContent: 'flex-end'}}>
                    <ButtonSm text={CERTIFICATION_TEXT.close} buttonType="quaternary" onClick={onClose}/>
                </div>}
            </div>
        </div>
    </>;
}
