import type {PipelineTaskCategory, StoredPipelineTaskEvent} from '@/services/server/server-helpers/pipeline-timing-types';

const SKELETON_INFERENCE = 'skeleton_inference';
/** A posthoc run's wait for the frame of every camera. */
const VIDEO_READ = 'video_read';
export const PIPELINE_RUN_STAGE = 'pipeline.run';

/** The engine that measured a row: skellytracker 2.0 spans, or null for freemocap's own stages.
 *  The legacy tracker path (PM commit 8) adds its own tag. */
export type TimingEngine = '2.0' | null;

type EventShape = Pick<StoredPipelineTaskEvent, 'nodeKind' | 'stage'>;

/** skellytracker 2.0 names its spans `<node_id>.<span>` (person.inference, crop.run) and `pipeline.run`. */
export function timingEngine(event: EventShape): TimingEngine {
    return event.nodeKind === SKELETON_INFERENCE && event.stage.includes('.') ? '2.0' : null;
}

export function classifyTaskCategory(event: Pick<StoredPipelineTaskEvent, 'nodeKind'>): PipelineTaskCategory {
    if (event.nodeKind === 'camera' || event.nodeKind === VIDEO_READ) return 'capture';
    if (event.nodeKind === SKELETON_INFERENCE) return 'tracking';
    return 'other';
}

export const CATEGORY_COLORS: Record<PipelineTaskCategory, string> = {
    capture: 'var(--green-400)',
    tracking: 'var(--warning-400)',
    other: 'var(--gray-400)',
};

/** Labels of freemocap's stages; a 2.0 span keeps its own `<node_id>.<span>` name. */
export const PRETTY_STAGE_LABELS: Record<string, string> = {
    'skeleton_inference:frame_read': 'Frame read',
    'skeleton_inference:predict_batch': 'Batch inference',
    'skeleton_inference:pipeline.run': 'Tracker run (pipeline.run)',
    'camera:charuco_detection': 'Charuco detection',
    'video_read:graph.camera_batch_wait': 'Video read (all cameras)',
};

/** freemocap's skeleton stages in processing order; 2.0 node spans follow `pipeline.run` in the order they ran. */
export const SKELETON_INFERENCE_STAGE_ORDER: readonly string[] = ['frame_read', 'predict_batch', PIPELINE_RUN_STAGE];

/** Stages drawn inside `predict_batch`. */
const PREDICT_BATCH_CHILD_STAGES = new Set([PIPELINE_RUN_STAGE]);

/** Rows nest: `pipeline.run` inside `predict_batch`, and every other 2.0 span inside `pipeline.run`. */
export function timelineIndent(event: EventShape): number {
    if (event.nodeKind !== SKELETON_INFERENCE) return 0;
    if (PREDICT_BATCH_CHILD_STAGES.has(event.stage)) return 1;
    return timingEngine(event) === '2.0' ? 2 : 0;
}

/** Order key of a stage: capture first, then the skeleton stages in processing order. */
export function stageOrdinal(event: EventShape): number {
    const category = classifyTaskCategory(event);
    if (category !== 'tracking') return category === 'capture' ? 0 : 100;
    const index = SKELETON_INFERENCE_STAGE_ORDER.indexOf(event.stage);
    return 10 + (index === -1 ? SKELETON_INFERENCE_STAGE_ORDER.length : index);
}

export function stageLabel(sourceKey: string, stage: string, cameraId: string | null): string {
    const normalized = cameraId ? sourceKey.replace(`:${cameraId}:`, ':') : sourceKey;
    const label = PRETTY_STAGE_LABELS[normalized] ?? stage;
    return cameraId ? `${cameraId} · ${label}` : label;
}

export function taskLabel(event: StoredPipelineTaskEvent): string {
    const base = stageLabel(event.sourceKey, event.stage, event.cameraId);
    return event.frameNumber != null ? `F${event.frameNumber} · ${base}` : base;
}

/**
 * Parents of each event. The server links each 2.0 span to its frame's `pipeline.run`; freemocap's stages
 * carry no parents, so `pipeline.run` is linked to its frame's `predict_batch` (it runs inside that wait)
 * and `predict_batch` to its frame's `frame_read`.
 */
export function linkParents(events: readonly StoredPipelineTaskEvent[]): StoredPipelineTaskEvent[] {
    const skeletonTask = new Map<string, string>();
    for (const event of events) {
        if (event.nodeKind === SKELETON_INFERENCE && event.frameNumber != null) {
            skeletonTask.set(`${event.frameNumber}:${event.stage}`, event.taskId);
        }
    }
    const implied: Record<string, string> = {[PIPELINE_RUN_STAGE]: 'predict_batch', predict_batch: 'frame_read'};
    return events.map(event => {
        const parentStage = implied[event.stage];
        if (event.parentTaskIds.length > 0 || event.nodeKind !== SKELETON_INFERENCE || !parentStage) return event;
        const parent = skeletonTask.get(`${event.frameNumber}:${parentStage}`);
        return parent ? {...event, parentTaskIds: [parent]} : event;
    });
}

export function compareTimelineRows(a: StoredPipelineTaskEvent, b: StoredPipelineTaskEvent): number {
    const frameA = a.frameNumber ?? Number.MAX_SAFE_INTEGER;
    const frameB = b.frameNumber ?? Number.MAX_SAFE_INTEGER;
    if (frameA !== frameB) return frameA - frameB;
    if (a.startMs !== b.startMs) return a.startMs - b.startMs;
    return a.taskId.localeCompare(b.taskId);
}

/** Place parents above children while keeping compareTimelineRows order among siblings. */
export function orderTasksParentsBeforeChildren(events: readonly StoredPipelineTaskEvent[]): StoredPipelineTaskEvent[] {
    const byId = new Map(events.map(event => [event.taskId, event]));
    const childrenByParent = new Map<string, StoredPipelineTaskEvent[]>();
    const roots: StoredPipelineTaskEvent[] = [];
    for (const event of events) {
        const parent = event.parentTaskIds.find(id => byId.has(id) && id !== event.taskId);
        if (parent) childrenByParent.set(parent, [...(childrenByParent.get(parent) ?? []), event]);
        else roots.push(event);
    }
    const ordered: StoredPipelineTaskEvent[] = [];
    const seen = new Set<string>();
    const visit = (event: StoredPipelineTaskEvent) => {
        if (seen.has(event.taskId)) return;
        seen.add(event.taskId);
        ordered.push(event);
        for (const child of (childrenByParent.get(event.taskId) ?? []).sort(compareTimelineRows)) visit(child);
    };
    roots.sort(compareTimelineRows).forEach(visit);
    // A parent cycle leaves events unvisited; show them rather than drop them.
    events.filter(event => !seen.has(event.taskId)).sort(compareTimelineRows).forEach(visit);
    return ordered;
}
