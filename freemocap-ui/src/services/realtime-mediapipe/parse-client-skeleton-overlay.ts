/**
 * Parse the client→server skeleton binary (same layout as
 * `freemocap.api.websocket.client_skeleton_binary`) into UI overlay payloads
 * without waiting for the server roundtrip. Keeps preview lined up with the
 * frame MediaPipe ran on.
 */
import {MESSAGE_TYPE_CLIENT_SKELETON_HEADER} from './client-skeleton-binary';
import type {MediapipeObservation} from '@/services/server/server-helpers/image-overlay/mediapipe-types';

const HEADER_SIZE = 77;
const META_SIZE = 28; // S16 + u4 + u4 + u4

function decodeCameraId(buf: Uint8Array, off: number): string {
    const slice = buf.subarray(off, off + 16);
    const z = slice.indexOf(0);
    const enc = new TextDecoder();
    return enc.decode(z >= 0 ? slice.subarray(0, z) : slice).trim();
}

/**
 * Returns one `MediapipeObservation` per camera in the buffer, or `null` if the
 * payload is not a valid client skeleton packet.
 */
export function parseClientSkeletonBinaryToObservations(
    buffer: ArrayBuffer,
    pointNames: readonly string[],
): Map<string, MediapipeObservation> | null {
    if (buffer.byteLength < HEADER_SIZE + META_SIZE) return null;
    const u8 = new Uint8Array(buffer);
    const dv = new DataView(buffer);
    if (u8[0] !== MESSAGE_TYPE_CLIENT_SKELETON_HEADER) return null;

    const frameNumber = Number(dv.getBigInt64(1, true));
    const numCameras = dv.getUint32(9, true);
    if (numCameras === 0 || numCameras > 32) return null;

    const out = new Map<string, MediapipeObservation>();
    let o = HEADER_SIZE;

    for (let c = 0; c < numCameras; c++) {
        if (o + META_SIZE > buffer.byteLength) return null;
        const cameraId = decodeCameraId(u8, o);
        const w = dv.getUint32(o + 16, true);
        const h = dv.getUint32(o + 20, true);
        const nPts = dv.getUint32(o + 24, true);
        o += META_SIZE;
        if (nPts !== pointNames.length) return null;
        const floatBytes = nPts * 3 * 4;
        if (o + floatBytes > buffer.byteLength) return null;
        /* Header (77) + per-camera meta (28) => first float block starts at 105 — not a
         * multiple of 4, so we cannot use `new Float32Array(buffer, o, …)` (typed-array
         * offset must be 4-byte aligned). Copy into a fresh buffer for an aligned view. */
        const flat = new Float32Array(buffer.slice(o, o + floatBytes));
        o += floatBytes;

        const points: MediapipeObservation['points'] = [];
        for (let i = 0; i < nPts; i++) {
            const x = flat[i * 3];
            const y = flat[i * 3 + 1];
            const visibility = flat[i * 3 + 2];
            if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
            points.push({
                name: pointNames[i]!,
                x,
                y,
                z: 0,
                visibility: Number.isFinite(visibility) ? visibility : 1,
            });
        }

        out.set(cameraId, {
            message_type: 'skeleton_overlay',
            camera_id: cameraId,
            frame_number: frameNumber,
            tracker_id: 'rtmpose_wholebody',
            image_width: w,
            image_height: h,
            points,
        });
    }

    return out.size > 0 ? out : null;
}
