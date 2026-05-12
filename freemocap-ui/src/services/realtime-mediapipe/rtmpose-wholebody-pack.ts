/**
 * Pack MediaPipe Tasks landmarks into the skellytracker `rtmpose_wholebody` layout
 * (see `rtmpose_wholebody.yaml`): body (23) + right_hand (21) + left_hand (21) + face (68) = 133.
 *
 * Body: COCO-WholeBody–style 23 joints from BlazePose 33 (toes/heels aligned to RTMPose naming).
 * Hands: same graph as RTMPose — MediaPipe hand indices already match `root, thumb*, forefinger*, …`.
 * Face: 68 indices into MediaPipe Face Landmarker mesh, aligned to iBUG 68 ordering (approximate).
 */
import type {NormalizedLandmark} from '@mediapipe/tasks-vision';

export const RTMPOSE_WHOLEBODY_NUM_POINTS = 133;

const BODY = 23;
const RIGHT_HAND = 21;
const LEFT_HAND = 21;
const FACE = 68;

const R0 = 0;
const RR = BODY;
const RL = BODY + RIGHT_HAND;
const RF = BODY + RIGHT_HAND + LEFT_HAND;

if (R0 + BODY + RIGHT_HAND + LEFT_HAND + FACE !== RTMPOSE_WHOLEBODY_NUM_POINTS) {
    throw new Error('rtmpose wholebody point count mismatch');
}

/** Stack Overflow–sourced 468-mesh → iBUG-68 index list (one landmark per iBUG point). */
const IBUG68_MEDIAPIPE_VERTEX: readonly number[] = [
    162, 234, 93, 58, 172, 136, 149, 148, 152, 377, 378, 365, 397, 288, 323, 454, 389, 71, 63, 105, 66, 107, 336, 296,
    334, 293, 301, 168, 197, 5, 4, 75, 97, 2, 326, 305, 33, 160, 158, 133, 153, 144, 362, 385, 387, 263, 373, 380, 61,
    39, 37, 0, 267, 269, 291, 405, 314, 17, 84, 181, 78, 82, 13, 312, 308, 317, 14, 87,
];

if (IBUG68_MEDIAPIPE_VERTEX.length !== FACE) {
    throw new Error('iBUG68 mapping must have length 68');
}

function setTri(
    out: Float32Array,
    i: number,
    x: number,
    y: number,
    v: number,
    sx: number,
    sy: number,
): void {
    const b = i * 3;
    out[b] = x * sx;
    out[b + 1] = y * sy;
    out[b + 2] = v;
}

function vis(lm: NormalizedLandmark | undefined): number {
    if (!lm) return 0;
    let v: number;
    const visRaw = lm.visibility;
    const pres = (lm as {presence?: number}).presence;
    if (typeof visRaw === 'number' && Number.isFinite(visRaw)) {
        v = visRaw;
    } else if (typeof pres === 'number' && Number.isFinite(pres)) {
        v = pres;
    } else {
        v = 1;
    }
    const hasXY =
        typeof lm.x === 'number' &&
        typeof lm.y === 'number' &&
        Number.isFinite(lm.x) &&
        Number.isFinite(lm.y);
    // Hands/face often report 0 visibility with valid coords — server drops vis≤1e-6.
    if (hasXY && v <= 1e-6) return 1;
    return v;
}

function px(
    lm: NormalizedLandmark | undefined,
    w: number,
    h: number,
): {x: number; y: number; v: number} {
    if (!lm) return {x: NaN, y: NaN, v: 0};
    return {
        x: lm.x * w,
        y: lm.y * h,
        v: vis(lm),
    };
}

function averagePx(
    plm: NormalizedLandmark[] | undefined,
    indices: readonly number[],
    iw: number,
    ih: number,
): {x: number; y: number; v: number} {
    if (!plm) return {x: NaN, y: NaN, v: 0};
    let sx = 0;
    let sy = 0;
    let sv = 1;
    let n = 0;
    for (const idx of indices) {
        const lm = plm[idx];
        if (!lm) continue;
        const {x, y, v} = px(lm, iw, ih);
        if (v <= 1e-6 || Number.isNaN(x)) continue;
        sx += x;
        sy += y;
        sv = Math.min(sv, v);
        n++;
    }
    if (n === 0) return {x: NaN, y: NaN, v: 0};
    return {x: sx / n, y: sy / n, v: sv};
}

/**
 * Fill `out` (133×3 floats: x_px, y_px, visibility) from pose / hand / face results.
 * Missing components leave NaN with visibility 0 (server treats as absent).
 */
export function fillRtmposeWholeBodyBuffer(
    out: Float32Array,
    iw: number,
    ih: number,
    sx: number,
    sy: number,
    args: {
        poseLm: NormalizedLandmark[] | undefined;
        /** Each detected hand's landmarks (21) and handedness categoryName. */
        hands: Array<{landmarks: NormalizedLandmark[]; category: string | undefined}>;
        faceLmks: NormalizedLandmark[] | undefined;
    },
): void {
    out.fill(NaN);
    const {poseLm, hands, faceLmks} = args;

    const writeInvalid = (slot: number) => setTri(out, slot, NaN, NaN, 0, sx, sy);

    // --- Body 0..22 (COCO WholeBody 23) from BlazePose 33 ---
    if (poseLm) {
        const g = (idx: number) => px(poseLm[idx], iw, ih);
        const set = (slot: number, p: {x: number; y: number; v: number}) =>
            setTri(out, slot, p.x, p.y, p.v, sx, sy);

        set(0, g(0));
        set(1, averagePx(poseLm, [1, 2, 3], iw, ih));
        set(2, averagePx(poseLm, [4, 5, 6], iw, ih));
        set(3, g(7));
        set(4, g(8));
        set(5, g(11));
        set(6, g(12));
        set(7, g(13));
        set(8, g(14));
        set(9, g(15));
        set(10, g(16));
        set(11, g(23));
        set(12, g(24));
        set(13, g(25));
        set(14, g(26));
        set(15, g(27));
        set(16, g(28));
        set(17, g(31));
        writeInvalid(18);
        set(19, g(29));
        set(20, g(32));
        writeInvalid(21);
        set(22, g(30));
    } else {
        for (let b = 0; b < BODY; b++) writeInvalid(b);
    }

    // --- Right hand 23..43, left hand 44..64 (prefix names differ; index order matches MediaPipe). ---
    for (let h = 0; h < hands.length; h++) {
        const {landmarks, category} = hands[h];
        const cat = category?.toLowerCase();
        const start = cat === 'right' ? RR : cat === 'left' ? RL : -1;
        if (start < 0 || !landmarks) continue;
        for (let j = 0; j < 21; j++) {
            const p = px(landmarks[j], iw, ih);
            setTri(out, start + j, p.x, p.y, p.v, sx, sy);
        }
    }

    // --- Face 65..132 (iBUG 68 via fixed mesh indices) ---
    if (faceLmks) {
        for (let f = 0; f < FACE; f++) {
            const srcIdx = IBUG68_MEDIAPIPE_VERTEX[f];
            const p = px(faceLmks[srcIdx], iw, ih);
            setTri(out, RF + f, p.x, p.y, p.v, sx, sy);
        }
    } else {
        for (let f = 0; f < FACE; f++) writeInvalid(RF + f);
    }
}
