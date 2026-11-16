// Run: node src/components/realtime-processing/run-realtime-processing-tests.mjs
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Children, isValidElement, type ReactElement, type ReactNode} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
// The store import follows the application entry order: the detector rows take their model list from the mocap slice.
import '@/store';
import type {DetectorType, TriangulationConfig} from '@/store/slices/mocap';
import {executionProviderOptions} from '@/services/server/execution-providers';
import type {ExecutionProviderChoices} from '@/hooks/useExecutionProviderOptions';
import {DETECTOR_OPTIONS} from './detector-options';
import {
    CONFIDENCE_INFO, DETECTOR_INFO, DetectorSettingRows, type DetectorSettingsValue, MODEL_INFO, REALTIME_DETECTOR_NOTES,
} from './detector-setting-rows';
import {executionProviderInfo} from './execution-provider-info';
import {OutlierRejectionRows} from './outlier-rejection-rows';
import SkeletonAnchorSetting from './skeleton-anchor-setting';

type DetectorRowsProps = Parameters<typeof DetectorSettingRows>[0];
type Handler = (value: string | number | boolean) => void;
interface Info {title: string; text: ReactNode}
interface RowProps {label?: ReactNode; info?: Info; control?: ReactElement<{onChange?: Handler; onToggle?: Handler}>; children?: ReactNode}

const DETECTORS: DetectorType[] = ['rtmpose', 'mediapipe'];
/** The realtime pipeline's detector defaults. */
const VALUE: DetectorSettingsValue = {
    detector: 'rtmpose', model: 'rtmw-x-l_256x192', provider: null, confidence: 0.0025, device: null,
};
const CONFIG: TriangulationConfig = {
    use_outlier_rejection: true, minimum_cameras_for_triangulation: 2, maximum_cameras_to_drop: 1, target_reprojection_error: 0.02,
};
const OUTLIER_LIMITS = ['Minimum cameras for triangulation', 'Maximum cameras to drop', 'Target reprojection error'];
const CPU = {key: 'cpu', label: 'CPU', description: 'Runs on the processor.', usable: true, install_hint: null, uses_gpu: false, devices: []};
const GPU = {key: 'gpu-ep', label: 'GPU EP', description: 'Runs on a GPU.', usable: false,
    install_hint: 'Run `install gpu-ep`.', uses_gpu: true, devices: []};
/** The server's answer as the hook gives it: here only RTMW takes an EP. */
const PROVIDERS: ExecutionProviderChoices = {
    providers: [CPU, GPU], options: executionProviderOptions(null, [CPU, GPU]), info: executionProviderInfo([CPU, GPU]),
    takesExecutionProvider: detector => detector === 'rtmpose', devicesOf: () => [], providerOf: () => undefined,
};

/** The detector rows' props as the realtime controls pass them, for one detector. */
const detectorProps = (detector: DetectorType, rows: 'all' | 'key', more: Partial<DetectorRowsProps> = {}): DetectorRowsProps => ({
    value: {...VALUE, detector}, onChange: () => {}, detectors: DETECTOR_OPTIONS, providers: PROVIDERS,
    context: 'realtime', rows, ...more,
});
const detectorRows = (detector: DetectorType, rows: 'all' | 'key', more?: Partial<DetectorRowsProps>): string =>
    renderToStaticMarkup(<DetectorSettingRows {...detectorProps(detector, rows, more)}/>);
const outlierRows = (config: TriangulationConfig, inactive?: boolean): string =>
    renderToStaticMarkup(<OutlierRejectionRows config={config} onChange={() => {}} inactive={inactive}/>);

