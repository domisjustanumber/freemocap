import type {ExecutionProviderName} from '@/types/execution-provider';
import {RTMW_CONFIDENCE_THRESHOLD} from '@/types/rtmw-confidence';
import {migrateExportSettings, migrateRemovedDetectors, takeLegacyExecutionProvider} from '@/store/export-settings-migration';
import {CameraMatchingOptions, defaultCameraMatchingOptions} from '@/types/camera-matching';
import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit';
import {RootState} from '../../root-state-types';
import type {ExportChannel, ExportFormat, ExportChannelKind} from '@/types/recording-exports';
import {loadFromStorage} from '@/store/persistence';
import {matchesSavedManualOffset, saveCalibrationTransform} from '@/store/slices/calibration/calibration-save';
import {
    processMocapRecording,
    startMocapRecording,
    stopMocapRecording,
} from "@/store/slices/mocap/mocap-thunks";
import {
    selectActiveRecordingFullPath,
    selectActiveRecordingOrigin,
    selectEffectiveRecordingPath,
} from "@/store/slices/active-recording/active-recording-slice";

// ==================== Types ====================

export interface TriangulationConfig {
    use_outlier_rejection: boolean;
    minimum_cameras_for_triangulation: number;
    maximum_cameras_to_drop: number;
    target_reprojection_error: number;
}

export interface PosthocFilterConfig {
    enabled: boolean;
    method: "butter_low_pass";
    cutoff: number;
    order: number;
}

export type DetectorType = "rtmpose" | "mediapipe";
export type RTMPoseModelName = "rtmw-x-l_256x192" | "rtmw-x-l_384x288" | "rtmw-l-m_256x192";
export type {ExecutionProviderName} from '@/types/execution-provider';

/** Exported after processing unless turned off; the recording's Parquet file is always written. */
const DEFAULT_EXPORT_FORMATS: ExportFormat[] = ['npz', 'wide_csv', 'notebook'];

export const RTMPOSE_MODELS: { label: string; value: RTMPoseModelName }[] = [
    { label: "Default", value: "rtmw-x-l_256x192" },
    { label: "High Res", value: "rtmw-x-l_384x288" },
    { label: "Fast", value: "rtmw-l-m_256x192" },
];

/**
 * Mirrors backend MocapPipelineConfig.
 */
export interface MocapConfig {
    cameraMatching: CameraMatchingOptions;
    charucoTrackingEnabled: boolean;
    triangulation: TriangulationConfig;
    posthoc_filter: PosthocFilterConfig;
    detectorType: DetectorType;
    rtmPoseModelName: RTMPoseModelName;
    rtmPoseConfidenceThreshold: number;
    executionProvider: ExecutionProviderName | null;
    /** A skellytracker device key of the chosen EP; null = skellytracker's choice. */
    executionDevice: string | null;
    mediapipeNumHands: 2;

    bodyAlignmentMode: 'auto' | 'calibration' | 'person';
    anchorSegmentName: string;
    exportTallCsv: boolean;
    exportFormats: ExportFormat[];
    exportChannels: ExportChannelKind[];
    exportChannelOverrides: ExportChannel[] | null;
    exportAfterProcessing: boolean;
    /** Row-major rigid offset applied after posthoc alignment, with translation in mm. */
    referenceTransform: number[] | null;
    referenceTransformEnabled: boolean;
}

export const DEFAULT_TRIANGULATION_CONFIG: TriangulationConfig = {
    use_outlier_rejection: true,
    minimum_cameras_for_triangulation: 2,
    maximum_cameras_to_drop: 1,
    target_reprojection_error: 0.02,
};


export const DEFAULT_POSTHOC_FILTER_CONFIG: PosthocFilterConfig ={
    enabled: true,
    method: "butter_low_pass",
    cutoff: 6.0,
    order: 4,
};


 
export interface MocapDirectoryInfo {
    exists: boolean;
    canRecord: boolean;
    canCalibrate: boolean;
    cameraMocapTomlPath: string | null;
    hasSynchronizedVideos: boolean;
    hasVideos: boolean;
    cameraCount: number;
    errorMessage: string | null;
}

/**
 * The EP key of a settings file saved before skellytracker 2. While it is pending, processing waits and nothing is
 * saved; skellytracker's suggestion then replaces it (null = Auto) and the notice says which key was replaced by which.
 */
export type ExecutionProviderMigration =
    | {saved: string; status: 'pending'}
    | {saved: string; status: 'replaced'; replacement: string | null};

