import type {ExecutionProviderOption} from '@/types/execution-provider';

/** What the EP menu and the legacy-key notice say about an EP that is not usable here: skellytracker's install sentence. */
export function NotUsableNote({provider}: {provider: ExecutionProviderOption}) {
    return <em>Not usable here.{provider.install_hint && <> {provider.install_hint}</>}</em>;
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
