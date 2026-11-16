import {createListenerMiddleware} from '@reduxjs/toolkit';
import {RootState} from './root-state-types';
import {saveToStorage} from './persistence';
import {MOCAP_SETTINGS_VERSION} from './export-settings-migration';

export const persistenceListenerMiddleware = createListenerMiddleware();

persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) => {
        const current = (curr as RootState).pipelines;
        const previous = (prev as RootState).pipelines;
        return current.serverInstanceId !== previous.serverInstanceId
            || current.dismissedBasePipelineIds !== previous.dismissedBasePipelineIds;
    },
    effect: (_, api) => {
        const {serverInstanceId, dismissedBasePipelineIds} = (api.getState() as RootState).pipelines;
        saveToStorage('pipelines.dismissals', {serverInstanceId, dismissedBasePipelineIds});
    },
});

// How long to wait after the last change before writing to localStorage.
// Rapid sequential actions (e.g. dragging a slider) collapse into one write.
const DEBOUNCE_MS = 300;

// ─── activeRecording ──────────────────────────────────────────────────────────
// Only persist the 3 user-meaningful fields; 'origin' is transient.
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) => {
        const c = (curr as RootState).activeRecording;
        const p = (prev as RootState).activeRecording;
        return c.recordingName !== p.recordingName
            || c.baseDirectory !== p.baseDirectory
            || c.layoutPreset !== p.layoutPreset;
    },
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        const s = api.getState() as RootState;
        saveToStorage('activeRecording', {
            recordingName: s.activeRecording.recordingName,
            baseDirectory: s.activeRecording.baseDirectory,
            layoutPreset: s.activeRecording.layoutPreset,
        });
    },
});

// ─── recording.config ─────────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) =>
        (curr as RootState).recording.config !== (prev as RootState).recording.config,
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        saveToStorage('recording.config', (api.getState() as RootState).recording.config);
    },
});

// ─── recording.directory ──────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) =>
        (curr as RootState).recording.recordingDirectory !== (prev as RootState).recording.recordingDirectory,
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        saveToStorage('recording.directory', (api.getState() as RootState).recording.recordingDirectory);
    },
});

// ─── calibration.config ───────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) =>
        (curr as RootState).calibration.config !== (prev as RootState).calibration.config,
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        saveToStorage('calibration.config', (api.getState() as RootState).calibration.config);
    },
});

// ─── mocap.config ─────────────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) =>
        (curr as RootState).mocap.config !== (prev as RootState).mocap.config,
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        const mocap = (api.getState() as RootState).mocap;
        // A pending legacy EP key is not saved over: the file keeps it until its replacement is applied.
        if (!mocap.exportSettingsError && mocap.executionProviderMigration?.status !== 'pending') {
            saveToStorage('mocap.config', {...mocap.config, settingsVersion: MOCAP_SETTINGS_VERSION});
        }
    },
});

// ─── cameras.filterVirtualCameras ─────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) =>
        (curr as RootState).cameras.filterVirtualCameras !== (prev as RootState).cameras.filterVirtualCameras,
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        saveToStorage('cameras.filterVirtualCameras', (api.getState() as RootState).cameras.filterVirtualCameras);
    },
});

// ─── blender.settings ─────────────────────────────────────────────────────────
persistenceListenerMiddleware.startListening({
    predicate: (_, curr, prev) => {
        const c = (curr as RootState).blender;
        const p = (prev as RootState).blender;
        return c.exportConfig !== p.exportConfig
            || c.developmentBuildHash !== p.developmentBuildHash
            || c.importRoute !== p.importRoute
            || c.packageName !== p.packageName
            || c.blenderExePath !== p.blenderExePath
            || c.exportToBlenderEnabled !== p.exportToBlenderEnabled
            || c.autoOpenBlendFile !== p.autoOpenBlendFile;
    },
    effect: async (_, api) => {
        api.cancelActiveListeners();
        await api.delay(DEBOUNCE_MS);
        const s = api.getState() as RootState;
        saveToStorage('blender.settings', {
            developmentBuildHash: s.blender.developmentBuildHash,
            exportConfig: s.blender.exportConfig,
            importRoute: s.blender.importRoute,
            packageName: s.blender.packageName,
            blenderExePath: s.blender.blenderExePath,
            exportToBlenderEnabled: s.blender.exportToBlenderEnabled,
            autoOpenBlendFile: s.blender.autoOpenBlendFile,
        });
    },
});