export interface MocapState {
    config: MocapConfig;
    exportSettingsError: string | null;
    executionProviderMigration: ExecutionProviderMigration | null;
    isRecording: boolean;
    recordingProgress: number;
    isLoading: boolean;
    error: string | null;
    directoryInfo: MocapDirectoryInfo | null;
    processingProgress: number;
    processingPhase: string;
}


const DEFAULT_MOCAP_CONFIG: MocapConfig = {
    cameraMatching: {...defaultCameraMatchingOptions},
    triangulation: {...DEFAULT_TRIANGULATION_CONFIG},
    posthoc_filter: {...DEFAULT_POSTHOC_FILTER_CONFIG},

    charucoTrackingEnabled: true,
    detectorType: "rtmpose",
    rtmPoseModelName: "rtmw-x-l_256x192",
    rtmPoseConfidenceThreshold: RTMW_CONFIDENCE_THRESHOLD,
    executionProvider: null,
    executionDevice: null,
    mediapipeNumHands: 2,
    bodyAlignmentMode: 'auto',
    anchorSegmentName: "pelvis",
    exportTallCsv: false,
    exportFormats: [...DEFAULT_EXPORT_FORMATS],
    exportChannels: ['LANDMARKS_3D'],
    exportChannelOverrides: null,
    exportAfterProcessing: true,
    referenceTransform: null,
    referenceTransformEnabled: false,
};

// ==================== Initial State ====================

const exportSettingsMigration = migrateExportSettings(loadFromStorage<Record<string, unknown> | null>('mocap.config', null));
const legacyExecutionProvider = takeLegacyExecutionProvider(migrateRemovedDetectors(exportSettingsMigration.config));
const _persistedMocapConfig = legacyExecutionProvider.config as Partial<MocapConfig>;

const initialMocapConfig: MocapConfig = {
    ...DEFAULT_MOCAP_CONFIG,
    ...(_persistedMocapConfig ?? {}),

    triangulation: {
        ...DEFAULT_MOCAP_CONFIG.triangulation,
        ...(_persistedMocapConfig?.triangulation ?? {}),
    },

    posthoc_filter: {
        ...DEFAULT_MOCAP_CONFIG.posthoc_filter,
        ...(_persistedMocapConfig?.posthoc_filter ?? {}),
    },
};

const initialState: MocapState = {
    config: initialMocapConfig,
    exportSettingsError: exportSettingsMigration.error,
    executionProviderMigration: legacyExecutionProvider.legacyKey === null ? null
        : {saved: legacyExecutionProvider.legacyKey, status: 'pending'},
    isRecording: false,
    recordingProgress: 0,
    isLoading: false,
    error: null,
    directoryInfo: null,
    processingProgress: 0,
    processingPhase: "",
};

// ==================== Slice ====================

