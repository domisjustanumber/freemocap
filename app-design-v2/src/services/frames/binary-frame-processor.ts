// ============================================
// BINARY FRAME PARSER (binary-frame-parser.ts) - WITH DEBUG LOGGING
// ============================================

// Message types from Python protocol
export const MessageType = {
    PAYLOAD_HEADER: 0,
    FRAME_HEADER: 1,
    PAYLOAD_FOOTER: 2,
} as const;

// Binary protocol constants - matching Python dtype definitions
export const PROTOCOL_SIZES = {
    PAYLOAD_HEADER: 24,
    FRAME_HEADER: 56,
    PAYLOAD_FOOTER: 24,
} as const;

// Payload Header layout
const PAYLOAD_HEADER_LAYOUT = {
    MESSAGE_TYPE: { offset: 0, size: 1 },
    PADDING: { offset: 1, size: 7 },
    FRAME_NUMBER: { offset: 8, size: 8 },
    NUM_CAMERAS: { offset: 16, size: 4 },
    PADDING_END: { offset: 20, size: 4 },
} as const;

// Frame Header layout
const FRAME_HEADER_LAYOUT = {
    MESSAGE_TYPE: { offset: 0, size: 1 },
    PADDING: { offset: 1, size: 7 },
    FRAME_NUMBER: { offset: 8, size: 8 },
    CAMERA_ID: { offset: 16, size: 16 },
    CAMERA_INDEX: { offset: 32, size: 4 },
    IMAGE_WIDTH: { offset: 36, size: 4 },
    IMAGE_HEIGHT: { offset: 40, size: 4 },
    COLOR_CHANNELS: { offset: 44, size: 4 },
    JPEG_LENGTH: { offset: 48, size: 4 },
    PADDING_END: { offset: 52, size: 4 },
} as const;

// Payload Footer layout (same structure as header)
const PAYLOAD_FOOTER_LAYOUT = {
    MESSAGE_TYPE: { offset: 0, size: 1 },
    PADDING: { offset: 1, size: 7 },
    FRAME_NUMBER: { offset: 8, size: 8 },
    NUM_CAMERAS: { offset: 16, size: 4 },
    PADDING_END: { offset: 20, size: 4 },
} as const;

// Type definitions
export interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    jpegData: Uint8Array;
}

export interface ParsedPayload {
    frameNumber: number;
    frames: ParsedFrame[];
}

interface PayloadHeader {
    messageType: number;
    frameNumber: number;
    numCameras: number;
}

interface FrameHeader {
    messageType: number;
    frameNumber: number;
    cameraId: string;
    cameraIndex: number;
    width: number;
    height: number;
    colorChannels: number;
    jpegLength: number;
}

type BinaryFrameWindow = Window & {
    /** Set `true` to force per-frame logs; `false` to suppress. Overrides URL heuristics. */
    __FM_VERBOSE_BINARY_FRAME_LOGS__?: boolean;
    chrome?: { webview?: unknown };
};

function hydrateBinaryFrameLogFlagFromUrl(): void {
    if (typeof window === 'undefined') return;
    try {
        const v = new URLSearchParams(window.location.search).get('debugBinaryFrames');
        if (v === '1' || v?.toLowerCase() === 'true') {
            (window as BinaryFrameWindow).__FM_VERBOSE_BINARY_FRAME_LOGS__ = true;
        }
    } catch {
        /* opaque origins, etc. */
    }
}

hydrateBinaryFrameLogFlagFromUrl();

let cachedUaLooksEmbeddedShell: boolean | undefined;

/** Electron / embedded WebViews / standalone PWA — often no inspector attached. */
function uaOrMediaLooksEmbeddedAppShell(win: Window): boolean {
    if (cachedUaLooksEmbeddedShell !== undefined) {
        return cachedUaLooksEmbeddedShell;
    }
    const ua = typeof win.navigator !== 'undefined' ? win.navigator.userAgent ?? '' : '';
    if (/electron/i.test(ua) || /webview/i.test(ua)) {
        cachedUaLooksEmbeddedShell = true;
        return true;
    }
    const chrom = (win as BinaryFrameWindow).chrome;
    if (chrom?.webview != null) {
        cachedUaLooksEmbeddedShell = true;
        return true;
    }
    cachedUaLooksEmbeddedShell = false;
    return false;
}

