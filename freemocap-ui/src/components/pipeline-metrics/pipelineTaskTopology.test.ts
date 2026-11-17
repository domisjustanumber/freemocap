import assert from 'node:assert/strict';
import {test} from 'node:test';
import {toStoredEvent} from '@/services/server/server-helpers/pipeline-timing-store';
import {
    classifyTaskCategory,
    linkParents,
    orderTasksParentsBeforeChildren,
    taskLabel,
    timelineIndent,
    timingEngine,
} from './pipelineTaskTopology';
import {realtimeFrame} from './__fixtures__/realtime-frame';

test('2.0 spans are tagged by engine and nest two levels deep; freemocap stages are not tagged', () => {
    const events = realtimeFrame(7).map(toStoredEvent);
    assert.deepEqual(events.map(e => [e.stage, timingEngine(e), timelineIndent(e), classifyTaskCategory(e)]), [
        ['charuco_detection', null, 0, 'capture'],
        ['frame_read', null, 0, 'tracking'],
        ['predict_batch', null, 0, 'tracking'],
        ['wholebody.inference', '2.0', 2, 'tracking'],
        ['person.inference', '2.0', 2, 'tracking'],
        ['pipeline.run', '2.0', 1, 'tracking'],
        ['crop.run', '2.0', 2, 'tracking'],
    ]);
    assert.equal(taskLabel(events[0]), 'F7 · cam0 · Charuco detection');
    assert.equal(taskLabel(events[4]), 'F7 · person.inference');
    assert.equal(taskLabel(events[5]), 'F7 · Tracker run (pipeline.run)');
});

test('parents: 2.0 spans keep the server link to pipeline.run, which goes under its frame predict_batch, under frame_read', () => {
    const linked = linkParents([...realtimeFrame(7), ...realtimeFrame(8, 40)].map(toStoredEvent));
    const parent = (taskId: string) => linked.find(e => e.taskId === taskId)!.parentTaskIds;
    assert.deepEqual(parent('p1:8:batch:skeleton_inference:pipeline.run'), ['8:batch:skeleton_inference:predict_batch']);
    assert.deepEqual(parent('8:batch:skeleton_inference:predict_batch'), ['8:batch:skeleton_inference:frame_read']);
    assert.deepEqual(parent('p1:8:batch:skeleton_inference:person.inference'), ['p1:8:batch:skeleton_inference:pipeline.run']);
    assert.deepEqual(parent('8:batch:skeleton_inference:frame_read'), []);
    assert.deepEqual(parent('8:cam0:camera:charuco_detection'), []);
});

test('rows put each parent directly above its children, in start order within a frame', () => {
    const ordered = orderTasksParentsBeforeChildren(linkParents([...realtimeFrame(8, 40), ...realtimeFrame(7)].map(toStoredEvent)));
    assert.deepEqual(ordered.slice(0, 7).map(e => e.stage), [
        'charuco_detection', 'frame_read', 'predict_batch', 'pipeline.run', 'person.inference', 'crop.run', 'wholebody.inference']);
    assert.deepEqual(ordered.slice(7).map(e => e.frameNumber), Array(7).fill(8));
});

// Deleted at skellytracker stage 2.4 (legacy tracker benchmark): this whole test.
test('legacy spans are tagged legacy, nest inside predict_batch, and the comparable ones name their 2.0 span', () => {
    const predict = `7:batch:skeleton_inference:predict_batch`;
    const base = realtimeFrame(7).filter(e => !e.stage.includes('.'));
    const legacy = [
        {...base[2], task_id: `p1:7:batch:skeleton_inference:object_detection_infer`, stage: 'object_detection_infer', parent_task_ids: [predict]},
        {...base[2], task_id: `p1:7:cam0:skeleton_inference:crop`, stage: 'crop', camera_id: 'cam0', parent_task_ids: [predict]},
    ];
    const events = [...base, ...legacy].map(toStoredEvent);
    assert.deepEqual(events.slice(-2).map(e => [timingEngine(e), timelineIndent(e)]), [['legacy', 1], ['legacy', 1]]);
    assert.equal(taskLabel(events.at(-2)!), 'F7 · Person detection inference (compare person.inference)');
    assert.equal(taskLabel(events.at(-1)!), 'F7 · cam0 · Crop');
    assert.equal(timingEngine({nodeKind: 'skeleton_inference', stage: 'child_hands'}), 'legacy');
    assert.equal(timingEngine({nodeKind: 'skeleton_inference', stage: 'predict_batch'}), null);
    const ordered = orderTasksParentsBeforeChildren(linkParents(events));
    assert.deepEqual(ordered.map(e => e.stage).slice(1), ['frame_read', 'predict_batch', 'object_detection_infer', 'crop']);
});
