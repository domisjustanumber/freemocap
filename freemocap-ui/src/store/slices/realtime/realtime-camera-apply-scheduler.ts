import type {AppDispatch, RootState} from '@/store/types';
import {guardRealtimeApply} from './guardRealtimeApply';
import {REALTIME_RESTART_REQUIRED_MESSAGE} from './realtime-messages';
import {realtimePipelineRestartRequired} from './realtime-notify-actions';
import {selectIsPipelineConnected} from './realtime-selectors';

const CAMERA_TOGGLE_APPLY_DELAY_MS = 2000;
let cameraToggleApplyTimer: ReturnType<typeof setTimeout> | null = null;

export function scheduleRealtimeRestartRequiredAfterCameraToggle(
    dispatch: AppDispatch,
    getState: () => RootState,
    delayMs = CAMERA_TOGGLE_APPLY_DELAY_MS,
): void {
    if (cameraToggleApplyTimer) clearTimeout(cameraToggleApplyTimer);
    cameraToggleApplyTimer = setTimeout(() => {
        cameraToggleApplyTimer = null;
        const state = getState();
        if (!selectIsPipelineConnected(state)) return;
        if (!guardRealtimeApply(dispatch, getState)) return;
        dispatch(realtimePipelineRestartRequired({message: REALTIME_RESTART_REQUIRED_MESSAGE}));
    }, delayMs);
}

export function cancelScheduledRealtimeCameraApply(): void {
    if (!cameraToggleApplyTimer) return;
    clearTimeout(cameraToggleApplyTimer);
    cameraToggleApplyTimer = null;
}

if (import.meta.hot) {
    import.meta.hot.dispose(() => {
        cancelScheduledRealtimeCameraApply();
    });
}
