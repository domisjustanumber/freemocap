import type {MocapState} from '@/store/slices/mocap/mocap-slice';
import {RTMW_CONFIDENCE_THRESHOLD} from '@/types/rtmw-confidence';

/** Historical local settings are input aliases, never names written by new clients. */
const aliases = {
    scientificExportFormats: 'exportFormats',
    scientificExportData: 'exportChannels',
    scientificExportChannels: 'exportChannelOverrides',
    scientificExportAfterProcessing: 'exportAfterProcessing',
} as const;

function signature(value: unknown): string {
    if (Array.isArray(value)) return `[${value.map(signature).join(',')}]`;
    if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
        .map(([key, item]) => `${JSON.stringify(key)}:${signature(item)}`).join(',')}}`;
    return JSON.stringify(value) ?? 'undefined';
}

export function migrateExportSettings(saved: Record<string, unknown> | null): {
    config: Record<string, unknown>; error: string | null;
} {
    const config = {...saved};
    const conflicts: string[] = [];
    for (const [oldName, name] of Object.entries(aliases)) {
        if (!(oldName in config)) continue;
        if (name in config && signature(config[name]) !== signature(config[oldName])) conflicts.push(name);
        else config[name] = config[oldName];
        delete config[oldName];
    }
    if (!conflicts.length) return {config, error: null};
    // Do not choose one conflicting value or overwrite saved settings. Hydrate
    // safe defaults until the user explicitly resets the export settings.
    for (const name of Object.values(aliases)) delete config[name];
    return {config, error: `Saved export settings conflict (${conflicts.join(', ')}). Reset export settings to continue.`};
}

/** Saved settings for a removed detector choice fall back to RTMW. */
const REMOVED_DETECTORS = ['rtmw_mediapipe_hands', 'mediapipe_hands', 'rtmw_onnx_hands', 'dlc'];

export function migrateRemovedDetectors(saved: Record<string, unknown>): Record<string, unknown> {
    const config = Object.fromEntries(Object.entries(saved).filter(([key]) => !key.startsWith('dlc')));
    if (REMOVED_DETECTORS.includes(config.detectorType as string)) config.detectorType = 'rtmpose';
    return config;
}

/**
 * Written with every saved mocap config. A saved config without it was written before skellytracker 2: its EP key is
 * legacy. Version 1 was written before the calibrated RTMW score (user T1): its confidence threshold is on the old scale.
 */
export const MOCAP_SETTINGS_VERSION = 2;
/** Saved while the old-scale threshold prompt is open, so the prompt shows again until the user answers (user M1). */
export const PRE_CALIBRATED_SCORE_SETTINGS_VERSION = 1;

/**
 * The confidence threshold of a config saved before the calibrated RTMW score, when the user must be asked about it
 * (user M1): only a saved number below the new default. Nothing is changed here; the saved value stays in force.
 */
export function oldScaleConfidenceThreshold(saved: Record<string, unknown>): number | null {
    const {settingsVersion: version, rtmPoseConfidenceThreshold: value} = saved;
    if (typeof version === 'number' && version > PRE_CALIBRATED_SCORE_SETTINGS_VERSION) return null;
    return typeof value === 'number' && value < RTMW_CONFIDENCE_THRESHOLD ? value : null;
}

/**
 * Holds back the EP key of a legacy saved config until skellytracker suggests its replacement (user G1-G3): the config
 * loads with Auto meanwhile, and the key comes back as `legacyKey`. A config with the version keeps its key as chosen.
 */
export function takeLegacyExecutionProvider(saved: Record<string, unknown>): {
    config: Record<string, unknown>; legacyKey: string | null;
} {
    const {settingsVersion, ...config} = saved;
    const key = config.executionProvider;
    if (settingsVersion !== undefined || typeof key !== 'string') return {config, legacyKey: null};
    return {config: {...config, executionProvider: null, executionDevice: null}, legacyKey: key};
}

/**
 * The mocap config to save, or null to leave the saved file as it is: a conflict or a pending legacy EP key is not
 * saved over. While the old-scale threshold prompt is open, the config is saved with the pre-T1 version (user M1).
 */
export function savedMocapConfig(mocap: MocapState): Record<string, unknown> | null {
    if (mocap.exportSettingsError || mocap.executionProviderMigration?.status === 'pending') return null;
    const settingsVersion = mocap.oldConfidenceThreshold === null ? MOCAP_SETTINGS_VERSION : PRE_CALIBRATED_SCORE_SETTINGS_VERSION;
    return {...mocap.config, settingsVersion};
}
