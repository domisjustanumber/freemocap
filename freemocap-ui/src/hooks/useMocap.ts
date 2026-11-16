import {useCallback} from 'react';
import type {StageSelection} from '@/services/recording/posthoc-processing';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {store} from '@/store';
import {calibrationAutoLoadDismissed, calibrationLoadedFromBundle, loadCalibrationToml, selectLoadedCalibration} from '@/store/slices/calibration';
import {useElectronIPC} from '@/services';
import {
    DetectorType,
    MocapDirectoryInfo,
    mocapDetectorTypeChanged,
    mocapDirectoryInfoUpdated,
    mocapErrorCleared,
    mocapRtmPoseConfidenceThresholdChanged,
    mocapRtmPoseModelNameChanged,
    mocapExecutionProviderChanged,
    mocapExecutionDeviceChanged,
    processMocapRecording,
    RTMPoseModelName,
    ExecutionProviderName,
    selectMocapExecutionProvider,
    selectMocapExecutionDevice,
    selectCanProcessMocapRecording,
    selectCanStartMocapRecording,
    selectIsUsingManualMocapPath,
    selectMocap,
    selectMocapDetectorType,
    selectMocapDirectoryInfo,
    selectMocapMediapipeNumHands,
    selectMocapRecordingPath,
    selectMocapRtmPoseConfidenceThreshold,
    selectMocapRtmPoseModelName,
    startMocapRecording,
    stopMocapRecording,
} from "@/store/slices/mocap";

function mocapDirectoryInfoEqual(a: MocapDirectoryInfo | null, b: MocapDirectoryInfo): boolean {
    if (!a) return false;
    return (
        a.exists === b.exists &&
        a.canRecord === b.canRecord &&
        a.canCalibrate === b.canCalibrate &&
        a.hasSynchronizedVideos === b.hasSynchronizedVideos &&
        a.hasVideos === b.hasVideos &&
        a.cameraCount === b.cameraCount &&
        a.cameraMocapTomlPath === b.cameraMocapTomlPath &&
        a.errorMessage === b.errorMessage
    );
}
import {pathRecomputed} from "@/store/slices/recording";
import {
    activeRecordingCleared,
    activeRecordingSet,
    splitParentAndName,
} from "@/store/slices/active-recording/active-recording-slice";

export function useMocap() {
    const dispatch = useAppDispatch();
    const {api, isElectron} = useElectronIPC();
    const mocapState = useAppSelector(selectMocap);
    const detectorType = useAppSelector(selectMocapDetectorType);
    const rtmPoseModelName = useAppSelector(selectMocapRtmPoseModelName);
    const executionProvider = useAppSelector(selectMocapExecutionProvider);
    const executionDevice = useAppSelector(selectMocapExecutionDevice);
    const rtmPoseConfidenceThreshold = useAppSelector(selectMocapRtmPoseConfidenceThreshold);
    const mediapipeNumHands = useAppSelector(selectMocapMediapipeNumHands);
    const canStartRecording = useAppSelector(selectCanStartMocapRecording);
    const canProcessMocapRecording = useAppSelector(selectCanProcessMocapRecording);
    const mocapRecordingPath = useAppSelector(selectMocapRecordingPath);
    const directoryInfo = useAppSelector(selectMocapDirectoryInfo);
    const isUsingManualPath = useAppSelector(selectIsUsingManualMocapPath);
    const calibrationTomlPath = useAppSelector(selectLoadedCalibration)?.path ?? null;

    const setDetectorType = useCallback(
        (type: DetectorType) => {
            dispatch(mocapDetectorTypeChanged(type));
        },
        [dispatch]
    );

    const setRtmPoseModelName = useCallback(
        (modelName: RTMPoseModelName) => {
            dispatch(mocapRtmPoseModelNameChanged(modelName));
        },
        [dispatch]
    );

    const setExecutionProvider = useCallback(
        (provider: ExecutionProviderName | null) => {
            dispatch(mocapExecutionProviderChanged(provider));
        },
        [dispatch]
    );

    const setExecutionDevice = useCallback(
        (device: string | null) => {
            dispatch(mocapExecutionDeviceChanged(device));
        },
        [dispatch]
    );

    const setRtmPoseConfidenceThreshold = useCallback(
        (threshold: number) => {
            dispatch(mocapRtmPoseConfidenceThresholdChanged(threshold));
        },
        [dispatch]
    );

    const validateDirectory = useCallback(
        async (directoryPath: string) => {
            if (!isElectron || !api) {
                console.warn('Electron API not available - skipping directory validation');
                return;
            }

            try {
                const info = await api.fileSystem.validateMocapDirectory.query({directoryPath});
                const current = store.getState().mocap.directoryInfo;
                if (!mocapDirectoryInfoEqual(current, info)) {
                    dispatch(mocapDirectoryInfoUpdated(info));
                }
            } catch (error) {
                console.error('Failed to validate mocap directory:', error);
            }
        },
        [dispatch, isElectron, api]
    );

    const setManualRecordingPath = useCallback(
        async (path: string) => {
            const parsed = splitParentAndName(path);
            if (parsed) {
                dispatch(activeRecordingSet({
                    recordingName: parsed.recordingName,
                    baseDirectory: parsed.baseDirectory,
                    origin: 'browsed',
                }));
            }
            await validateDirectory(path);
        },
        [dispatch, validateDirectory]
    );

    const clearManualRecordingPath = useCallback(() => {
        dispatch(activeRecordingCleared());
        dispatch(pathRecomputed());
    }, [dispatch]);

    const dispatchStartMocapRecording = useCallback(() => {
        dispatch(startMocapRecording());
    }, [dispatch]);

    const dispatchStopMocapRecording = useCallback(() => {
        dispatch(stopMocapRecording());
    }, [dispatch]);

    const dispatchProcessMocapRecording = useCallback((selection?: StageSelection) =>
        dispatch(processMocapRecording(selection)), [dispatch]);

    const setCalibrationTomlPath = useCallback(
        (path: string) => {
            void dispatch(loadCalibrationToml({path, force: true}));
        },
        [dispatch]
    );

    const clearCalibrationTomlPath = useCallback(() => {
        dispatch(calibrationAutoLoadDismissed(calibrationTomlPath));
        dispatch(calibrationLoadedFromBundle(null));
    }, [dispatch, calibrationTomlPath]);

    const clearError = useCallback(() => {
        dispatch(mocapErrorCleared());
    }, [dispatch]);

    return {
        // State
        config: mocapState.config,
        detectorType,
        rtmPoseModelName,
        rtmPoseConfidenceThreshold,
        mediapipeNumHands,
        error: mocapState.error,
        isLoading: mocapState.isLoading,
        isRecording: mocapState.isRecording,
        recordingProgress: mocapState.recordingProgress,
        processingProgress: mocapState.processingProgress,
        processingPhase: mocapState.processingPhase,
        mocapRecordingPath,
        directoryInfo,
        isUsingManualPath,
        canStartRecording,
        canProcessMocapRecording,
        calibrationTomlPath,
        // Actions
        setDetectorType,
        setRtmPoseModelName,
        executionProvider,
        setExecutionProvider,
        executionDevice,
        setExecutionDevice,
        setRtmPoseConfidenceThreshold,
        setManualRecordingPath,
        clearManualRecordingPath,
        dispatchStartMocapRecording,
        dispatchStopMocapRecording,
        dispatchProcessMocapRecording,
        validateDirectory,
        setCalibrationTomlPath,
        clearCalibrationTomlPath,
        clearError,
    };
}
