/** Longest side cap for frames fed to MediaPipe in the worker (inference-only). */
export const MEDIAPIPE_INFER_MAX_SIDE = 640;

/**
 * Clone a decoded camera frame for browser MediaPipe inference.
 * Downscales when the stream is larger than {@link MEDIAPIPE_INFER_MAX_SIDE} on
 * the longest side to cut per-frame ImageBitmap memory (~4× less at 1280×720).
 * Landmark coordinates are scaled back to full resolution in the worker.
 */
export async function cloneFrameBitmapForMediapipe(
    source: ImageBitmap,
    origWidth: number,
    origHeight: number,
): Promise<ImageBitmap> {
    const max = Math.max(origWidth, origHeight);
    if (max <= MEDIAPIPE_INFER_MAX_SIDE) {
        return createImageBitmap(source);
    }
    const scale = MEDIAPIPE_INFER_MAX_SIDE / max;
    const rw = Math.max(1, Math.round(origWidth * scale));
    const rh = Math.max(1, Math.round(origHeight * scale));
    return createImageBitmap(source, {
        resizeWidth: rw,
        resizeHeight: rh,
        premultiplyAlpha: 'none',
        colorSpaceConversion: 'none',
        resizeQuality: 'medium',
    });
}
