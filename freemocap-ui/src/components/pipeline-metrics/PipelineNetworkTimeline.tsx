import React, {memo, useLayoutEffect, useMemo, useRef, useState} from 'react';
import {useTranslation} from 'react-i18next';
import {
    barWidthPercentInViewport,
    buildRulerTicks,
    formatBarDuration,
    formatDurationPrecise,
    formatRulerTick,
    type PipelineTimelineViewModel,
    type TimelineRowView,
    type VisibleTimelineWindow,
} from '@/components/pipeline-metrics/pipelineTimelineModel';
import {getPipelineStageRowTooltip} from '@/components/pipeline-metrics/pipelineStageTooltips';
import {CATEGORY_COLORS} from '@/components/pipeline-metrics/pipelineTaskTopology';
import IconButton from '@/components/ui-components/IconButton';
import {useTimelineChartZoom} from '@/hooks/useTimelineChartZoom';

const ROW_HEIGHT = 22;
const LABEL_WIDTH = 300;
const RULER_HEIGHT = 28;
const CHART_PADDING_RIGHT = 8;
const INDENT_PX = 14;

const tint = (color: string, percent: number) => `color-mix(in srgb, ${color} ${percent}%, transparent)`;

type Props = {
    model: PipelineTimelineViewModel;
    selectedTaskId: string | null;
    onSelectTask: (taskId: string | null) => void;
};

/** Parent-to-child links; the SVG scrolls with the rows it sits among. */
function TimelineLinks({model}: {model: PipelineTimelineViewModel}): React.ReactElement {
    const height = model.rows.length * ROW_HEIGHT;
    const paths = model.edges.map(edge => {
        const fromY = edge.fromRowIndex * ROW_HEIGHT + ROW_HEIGHT / 2;
        const toY = edge.toRowIndex * ROW_HEIGHT + ROW_HEIGHT / 2;
        const x1 = LABEL_WIDTH + 8;
        const x2 = LABEL_WIDTH + 24;
        const midX = (x1 + x2) / 2;
        return `M ${x1} ${fromY} C ${midX} ${fromY}, ${midX} ${toY}, ${x2} ${toY}`;
    });
    return (
        <svg style={{position: 'absolute', left: 0, top: 0, width: '100%', height, pointerEvents: 'none', overflow: 'visible'}}>
            {paths.map((d, i) => <path key={i} d={d} fill="none" stroke="currentColor" strokeOpacity={0.25} strokeWidth={1}/>)}
        </svg>
    );
}