function displayModeStandalone(win: Window): boolean {
    return typeof win.matchMedia === 'function' && win.matchMedia('(display-mode: standalone)').matches;
}

/**
 * DevTools docked vertically/horizontally usually changes outer vs inner window dimensions (imperfect but cheap).
 */
function appearsInspectorChromeLikelyShowing(win: Window): boolean {
    const dw = Math.abs(win.outerWidth - win.innerWidth);
    const dh = Math.abs(win.outerHeight - win.innerHeight);
    return dw > 160 || dh > 160;
}

function shouldEmitBinaryFrameVerboseLogs(): boolean {
    if (typeof window === 'undefined') {
        return false;
    }
    const win = window as BinaryFrameWindow;
    if (win.__FM_VERBOSE_BINARY_FRAME_LOGS__ === true) {
        return true;
    }
    if (win.__FM_VERBOSE_BINARY_FRAME_LOGS__ === false) {
        return false;
    }
    if (import.meta.env.PROD) {
        return false;
    }
    const embeddedShell = uaOrMediaLooksEmbeddedAppShell(win) || displayModeStandalone(win);
    if (!embeddedShell) {
        return true;
    }
    return appearsInspectorChromeLikelyShowing(win);
}

function logBinaryFrameVerbose(...args: Parameters<typeof console.log>): void {
    if (!shouldEmitBinaryFrameVerboseLogs()) {
        return;
    }
    console.log(...args);
}

function warnBinaryFrameVerbose(...args: Parameters<typeof console.warn>): void {
    if (!shouldEmitBinaryFrameVerboseLogs()) {
        return;
    }
    console.warn(...args);
}

export class BinaryFrameParser {
    private textDecoder = new TextDecoder();

    // Performance monitoring
    private parseWarningsEnabled = true;
    private maxParseTimeMs = 5;

    // Debug stats
    private parseStats = {
        totalPayloadsParsed: 0,
        totalFramesParsed: 0,
        totalBytesProcessed: 0,
        totalParseErrors: 0,
        lastParseTime: 0,
    };

    constructor(options?: {
        parseWarningsEnabled?: boolean;
        maxParseTimeMs?: number;
    }) {
        logBinaryFrameVerbose('🔬 BinaryFrameParser: Constructor called with options:', options);

        if (options?.parseWarningsEnabled !== undefined) {
            this.parseWarningsEnabled = options.parseWarningsEnabled;
        }
        if (options?.maxParseTimeMs !== undefined) {
            this.maxParseTimeMs = options.maxParseTimeMs;
        }
    }

    /**
     * Parse binary frame data from WebSocket
     */
    parseFrameData(data: ArrayBuffer): ParsedPayload | null {
        const startTime = this.parseWarningsEnabled ? performance.now() : 0;

        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Starting parse of ${data.byteLength} bytes`);
        this.parseStats.totalBytesProcessed += data.byteLength;

        try {
            // Log first 100 bytes for debugging (avoid work when nobody is consuming logs)
            if (shouldEmitBinaryFrameVerboseLogs()) {
                const preview = new Uint8Array(data, 0, Math.min(100, data.byteLength));
                console.log(
                    '🔬 BinaryFrameParser: First 100 bytes:',
                    Array.from(preview).map(b => b.toString(16).padStart(2, '0')).join(' ')
                );
            }

            const result = this.parsePayload(data);

            if (this.parseWarningsEnabled) {
                const parseTime = performance.now() - startTime;
                this.parseStats.lastParseTime = parseTime;

                if (parseTime > this.maxParseTimeMs) {
                    warnBinaryFrameVerbose(`⚠️ BinaryFrameParser: Slow parse! ${parseTime.toFixed(2)}ms (threshold: ${this.maxParseTimeMs}ms)`);
                } else {
                    logBinaryFrameVerbose(`⏱️ BinaryFrameParser: Parse completed in ${parseTime.toFixed(2)}ms`);
                }
            }

            if (result) {
                this.parseStats.totalPayloadsParsed++;
                logBinaryFrameVerbose(`✅ BinaryFrameParser: Successfully parsed payload #${this.parseStats.totalPayloadsParsed}`);
                logBinaryFrameVerbose(`📊 BinaryFrameParser: Parse stats:`, this.parseStats);
            }

