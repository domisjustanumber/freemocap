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

/** Written with every saved mocap config. A saved config without it was written before skellytracker 2: its EP key is legacy. */
export const MOCAP_SETTINGS_VERSION = 1;

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
