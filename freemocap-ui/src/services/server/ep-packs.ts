import {createHttpClient} from '@freemocap/client/http';
import type {Certification} from '@freemocap/client';
import type {ExecutionProviderOption} from '@/types/execution-provider';
import {describeError} from '@/store/slices/thunk-helpers';

export type EpPackRun = NonNullable<Certification['pack_run']>;
export type EpPackResult = NonNullable<Certification['last_pack_result']>;
export type EpPackAction = 'install' | 'remove';

/**
 * The Install and Remove controls of an EP (F15 step 5, F16): only for an EP of the Windows ML catalog (so only on
 * Windows) that a GPU here can run and that is not a field-test EP with no opt-in (skellytracker never offers that one).
 * Install only adds a missing package; Remove is always there, so a cancelled install can be cleared. Null: no controls.
 */
export function packControls({source, state}: ExecutionProviderOption): {install: boolean} | null {
    if (source !== 'windows-ml' || state === undefined || state === 'unsupported' || state === 'field_test') return null;
    return {install: state === 'not_installed'};
}

/** Everything the controls say, in one place. "machine" is the computer (G1). */
export const EP_PACK_TEXT = {
    install: 'Install',
    remove: 'Remove',
    cancel: 'Cancel install',
    keep: 'Keep',
    confirmRemove: (label: string) => `Remove ${label}? Windows removes the package that this app installed for it; a `
        + 'package that was on this system before stays.',
    couldNotStart: (action: EpPackAction) => `${action === 'install' ? 'Install' : 'Remove'} could not start: `,
} as const;

/** skellytracker's state of a Windows ML EP, in words. */
export const packStateText = (state: string) => state === 'not_installed' ? 'not installed'
    : state === 'ready' ? 'installed' : state.replace(/_/g, ' ');

/** The running install or remove: Windows ML's fraction as a percentage once it has one. */
export function packProgressText(run: EpPackRun, label: string): string {
    if (run.action !== 'install') return `Removing ${label}…`;
    return `Installing ${label}: ${run.fraction === undefined ? 'starting' : `${Math.round(run.fraction * 100)}%`}`;
}

/** How the last install or remove ended, from `certification.last_pack_result`. */
export function packResultText({action, result, reason, message}: EpPackResult, label: string): string {
    const verb = action === 'install' ? 'Install' : 'Remove';
    if (result === 'done') {
        if (action === 'install') return `${label} installed`;
        return reason === 'was-present'
            ? `${label} removed from this app; its package was on this system before and stays` : `${label} removed`;
    }
    if (result === 'cancelled') return `Install of ${label} cancelled. Remove takes away anything it added.`;
    if (result === 'failed' && action === 'remove' && reason === 'no-record') {
        return `Nothing to remove: no install of ${label} by this app is recorded`;
    }
    if (result === 'failed') return `${verb} of ${label} failed: ${message ?? reason ?? result}`;
    return `${verb} of ${label} could not run: ${reason ?? result}`;
}

/** Start an install or remove of one EP. Null when accepted, else the server's reason. */
export async function requestEpPack(baseUrl: string, action: EpPackAction, executionProvider: string,
    request: typeof fetch = fetch): Promise<string | null> {
    const responses = createHttpClient({baseUrl, fetch: request}).responses;
    const body = {body: {execution_provider: executionProvider}};
    const response = action === 'install'
        ? await responses.install_ep_pack_freemocap_certify_ep_pack_install_post(body)
        : await responses.remove_ep_pack_freemocap_certify_ep_pack_remove_post(body);
    if (response.ok) return null;
    const answer: unknown = await response.json().catch(() => null);
    return describeError(answer) || `HTTP ${response.status}`;
}

/** Ask a running install to stop; the server's state shows when and how it ended. */
export async function requestEpPackCancel(baseUrl: string, request: typeof fetch = fetch): Promise<void> {
    const response = await createHttpClient({baseUrl, fetch: request}).responses.cancel_ep_pack_freemocap_certify_ep_pack_delete({});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
}
