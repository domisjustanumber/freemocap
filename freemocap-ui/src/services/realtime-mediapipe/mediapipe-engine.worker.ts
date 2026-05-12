/**
 * Browser MediaPipe Tasks (pose + hands + face) for realtime holistic keypoints.
 * Runs in a dedicated worker; posts compact binary back to main for WebSocket upload.
 */
/// <reference lib="webworker" />

import {
    FaceLandmarker,
    FilesetResolver,
    HandLandmarker,
    PoseLandmarker,
    type NormalizedLandmark,
} from '@mediapipe/tasks-vision';

import {buildClientSkeletonBinary, RTMPOSE_WHOLEBODY_NUM_POINTS} from './client-skeleton-binary';
import {fillRtmposeWholeBodyBuffer} from './rtmpose-wholebody-pack';

const WASM_BASE = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm';

const POSE_MODEL: Record<string, string> = {
    lite: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task',
    full: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task',
    heavy: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task',
};

const HAND_MODEL =
    'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task';
const FACE_MODEL =
    'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task';

let poseLm: PoseLandmarker | null = null;
let handLm: HandLandmarker | null = null;
let faceLm: FaceLandmarker | null = null;

type HolisticTaskTimings = {poseMs: number; handMs: number; faceMs: number};

function fillRtmposeWholeBody(
    out: Float32Array,
    origW: number,
    origH: number,
    ts: number,
    image: ImageBitmap,
): HolisticTaskTimings {
    const iw = image.width;
    const ih = image.height;
    const sx = origW / iw;
    const sy = origH / ih;

    let t0 = performance.now();
    const poseRes = poseLm!.detectForVideo(image, ts);
    const poseMs = performance.now() - t0;

    t0 = performance.now();
    const handRes = handLm!.detectForVideo(image, ts);
    const handMs = performance.now() - t0;
    const hands: Array<{landmarks: NormalizedLandmark[]; category: string | undefined}> = [];
    if (handRes.landmarks) {
        for (let hi = 0; hi < handRes.landmarks.length; hi++) {
            const cat = handRes.handednesses?.[hi]?.[0]?.categoryName;
            const lm = handRes.landmarks[hi];
            if (lm) hands.push({landmarks: lm, category: cat});
        }
    }

    t0 = performance.now();
    const faceRes = faceLm!.detectForVideo(image, ts);
    const faceMs = performance.now() - t0;
    const faceLmks = faceRes.faceLandmarks?.[0];

    fillRtmposeWholeBodyBuffer(out, iw, ih, sx, sy, {
        poseLm: poseRes.landmarks[0],
        hands,
        faceLmks,
    });

    return {poseMs, handMs, faceMs};
}

/**
 * Distinct, strictly-increasing timestamps per landmarker (in any of pose/hand/face)
 * across both cameras within the same `infer` batch and across batches. MediaPipe
 * Tasks VIDEO mode rejects non-monotonic timestamps with a "Packet timestamp
 * mismatch" error and the landmarker enters an unrecoverable state.
 */
let _lastTimestampMs = 0;
function nextTimestampMs(): number {
    const now = performance.now();
    _lastTimestampMs = now > _lastTimestampMs ? now : _lastTimestampMs + 1;
    return _lastTimestampMs;
}

self.onmessage = async (e: MessageEvent) => {
    const msg = e.data as {type: string; modelSize?: string};
    if (msg.type === 'init') {
        try {
            const modelSize = (msg.modelSize as keyof typeof POSE_MODEL) || 'full';
            const vision = await FilesetResolver.forVisionTasks(WASM_BASE);
            const tryDelegate = async (delegate: 'GPU' | 'CPU') => {
                const base = (path: string) => ({modelAssetPath: path, delegate});
                const poseUrl = POSE_MODEL[modelSize] ?? POSE_MODEL.full;
                poseLm?.close?.();
                handLm?.close?.();
                faceLm?.close?.();
                poseLm = null;
                handLm = null;
                faceLm = null;
                poseLm = await PoseLandmarker.createFromOptions(vision, {
                    baseOptions: base(poseUrl),
                    runningMode: 'VIDEO',
                    numPoses: 1,
                });
                handLm = await HandLandmarker.createFromOptions(vision, {
                    baseOptions: base(HAND_MODEL),
                    runningMode: 'VIDEO',
                    numHands: 2,
                });
                faceLm = await FaceLandmarker.createFromOptions(vision, {
                    baseOptions: base(FACE_MODEL),
                    runningMode: 'VIDEO',
                    outputFaceBlendshapes: false,
                    outputFacialTransformationMatrixes: false,
                });
            };
            try {
                await tryDelegate('GPU');
            } catch {
                await tryDelegate('CPU');
            }
            _lastTimestampMs = 0;
            self.postMessage({type: 'ready'});
        } catch (err) {
            poseLm?.close?.();
            handLm?.close?.();
            faceLm?.close?.();
            poseLm = null;
            handLm = null;
            faceLm = null;
            self.postMessage({
                type: 'init-error',
                message: err instanceof Error ? `${err.name}: ${err.message}` : String(err),
            });
        }
        return;
    }

    if (msg.type === 'infer') {
        const {frameNumber, cameraGroupId, cameras} = e.data as unknown as {
            frameNumber: number;
            cameraGroupId: string;
            cameras: Array<{
                cameraId: string;
                origWidth: number;
                origHeight: number;
                bitmap: ImageBitmap;
            }>;
        };
        if (!poseLm || !handLm || !faceLm) {
            for (const cam of cameras) {
                try {
                    cam.bitmap.close();
                } catch {
                    /* already closed */
                }
            }
            self.postMessage({type: 'infer-error', frameNumber, message: 'Landmarkers not initialized'});
            return;
        }

        const packed: Array<{cameraId: string; width: number; height: number; landmarks: Float32Array}> = [];
        const perCamera: Array<{cameraId: string; poseMs: number; handMs: number; faceMs: number}> = [];

        try {
            for (const cam of cameras) {
                const buf = new Float32Array(RTMPOSE_WHOLEBODY_NUM_POINTS * 3);
                try {
                    const t = fillRtmposeWholeBody(
                        buf,
                        cam.origWidth,
                        cam.origHeight,
                        nextTimestampMs(),
                        cam.bitmap,
                    );
                    perCamera.push({
                        cameraId: cam.cameraId,
                        poseMs: t.poseMs,
                        handMs: t.handMs,
                        faceMs: t.faceMs,
                    });
                } finally {
                    cam.bitmap.close();
                }
                packed.push({
                    cameraId: cam.cameraId,
                    width: cam.origWidth,
                    height: cam.origHeight,
                    landmarks: buf,
                });
            }
        } catch (err) {
            self.postMessage({
                type: 'infer-error',
                frameNumber,
                message: err instanceof Error ? `${err.name}: ${err.message}` : String(err),
            });
            return;
        }

        const binary = buildClientSkeletonBinary({
            frameNumber,
            cameraGroupId,
            cameras: packed,
        });
        const timings = {perCamera};
        self.postMessage({type: 'result', frameNumber, buffer: binary, timings}, [binary]);
    }
};