export const mocapSlice = createSlice({
    name: 'mocap',
    initialState,
    reducers: {
        exportSettingsReset: (state) => {
            state.config.exportFormats = [...DEFAULT_MOCAP_CONFIG.exportFormats];
            state.config.exportChannels = ['LANDMARKS_3D'];
            state.config.exportChannelOverrides = null;
            state.config.exportAfterProcessing = DEFAULT_MOCAP_CONFIG.exportAfterProcessing;
            state.exportSettingsError = null;
        },
        exportChannelsUpdated: (state, action: PayloadAction<ExportChannelKind[]>) => {
            state.config.exportChannels = action.payload;
            state.config.exportChannelOverrides = null;
        },
        exportFormatsUpdated: (state, action: PayloadAction<ExportFormat[]>) => {
            state.config.exportFormats = action.payload;
        },
        exportChannelOverridesUpdated: (state, action: PayloadAction<ExportChannel[] | null>) => {
            state.config.exportChannelOverrides = action.payload;
        },
        exportAfterProcessingUpdated: (state, action: PayloadAction<boolean>) => {
            state.config.exportAfterProcessing = action.payload;
        },
        exportTallCsvUpdated: (state, action: PayloadAction<boolean>) => {
            state.config.exportTallCsv = action.payload;
        },
        bodyAlignmentModeUpdated: (state, action: PayloadAction<'auto' | 'calibration' | 'person'>) => {
            state.config.bodyAlignmentMode = action.payload;
        },
        anchorSegmentNameUpdated: (state, action: PayloadAction<string>) => {
            state.config.anchorSegmentName = action.payload;
        },
        /** Row-major 4x4, or null when no additional transformation is defined. */
        referenceTransformUpdated: (state, action: PayloadAction<number[] | null>) => {
            state.config.referenceTransform = action.payload;
            if (action.payload === null) state.config.referenceTransformEnabled = false;
        },
        referenceTransformEnabledUpdated: (state, action: PayloadAction<boolean>) => {
            state.config.referenceTransformEnabled = action.payload;
        },
        cameraMatchingUpdated: (state, action: PayloadAction<CameraMatchingOptions>) => {
            state.config.cameraMatching = action.payload;
        },
        mocapCharucoTrackingChanged: (state, action: PayloadAction<boolean>) => {
            state.config.charucoTrackingEnabled = action.payload;
        },
        /** Switch between rtmpose and mediapipe detector backends. */
        mocapDetectorTypeChanged: (state, action: PayloadAction<DetectorType>) => {
            state.config.detectorType = action.payload;
        },

        /** Change the RTMPose model variant. */
        mocapRtmPoseModelNameChanged: (state, action: PayloadAction<RTMPoseModelName>) => {
            state.config.rtmPoseModelName = action.payload;
        },

        /** Change the ONNX execution provider (null = auto). */
        mocapExecutionProviderChanged: (state, action: PayloadAction<ExecutionProviderName | null>) => {
            // A choice made now is the user's: it ends a pending legacy replacement.
            if (state.executionProviderMigration?.status === 'pending') state.executionProviderMigration = null;
            if (state.config.executionProvider !== action.payload) state.config.executionDevice = null;
            state.config.executionProvider = action.payload;
        },
        mocapExecutionDeviceChanged: (state, action: PayloadAction<string | null>) => {
            state.config.executionDevice = action.payload;
        },
        legacyExecutionProviderResolved: (state, action: PayloadAction<{saved: string; suggested: string | null}>) => {
            const migration = state.executionProviderMigration;
            if (migration?.status !== 'pending' || migration.saved !== action.payload.saved) return;
            state.config.executionProvider = action.payload.suggested;
            state.config.executionDevice = null;
            state.executionProviderMigration = {saved: migration.saved, status: 'replaced', replacement: action.payload.suggested};
        },
        executionProviderNoticeDismissed: (state) => {
            if (state.executionProviderMigration?.status === 'replaced') state.executionProviderMigration = null;
        },

        /** Change the RTMPose keypoint confidence threshold. */
        mocapRtmPoseConfidenceThresholdChanged: (state, action: PayloadAction<number>) => {
            state.config.rtmPoseConfidenceThreshold = action.payload;
        },

        triangulationConfigUpdated: (state, action: PayloadAction<Partial<TriangulationConfig>>) => {
            state.config.triangulation = { ...state.config.triangulation, ...action.payload };
        },

        posthocFilterConfigUpdated: (state, action: PayloadAction<Partial<PosthocFilterConfig>>) => {
            state.config.posthoc_filter = {...state.config.posthoc_filter, ...action.payload};
        },

        mocapProgressUpdated: (state, action: PayloadAction<number>) => {
            state.recordingProgress = action.payload;
        },

        mocapErrorCleared: (state) => {
            state.error = null;
        },

        mocapDirectoryInfoUpdated: (state, action: PayloadAction<MocapDirectoryInfo>) => {
            state.directoryInfo = action.payload;
        },


        posthocProgressReceived: (state, action: PayloadAction<{phase: string; progress_fraction: number; detail: string}>) => {
            state.processingPhase = action.payload.phase;
            state.processingProgress = Math.round(action.payload.progress_fraction * 100);
            if (action.payload.phase === 'complete' || action.payload.phase === 'failed') {
                state.isLoading = false;
            }
        },

        resetMocapState: () => initialState,
    },

    extraReducers: (builder) => {
        builder.addCase(saveCalibrationTransform.fulfilled, (state, action) => {
            const request = action.meta.arg;
            if (request && matchesSavedManualOffset(request, state.config.referenceTransform)) {
                state.config.referenceTransform = null;
                state.config.referenceTransformEnabled = false;
            }
        });
        builder
            .addCase(startMocapRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(startMocapRecording.fulfilled, (state) => {
                state.isLoading = false;
                state.isRecording = true;
                state.recordingProgress = 0;
            })
            .addCase(startMocapRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to start recording';
            });

        builder
            .addCase(stopMocapRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(stopMocapRecording.fulfilled, (state) => {
                state.isLoading = false;
                state.isRecording = false;
                state.recordingProgress = 0;
            })
            .addCase(stopMocapRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to stop recording';
            });

        builder
            .addCase(processMocapRecording.pending, (state) => {
                state.isLoading = true;
                state.error = null;
                state.processingProgress = 0;
                state.processingPhase = '';
            })
            .addCase(processMocapRecording.fulfilled, (state) => {
                // isLoading stays true — it will be reset by posthocProgressReceived
                // when the pipeline emits 'complete' or 'failed' over WebSocket
            })
            .addCase(processMocapRecording.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.payload || 'Failed to process recording';
            });

    },
});