            return result;
        } catch (error) {
            this.parseStats.totalParseErrors++;
            console.error('❌ BinaryFrameParser: Parse failed:', error);
            console.error('📊 BinaryFrameParser: Error stats:', this.parseStats);
            return null;
        }
    }

    private parsePayload(data: ArrayBuffer): ParsedPayload | null {
        const dataView = new DataView(data);
        let offset = 0;

        logBinaryFrameVerbose(`🔬 BinaryFrameParser: parsePayload - buffer size: ${data.byteLength} bytes`);

        // Parse Payload Header
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Parsing payload header at offset ${offset}`);
        const header = this.parsePayloadHeader(dataView, offset);
        if (!header) {
            console.error('❌ BinaryFrameParser: Failed to parse payload header');
            return null;
        }

        logBinaryFrameVerbose(`✅ BinaryFrameParser: Payload header parsed:`, {
            messageType: header.messageType,
            frameNumber: header.frameNumber,
            numCameras: header.numCameras
        });

        offset += PROTOCOL_SIZES.PAYLOAD_HEADER;

        // Parse all camera frames
        const frames: ParsedFrame[] = [];
        for (let i = 0; i < header.numCameras; i++) {
            logBinaryFrameVerbose(`🔬 BinaryFrameParser: Parsing frame ${i + 1}/${header.numCameras} at offset ${offset}`);

            const frame = this.parseFrame(
                data,
                dataView,
                offset,
                header.frameNumber
            );

            if (!frame) {
                console.error(`❌ BinaryFrameParser: Failed to parse frame ${i + 1}/${header.numCameras}`);
                return null;
            }

            logBinaryFrameVerbose(`✅ BinaryFrameParser: Frame ${i + 1} parsed:`, {
                cameraId: frame.parsedFrame.cameraId,
                cameraIndex: frame.parsedFrame.cameraIndex,
                dimensions: `${frame.parsedFrame.width}x${frame.parsedFrame.height}`,
                jpegSize: frame.parsedFrame.jpegData.length
            });

            frames.push(frame.parsedFrame);
            offset = frame.nextOffset;
            this.parseStats.totalFramesParsed++;
        }

        // Verify Payload Footer
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Verifying payload footer at offset ${offset}`);
        if (!this.verifyPayloadFooter(dataView, offset, header)) {
            console.error('❌ BinaryFrameParser: Payload footer verification failed');
            return null;
        }

        logBinaryFrameVerbose('✅ BinaryFrameParser: Payload footer verified');

        const totalSize = offset + PROTOCOL_SIZES.PAYLOAD_FOOTER;
        logBinaryFrameVerbose(`📏 BinaryFrameParser: Total payload size: ${totalSize} bytes (buffer: ${data.byteLength} bytes)`);

        if (totalSize !== data.byteLength) {
            warnBinaryFrameVerbose(`⚠️ BinaryFrameParser: Size mismatch! Expected ${totalSize}, got ${data.byteLength}`);
        }

        return {
            frameNumber: header.frameNumber,
            frames,
        };
    }

    private parsePayloadHeader(dataView: DataView, offset: number): PayloadHeader | null {
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: parsePayloadHeader at offset ${offset}`);

        // Check buffer bounds
        if (dataView.byteLength < offset + PROTOCOL_SIZES.PAYLOAD_HEADER) {
            console.error(`❌ BinaryFrameParser: Buffer too small for payload header. Need ${offset + PROTOCOL_SIZES.PAYLOAD_HEADER}, have ${dataView.byteLength}`);
            return null;
        }

        const messageType = dataView.getUint8(offset + PAYLOAD_HEADER_LAYOUT.MESSAGE_TYPE.offset);
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Message type: ${messageType} (expected ${MessageType.PAYLOAD_HEADER})`);

        if (messageType !== MessageType.PAYLOAD_HEADER) {
            console.error(`❌ BinaryFrameParser: Wrong message type! Expected ${MessageType.PAYLOAD_HEADER}, got ${messageType}`);

            // Log surrounding bytes for debugging
            const contextBytes = new Uint8Array(dataView.buffer, dataView.byteOffset + offset, Math.min(32, dataView.byteLength - offset));
            console.error('Context bytes:', Array.from(contextBytes).map(b => b.toString(16).padStart(2, '0')).join(' '));
            return null;
        }

        const frameNumber = Number(dataView.getBigInt64(
            offset + PAYLOAD_HEADER_LAYOUT.FRAME_NUMBER.offset,
            true // little-endian
        ));
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Frame number: ${frameNumber}`);

        const numCameras = dataView.getInt32(
            offset + PAYLOAD_HEADER_LAYOUT.NUM_CAMERAS.offset,
            true
        );
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Number of cameras: ${numCameras}`);

        if (numCameras <= 0 || numCameras > 100) {
            console.error(`❌ BinaryFrameParser: Invalid number of cameras: ${numCameras}`);
            return null;
        }

        return { messageType, frameNumber, numCameras };
    }

    private parseFrame(
        data: ArrayBuffer,
        dataView: DataView,
        offset: number,
        expectedFrameNumber: number
    ): { parsedFrame: ParsedFrame; nextOffset: number } | null {
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: parseFrame at offset ${offset}`);

        // Parse Frame Header
        const frameHeader = this.parseFrameHeader(dataView, offset);
        if (!frameHeader) {
            console.error('❌ BinaryFrameParser: Failed to parse frame header');
            return null;
        }

        // Verify frame number matches
        if (frameHeader.frameNumber !== expectedFrameNumber) {
            console.error(
                `❌ BinaryFrameParser: Frame number mismatch! Expected ${expectedFrameNumber}, got ${frameHeader.frameNumber}`
            );
            return null;
        }

        offset += PROTOCOL_SIZES.FRAME_HEADER;

        // Check JPEG data bounds
        if (offset + frameHeader.jpegLength > dataView.byteLength) {
            console.error(`❌ BinaryFrameParser: Buffer too small for JPEG data. Need ${offset + frameHeader.jpegLength}, have ${dataView.byteLength}`);
            return null;
        }

        // Extract JPEG data (create a view, not a copy, for efficiency)
        const jpegData = new Uint8Array(data, offset, frameHeader.jpegLength);

        // Verify JPEG magic bytes
        if (jpegData.length >= 2) {
            const jpegMagic = (jpegData[0] << 8) | jpegData[1];
            if (jpegMagic === 0xFFD8) {
                logBinaryFrameVerbose(`✅ BinaryFrameParser: Valid JPEG magic bytes found (0xFFD8)`);
            } else {
                warnBinaryFrameVerbose(`⚠️ BinaryFrameParser: Unexpected JPEG magic bytes: 0x${jpegMagic.toString(16)}`);
            }
        }

        offset += frameHeader.jpegLength;

        return {
            parsedFrame: {
                cameraId: frameHeader.cameraId,
                cameraIndex: frameHeader.cameraIndex,
                frameNumber: frameHeader.frameNumber,
                width: frameHeader.width,
                height: frameHeader.height,
                jpegData,
            },
            nextOffset: offset,
        };
    }

    private parseFrameHeader(dataView: DataView, offset: number): FrameHeader | null {
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: parseFrameHeader at offset ${offset}`);

        // Check buffer bounds
        if (dataView.byteLength < offset + PROTOCOL_SIZES.FRAME_HEADER) {
            console.error(`❌ BinaryFrameParser: Buffer too small for frame header. Need ${offset + PROTOCOL_SIZES.FRAME_HEADER}, have ${dataView.byteLength}`);
            return null;
        }

        const messageType = dataView.getUint8(offset + FRAME_HEADER_LAYOUT.MESSAGE_TYPE.offset);
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Frame message type: ${messageType} (expected ${MessageType.FRAME_HEADER})`);

        if (messageType !== MessageType.FRAME_HEADER) {
            console.error(`❌ BinaryFrameParser: Wrong frame message type! Expected ${MessageType.FRAME_HEADER}, got ${messageType}`);
            return null;
        }

        const frameNumber = Number(dataView.getBigInt64(
            offset + FRAME_HEADER_LAYOUT.FRAME_NUMBER.offset,
            true
        ));

        // Extract camera ID efficiently
        const cameraId = this.extractCameraId(dataView, offset + FRAME_HEADER_LAYOUT.CAMERA_ID.offset);
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Camera ID: "${cameraId}"`);

        const cameraIndex = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.CAMERA_INDEX.offset,
            true
        );

        const width = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.IMAGE_WIDTH.offset,
            true
        );

        const height = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.IMAGE_HEIGHT.offset,
            true
        );

        const colorChannels = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.COLOR_CHANNELS.offset,
            true
        );

        const jpegLength = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.JPEG_LENGTH.offset,
            true
        );

        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Frame details:`, {
            frameNumber,
            cameraId,
            cameraIndex,
            dimensions: `${width}x${height}`,
            colorChannels,
            jpegLength
        });

        // Sanity checks
        if (width <= 0 || width > 10000 || height <= 0 || height > 10000) {
            console.error(`❌ BinaryFrameParser: Invalid image dimensions: ${width}x${height}`);
            return null;
        }

        if (jpegLength <= 0 || jpegLength > 10 * 1024 * 1024) {
            console.error(`❌ BinaryFrameParser: Invalid JPEG length: ${jpegLength} bytes`);
            return null;
        }

        return {
            messageType,
            frameNumber,
            cameraId,
            cameraIndex,
            width,
            height,
            colorChannels,
            jpegLength,
        };
    }

    private extractCameraId(dataView: DataView, offset: number): string {
        // Create a view of the camera ID bytes
        const cameraIdBytes = new Uint8Array(
            dataView.buffer,
            dataView.byteOffset + offset,
            FRAME_HEADER_LAYOUT.CAMERA_ID.size
        );

        // Log raw bytes for debugging
        logBinaryFrameVerbose('🔬 BinaryFrameParser: Camera ID bytes:',
            Array.from(cameraIdBytes).map(b => b.toString(16).padStart(2, '0')).join(' '));

        // Find null terminator
        let cameraIdLength = 0;
        while (
            cameraIdLength < FRAME_HEADER_LAYOUT.CAMERA_ID.size &&
            cameraIdBytes[cameraIdLength] !== 0
            ) {
            cameraIdLength++;
        }

        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Camera ID length: ${cameraIdLength}`);

        // Decode the string
        const cameraId = this.textDecoder.decode(
            cameraIdBytes.subarray(0, cameraIdLength)
        );

        return cameraId;
    }

    private verifyPayloadFooter(
        dataView: DataView,
        offset: number,
        header: PayloadHeader
    ): boolean {
        logBinaryFrameVerbose(`🔬 BinaryFrameParser: verifyPayloadFooter at offset ${offset}`);

        // Check buffer bounds
        if (dataView.byteLength < offset + PROTOCOL_SIZES.PAYLOAD_FOOTER) {
            console.error(`❌ BinaryFrameParser: Buffer too small for payload footer. Need ${offset + PROTOCOL_SIZES.PAYLOAD_FOOTER}, have ${dataView.byteLength}`);
            return false;
        }

        const footerMessageType = dataView.getUint8(
            offset + PAYLOAD_FOOTER_LAYOUT.MESSAGE_TYPE.offset
        );

        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Footer message type: ${footerMessageType} (expected ${MessageType.PAYLOAD_FOOTER})`);

        if (footerMessageType !== MessageType.PAYLOAD_FOOTER) {
            console.error(
                `❌ BinaryFrameParser: Wrong footer message type! Expected ${MessageType.PAYLOAD_FOOTER}, got ${footerMessageType}`
            );
            return false;
        }

        const footerFrameNumber = Number(dataView.getBigInt64(
            offset + PAYLOAD_FOOTER_LAYOUT.FRAME_NUMBER.offset,
            true
        ));

        const footerNumCameras = dataView.getInt32(
            offset + PAYLOAD_FOOTER_LAYOUT.NUM_CAMERAS.offset,
            true
        );

        logBinaryFrameVerbose(`🔬 BinaryFrameParser: Footer data:`, {
            frameNumber: footerFrameNumber,
            numCameras: footerNumCameras
        });

        if (footerFrameNumber !== header.frameNumber || footerNumCameras !== header.numCameras) {
            console.error(
                `❌ BinaryFrameParser: Footer mismatch! Header: ${header.frameNumber}/${header.numCameras}, ` +
                `Footer: ${footerFrameNumber}/${footerNumCameras}`
            );
            return false;
        }

        logBinaryFrameVerbose('✅ BinaryFrameParser: Footer verification passed');
        return true;
    }

    /**
     * Get protocol information for debugging
     */
    getProtocolInfo() {
        return {
            sizes: PROTOCOL_SIZES,
            layouts: {
                payloadHeader: PAYLOAD_HEADER_LAYOUT,
                frameHeader: FRAME_HEADER_LAYOUT,
                payloadFooter: PAYLOAD_FOOTER_LAYOUT,
            },
            messageTypes: MessageType,
            stats: this.parseStats,
        };
    }

    /**
     * Get current parse statistics
     */
    getStats() {
        return { ...this.parseStats };
    }
}
