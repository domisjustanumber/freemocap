import assert from 'node:assert/strict';
import {test} from 'node:test';
import type {TFunction} from 'i18next';
import english from '@/i18n/locales/en-english.json';
import {getPipelineStageRowTooltip} from './pipelineStageTooltips';

// i18next's lookup: a dotted path into the English resources, else the key itself.
const t = ((key: string) => key.split('.').reduce<unknown>((node, part) =>
    (node as Record<string, unknown> | undefined)?.[part], english) ?? key) as unknown as TFunction;

test('freemocap stages and per-camera stages have English descriptions', () => {
    assert.equal(getPipelineStageRowTooltip('skeleton_inference:predict_batch', t).short, 'Batch inference');
    assert.equal(getPipelineStageRowTooltip('skeleton_inference:pipeline.run', t).short, 'Tracker run');
    assert.equal(getPipelineStageRowTooltip('camera:cam0:charuco_detection', t).short, 'Charuco detection');
});

test('a 2.0 node span is described by its span kind, and an unknown stage falls back', () => {
    assert.deepEqual(getPipelineStageRowTooltip('skeleton_inference:person.inference', t),
        {short: 'person.inference', long: english.pipelineMetrics.spans.inference});
    assert.equal(getPipelineStageRowTooltip('skeleton_inference:carried_box.run', t).long, english.pipelineMetrics.spans.run);
    assert.deepEqual(getPipelineStageRowTooltip('aggregator:triangulate', t),
        {short: 'triangulate', long: english.pipelineMetrics.stages.no_description});
});
