import {useCallback, useEffect, useRef, useState} from "react";
import type {Certification} from "@freemocap/client";
import {
    type HandInList, type HandInMessage, CERTIFICATION_TEXT, ISSUE_FORM_URL, requestHandIn, requestNotSent, requestOpened,
    requestReportFile, requestSend, type ViewedReport, viewIsCurrent,
} from "@/services/server/certification-hand-in";
import {describeError} from "@/store/slices/thunk-helpers";

interface Local {list: HandInList | null; note: string; view: ViewedReport | null; message: HandInMessage | null}
const NONE: Local = {list: null, note: '', view: null, message: null};

const errorText = (error: unknown) => describeError(error instanceof Error ? error.message : error) || String(error);

/** The browser's download of a text file, on the machine of this window (Electron shows its save dialog). */
function saveTextFile(name: string, content: string) {
    const url = URL.createObjectURL(new Blob([content], {type: 'text/markdown'}));
    const link = Object.assign(document.createElement('a'), {href: url, download: name});
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

/**
 * The hand-in part of the Certification dialog for one server identity (`serverKey`: endpoint, pid, connected).
 * The pending reports come from the server's `certification` state; the hand-in list (states, links, kept files) is
 * read while the dialog is open and again whenever the pending list changes. Answers to this window's requests are
 * shown until the next view or server change and never gate a later request.
 */
export function useHandIn(endpoint: string, serverKey: string, open: boolean, certification: Certification | null) {
    const [state, setState] = useState<Local & {key: string}>({key: serverKey, ...NONE});
    const local: Local = state.key === serverKey ? state : NONE;
    const update = useCallback((patch: Partial<Local>) => setState(previous =>
        ({...(previous.key === serverKey ? previous : {key: serverKey, ...NONE}), ...patch})), [serverKey]);
    const current = useRef(serverKey);
    current.current = serverKey;
    // Each request answers only if the server is still the one it asked.
    const answer = useCallback(<T, >(key: string, apply: (value: T) => void) => (value: T) => {
        if (current.current === key) apply(value);
    }, []);

    const pending = certification?.pending_reports ?? [];
    const pendingKey = pending.map(report => report.report_id).join('\n');
    const known = certification !== null;
    useEffect(() => {
        if (!open || !known) return;
        const controller = new AbortController();
        requestHandIn(endpoint, controller.signal)
            .then(list => { if (!controller.signal.aborted) update({list}); })
            .catch(error => { if (!controller.signal.aborted) console.warn("Could not read the hand-in list:", error); });
        return () => controller.abort();
    }, [open, known, endpoint, serverKey, pendingKey, update]);

    const view = useCallback(() => {
        const key = serverKey, reportIds = pendingKey ? pendingKey.split('\n') : [], note = local.note;
        update({view: null, message: null});
        requestReportFile(endpoint, reportIds, note).then(answer(key, file => update({view: {reportIds, note, file}})),
            answer(key, error => update({message: {text: CERTIFICATION_TEXT.couldNotView + errorText(error), error: true, offerIssueForm: false}})));
    }, [endpoint, serverKey, pendingKey, local.note, update, answer]);

    const viewed = viewIsCurrent(local.view, pending, local.note) ? local.view : null;
    const sending = useRef(false);
    const send = useCallback(() => {
        if (!viewed || sending.current) return;
        const key = serverKey;
        sending.current = true;
        requestSend(endpoint, viewed)
            .catch(error => ({text: CERTIFICATION_TEXT.couldNotSend + errorText(error), error: true, offerIssueForm: false}))
            .then(answer(key, (message: HandInMessage) => {
                update(message.viewAgain ? {message, view: null} : {message});
                requestHandIn(endpoint).then(answer(key, list => update({list})), () => undefined);
            }))
            .finally(() => { sending.current = false; });
    }, [endpoint, serverKey, viewed, update, answer]);

    /** Save the viewed file here, open the issue form, then mark the reports opened (handed in, no link; decision 24). */
    const issueForm = useCallback(() => {
        if (!viewed) return;
        const key = serverKey;
        saveTextFile(viewed.file.file_name, viewed.file.content);
        window.open(ISSUE_FORM_URL, '_blank', 'noopener');
        requestOpened(endpoint, viewed).then(answer(key, list => update({list, message: {text: CERTIFICATION_TEXT.issueFormHelp,
            error: false, offerIssueForm: false}})), answer(key, error => update({message: {text: CERTIFICATION_TEXT.couldNotMark
            + errorText(error), error: true, offerIssueForm: false}})));
    }, [endpoint, serverKey, viewed, update, answer]);

    /** "Not sent" (F19, F20): these reports are pending again and any kept file holding them is deleted. */
    const notSent = useCallback((reportIds: string[]) => {
        const key = serverKey;
        requestNotSent(endpoint, reportIds).then(answer(key, list => update({list, message: null})),
            answer(key, error => update({message: {text: errorText(error), error: true, offerIssueForm: false}})));
    }, [endpoint, serverKey, update, answer]);

    return {
        list: local.list,
        note: local.note,
        setNote: useCallback((note: string) => update({note}), [update]),
        /** The viewed file while it is still everything pending with the current note. */
        view: viewed,
        message: local.message,
        viewReport: view,
        send,
        issueForm,
        notSent,
    };
}
