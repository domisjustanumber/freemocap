import {useEffect, useMemo, useState} from "react";
import {serverUrls} from "@/services";
import {useAppSelector} from "@/store/hooks";
import type {ExecutionProviderCatalog, ExecutionProviderName} from "@/types/execution-provider";
import {detectorShowsExecutionProvider, requestExecutionProviders, executionProviderOptions, offeredDevices} from "@/services/server/execution-providers";
import {executionProviderInfo} from "@/components/mocap-setup/execution-provider-info";

const NO_CATALOG: ExecutionProviderCatalog = {providers: [], detectorTakesExecutionProvider: {}, autoOffers: []};

/** The server's EP choices, their explanation, and which detectors take an EP. Queried again after reconnects or server changes. */
export function useExecutionProviderOptions(selected: ExecutionProviderName | null) {
    const {isConnected, serverPid} = useAppSelector(state => state.connection);
    const endpoint = serverUrls.getHttpUrl();
    const [loaded, setLoaded] = useState<{key: string; catalog: ExecutionProviderCatalog} | null>(null);
    const key = `${endpoint}:${serverPid}:${isConnected}`;
    useEffect(() => {
        setLoaded(null);
        if (!isConnected) return;
        const controller = new AbortController();
        requestExecutionProviders(endpoint, controller.signal)
            .then(catalog => {
                if (!controller.signal.aborted) setLoaded({key, catalog});
            })
            .catch(error => {
                if (!controller.signal.aborted) console.warn("Could not query ONNX providers:", error);
            });
        return () => controller.abort();
    }, [endpoint, isConnected, serverPid, key]);
    // A failed query must not advertise unsupported providers. Keep saved choices visible.
    const catalog = loaded?.key === key ? loaded.catalog : NO_CATALOG;
    const info = useMemo(() => executionProviderInfo(catalog.providers), [catalog]);
    return {
        /** The server's EPs as skellytracker gives them, in its order. */
        providers: catalog.providers,
        /** skellytracker's offers for its Auto recommendation on the server's host. */
        autoOffers: catalog.autoOffers,
        options: executionProviderOptions(selected, catalog.providers),
        info,
        /** The server's row of an EP, as skellytracker gives it; undefined for Auto or a key it does not list. */
        providerOf: (provider: ExecutionProviderName | null) => catalog.providers.find(({key}) => key === provider),
        /** The GPUs of an EP that skellytracker's checks make usable, most VRAM first; none for Auto or an unknown key. */
        devicesOf: (provider: ExecutionProviderName | null) => offeredDevices(catalog.providers.find(({key}) => key === provider)),
        /** The server's flag once it answers; before that, RTMW shows the row with Auto and the saved key. */
        takesExecutionProvider: (detector: string) =>
            detectorShowsExecutionProvider(loaded?.key === key ? catalog.detectorTakesExecutionProvider : null, detector),
    };
}

export type ExecutionProviderChoices = ReturnType<typeof useExecutionProviderOptions>;
