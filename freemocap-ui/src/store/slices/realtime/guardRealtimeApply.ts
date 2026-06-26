import type {Dispatch, UnknownAction} from '@reduxjs/toolkit';
import {countRealtimeApplyCameras} from './realtime-apply-camera-count';
import {REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE} from './realtime-messages';
import {realtimeApplyBlocked} from './realtime-notify-actions';

type GuardGetState = () => Parameters<typeof countRealtimeApplyCameras>[0];

export function guardRealtimeApply(
    dispatch: Dispatch<UnknownAction>,
    getState: GuardGetState,
): boolean {
    if (countRealtimeApplyCameras(getState()) > 0) return true;
    dispatch(realtimeApplyBlocked({message: REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE}));
    return false;
}
