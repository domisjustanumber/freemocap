import type {RootState} from '@/store/types';
import {selectRealtimeEnabledCameraConfigs} from '@/store/slices/cameras/cameras-selectors';

export function countRealtimeApplyCameras(state: RootState): number {
    return Object.keys(selectRealtimeEnabledCameraConfigs(state)).length;
}
