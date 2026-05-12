/** Wire format must match `freemocap.api.websocket.client_skeleton_binary`. */

export const MESSAGE_TYPE_CLIENT_SKELETON_HEADER = 6;
export const MESSAGE_TYPE_CLIENT_SKELETON_FOOTER = 7;

const HEADER_SIZE = 77; // u1 + i8 + u4 + S64 packed (numpy default, no align)
const META_SIZE = 28; // S16 + u4 + u4 + u4

/** RTMPose-compatible 133-point layout from browser (matches `rtmpose_wholebody` YAML). */
const RTMPOSE_WHOLEBODY_NUM_POINTS = 133;

function encodeAsciiFixed(str: string, len: number): Uint8Array {
    const enc = new TextEncoder();
    const out = new Uint8Array(len);
    const raw = enc.encode(str);
    out.set(raw.subarray(0, Math.min(raw.length, len)));
    return out;
}

export function buildClientSkeletonBinary(args: {
    frameNumber: number;
    cameraGroupId: string;
    cameras: Array<{
        cameraId: string;
        width: number;
        height: number;
        /** Length must be RTMPOSE_WHOLEBODY_NUM_POINTS * 3 (x, y, visibility) float32 pixels */
        landmarks: Float32Array;
    }>;
}): ArrayBuffer {
    const {frameNumber, cameraGroupId, cameras} = args;
    const n = cameras.length;
    const dataBytes = n * (META_SIZE + RTMPOSE_WHOLEBODY_NUM_POINTS * 3 * 4);
    const total = HEADER_SIZE + dataBytes + HEADER_SIZE;
    const buf = new ArrayBuffer(total);
    const u8 = new Uint8Array(buf);
    const dv = new DataView(buf);

    let o = 0;
    dv.setUint8(o, MESSAGE_TYPE_CLIENT_SKELETON_HEADER);
    o += 1;
    dv.setBigInt64(o, BigInt(frameNumber), true);
    o += 8;
    dv.setUint32(o, n, true);
    o += 4;
    u8.set(encodeAsciiFixed(cameraGroupId, 64), o);
    o += 64;

    for (const cam of cameras) {
        if (cam.landmarks.length !== RTMPOSE_WHOLEBODY_NUM_POINTS * 3) {
            throw new Error(
                `Expected ${RTMPOSE_WHOLEBODY_NUM_POINTS * 3} floats per camera, got ${cam.landmarks.length}`,
            );
        }
        u8.set(encodeAsciiFixed(cam.cameraId, 16), o);
        o += 16;
        dv.setUint32(o, cam.width >>> 0, true);
        o += 4;
        dv.setUint32(o, cam.height >>> 0, true);
        o += 4;
        dv.setUint32(o, RTMPOSE_WHOLEBODY_NUM_POINTS, true);
        o += 4;
        u8.set(new Uint8Array(cam.landmarks.buffer, cam.landmarks.byteOffset, cam.landmarks.byteLength), o);
        o += cam.landmarks.byteLength;
    }

    dv.setUint8(o, MESSAGE_TYPE_CLIENT_SKELETON_FOOTER);
    o += 1;
    dv.setBigInt64(o, BigInt(frameNumber), true);
    o += 8;
    dv.setUint32(o, n, true);
    o += 4;
    u8.set(encodeAsciiFixed(cameraGroupId, 64), o);

    return buf;
}

export {RTMPOSE_WHOLEBODY_NUM_POINTS};