const TimelineRow = memo(function TimelineRow({row, visibleWindow, selected, onSelect, isIncomplete}: {
    row: TimelineRowView;
    visibleWindow: VisibleTimelineWindow;
    selected: boolean;
    onSelect: () => void;
    isIncomplete: boolean;
}) {
    const {t} = useTranslation();
    const {leftPct, widthPct, visible} = barWidthPercentInViewport(row, visibleWindow.visibleStartMs, visibleWindow.visibleDurationMs);
    const parentSpan = row.parentSpanStartMs != null && row.parentSpanEndMs != null
        ? barWidthPercentInViewport({barStartMs: row.parentSpanStartMs, barEndMs: row.parentSpanEndMs},
            visibleWindow.visibleStartMs, visibleWindow.visibleDurationMs)
        : null;
    const color = CATEGORY_COLORS[row.category];
    const durationLabel = formatBarDuration(row.durationMs);
    const tooltipText = `${getPipelineStageRowTooltip(row.sourceKey, t).long} (${formatDurationPrecise(row.durationMs)})`;

    const barRef = useRef<HTMLDivElement>(null);
    const labelRef = useRef<HTMLSpanElement>(null);
    const [labelFits, setLabelFits] = useState(false);
    useLayoutEffect(() => {
        const bar = barRef.current;
        const label = labelRef.current;
        if (!bar || !label || !visible) {
            setLabelFits(false);
            return;
        }
        const measure = () => setLabelFits(label.getBoundingClientRect().width <= bar.getBoundingClientRect().width);
        measure();
        const observer = new ResizeObserver(measure);
        observer.observe(bar);
        return () => observer.disconnect();
    }, [visible, widthPct, visibleWindow.visibleDurationMs, durationLabel]);

    const frameBg = row.frameNumber == null ? 'transparent' : row.frameNumber % 2 === 1 ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.10)';
    const rowBg = selected ? tint('var(--green-500)', 12) : frameBg;
    return (
        <div onClick={onSelect} style={{
            display: 'flex', alignItems: 'center', height: ROW_HEIGHT, cursor: 'pointer', minWidth: 0, backgroundColor: rowBg,
            // Hatching marks a frame the server lists as incomplete.
            backgroundImage: isIncomplete
                ? 'repeating-linear-gradient(-45deg, transparent, transparent 4px, rgba(255, 200, 50, 0.08) 4px, rgba(255, 200, 50, 0.08) 8px)'
                : undefined,
        }}>
            <div style={{width: LABEL_WIDTH, minWidth: LABEL_WIDTH, flexShrink: 0, overflow: 'hidden', display: 'flex',
                alignItems: 'center', gap: 4, paddingLeft: 8 + row.indentLevel * INDENT_PX, paddingRight: 8}}>
                <span title={tooltipText} style={{flex: 1, minWidth: 0, fontSize: '0.7rem', color: 'var(--gray-400)', cursor: 'help',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                    {row.label}
                </span>
                {row.engine && <span title="skellytracker 2.0 span" style={{fontSize: '0.6rem', color: 'var(--blue-300)',
                    border: '1px solid var(--blue-700)', borderRadius: 3, padding: '0 3px'}}>{row.engine}</span>}
            </div>
            <div style={{flex: 1, position: 'relative', height: '100%', paddingRight: CHART_PADDING_RIGHT, minWidth: 0, overflow: 'hidden'}}>
                {parentSpan?.visible && <div style={{position: 'absolute', top: 2, bottom: 2, left: `${parentSpan.leftPct}%`,
                    width: `${parentSpan.widthPct}%`, borderLeft: `1px solid ${tint(color, 35)}`,
                    borderRight: `1px solid ${tint(color, 35)}`, backgroundColor: tint(color, 8), pointerEvents: 'none'}}/>}
                {visible && (
                    <div ref={barRef} title={tooltipText} style={{position: 'absolute', top: 4, bottom: 4, left: `${leftPct}%`,
                        width: `${widthPct}%`, minWidth: 2, borderRadius: 4, backgroundColor: color, display: 'flex',
                        alignItems: 'center', justifyContent: 'center', overflow: 'hidden'}}>
                        <span ref={labelRef} style={{fontSize: '0.6rem', fontWeight: 600, lineHeight: 1, color: 'var(--gray-100)',
                            textShadow: '0 0 2px rgba(0,0,0,0.75)', pointerEvents: 'none', padding: '0 1px', whiteSpace: 'nowrap',
                            visibility: labelFits ? 'visible' : 'hidden'}}>
                            {durationLabel}
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
});

export function PipelineNetworkTimeline({model, selectedTaskId, onSelectTask}: Props): React.ReactElement {
    const {t} = useTranslation();
    const {containerRef, visibleWindow, isZoomed, resetZoom, zoomIn, zoomOut, chartCursor, chartHandlers} = useTimelineChartZoom({
        baseStartMs: model.windowStartMs, baseDurationMs: model.windowDurationMs,
        labelWidthPx: LABEL_WIDTH, chartPaddingRightPx: CHART_PADDING_RIGHT,
    });
    const rulerTicks = useMemo(() => buildRulerTicks(visibleWindow.visibleDurationMs), [visibleWindow.visibleDurationMs]);
    const incompleteFrames = useMemo(() => new Set(model.incompleteFrames), [model.incompleteFrames]);
    const selectedRow = model.rows.find(row => row.taskId === selectedTaskId) ?? null;

    return (
        <div style={{display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0}}>
            <div style={{display: 'flex', height: RULER_HEIGHT, borderBottom: '1px solid var(--gray-700)', flexShrink: 0}}>
                <div style={{width: LABEL_WIDTH, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 2, paddingRight: 4}}>
                    <IconButton icon="minus-icon" title={t('zoomOut')} onClick={zoomOut}/>
                    <IconButton icon="plus-icon" title={t('zoomIn')} onClick={zoomIn}/>
                    {isZoomed && <IconButton icon="back-icon" title={t('resetZoom')} onClick={resetZoom}/>}
                </div>
                <div style={{flex: 1, position: 'relative', marginRight: CHART_PADDING_RIGHT}}>
                    {rulerTicks.map(tick => (
                        <span key={tick} style={{position: 'absolute', left: `${(tick / visibleWindow.visibleDurationMs) * 100}%`,
                            transform: 'translateX(-50%)', fontSize: '0.65rem', color: 'var(--gray-500)', top: 6}}>
                            {formatRulerTick(tick + (visibleWindow.visibleStartMs - model.windowStartMs))}
                        </span>
                    ))}
                </div>
            </div>
            <div ref={containerRef as React.Ref<HTMLDivElement>}
                style={{flex: 1, overflow: 'auto', position: 'relative', cursor: chartCursor}} {...chartHandlers}>
                <TimelineLinks model={model}/>
                {model.rows.length === 0
                    ? <p className="text sm p-2" style={{color: 'var(--gray-400)'}}>No task events in the newest frames yet.</p>
                    : model.rows.map(row => (
                        <TimelineRow key={row.taskId} row={row} visibleWindow={visibleWindow} selected={row.taskId === selectedTaskId}
                            onSelect={() => onSelectTask(row.taskId === selectedTaskId ? null : row.taskId)}
                            isIncomplete={row.frameNumber != null && incompleteFrames.has(row.frameNumber)}/>
                    ))}
            </div>
            {selectedRow && (
                <div className="text sm" style={{padding: 8, borderTop: '1px solid var(--gray-700)', flexShrink: 0, color: 'var(--gray-400)'}}>
                    <span style={{fontWeight: 600}}>{selectedRow.label}</span> · {selectedRow.durationMs.toFixed(2)} ms
                    {selectedRow.engine ? ` · skellytracker ${selectedRow.engine}` : ''}
                    <div style={{marginTop: 2}}>{getPipelineStageRowTooltip(selectedRow.sourceKey, t).long}</div>
                </div>
            )}
        </div>
    );
}