// ==================== Selectors ====================

export const selectMocap = (state: RootState) => state.mocap;
export const selectMocapConfig = (state: RootState) => state.mocap.config;
export const selectMocapTriangulationConfig = (state: RootState) => state.mocap.config.triangulation;
export const selectPosthocFilterConfig = (state: RootState) => state.mocap.config.posthoc_filter;
export const selectReferenceTransform = (state: RootState) => state.mocap.config.referenceTransform;
export const selectReferenceTransformEnabled = (state: RootState) => state.mocap.config.referenceTransformEnabled;
export const selectMocapDetectorType = (state: RootState) => state.mocap.config.detectorType;
export const selectMocapRtmPoseModelName = (state: RootState) => state.mocap.config.rtmPoseModelName;
export const selectMocapExecutionProvider = (state: RootState) => state.mocap.config.executionProvider;
export const selectMocapExecutionDevice = (state: RootState) => state.mocap.config.executionDevice;
export const selectMocapRtmPoseConfidenceThreshold = (state: RootState) => state.mocap.config.rtmPoseConfidenceThreshold;
export const selectMocapMediapipeNumHands = (state: RootState) => state.mocap.config.mediapipeNumHands;
export const selectMocapIsLoading = (state: RootState) => state.mocap.isLoading;
export const selectMocapIsRecording = (state: RootState) => state.mocap.isRecording;
export const selectMocapProgress = (state: RootState) => state.mocap.recordingProgress;
export const selectMocapError = (state: RootState) => state.mocap.error;
export const selectMocapDirectoryInfo = (state: RootState) => state.mocap.directoryInfo;
export const selectProcessingProgress = (state: RootState) => state.mocap.processingProgress;
export const selectProcessingPhase = (state: RootState) => state.mocap.processingPhase;

export const selectMocapRecordingPath = selectActiveRecordingFullPath;

export const selectIsUsingManualMocapPath = createSelector(
    [selectActiveRecordingOrigin],
    (origin) => origin === 'browsed',
);

// The only thing the UI checks before sending is whether the request can be formed:
// there must be a target path to put in the request body. It does NOT gate on server
// state it is only guessing at — "am I already recording" (assumed from a prior
// command, never reconciled) or "is a request in flight". The button always sends;
// the server reconciles the request against live state and reports back.
export const selectCanStartMocapRecording = createSelector(
    [selectEffectiveRecordingPath],
    (effectivePath) => !!effectivePath
);

export const selectExecutionProviderMigration = (state: RootState) => state.mocap.executionProviderMigration;

/** Processing waits for the replacement of a legacy EP key: no request goes out with the old key. */
export const selectCanProcessMocapRecording = createSelector(
    [selectMocapRecordingPath, selectExecutionProviderMigration],
    (mocapPath, migration) => !!mocapPath && migration?.status !== 'pending'
);

// ==================== Actions Export ====================

export const {
    bodyAlignmentModeUpdated,
    anchorSegmentNameUpdated,
    exportTallCsvUpdated,
    exportSettingsReset,
    exportFormatsUpdated,
    exportChannelsUpdated,
    exportChannelOverridesUpdated,
    exportAfterProcessingUpdated,
    referenceTransformUpdated,
    referenceTransformEnabledUpdated,
    cameraMatchingUpdated,
    mocapCharucoTrackingChanged,
    mocapDetectorTypeChanged,
    mocapRtmPoseModelNameChanged,
    mocapRtmPoseConfidenceThresholdChanged,
    mocapExecutionProviderChanged,
    mocapExecutionDeviceChanged,
    legacyExecutionProviderResolved,
    executionProviderNoticeDismissed,
    triangulationConfigUpdated,
    posthocFilterConfigUpdated,
    mocapProgressUpdated,
    mocapErrorCleared,
    mocapDirectoryInfoUpdated,
    posthocProgressReceived,
    resetMocapState
} = mocapSlice.actions;

export default mocapSlice.reducer;
