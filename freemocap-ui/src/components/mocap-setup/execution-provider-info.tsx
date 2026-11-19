import type {ExecutionProviderOffer, ExecutionProviderOption} from '@/types/execution-provider';
import {isOffered} from '@/services/server/execution-providers';

/** What the EP menu and the legacy-key notice say about an EP that is not usable here: skellytracker's install sentence. */
export function NotUsableNote({provider}: {provider: ExecutionProviderOption}) {
    return <em>Not usable here.{provider.install_hint && <> {provider.install_hint}</>}</em>;
}

/**
 * What Auto could gain on the server's host, as skellytracker offers it (A1): each offer's own sentence, the label of its EP,
 * its download size and the licence link of a pack. All text comes from skellytracker; freemocap derives none.
 */
export function AutoOffersNote({offers, providers}: {
    offers: readonly ExecutionProviderOffer[]; providers: readonly ExecutionProviderOption[];
}) {
    if (!offers.length) return null;
    return <div className="settings-note" role="status">
        <p>For Auto, SkellyTracker offers:</p>
        {offers.map((offer, index) => <p key={`${offer.kind}:${offer.ep_key ?? index}`}>
            {offer.ep_key && <><strong>{providers.find(({key}) => key === offer.ep_key)?.label ?? offer.ep_key}</strong>: </>}
            {offer.note}
            {offer.download_bytes !== null && <> ({Math.round(offer.download_bytes / 1e6)} MB download)</>}
            {offer.licence_url && <> <a href={offer.licence_url} target="_blank" rel="noopener noreferrer">{offer.licence_url}</a></>}
        </p>)}
    </div>;
}

/** The explanation of the execution provider row: skellytracker's sentence for each EP of the server's host. */
export function executionProviderInfo(providers: readonly ExecutionProviderOption[]) {
    return {
        title: 'Execution provider',
        text: <>
            <p><strong>Auto</strong> — the recommendation of SkellyTracker for this computer.</p>
            {providers.map(provider => <p key={provider.key}>
                <strong>{provider.label}</strong> — {provider.description}
                {!isOffered(provider) && <> <NotUsableNote provider={provider}/></>}
                {provider.checks.filter(check => check.usable && !check.certified && check.local_result === 'passed').map(check =>
                    <em key={check.device_key}> {provider.devices.find(({key}) => key === check.device_key)?.name ?? check.device_key}:
                        passed on this device, not yet reviewed.</em>)}
            </p>)}
        </>,
    };
}
