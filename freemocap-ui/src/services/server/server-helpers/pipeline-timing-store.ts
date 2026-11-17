import {ConnectionState} from '@/services/server/server-helpers/websocket-connection';
import type {TransportService} from '@/services/server/transport/TransportService';
import type {PipelineTimingEvent, PipelineTimingMessage} from '@/services/server/transport/message-contract';
import {
    MAX_SAMPLED_FRAMES,
    RUN_EXPIRY_MS,
    type RunTimingSnapshot,
    type SampleStats,
    type StageStats,
    type StoredPipelineTaskEvent,
} from '@/services/server/server-helpers/pipeline-timing-types';

export interface FrameTiming {
    endToEndMs: number;
    /** Summed duration per source key within the frame. */
    stageMs: Map<string, number>;
}

export function sourceKeyOf(event: Pick<PipelineTimingEvent, 'node_kind' | 'camera_id' | 'stage'>): string {
    return event.node_kind === 'camera' && event.camera_id
        ? `camera:${event.camera_id}:${event.stage}`
        : `${event.node_kind}:${event.stage}`;
}

export function toStoredEvent(event: PipelineTimingEvent): StoredPipelineTaskEvent {
    return {
        taskId: event.task_id, parentTaskIds: event.parent_task_ids, stage: event.stage, nodeKind: event.node_kind,
        cameraId: event.camera_id, frameNumber: event.frame_number,
        startMs: event.start_time_ns / 1e6, endMs: event.end_time_ns / 1e6, durationMs: event.duration_ms,
        batchSize: event.batch_size, sourceKey: sourceKeyOf(event),
    };
}

/**
 * The timing of each complete frame from that frame's own events (PM plan §10.7, Q3): its end-to-end time
 * from the first event start to the last event end, and each stage's time. Never a sum of windows that were
 * sampled separately. The server sends only frames every active node kind reached; a frame it lists as
 * incomplete is skipped all the same.
 */
export function frameTimings(events: readonly StoredPipelineTaskEvent[], incompleteFrames: readonly number[]): Map<number, FrameTiming> {
    const incomplete = new Set(incompleteFrames);
    const byFrame = new Map<number, StoredPipelineTaskEvent[]>();
    for (const event of events) {
        if (event.frameNumber == null || incomplete.has(event.frameNumber)) continue;
        byFrame.set(event.frameNumber, [...(byFrame.get(event.frameNumber) ?? []), event]);
    }
    const timings = new Map<number, FrameTiming>();
    for (const [frame, frameEvents] of byFrame) {
        const stageMs = new Map<string, number>();
        for (const event of frameEvents) stageMs.set(event.sourceKey, (stageMs.get(event.sourceKey) ?? 0) + event.durationMs);
        timings.set(frame, {
            endToEndMs: Math.max(...frameEvents.map(e => e.endMs)) - Math.min(...frameEvents.map(e => e.startMs)),
            stageMs,
        });
    }
    return timings;
}

export function sampleStats(values: readonly number[]): SampleStats | null {
    if (values.length === 0) return null;
    return {meanMs: values.reduce((sum, value) => sum + value, 0) / values.length,
        minMs: Math.min(...values), maxMs: Math.max(...values), frames: values.length};
}

interface RunState {
    snapshot: RunTimingSnapshot;
    /** Complete frames by frame number: a frame seen again in a later message replaces its earlier timing. */
    frames: Map<number, FrameTiming>;
    stageInfo: Map<string, Pick<StageStats, 'stage' | 'nodeKind' | 'cameraId'>>;
}

/**
 * The newest pipeline_timing message of each run, keyed by mode and pipeline id, with the statistics of
 * the complete frames the window has seen. Each message replaces its run's picture; only the frame
 * statistics and the dropped-event sum since the window opened carry over, and `clear()` drops them.
 */
export class PipelineTimingStore {
    private readonly runsByKey = new Map<string, RunState>();

    ingest(message: PipelineTimingMessage, nowMs: number = performance.now()): void {
        const key = `${message.mode}:${message.pipeline_id}`;
        const previous = this.runsByKey.get(key);
        const frames = previous?.frames ?? new Map<number, FrameTiming>();
        const stageInfo = previous?.stageInfo ?? new Map<string, Pick<StageStats, 'stage' | 'nodeKind' | 'cameraId'>>();
        const events = message.events.map(toStoredEvent);
        for (const event of events) stageInfo.set(event.sourceKey, {stage: event.stage, nodeKind: event.nodeKind, cameraId: event.cameraId});
        for (const [frame, timing] of frameTimings(events, message.incomplete_frames)) frames.set(frame, timing);
        const newestFirst = [...frames.keys()].sort((a, b) => b - a);
        for (const frame of newestFirst.slice(MAX_SAMPLED_FRAMES)) frames.delete(frame);

        const timings = [...frames.values()];
        const stages: StageStats[] = [];
        for (const [sourceKey, info] of stageInfo) {
            const stats = sampleStats(timings.flatMap(timing => timing.stageMs.has(sourceKey) ? [timing.stageMs.get(sourceKey)!] : []));
            if (stats) stages.push({...stats, ...info, sourceKey, fps: stats.meanMs > 0 ? 1000 / stats.meanMs : 0});
        }
        this.runsByKey.set(key, {frames, stageInfo, snapshot: {
            key, mode: message.mode, pipelineId: message.pipeline_id, cameraGroupId: message.camera_group_id,
            active: message.realtime_pipeline_active, timingEnabled: message.log_pipeline_times_enabled,
            configuredCameraFpsHz: message.configured_camera_fps_hz, events,
            incompleteFrames: message.incomplete_frames, nodeLag: message.node_lag, staleNodes: message.stale_nodes,
            droppedInLastMessage: message.dropped_timing_events,
            droppedSinceOpened: (previous?.snapshot.droppedSinceOpened ?? 0) + message.dropped_timing_events,
            endToEnd: sampleStats(timings.map(timing => timing.endToEndMs)), stages, receivedAtMs: nowMs,
        }});
    }

    /** The runs that reported recently, in key order. */
    runs(nowMs: number = performance.now()): RunTimingSnapshot[] {
        return [...this.runsByKey.values()].map(run => run.snapshot)
            .filter(snapshot => nowMs - snapshot.receivedAtMs <= RUN_EXPIRY_MS)
            .sort((a, b) => a.key.localeCompare(b.key));
    }

    clear(): void {
        this.runsByKey.clear();
    }
}

/**
 * Feed a store from a transport. The store empties whenever the connection is not open, so after a
 * reconnect or a server restart it is rebuilt from fresh messages alone. Returns the unsubscribe.
 */
export function feedPipelineTimingStore(transport: TransportService, store: PipelineTimingStore): () => void {
    const onState = (state: ConnectionState) => { if (state !== ConnectionState.CONNECTED) store.clear(); };
    transport.on('state-change', onState);
    const stop = transport.subscribeToPipelineTiming(message => store.ingest(message));
    return () => { stop(); transport.off('state-change', onState); };
}
