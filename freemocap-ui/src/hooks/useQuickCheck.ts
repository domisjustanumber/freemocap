import {useCallback, useEffect, useRef, useState} from "react";
import type {Certification} from "@freemocap/client";
import {
    type CheckIntent, checkIntentOutcome, type MenuPair, requestQuickCheck, requestQuickCheckCancel,
} from "@/services/server/execution-providers";
import type {DetectorType, RTMPoseModelName} from "@/store/slices/mocap";
import type {ExecutionProviderName} from "@/types/execution-provider";
import {describeError} from "@/store/slices/thunk-helpers";

/** The choice a prompt asks about (F5, F9): one pair, and the selection a pass makes. */
export interface QuickCheckPrompt {
    pair: MenuPair;
    change: {provider: ExecutionProviderName; device: string | null};
}

interface Local {
    prompt: QuickCheckPrompt | null;
    intent: CheckIntent | null;
    /** The server's refusal of this window's last start; the answer to that request only. */
    refusal: string | null;
    /** The `last_result` the person moved on from by a new choice; hidden until the next check. */
    dismissed: string | null;
}
const NONE: Local = {prompt: null, intent: null, refusal: null, dismissed: null};

/**
 * The quick-check prompt and the check this window started, for one server identity (`serverKey`: endpoint, pid,
 * connected). Everything shown about a check comes from `certification`; this keeps only what the person asked in
 * this window, and drops it when the server changes or the person makes another choice. Nothing is queued (F8).
 */
export function useQuickCheck(endpoint: string, serverKey: string, certification: Certification | null) {
    const [state, setState] = useState<Local & {key: string}>({key: serverKey, ...NONE});
    const local: Local = state.key === serverKey ? state : NONE;
    const update = useCallback((patch: Partial<Local>) => setState(previous =>
        ({...(previous.key === serverKey ? previous : {key: serverKey, ...NONE}), ...patch})), [serverKey]);
    // A start answered after a newer choice, or by a server that is no longer this one, is obsolete.
    const generation = useRef(0);
    const current = useRef(serverKey);
    current.current = serverKey;

    const outcome = local.intent ? checkIntentOutcome(local.intent, certification) : null;
    const resultKey = certification?.last_result ? JSON.stringify(certification.last_result) : null;
    useEffect(() => {
        if (certification?.run && local.dismissed !== null) update({dismissed: null});
        if (outcome === 'running' && certification?.run && local.intent && !local.intent.sawRun) {
            update({intent: {...local.intent, sawRun: true}});
        }
        if (outcome === 'ended') update({intent: null});
    }, [certification, outcome, local.intent, local.dismissed, update]);

    /** The person made a choice in the EP, Device or detector row: earlier prompts, refusals and results are done. */
    const choose = useCallback((prompt: QuickCheckPrompt | null = null) => {
        generation.current += 1;
        update({prompt, intent: null, refusal: null, dismissed: resultKey});
    }, [update, resultKey]);

    const run = useCallback(async (pair: {execution_provider: string; device_key: string}, change: QuickCheckPrompt['change'] | null,
        detector: {detector_type: DetectorType; rtmpose_model_name: RTMPoseModelName}) => {
        const started = ++generation.current, key = serverKey, before = resultKey ?? undefined;
        update({prompt: null, intent: null, refusal: null});
        const refusal = await requestQuickCheck(endpoint, pair, detector).catch(error => describeError(error) || String(error));
        if (generation.current !== started || current.current !== key) return;
        update(refusal !== null ? {refusal} : {intent: change && {pair, change, before, sawRun: false}});
    }, [endpoint, serverKey, resultKey, update]);

    const cancel = useCallback(() => {
        requestQuickCheckCancel(endpoint).catch(error => console.warn("Could not cancel the quick check:", error));
    }, [endpoint]);

    return {
        prompt: local.prompt,
        refusal: local.refusal,
        /** The last check's ending, unless the person has made a choice since (item 6). */
        showsResult: resultKey !== null && !certification?.run && resultKey !== local.dismissed,
        /** The selection a passed check of this window makes (F6); the rows apply it, then call `settle`. */
        passed: outcome === 'passed' ? local.intent?.change ?? null : null,
        settle: useCallback(() => update({intent: null}), [update]),
        choose,
        /** "Not now": the prompt closes and the selection stays what it was (F6). */
        notNow: useCallback(() => update({prompt: null}), [update]),
        run,
        cancel,
    };
}

export type QuickCheckControls = ReturnType<typeof useQuickCheck>;
