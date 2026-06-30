import type {AppDispatch, RootState} from '@/store/types';
import {countRealtimeApplyCameras} from './realtime-apply-camera-count';
import {REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE} from './realtime-messages';
import {realtimeApplyBlocked} from './realtime-notify-actions';

export function guardRealtimeApply(
    dispatch: AppDispatch,
    getState: () => RootState,
): boolean {
    if (countRealtimeApplyCameras(getState()) > 0) return true;
    dispatch(realtimeApplyBlocked({message: REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE}));
    return false;
}