/** The opening tag of a setting row: its class list starts with the row's own class. */
const ROW = /<div class="setting-row[ "][^>]*>/;
/** Each setting row's markup, in order. A row runs from its opening tag to the next row's. */
const rowsOf = (html: string): string[] => html.split(new RegExp(`(?=${ROW.source})`)).filter(part => part.search(ROW) === 0);
/** A row's visible label. */
const labelOf = (row: string): string => row.match(/<span class="setting-row-label">([^<]*)</)?.[1] ?? '';
const labels = (html: string): string[] => rowsOf(html).map(labelOf);
const rowLabelled = (html: string, label: string): string => rowsOf(html).find(row => labelOf(row) === label) ?? '';
/** The labels of the dimmed rows. */
const dimmed = (html: string): string[] => rowsOf(html).filter(row => / setting-row-inactive[ "]/.test(row.match(ROW)?.[0] ?? '')).map(labelOf);
/** The values a row's select offers. */
const optionsOf = (row: string): string[] => [...row.matchAll(/<option value="([^"]*)"/g)].map(match => match[1]);

/**
 * The row with this label, as the element the rows return. The unit runner has no DOM to act in and a row's
 * explanation is not in the markup until it is opened, so the tests below read both from the row's own props.
 */
function rowElement(rows: ReactNode, label: string): RowProps | undefined {
    for (const child of Children.toArray(rows)) {
        if (!isValidElement<RowProps>(child)) continue;
        const found = child.props.label === label ? child.props : rowElement(child.props.children, label);
        if (found) return found;
    }
    return undefined;
}
/** The change handler of the control in the row with this label; the test calls it as the control would. */
function handlerOf(rows: ReactNode, label: string): Handler {
    const control = rowElement(rows, label)?.control;
    const handler = control?.props.onChange ?? control?.props.onToggle;
    assert.ok(handler, `no control with a change handler in a row labelled "${label}"`);
    return handler;
}
/** The explanation behind the info button of the row with this label. */
function infoOf(rows: ReactNode, label: string): Info {
    const info = rowElement(rows, label)?.info;
    assert.ok(info, `no row labelled "${label}"`);
    return info;
}
/** An explanation's text as markup. */
const textOf = (info: Info): string => renderToStaticMarkup(<>{info.text}</>);

/** The posthoc explanation of each detector row. */
const POSTHOC_INFO: Record<string, Info> = {
    'Skeleton detector': DETECTOR_INFO, 'Execution provider': PROVIDERS.info, 'Model': MODEL_INFO,
    'Confidence threshold': CONFIDENCE_INFO,
};
/** What the realtime Skeleton Setup dialog says about the selected detector. */
const DETECTOR_NOTES: Partial<Record<DetectorType, string>> = REALTIME_DETECTOR_NOTES;

test('key rows are the detector and its model', () => {
    // MediaPipe Holistic has no model choice in the settings.
    const expected: Record<DetectorType, string[]> = {rtmpose: ['Skeleton detector', 'Model'], mediapipe: ['Skeleton detector']};
    for (const detector of DETECTORS) assert.deepEqual(labels(detectorRows(detector, 'key')), expected[detector], detector);
    assert.deepEqual(optionsOf(rowLabelled(detectorRows('rtmpose', 'key'), 'Skeleton detector')), DETECTORS);
    assert.deepEqual(optionsOf(rowLabelled(detectorRows('rtmpose', 'key'), 'Model')), ['rtmw-x-l_256x192', 'rtmw-x-l_384x288', 'rtmw-l-m_256x192']);
});

test('all rows follow the detector', () => {
    const expected: Record<DetectorType, string[]> = {
        rtmpose: ['Skeleton detector', 'Execution provider', 'Model', 'Confidence threshold'],
        mediapipe: ['Skeleton detector'],
    };
    for (const detector of DETECTORS) assert.deepEqual(labels(detectorRows(detector, 'all')), expected[detector], detector);
});

test('the execution provider row follows the server, not the detector name', () => {
    const every = {...PROVIDERS, takesExecutionProvider: () => true};
    const none = {...PROVIDERS, takesExecutionProvider: () => false};
    assert.ok(labels(detectorRows('mediapipe', 'all', {providers: every})).includes('Execution provider'));
    assert.ok(!labels(detectorRows('rtmpose', 'all', {providers: none})).includes('Execution provider'));
});

test('a device row follows an EP with more than one device and reports the device key', () => {
    const two = [{key: 'gpu:0', name: 'Big GPU', vram_total_bytes: 24 * 2 ** 30}, {key: 'gpu:1', name: null, vram_total_bytes: null}];
    const providers = {...PROVIDERS, devicesOf: (provider: string | null) => provider === 'gpu-ep' ? two : two.slice(0, 1)};
    const html = detectorRows('rtmpose', 'all', {providers, value: {...VALUE, provider: 'gpu-ep'}});
    assert.deepEqual(labels(html), ['Skeleton detector', 'Execution provider', 'Device', 'Model', 'Confidence threshold']);
    assert.deepEqual(optionsOf(rowLabelled(html, 'Device')), ['auto', 'gpu:0', 'gpu:1']);
    assert.match(rowLabelled(html, 'Device'), /Big GPU \(24\.0 GiB\)/);
    assert.ok(!labels(detectorRows('rtmpose', 'all', {providers, value: {...VALUE, provider: 'cpu'}})).includes('Device'));
    const changes: Partial<DetectorSettingsValue>[] = [];
    const rows = DetectorSettingRows(detectorProps('rtmpose', 'all', {providers, value: {...VALUE, provider: 'gpu-ep'},
        onChange: change => changes.push(change)}));
    handlerOf(rows, 'Device')('gpu:1');
    handlerOf(rows, 'Device')('auto');
    handlerOf(rows, 'Execution provider')('cpu');
    assert.deepEqual(changes, [{device: 'gpu:1'}, {device: null}, {provider: 'cpu', device: null}]);
});

test('the execution provider explanation is the sentence of each EP, with the install hint of one that is not usable', () => {
    const text = renderToStaticMarkup(<>{PROVIDERS.info.text}</>);
    assert.match(text, /<strong>CPU<\/strong> — Runs on the processor\./);
    assert.match(text, /<strong>GPU EP<\/strong> — Runs on a GPU\. <em>Not usable here\. Run `install gpu-ep`\.<\/em>/);
    assert.deepEqual(optionsOf(rowLabelled(detectorRows('rtmpose', 'all'), 'Execution provider')), ['auto', 'cpu']);
});

test('outlier rows dim with their switch', () => {
    const on = outlierRows(CONFIG);
    assert.deepEqual(labels(on), ['Use outlier rejection', ...OUTLIER_LIMITS]);
    assert.deepEqual(dimmed(on), []);
    const off = outlierRows({...CONFIG, use_outlier_rejection: false});
    assert.deepEqual(labels(off), ['Use outlier rejection', ...OUTLIER_LIMITS]);
    assert.deepEqual(dimmed(off), OUTLIER_LIMITS);
    assert.ok(!rowLabelled(off, 'Use outlier rejection').includes('disabled'), off);

    // A stage that is off dims all four rows and locks the switch, whatever the switch says.
    for (const use_outlier_rejection of [true, false]) {
        const inactive = outlierRows({...CONFIG, use_outlier_rejection}, true);
        assert.deepEqual(dimmed(inactive), ['Use outlier rejection', ...OUTLIER_LIMITS]);
        assert.match(rowLabelled(inactive, 'Use outlier rejection'), /<button type="button" role="switch"[^>]* disabled=""/);
    }
});

test('each control reports its own field', () => {
    const changes: Partial<DetectorSettingsValue>[] = [];
    const all = (detector: DetectorType): ReactNode => DetectorSettingRows(detectorProps(detector, 'all', {onChange: change => changes.push(change)}));
    const rtmw = all('rtmpose');
    handlerOf(rtmw, 'Execution provider')('cpu');
    handlerOf(rtmw, 'Execution provider')('auto');
    handlerOf(rtmw, 'Model')('rtmw-l-m_256x192');
    handlerOf(rtmw, 'Confidence threshold')(0.3);
    handlerOf(all('mediapipe'), 'Skeleton detector')('rtmpose');
    assert.deepEqual(changes, [{provider: 'cpu', device: null}, {provider: null, device: null}, {model: 'rtmw-l-m_256x192'}, {confidence: 0.3},
        {detector: 'rtmpose'}]);

    // The outlier rows report the whole configuration with the one field changed.
    const configs: TriangulationConfig[] = [];
    const outlier = OutlierRejectionRows({config: CONFIG, onChange: config => configs.push(config)});
    handlerOf(outlier, 'Use outlier rejection')(false);
    handlerOf(outlier, 'Minimum cameras for triangulation')(3);
    handlerOf(outlier, 'Maximum cameras to drop')(2);
    handlerOf(outlier, 'Target reprojection error')(0.05);
    assert.deepEqual(configs, [{...CONFIG, use_outlier_rejection: false}, {...CONFIG, minimum_cameras_for_triangulation: 3},
        {...CONFIG, maximum_cameras_to_drop: 2}, {...CONFIG, target_reprojection_error: 0.05}]);
});

test('posthoc keeps its promoted detector row and its confidence step', () => {
    const posthoc = detectorRows('rtmpose', 'all', {context: 'posthoc', detectors: DETECTOR_OPTIONS});
    const realtime = detectorRows('rtmpose', 'all');
    assert.equal(posthoc.match(ROW)?.[0], '<div class="setting-row setting-row-promoted">', posthoc);
    assert.equal(realtime.match(ROW)?.[0], '<div class="setting-row">', realtime);
    assert.equal(posthoc.split('setting-row-promoted').length - 1, 1, posthoc);
    assert.ok(rowLabelled(posthoc, 'Confidence threshold').includes(' step="0.001" '), posthoc);
    assert.ok(rowLabelled(realtime, 'Confidence threshold').includes(' step="0.0005" '), realtime);
    assert.deepEqual(optionsOf(rowLabelled(posthoc, 'Skeleton detector')), ['rtmpose', 'mediapipe']);
});

test('inactive dims every row', () => {
    for (const detector of DETECTORS) {
        for (const rows of ['key', 'all'] as const) {
            const active = detectorRows(detector, rows);
            assert.deepEqual(dimmed(active), [], `${detector} ${rows}`);
            // The same rows stay on screen, each of them dimmed.
            assert.deepEqual(dimmed(detectorRows(detector, rows, {inactive: true})), labels(active), `${detector} ${rows}`);
        }
    }
    assert.deepEqual(dimmed(renderToStaticMarkup(<SkeletonAnchorSetting value="pelvis" onChange={() => {}}/>)), []);
    assert.deepEqual(dimmed(renderToStaticMarkup(<SkeletonAnchorSetting value="pelvis" onChange={() => {}} inactive/>)), ['Skeleton anchor']);
});

test('number fields are named after their rows', () => {
    /** The accessible names of a row's elements of one kind, in order. */
    const names = (row: string, tag: string): (string | undefined)[] =>
        (row.match(new RegExp(`<${tag}[^>]*>`, 'g')) ?? []).map(opening => opening.match(/ aria-label="([^"]*)"/)?.[1]);
    const named = (html: string, label: string, where: string): void => {
        const row = rowLabelled(html, label);
        assert.deepEqual(names(row, 'input'), [label], `${where}: ${row}`);
        // The row's buttons in order: its explanation, then the steppers either side of the field.
        assert.deepEqual(names(row, 'button'), [label, `Decrease ${label}`, `Increase ${label}`], `${where}: ${row}`);
    };
    for (const context of ['posthoc', 'realtime'] as const) {
        named(detectorRows('rtmpose', 'all', {context}), 'Confidence threshold', context);
    }
    for (const label of OUTLIER_LIMITS) named(outlierRows(CONFIG), label, 'outlier rejection');
});

test('realtime explanations carry the Skeleton Setup notes', () => {
    /** The note that ends a realtime row's explanation for this detector, where the dialog has one about that row. */
    const noteFor = (label: string, detector: DetectorType): string | undefined =>
        label === 'Skeleton detector' ? DETECTOR_NOTES[detector] : undefined;
    const shown = new Set<string>();
    for (const detector of DETECTORS) {
        for (const set of ['key', 'all'] as const) {
            const rows = DetectorSettingRows(detectorProps(detector, set));
            for (const label of labels(detectorRows(detector, set))) {
                const info = infoOf(rows, label), posthoc = POSTHOC_INFO[label], note = noteFor(label, detector);
                assert.equal(info.title, posthoc.title, `${detector} ${set} ${label}`);
                if (note === undefined) {
                    assert.equal(info, posthoc, `${detector} ${set} ${label}`);
                    continue;
                }
                // The row's own explanation, then the note as its last paragraph.
                const own = typeof posthoc.text === 'string' ? `<p>${posthoc.text}</p>` : textOf(posthoc);
                assert.equal(textOf(info), `${own}<p>${note}</p>`, `${detector} ${set} ${label}`);
                shown.add(note);
            }
        }
    }
    // Each of the dialog's notes has a row: none is left behind with the dialog.
    assert.deepEqual([...shown].sort(), Object.values(DETECTOR_NOTES).sort());
});

test('posthoc explanations are unchanged', () => {
    for (const {value: detector} of DETECTOR_OPTIONS) {
        const posthoc = {context: 'posthoc', detectors: DETECTOR_OPTIONS} as const;
        const rows = DetectorSettingRows(detectorProps(detector, 'all', posthoc));
        const shown = labels(detectorRows(detector, 'all', posthoc));
        assert.ok(shown.length > 0, detector);
        // The very objects posthoc had before the rows were shared.
        for (const label of shown) assert.equal(infoOf(rows, label), POSTHOC_INFO[label], `${detector} ${label}`);
    }
});
