import type {RealtimeModelSize} from '@/store/slices/realtime/realtime-types';
import type {FrameData} from '@/services/server/server-helpers/frame-processor/frame-processor';

import MediapipeWorkerConstructor from './mediapipe-engine.worker?worker';

export type MediapipeInferTimings = {poseMs: number; handMs: number; faceMs: number};

type WorkerMessage =
    | {type: 'ready'}
    | {type: 'init-error'; message: string}
    | {type: 'result'; frameNumber: number; buffer: ArrayBuffer; timings: MediapipeInferTimings}
    | {type: 'infer-error'; frameNumber: number; message: string};

type PendingInfer = {
    frameNumber: number;
    resolve: (result: {buffer: ArrayBuffer; timings: MediapipeInferTimings}) => void;
    reject: (err: Error) => void;
};

/**
 * Runs MediaPipe Tasks (pose + hands + face) in a dedicated worker.
 *
 * Inference calls are **serialized** — MediaPipe Tasks VIDEO mode does not
 * support concurrent calls into the same landmarker and the worker drives all
 * three landmarkers sequentially. While one batch is processing, new
 * `inferFrame` requests are dropped (their bitmaps closed) so the preview
 * pipeline isn't starved waiting for a backlog to drain.
 */
export class MediapipeRealtimeEngine {
    private worker: Worker | null = null;
    private pendingInfer: PendingInfer | null = null;
    private readyResolve: (() => void) | null = null;
    private readyReject: ((err: Error) => void) | null = null;

    public isRunning(): boolean {
        return this.worker != null;
    }

    /** True while a previously submitted batch is still being processed. */
    public isBusy(): boolean {
        return this.pendingInfer !== null;
    }

    public async start(modelSize: RealtimeModelSize): Promise<void> {
        this.stop();
        const WorkerCtor = MediapipeWorkerConstructor as unknown as new () => Worker;
        const worker = new WorkerCtor();
        this.worker = worker;
        worker.addEventListener('message', this.handleMessage);
        worker.addEventListener('error', this.handleWorkerError);
        worker.addEventListener('messageerror', this.handleWorkerError);

        await new Promise<void>((resolve, reject) => {
            this.readyResolve = resolve;
            this.readyReject = reject;
            worker.postMessage({type: 'init', modelSize});
        });
    }

    public stop(): void {
        const worker = this.worker;
        if (worker) {
            worker.removeEventListener('message', this.handleMessage);
            worker.removeEventListener('error', this.handleWorkerError);
            worker.removeEventListener('messageerror', this.handleWorkerError);
            worker.terminate();
        }
        this.worker = null;
        if (this.pendingInfer) {
            this.pendingInfer.reject(new Error('MediaPipe worker stopped'));
            this.pendingInfer = null;
        }
        if (this.readyReject) {
            this.readyReject(new Error('MediaPipe worker stopped before init completed'));
        }
        this.readyResolve = null;
        this.readyReject = null;
    }

    /**
     * Each `FrameData.bitmap` must be owned for this infer call only (e.g. clones
     * created before the canvas path transfers the decode worker bitmaps). The
     * worker closes each bitmap after inference; on a dropped call we close them
     * here.
     *
     * Returns `false` when the previous batch is still in flight (caller dropped
     * its turn). Returns `true` when the batch was accepted; `onResult` fires
     * exactly once when the worker finishes.
     */
    public inferFrame(
        frameNumber: number,
        cameraGroupId: string,
        frames: FrameData[],
        onResult: (result: {buffer: ArrayBuffer; timings: MediapipeInferTimings}) => void,
        onError?: (err: Error) => void,
    ): boolean {
        const worker = this.worker;
        if (!worker) {
            this.closeBitmaps(frames);
            return false;
        }
        if (this.pendingInfer) {
            this.closeBitmaps(frames);
            return false;
        }
        const cameras = frames.map((f) => ({
            cameraId: f.cameraId,
            origWidth: f.width,
            origHeight: f.height,
            bitmap: f.bitmap,
        }));
        const transfers = cameras.map((c) => c.bitmap);
        this.pendingInfer = {
            frameNumber,
            resolve: onResult,
            reject: (err) => onError?.(err),
        };
        try {
            worker.postMessage({type: 'infer', frameNumber, cameraGroupId, cameras}, transfers);
        } catch (err) {
            this.pendingInfer = null;
            this.closeBitmaps(frames);
            onError?.(err instanceof Error ? err : new Error(String(err)));
            return false;
        }
        return true;
    }

    private closeBitmaps(frames: FrameData[]): void {
        for (const f of frames) {
            try {
                f.bitmap.close();
            } catch {
                /* already closed or transferred */
            }
        }
    }

    private handleMessage = (ev: MessageEvent<WorkerMessage>): void => {
        const data = ev.data;
        if (!data || typeof data !== 'object') return;
        switch (data.type) {
            case 'ready': {
                this.readyResolve?.();
                this.readyResolve = null;
                this.readyReject = null;
                return;
            }
            case 'init-error': {
                const err = new Error(`MediaPipe init failed: ${data.message}`);
                this.readyReject?.(err);
                this.readyResolve = null;
                this.readyReject = null;
                return;
            }
            case 'result': {
                const pending = this.pendingInfer;
                this.pendingInfer = null;
                pending?.resolve({buffer: data.buffer, timings: data.timings});
                return;
            }
            case 'infer-error': {
                const pending = this.pendingInfer;
                this.pendingInfer = null;
                pending?.reject(new Error(`MediaPipe infer failed: ${data.message}`));
                return;
            }
        }
    };

    private handleWorkerError = (event: Event): void => {
        const message =
            event instanceof ErrorEvent && event.message ? event.message : 'MediaPipe worker error';
        const err = new Error(message);
        if (this.readyReject) {
            this.readyReject(err);
            this.readyResolve = null;
            this.readyReject = null;
        }
        if (this.pendingInfer) {
            const pending = this.pendingInfer;
            this.pendingInfer = null;
            pending.reject(err);
        }
    };
}
