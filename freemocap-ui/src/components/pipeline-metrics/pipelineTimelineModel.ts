import {
    PIPELINE_TIMELINE_FRAME_WINDOW,
    type PipelineTaskCategory,
    type StoredPipelineTaskEvent,
} from '@/services/server/server-helpers/pipeline-timing-types';
import {
    classifyTaskCategory,
    linkParents,
    orderTasksParentsBeforeChildren,
    taskLabel,
    timelineIndent,
    timingEngine,
    type TimingEngine,
} from '@/components/pipeline-metrics/pipelineTaskTopology';

export const FALLBACK_FRAME_DURATION_MS = 1000 / 30;
export const MIN_STARTUP_SCALE_FRAME_ANCHORS = 3;

export interface TimelineRowView {
    taskId: string;
    label: string;
    category: PipelineTaskCategory;
    engine: TimingEngine;
    frameNumber: number | null;
    barStartMs: number;
    barEndMs: number;
    durationMs: number;
    sourceKey: string;
    indentLevel: number;
    /** The span of the row's parent, drawn behind a nested row (absolute ms). */
    parentSpanStartMs: number | null;
    parentSpanEndMs: number | null;
}

export interface TimelineEdgeView {
    fromTaskId: string;
    toTaskId: string;
    fromRowIndex: number;
    toRowIndex: number;
}

export interface PipelineTimelineViewModel {
    windowStartMs: number;
    windowDurationMs: number;
    frameStart: number | null;
    frameEnd: number | null;
    frameDurationMs: number;
    rows: TimelineRowView[];
    edges: TimelineEdgeView[];
    incompleteFrames: number[];
}

export function formatBarDuration(durationMs: number): string {
    return durationMs < 1 ? '<1 ms' : `${Math.round(durationMs)} ms`;
}

export function formatDurationPrecise(durationMs: number): string {
    if (durationMs >= 100) return `${Math.round(durationMs)} ms`;
    if (durationMs >= 10) return `${durationMs.toFixed(1)} ms`;
    return `${durationMs.toFixed(2)} ms`;
}

/** Median time per frame between the earliest events of successive frames, once enough frames are seen. */
export function estimateFrameDurationFromFrameAnchors(
    events: readonly StoredPipelineTaskEvent[],
    minFrameAnchors = MIN_STARTUP_SCALE_FRAME_ANCHORS,
): number | null {
    const startByFrame = new Map<number, number>();
    for (const event of events) {
        if (event.frameNumber == null) continue;
        const existing = startByFrame.get(event.frameNumber);
        if (existing == null || event.startMs < existing) startByFrame.set(event.frameNumber, event.startMs);
    }
    const anchors = [...startByFrame.entries()].sort(([a], [b]) => a - b);
    if (anchors.length < minFrameAnchors) return null;
    const deltas: number[] = [];
    for (let i = 1; i < anchors.length; i++) {
        const frameDelta = anchors[i][0] - anchors[i - 1][0];
        const timeDelta = anchors[i][1] - anchors[i - 1][1];
        if (frameDelta > 0 && timeDelta > 0) deltas.push(timeDelta / frameDelta);
    }
    if (deltas.length === 0) return null;
    deltas.sort((a, b) => a - b);
    return deltas[Math.floor(deltas.length / 2)];
}

/** The camera's configured frame time, else the measured one, else 30 fps. */
export function resolveTimelineFrameDurationMs(events: readonly StoredPipelineTaskEvent[], configuredCameraFpsHz: number | null): number {
    if (configuredCameraFpsHz != null && configuredCameraFpsHz > 0) return 1000 / configuredCameraFpsHz;
    return estimateFrameDurationFromFrameAnchors(events) ?? FALLBACK_FRAME_DURATION_MS;
}

/**
 * The newest PIPELINE_TIMELINE_FRAME_WINDOW frames of one message as rows, parents above children.
 * The window spans that many frame times from the first frame's earliest event, in whole steps of that
 * width so a slow frame widens it without rescaling the chart on every message.
 */
