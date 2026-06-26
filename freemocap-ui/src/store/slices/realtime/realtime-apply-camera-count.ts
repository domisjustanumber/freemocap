import {selectRealtimeEnabledCameraConfigs} from '@/store/slices/cameras/cameras-selectors';

type RealtimeApplyCountState = Parameters<typeof selectRealtimeEnabledCameraConfigs>[0];

export function countRealtimeApplyCameras(state: RealtimeApplyCountState): number {
    return Object.keys(selectRealtimeEnabledCameraConfigs(state)).length;
}
