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

import faceContourIndices from './holistic-face-indices.json';
import {buildClientSkeletonBinary, HOLISTIC_NUM_POINTS} from './client-skeleton-binary';

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

const FACE_IDX: number[] = faceContourIndices as number[];

let poseLm: PoseLandmarker | null = null;
let handLm: HandLandmarker | null = null;
let faceLm: FaceLandmarker | null = null;

function lmToPx(lm: NormalizedLandmark, w: number, h: number): {x: number; y: number; v: number} {
    return {
        x: lm.x * w,
        y: lm.y * h,
        v: (lm.visibility ?? (lm as {presence?: number}).presence ?? 1) as number,
    };
}

type HolisticTaskTimings = {poseMs: number; handMs: number; faceMs: number};

function fillHolisticBuffer(
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
    out.fill(NaN);
    const setTri = (i: number, x: number, y: number, v: number) => {
        const b = i * 3;
        out[b] = x * sx;
        out[b + 1] = y * sy;
        out[b + 2] = v;
    };

    let t0 = performance.now();
    const poseRes = poseLm!.detectForVideo(image, ts);
    const poseMs = performance.now() - t0;
    const plm = poseRes.landmarks[0];
    if (plm) {
        for (let i = 0; i < 33; i++) {
            const lm = plm[i];
            if (!lm) continue;
            const {x, y, v} = lmToPx(lm, iw, ih);
            setTri(i, x, y, v);
        }
    }

    t0 = performance.now();
    const handRes = handLm!.detectForVideo(image, ts);
    const handMs = performance.now() - t0;
    const fillHand = (startIdx: number, landmarks: NormalizedLandmark[] | undefined) => {
        if (!landmarks) return;
        for (let j = 0; j < 21; j++) {
            const lm = landmarks[j];
            if (!lm) continue;
            const {x, y, v} = lmToPx(lm, iw, ih);
            setTri(startIdx + j, x, y, v);
        }
    };
    if (handRes.landmarks) {
        for (let hi = 0; hi < handRes.landmarks.length; hi++) {
            const cat = handRes.handednesses?.[hi]?.[0]?.categoryName?.toLowerCase();
            const lm = handRes.landmarks[hi];
            if (cat === 'right') fillHand(33, lm);
            if (cat === 'left') fillHand(54, lm);
        }
    }

    t0 = performance.now();
    const faceRes = faceLm!.detectForVideo(image, ts);
    const faceMs = performance.now() - t0;
    const faceLmks = faceRes.faceLandmarks?.[0];
    const base = 75;
    if (faceLmks) {
        for (let f = 0; f < FACE_IDX.length; f++) {
            const srcIdx = FACE_IDX[f];
            const lm = faceLmks[srcIdx];
            if (!lm) continue;
            const px = lmToPx(lm, iw, ih);
            setTri(base + f, px.x, px.y, px.v);
        }
    }

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
        let sumPose = 0;
        let sumHand = 0;
        let sumFace = 0;
        const n = cameras.length;

        try {
            for (const cam of cameras) {
                const buf = new Float32Array(HOLISTIC_NUM_POINTS * 3);
                try {
                    const t = fillHolisticBuffer(
                        buf,
                        cam.origWidth,
                        cam.origHeight,
                        nextTimestampMs(),
                        cam.bitmap,
                    );
                    sumPose += t.poseMs;
                    sumHand += t.handMs;
                    sumFace += t.faceMs;
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
        const timings =
            n > 0
                ? {poseMs: sumPose / n, handMs: sumHand / n, faceMs: sumFace / n}
                : {poseMs: 0, handMs: 0, faceMs: 0};
        self.postMessage({type: 'result', frameNumber, buffer: binary, timings}, [binary]);
    }
};