export function buildTimelineViewModel(params: {
    events: readonly StoredPipelineTaskEvent[];
    configuredCameraFpsHz: number | null;
    incompleteFrames?: number[];
}): PipelineTimelineViewModel {
    const framed = params.events.filter(e => e.frameNumber != null);
    const frameEnd = framed.length > 0 ? Math.max(...framed.map(e => e.frameNumber as number)) : null;
    const frameStart = frameEnd != null ? Math.max(0, frameEnd - (PIPELINE_TIMELINE_FRAME_WINDOW - 1)) : null;
    const windowEvents = frameStart != null && frameEnd != null
        ? framed.filter(e => e.frameNumber! >= frameStart && e.frameNumber! <= frameEnd) : [];
    const frameDurationMs = resolveTimelineFrameDurationMs(params.events, params.configuredCameraFpsHz);
    const step = frameDurationMs * PIPELINE_TIMELINE_FRAME_WINDOW;
    const windowStartMs = windowEvents.length > 0 ? Math.min(...windowEvents.map(e => e.startMs)) : 0;
    const spanMs = windowEvents.length > 0 ? Math.max(...windowEvents.map(e => e.endMs)) - windowStartMs : 0;
    const windowDurationMs = Math.max(1, Math.ceil(spanMs / step)) * step;

    const ordered = orderTasksParentsBeforeChildren(linkParents(windowEvents));
    const byId = new Map(ordered.map(event => [event.taskId, event]));
    const rows: TimelineRowView[] = ordered.map(event => {
        const parent = event.parentTaskIds.map(id => byId.get(id)).find(Boolean);
        const indentLevel = timelineIndent(event);
        return {
            taskId: event.taskId, label: taskLabel(event), category: classifyTaskCategory(event),
            engine: timingEngine(event), frameNumber: event.frameNumber,
            barStartMs: event.startMs, barEndMs: event.endMs, durationMs: event.durationMs, sourceKey: event.sourceKey,
            indentLevel,
            parentSpanStartMs: indentLevel > 0 && parent ? parent.startMs : null,
            parentSpanEndMs: indentLevel > 0 && parent ? parent.endMs : null,
        };
    });
    const rowIndex = new Map(rows.map((row, index) => [row.taskId, index]));
    const edges: TimelineEdgeView[] = ordered.flatMap(event => event.parentTaskIds.flatMap(parentId => {
        const fromRowIndex = rowIndex.get(parentId), toRowIndex = rowIndex.get(event.taskId)!;
        return fromRowIndex === undefined || fromRowIndex === toRowIndex ? []
            : [{fromTaskId: parentId, toTaskId: event.taskId, fromRowIndex, toRowIndex}];
    }));
    return {windowStartMs, windowDurationMs, frameStart, frameEnd, frameDurationMs, rows, edges,
        incompleteFrames: params.incompleteFrames ?? []};
}

