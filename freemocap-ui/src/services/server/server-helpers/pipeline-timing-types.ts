/** The timeline shows this many of the newest complete frames a pipeline_timing message carries. */
export const PIPELINE_TIMELINE_FRAME_WINDOW = 5;

/** Complete frames kept per run for the end-to-end and per-stage statistics. */
export const MAX_SAMPLED_FRAMES = 120;

/** A run that sent nothing for this long has stopped reporting; the server sends about 4 Hz. */
export const RUN_EXPIRY_MS = 2000;

export type PipelineTaskCategory = 'capture' | 'tracking' | 'other';

/** One task event of a pipeline_timing message, in milliseconds of the server's perf_counter clock. */
export interface StoredPipelineTaskEvent {
    taskId: string;
    parentTaskIds: string[];
    stage: string;
    nodeKind: string;
    cameraId: string | null;
    frameNumber: number | null;
    startMs: number;
    endMs: number;
    durationMs: number;
    batchSize: number | null;
    /** `node_kind:stage`, or `camera:<camera id>:stage` for a per-camera event. */
    sourceKey: string;
}

/** Mean and range over the complete frames sampled so far. */
export interface SampleStats {
    meanMs: number;
    minMs: number;
    maxMs: number;
    frames: number;
}

/** One stage's time per frame, paired with the frame rate that time alone allows. */
export interface StageStats extends SampleStats {
    sourceKey: string;
    stage: string;
    nodeKind: string;
    cameraId: string | null;
    fps: number;
}

/** What the newest message of one run says, with the statistics of its sampled frames. */
export interface RunTimingSnapshot {
    /** `mode:pipeline_id`. */
    key: string;
    mode: 'realtime' | 'posthoc';
    pipelineId: string;
    cameraGroupId: string;
    active: boolean;
    timingEnabled: boolean;
    configuredCameraFpsHz: number | null;
    events: StoredPipelineTaskEvent[];
    incompleteFrames: number[];
    nodeLag: Record<string, number>;
    staleNodes: string[];
    /** Events the nodes dropped since the server built its previous message. */
    droppedInLastMessage: number;
    /** Running sum over the messages this window received for the run; restarts on reconnect. */
    droppedSinceOpened: number;
    /** First event start to last event end of each complete frame, from that frame's own events. */
    endToEnd: SampleStats | null;
    stages: StageStats[];
    receivedAtMs: number;
}
