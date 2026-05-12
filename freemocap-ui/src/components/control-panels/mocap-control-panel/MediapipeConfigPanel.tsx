import React, {useCallback, useMemo} from "react";
import {
    Box,
    Chip,
    Divider,
    FormControl,
    FormControlLabel,
    InputLabel,
    MenuItem,
    Select,
    Slider,
    Stack,
    Switch,
    Typography,
    useTheme,
} from "@mui/material";
import {useMocap} from "@/hooks/useMocap";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {store} from "@/store";
import {applyRealtimePipeline} from "@/store/slices/realtime/realtime-thunks";
import {
    MEDIAPIPE_POSTHOC_PRESET,
    MEDIAPIPE_REALTIME_PRESET,
    MediapipeDetectorConfig,
    MediapipeModelComplexity,
    mocapRealtimeDetectionSet,
    selectMocapConfig,
} from "@/store/slices/mocap";
import type {RealtimeDetectorKind, RealtimeModelSize} from "@/store/slices/realtime/realtime-types";

const MODEL_COMPLEXITY_LABELS: Record<MediapipeModelComplexity, string> = {
    0: "Lite (fastest)",
    1: "Full (balanced)",
    2: "Heavy (most accurate)",
};

type DetectorPreset = "realtime" | "posthoc" | "custom";

function detectPreset(
    config: { model_complexity: number; enable_segmentation: boolean; smooth_segmentation: boolean }
): DetectorPreset {
    if (
        config.model_complexity === 0 &&
        !config.enable_segmentation &&
        !config.smooth_segmentation
    ) return "realtime";
    if (
        config.model_complexity === 2 &&
        config.enable_segmentation &&
        config.smooth_segmentation
    ) return "posthoc";
    return "custom";
}

/** Shared slider sx that matches the camera config panel style. */
const useSliderSx = () => {
    const theme = useTheme();
    return {
        color: theme.palette.primary.light,
        "& .MuiSlider-thumb": {
            "&:hover, &.Mui-focusVisible": {
                boxShadow: `0px 0px 0px 8px ${theme.palette.primary.light}33`,
            },
        },
    } as const;
};

interface MediapipeConfigPanelProps {
    variant?: "realtime" | "posthoc";
    updateDetectorConfig?: (updates: Partial<MediapipeDetectorConfig>) => void;
    replaceDetectorConfig?: (config: MediapipeDetectorConfig) => void;
}

function compoundValue(kind: RealtimeDetectorKind, size: RealtimeModelSize): string {
    return `${kind}:${size}`;
}

function parseCompound(v: string): {kind: RealtimeDetectorKind; size: RealtimeModelSize} {
    const [kind, size] = v.split(":");
    return {
        kind: (kind === "mediapipe_js" ? "mediapipe_js" : "rtmpose") as RealtimeDetectorKind,
        size: (["lite", "full", "heavy"].includes(size) ? size : "full") as RealtimeModelSize,
    };
}

/** Title-case size for UI: lite → Lite */
function sizeTitle(size: RealtimeModelSize): string {
    return size.charAt(0).toUpperCase() + size.slice(1);
}

/** Closed select + menu rows: "RTMPose (Lite)" / "MediaPipe (Full)" */
export function realtimeDetectionModelLabel(kind: RealtimeDetectorKind, size: RealtimeModelSize): string {
    const s = sizeTitle(size);
    return kind === "mediapipe_js" ? `MediaPipe (${s})` : `RTMPose (${s})`;
}

