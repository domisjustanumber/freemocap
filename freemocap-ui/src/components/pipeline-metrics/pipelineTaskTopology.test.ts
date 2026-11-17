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
