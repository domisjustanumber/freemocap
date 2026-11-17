import type {PipelineTimingEvent} from '@/services/server/transport/message-contract';

const MS = 1_000_000;

/** One realtime frame as S's backend sends it: freemocap's stages unprefixed, 2.0 spans prefixed by the pipeline id. */
export function realtimeFrame(frame: number, offsetMs = 0): PipelineTimingEvent[] {
    const span = (stage: string, startMs: number, endMs: number, taskId: string, parents: string[] = [], overrides: Partial<PipelineTimingEvent> = {}): PipelineTimingEvent => ({
        task_id: taskId, parent_task_ids: parents, stage, node_kind: 'skeleton_inference', camera_id: null, frame_number: frame,
        start_time_ns: (offsetMs + startMs) * MS, end_time_ns: (offsetMs + endMs) * MS, duration_ms: endMs - startMs,
        batch_index: null, batch_size: 2, ...overrides});
    const run = `p1:${frame}:batch:skeleton_inference:pipeline.run`;
    const spanId = (stage: string) => `p1:${frame}:batch:skeleton_inference:${stage}`;
    return [
        span('charuco_detection', 0, 4, `${frame}:cam0:camera:charuco_detection`, [], {node_kind: 'camera', camera_id: 'cam0'}),
        span('frame_read', 1, 2, `${frame}:batch:skeleton_inference:frame_read`),
        span('predict_batch', 2, 20, `${frame}:batch:skeleton_inference:predict_batch`),
        span('wholebody.inference', 12, 17, spanId('wholebody.inference'), [run]),
        span('person.inference', 4, 9, spanId('person.inference'), [run]),
        span('pipeline.run', 3, 19, run),
        span('crop.run', 10, 11, spanId('crop.run'), [run]),
    ];
}