export const MediapipeConfigPanel: React.FC<MediapipeConfigPanelProps> = ({
    variant = "posthoc",
    updateDetectorConfig: updateDetectorConfigProp,
    replaceDetectorConfig: replaceDetectorConfigProp,
}) => {
    const theme = useTheme();
    const sliderSx = useSliderSx();
    const dispatch = useAppDispatch();
    const mocapCfg = useAppSelector(selectMocapConfig);
    const {
        detectorConfig,
        updateDetectorConfig: updateDetectorConfigHook,
        replaceDetectorConfig: replaceDetectorConfigHook,
        isLoading,
    } = useMocap();
    const updateDetectorConfig = updateDetectorConfigProp ?? updateDetectorConfigHook;
    const replaceDetectorConfig = replaceDetectorConfigProp ?? replaceDetectorConfigHook;

    const currentPreset = detectPreset(detectorConfig);

    const handlePresetChange = useCallback(
        (preset: DetectorPreset) => {
            if (preset === "realtime") replaceDetectorConfig({...MEDIAPIPE_REALTIME_PRESET});
            else if (preset === "posthoc") replaceDetectorConfig({...MEDIAPIPE_POSTHOC_PRESET});
        },
        [replaceDetectorConfig]
    );

    const realtimeSelectValue = useMemo(
        () => compoundValue(mocapCfg.realtime_detector_kind, mocapCfg.realtime_model_size),
        [mocapCfg.realtime_detector_kind, mocapCfg.realtime_model_size],
    );

    const mpUiDisabled = variant === "realtime" && mocapCfg.realtime_detector_kind === "rtmpose";

    const handleRealtimeModelSelect = useCallback(
        (v: string) => {
            const {kind, size} = parseCompound(v);
            dispatch(mocapRealtimeDetectionSet({kind, size}));
            if (variant === "realtime") {
                void dispatch(applyRealtimePipeline(store.getState().realtime.pipelineConfig));
            }
        },
        [dispatch, variant]
    );

    return (
        <Stack spacing={2}>
            <Typography variant="subtitle2" sx={{color: theme.palette.text.secondary, fontWeight: 600}}>
                {variant === "realtime" ? "Realtime detection model" : "MediaPipe Detector"}
            </Typography>

            {variant === "realtime" && (
                <FormControl size="small" fullWidth>
                    <InputLabel id="realtime-detection-model-label">Realtime model</InputLabel>
                    <Select
                        labelId="realtime-detection-model-label"
                        value={realtimeSelectValue}
                        label="Realtime model"
                        onChange={(e) => handleRealtimeModelSelect(String(e.target.value))}
                        disabled={isLoading}
                        sx={{color: theme.palette.text.primary}}
                        renderValue={(v) => {
                            const {kind, size} = parseCompound(String(v));
                            return realtimeDetectionModelLabel(kind, size);
                        }}
                    >
                        <MenuItem value={compoundValue("rtmpose", "lite")}>
                            {realtimeDetectionModelLabel("rtmpose", "lite")}
                        </MenuItem>
                        <MenuItem value={compoundValue("rtmpose", "full")}>
                            {realtimeDetectionModelLabel("rtmpose", "full")}
                        </MenuItem>
                        <MenuItem value={compoundValue("rtmpose", "heavy")}>
                            {realtimeDetectionModelLabel("rtmpose", "heavy")}
                        </MenuItem>
                        <Divider component="li" sx={{my: 0.5}} />
                        <MenuItem value={compoundValue("mediapipe_js", "lite")}>
                            {realtimeDetectionModelLabel("mediapipe_js", "lite")}
                        </MenuItem>
                        <MenuItem value={compoundValue("mediapipe_js", "full")}>
                            {realtimeDetectionModelLabel("mediapipe_js", "full")}
                        </MenuItem>
                        <MenuItem value={compoundValue("mediapipe_js", "heavy")}>
                            {realtimeDetectionModelLabel("mediapipe_js", "heavy")}
                        </MenuItem>
                    </Select>
                </FormControl>
            )}

            {/* Preset selector — posthoc / mocap task context only */}
            {variant === "posthoc" && (
            <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="caption" sx={{color: theme.palette.text.secondary, minWidth: 48}}>
                    Preset
                </Typography>
                <Chip
                    label="Realtime"
                    size="small"
                    variant={currentPreset === "realtime" ? "filled" : "outlined"}
                    color={currentPreset === "realtime" ? "primary" : "default"}
                    onClick={() => handlePresetChange("realtime")}
                    disabled={isLoading}
                    sx={{cursor: "pointer"}}
                />
                <Chip
                    label="Posthoc"
                    size="small"
                    variant={currentPreset === "posthoc" ? "filled" : "outlined"}
                    color={currentPreset === "posthoc" ? "primary" : "default"}
                    onClick={() => handlePresetChange("posthoc")}
                    disabled={isLoading}
                    sx={{cursor: "pointer"}}
                />
                {currentPreset === "custom" && (
                    <Chip label="Custom" size="small" variant="outlined" color="warning" />
                )}
            </Stack>
            )}

            {/* Model complexity — posthoc only (realtime uses grouped model select) */}
            {variant === "posthoc" && (
            <FormControl size="small" fullWidth>
                <InputLabel id="model-complexity-label">Model Complexity</InputLabel>
                <Select
                    labelId="model-complexity-label"
                    value={detectorConfig.model_complexity}
                    label="Model Complexity"
                    onChange={(e) =>
                        updateDetectorConfig({
                            model_complexity: e.target.value as MediapipeModelComplexity,
                        })
                    }
                    disabled={isLoading}
                    sx={{color: theme.palette.text.primary}}
                >
                    <MenuItem value={0}>{MODEL_COMPLEXITY_LABELS[0]}</MenuItem>
                    <MenuItem value={1}>{MODEL_COMPLEXITY_LABELS[1]}</MenuItem>
                    <MenuItem value={2}>{MODEL_COMPLEXITY_LABELS[2]}</MenuItem>
                </Select>
            </FormControl>
            )}

            {/* Confidence sliders */}
            <Box>
                <Typography variant="caption" color="text.secondary">
                    Min Detection Confidence: {detectorConfig.min_detection_confidence.toFixed(2)}
                </Typography>
                <Slider
                    value={detectorConfig.min_detection_confidence}
                    onChange={(_ , value) =>
                        updateDetectorConfig({min_detection_confidence: value as number})
                    }
                    min={0} max={1} step={0.05} size="small" disabled={isLoading || mpUiDisabled}
                    sx={sliderSx}
                />
            </Box>

            <Box>
                <Typography variant="caption" color="text.secondary">
                    Min Tracking Confidence: {detectorConfig.min_tracking_confidence.toFixed(2)}
                </Typography>
                <Slider
                    value={detectorConfig.min_tracking_confidence}
                    onChange={(_, value) =>
                        updateDetectorConfig({min_tracking_confidence: value as number})
                    }
                    min={0} max={1} step={0.05} size="small" disabled={isLoading || mpUiDisabled}
                    sx={sliderSx}
                />
            </Box>

            {/* Boolean toggles */}
            <Stack spacing={0}>
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.smooth_landmarks}
                            onChange={(_, checked) =>
                                updateDetectorConfig({smooth_landmarks: checked})
                            }
                            disabled={isLoading || mpUiDisabled}
                        />
                    }
                    label={<Typography variant="body2">Smooth Landmarks</Typography>}
                />
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.enable_segmentation}
                            onChange={(_, checked) =>
                                updateDetectorConfig({enable_segmentation: checked})
                            }
                            disabled={isLoading || mpUiDisabled}
                        />
                    }
                    label={<Typography variant="body2">Enable Segmentation</Typography>}
                />
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.smooth_segmentation}
                            onChange={(_, checked) =>
                                updateDetectorConfig({smooth_segmentation: checked})
                            }
                            disabled={isLoading || mpUiDisabled || !detectorConfig.enable_segmentation}
                        />
                    }
                    label={<Typography variant="body2">Smooth Segmentation</Typography>}
                />
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.refine_face_landmarks}
                            onChange={(_, checked) =>
                                updateDetectorConfig({refine_face_landmarks: checked})
                            }
                            disabled={isLoading || mpUiDisabled}
                        />
                    }
                    label={<Typography variant="body2">Refine Face Landmarks</Typography>}
                />
                <FormControlLabel
                    control={
                        <Switch
                            size="small"
                            checked={detectorConfig.static_image_mode}
                            onChange={(_, checked) =>
                                updateDetectorConfig({static_image_mode: checked})
                            }
                            disabled={isLoading || mpUiDisabled}
                        />
                    }
                    label={<Typography variant="body2">Static Image Mode</Typography>}
                />
            </Stack>
        </Stack>
    );
};
