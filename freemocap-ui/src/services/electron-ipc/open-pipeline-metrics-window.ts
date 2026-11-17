import {isElectron} from '@/services/electron-ipc/electron-ipc';
import {electronIpcClient} from '@/services/electron-ipc/electron-ipc-client';

export const PIPELINE_METRICS_HASH = '#/pipeline-metrics';

/** The window's hash; `pipeline` (`mode:pipeline_id`) preselects that run. */
export function pipelineMetricsHash(pipeline?: string): string {
    return pipeline ? `${PIPELINE_METRICS_HASH}?${new URLSearchParams({pipeline})}` : PIPELINE_METRICS_HASH;
}

/** Open the pipeline metrics window, or focus it when it is already open; with `pipeline`, show that run. */
export async function openPipelineMetricsWindow(pipeline?: string): Promise<void> {
    if (isElectron()) {
        await electronIpcClient.windows.openPipelineMetrics.mutate(pipeline ? {pipeline} : undefined);
        return;
    }
    // The named target reuses the window a second open made; a new hash switches its run.
    window.open(`${window.location.origin}${window.location.pathname}${pipelineMetricsHash(pipeline)}`,
        'freemocap-pipeline-metrics', 'width=1100,height=760')?.focus();
}