export function formatRulerTick(ms: number): string {
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

export const TIMELINE_MIN_VISIBLE_MS = 2;
export const TIMELINE_MAX_ZOOM_LEVEL = 500;
export const TIMELINE_ZOOM_WHEEL_FACTOR = 1.12;

export type TimelineZoomState = {
    zoomLevel: number;
    panMs: number;
};

export type VisibleTimelineWindow = TimelineZoomState & {
    visibleStartMs: number;
    visibleDurationMs: number;
    visibleEndMs: number;
};

export function resolveVisibleTimelineWindow(
    baseStartMs: number,
    baseDurationMs: number,
    zoomLevel: number,
    panMs: number,
): VisibleTimelineWindow {
    const safeBaseDuration = Math.max(baseDurationMs, TIMELINE_MIN_VISIBLE_MS);
    const maxZoom = Math.max(1, Math.min(TIMELINE_MAX_ZOOM_LEVEL, safeBaseDuration / TIMELINE_MIN_VISIBLE_MS));
    const clampedZoom = Math.max(1, Math.min(maxZoom, zoomLevel));
    const visibleDurationMs = Math.max(TIMELINE_MIN_VISIBLE_MS, safeBaseDuration / clampedZoom);
    const clampedPanMs = Math.max(0, Math.min(Math.max(0, safeBaseDuration - visibleDurationMs), panMs));
    const visibleStartMs = baseStartMs + clampedPanMs;
    return {zoomLevel: clampedZoom, panMs: clampedPanMs, visibleStartMs, visibleDurationMs,
        visibleEndMs: visibleStartMs + visibleDurationMs};
}

export function zoomTimelineAtPointer(
    baseStartMs: number,
    baseDurationMs: number,
    zoomLevel: number,
    panMs: number,
    pointerRatio: number,
    zoomIn: boolean,
): TimelineZoomState {
    const current = resolveVisibleTimelineWindow(baseStartMs, baseDurationMs, zoomLevel, panMs);
    const factor = zoomIn ? TIMELINE_ZOOM_WHEEL_FACTOR : 1 / TIMELINE_ZOOM_WHEEL_FACTOR;
    const nextDuration = Math.max(TIMELINE_MIN_VISIBLE_MS, current.visibleDurationMs / factor);
    const clampedPointer = Math.max(0, Math.min(1, pointerRatio));
    const timeAtPointer = current.visibleStartMs + clampedPointer * current.visibleDurationMs;
    const nextPanMs = timeAtPointer - clampedPointer * nextDuration - baseStartMs;
    return resolveVisibleTimelineWindow(baseStartMs, baseDurationMs, baseDurationMs / nextDuration, nextPanMs);
}

export function panTimelineByPixels(
    baseStartMs: number,
    baseDurationMs: number,
    zoomLevel: number,
    panMs: number,
    deltaPixels: number,
    chartWidthPx: number,
): TimelineZoomState {
    const current = resolveVisibleTimelineWindow(baseStartMs, baseDurationMs, zoomLevel, panMs);
    if (current.zoomLevel <= 1 || chartWidthPx <= 0) return {zoomLevel: current.zoomLevel, panMs: current.panMs};
    const msPerPixel = current.visibleDurationMs / chartWidthPx;
    return resolveVisibleTimelineWindow(baseStartMs, baseDurationMs, current.zoomLevel, current.panMs - deltaPixels * msPerPixel);
}

export function buildRulerTicks(visibleDurationMs: number): number[] {
    const step = visibleDurationMs <= 20 ? 2 : visibleDurationMs <= 100 ? 10 : visibleDurationMs <= 500 ? 50 : 100;
    const ticks: number[] = [];
    for (let t = 0; t <= visibleDurationMs; t += step) ticks.push(t);
    if (ticks[ticks.length - 1] !== visibleDurationMs) ticks.push(visibleDurationMs);
    return ticks;
}

export function barWidthPercentInViewport(
    row: Pick<TimelineRowView, 'barStartMs' | 'barEndMs'>,
    visibleStartMs: number,
    visibleDurationMs: number,
): {leftPct: number; widthPct: number; visible: boolean} {
    const clippedStartMs = Math.max(row.barStartMs, visibleStartMs);
    const clippedEndMs = Math.min(row.barEndMs, visibleStartMs + visibleDurationMs);
    if (clippedEndMs <= clippedStartMs || visibleDurationMs <= 0) return {leftPct: 0, widthPct: 0, visible: false};
    return {
        leftPct: Math.max(0, Math.min(100, ((clippedStartMs - visibleStartMs) / visibleDurationMs) * 100)),
        widthPct: Math.max(0.15, Math.min(100, ((clippedEndMs - clippedStartMs) / visibleDurationMs) * 100)),
        visible: true,
    };
}
