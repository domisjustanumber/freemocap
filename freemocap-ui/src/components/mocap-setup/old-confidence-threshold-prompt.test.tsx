import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup} from 'react-dom/server';
import {OldConfidenceThresholdPrompt} from './old-confidence-threshold-prompt';

const text = (html: string) => html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();

test('the prompt names the saved value, the new scale and default, and offers reset or keep (M1)', () => {
    assert.equal(text(renderToStaticMarkup(<OldConfidenceThresholdPrompt saved={0.004} onAnswer={() => {}}/>)),
        'The keypoint confidence score changed to a probability from 0 to 1. Your saved threshold 0.004 is on the old '
        + 'scale and lets almost every point through. The new default is 0.5.Reset to 0.5Keep 0.004');
});
