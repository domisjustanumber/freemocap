import {stageOrdinal} from '@/components/pipeline-metrics/pipelineTaskTopology';
import type {RunTimingSnapshot, StageStats} from '@/services/server/server-helpers/pipeline-timing-types';

export type MetricsState = 'disconnected' | 'no-pipeline' | 'not-running' | 'timing-disabled' | 'ready';

/** What the window can show, from the current connection and the newest message of the chosen run only. */
export function metricsState(connected: boolean, run: RunTimingSnapshot | null): MetricsState {
    if (!connected) return 'disconnected';
    if (!run) return 'no-pipeline';
    if (!run.active) return 'not-running';
    return run.timingEnabled ? 'ready' : 'timing-disabled';
}

export function runLabel(run: Pick<RunTimingSnapshot, 'mode' | 'pipelineId' | 'cameraGroupId'>): string {
    return run.mode === 'realtime' ? `Real-time · camera group ${run.cameraGroupId}` : `Posthoc · ${run.pipelineId}`;
}

export function sortStages(stages: readonly StageStats[]): StageStats[] {
    // Stable sort: stages of equal rank keep the order they ran in.
    return [...stages].sort((a, b) => stageOrdinal(a) - stageOrdinal(b));
}
