import type {TFunction} from 'i18next';

// i18next splits keys at dots, and 2.0 span names contain one, so both separators become underscores.
const stageKey = (rowKey: string) => `pipelineMetrics.stages.${rowKey.replace(/[:.]/g, '_')}`;

function lookup(t: TFunction, key: string): {short: string; long: string} | null {
    const short = t(`${key}.short`);
    return short === `${key}.short` ? null : {short, long: t(`${key}.long`)};
}

/** Short label and description of a timeline row, by `node_kind:stage` or `camera:<camera id>:stage`. */
export function getPipelineStageRowTooltip(rowKey: string, t: TFunction): {short: string; long: string} {
    const parts = rowKey.split(':');
    const stage = parts.slice(parts.length >= 3 ? 2 : 1).join(':');
    const known = lookup(t, stageKey(rowKey))
        ?? (parts.length >= 3 ? lookup(t, stageKey(`${parts[0]}:${stage}`)) : null);
    if (known) return known;
    // A skellytracker 2.0 node span `<node_id>.<span>`: describe the span kind; node ids vary by pipeline.
    const span = stage.includes('.') ? stage.slice(stage.lastIndexOf('.') + 1) : null;
    const spanLong = span ? t(`pipelineMetrics.spans.${span}`) : null;
    if (span && spanLong !== `pipelineMetrics.spans.${span}`) return {short: stage, long: spanLong!};
    return {short: stage, long: t('pipelineMetrics.stages.no_description')};
}
