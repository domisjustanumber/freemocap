import {useEffect, useMemo, useState} from "react";
import {serverUrls} from "@/services";
import {useAppSelector} from "@/store/hooks";
import type {ExecutionProviderCatalog, ExecutionProviderName} from "@/types/execution-provider";
import {requestExecutionProviders, executionProviderOptions} from "@/services/server/execution-providers";
import {executionProviderInfo} from "@/components/mocap-setup/execution-provider-info";

const NO_CATALOG: ExecutionProviderCatalog = {providers: [], detectorTakesExecutionProvider: {}};

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
        options: executionProviderOptions(selected, catalog.providers),
        info,
        /** Unknown until the server answers: the row stays hidden, as no EP can be offered yet. */
        takesExecutionProvider: (detector: string) => catalog.detectorTakesExecutionProvider[detector] ?? false,
    };
}

export type ExecutionProviderChoices = ReturnType<typeof useExecutionProviderOptions>;
