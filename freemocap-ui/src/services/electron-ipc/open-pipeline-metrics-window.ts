import {isElectron} from '@/services/electron-ipc/electron-ipc';
import {electronIpcClient} from '@/services/electron-ipc/electron-ipc-client';

export const PIPELINE_METRICS_HASH = '#/pipeline-metrics';

/** Open the pipeline metrics window, or focus it when it is already open. */
export async function openPipelineMetricsWindow(): Promise<void> {
    if (isElectron()) {
        await electronIpcClient.windows.openPipelineMetrics.mutate();
        return;
    }
    // The named target reuses the window a second open made.
    window.open(`${window.location.origin}${window.location.pathname}${PIPELINE_METRICS_HASH}`,
        'freemocap-pipeline-metrics', 'width=1100,height=760')?.focus();
}
