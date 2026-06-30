import {describe, expect, it} from 'vitest';
import type {RootState} from '@/store/types';
import {
    selectRealtimeCameraSelectionDrift,
    selectRealtimePipelineRestartNeeded,
} from './realtime-selectors';
import {areSortedCameraIdSetsEqual, sortCameraIds} from './realtime-camera-selection';
import {defaultRealtimePipelineConfig} from './realtime-types';

describe('realtime-camera-selection helpers', () => {
    it('sorts camera ids for stable comparison', () => {
        expect(sortCameraIds(['cam_b', 'cam_a'])).toEqual(['cam_a', 'cam_b']);
    });

    it('compares sorted camera id sets', () => {
        expect(areSortedCameraIdSetsEqual(['cam_a', 'cam_b'], ['cam_a', 'cam_b'])).toBe(true);
        expect(areSortedCameraIdSetsEqual(['cam_a'], ['cam_a', 'cam_b'])).toBe(false);
    });
});

function makeState(cameraOverrides: Array<{id: string; selected: boolean; realtimeEnabled: boolean}>) {
    return {
        realtime: {
            pipelineConfig: defaultRealtimePipelineConfig,
            pipelineId: 'pipe-1',
            isConnected: true,
            isLoading: false,
            error: null,
            gpuCapabilities: null,
            gpuCapabilitiesLoading: false,
            gpuCapabilitiesError: null,
            executionProvider: null,
            latestApplyRequestId: null,
            realtimeApplyBlockedMessage: null,
            restartRequired: false,
            restartRequiredMessage: null,
            appliedRealtimeCameraIds: ['cam_a', 'cam_b'],
        },
        cameras: {
            cameras: cameraOverrides.map((camera, index) => ({
                id: camera.id,
                name: `Camera ${index + 1}`,
                index,
                selected: camera.selected,
                realtimeEnabled: camera.realtimeEnabled,
                connectionStatus: 'connected' as const,
                desiredConfig: {} as never,
                actualConfig: {} as never,
                hasConfigMismatch: false,
            })),
            isPaused: false,
            isLoading: false,
            autoApply: true,
            error: null,
        },
    } as RootState;
}

describe('realtime camera selection drift', () => {
    it('has no drift when desired cameras match the active pipeline', () => {
        const state = makeState([
            {id: 'cam_a', selected: true, realtimeEnabled: true},
            {id: 'cam_b', selected: true, realtimeEnabled: true},
        ]);
        expect(selectRealtimeCameraSelectionDrift(state)).toBe(false);
        expect(selectRealtimePipelineRestartNeeded(state)).toBe(false);
    });

    it('detects drift immediately when a pipeline camera is deselected', () => {
        const state = makeState([
            {id: 'cam_a', selected: true, realtimeEnabled: true},
            {id: 'cam_b', selected: true, realtimeEnabled: false},
        ]);
        expect(selectRealtimeCameraSelectionDrift(state)).toBe(true);
        expect(selectRealtimePipelineRestartNeeded(state)).toBe(true);
    });

    it('clears drift immediately when selection matches the active pipeline again', () => {
        const driftState = makeState([
            {id: 'cam_a', selected: true, realtimeEnabled: true},
            {id: 'cam_b', selected: true, realtimeEnabled: false},
        ]);
        const restoredState = makeState([
            {id: 'cam_a', selected: true, realtimeEnabled: true},
            {id: 'cam_b', selected: true, realtimeEnabled: true},
        ]);
        expect(selectRealtimeCameraSelectionDrift(driftState)).toBe(true);
        expect(selectRealtimeCameraSelectionDrift(restoredState)).toBe(false);
        expect(selectRealtimePipelineRestartNeeded(restoredState)).toBe(false);
    });

    it('detects drift immediately when a pipeline camera is unselected', () => {
        const state = makeState([
            {id: 'cam_a', selected: true, realtimeEnabled: true},
            {id: 'cam_b', selected: false, realtimeEnabled: false},
        ]);
        expect(selectRealtimeCameraSelectionDrift(state)).toBe(true);
    });
});
