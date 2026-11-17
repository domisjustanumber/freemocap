import type {ExecutionProviderOffer, ExecutionProviderOption} from '@/types/execution-provider';

/** What the EP menu and the legacy-key notice say about an EP that is not usable here: skellytracker's install sentence. */
export function NotUsableNote({provider}: {provider: ExecutionProviderOption}) {
    return <em>Not usable here.{provider.install_hint && <> {provider.install_hint}</>}</em>;
}

/**
 * What Auto could gain on the server's host, as skellytracker offers it (A1): each offer's own sentence, the label of its EP
 * and its download size. An offer without a sentence is not shown: freemocap derives no text.
 */
export function AutoOffersNote({offers, providers}: {
    offers: readonly ExecutionProviderOffer[]; providers: readonly ExecutionProviderOption[];
}) {
    const shown = offers.filter(offer => offer.note);
    if (!shown.length) return null;
    return <div className="settings-note" role="status">
        <p>For Auto, SkellyTracker offers:</p>
        {shown.map((offer, index) => <p key={`${offer.kind}:${offer.ep_key ?? index}`}>
            {offer.ep_key && <><strong>{providers.find(({key}) => key === offer.ep_key)?.label ?? offer.ep_key}</strong>: </>}
            {offer.note}
            {offer.download_bytes !== null && <> ({Math.round(offer.download_bytes / 1e6)} MB download)</>}
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
                {!provider.usable && <> <NotUsableNote provider={provider}/></>}
            </p>)}
        </>,
    };
}
