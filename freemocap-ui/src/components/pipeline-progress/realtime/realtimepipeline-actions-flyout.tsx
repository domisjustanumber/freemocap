import React, { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import IconButton from "@/components/ui-components/IconButton";
import ButtonSm from "@/components/ui-components/ButtonSm";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { useRealtimePipelineSync } from "@/hooks/useRealtimePipelineSync";
import { openPipelineMetricsWindow } from "@/services/electron-ipc/open-pipeline-metrics-window";
import {
    closePipeline,
    pipelineErrorDismissed,
    selectCanConnectPipeline,
    selectIsPipelineConnected,
    selectPipelineError,
    selectRealtimePipelineRestartNeeded,
} from "@/store/slices/realtime";

interface RTPPipelineActionsFlyoutProps {
    open: boolean;
    onClose: () => void;
}

const RTPPipelineActionsFlyout: React.FC<RTPPipelineActionsFlyoutProps> = ({
    open,
    onClose,
}) => {
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const modalRef = useRef<HTMLDivElement>(null);
    const {
        pipelineConfig,
        applyOrUpdatePipelineConfig,
        isLoading,
        restartPipeline,
    } = useRealtimePipelineSync();
    const pipelineError = useAppSelector(selectPipelineError);
    const isConnected = useAppSelector(selectIsPipelineConnected);
    const pipelineRestartNeeded = useAppSelector(selectRealtimePipelineRestartNeeded);
    const canConnect = useAppSelector(selectCanConnectPipeline);

    const isTrtCompiling = isLoading && !isConnected;

    const logPipelineTimes = pipelineConfig.log_pipeline_times !== false;

    useEffect(() => {
        if (!open) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };

        const handleClickOutside = (e: MouseEvent) => {
            if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
                onClose();
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        document.addEventListener("mousedown", handleClickOutside);

        return () => {
            window.removeEventListener("keydown", handleKeyDown);
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [open, onClose]);

    if (!open) return null;

    const handleOpenPipelineMetrics = (): void => {
        void openPipelineMetricsWindow();
        onClose();
    };

    const handleLogPipelineTimesToggle = (checked: boolean): void => {
        applyOrUpdatePipelineConfig({
            ...pipelineConfig,
            log_pipeline_times: checked,
        });
    };

    return (
        <div
            ref={modalRef}
            className="RTP-settings-flyout pos-abs top-5 right-0 draggable border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1"
        >
            <div className="gap-1 flex flex-col right-0 p-2 bg-middark br-1 z-1">
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text={t("pipelineActions")} />
                    <IconButton icon="close-icon" className="button sm" onClick={onClose} />
                </div>

                {isTrtCompiling && !pipelineError && (
                    <div className="flex flex-col gap-1 p-1 pipeline-trt-compiling-message">
                        <p className="text sm text-wrap">
                            Initializing pipeline — first run may take 1–3 minutes for TensorRT compilation.
                        </p>
                        <ButtonSm
                            text="Cancel"
                            onClick={() => {
                                void dispatch(closePipeline());
                                onClose();
                            }}
                            className="secondary w-full"
                        />
                    </div>
                )}

                {pipelineError && (
                    <div className="flex flex-col gap-1 p-1 pipeline-error-message">
                        <p className="text sm text-error text-wrap">{pipelineError}</p>
                        <ButtonSm
                            text="Dismiss error"
                            onClick={() => dispatch(pipelineErrorDismissed())}
                            className="secondary w-full"
                        />
                        {canConnect && (
                            <ButtonSm
                                text="Retry"
                                onClick={() => {
                                    void restartPipeline();
                                    onClose();
                                }}
                                className="primary w-full"
                            />
                        )}
                    </div>
                )}

                {pipelineRestartNeeded && !pipelineError && (
                    <div className="flex flex-col gap-1 p-1 pipeline-restart-required-message">
                        <p className="text sm text-warning text-wrap">{t("realtime_restartRequired")}</p>
                        <ButtonSm
                            text="Restart pipeline"
                            onClick={() => {
                                void restartPipeline();
                                onClose();
                            }}
                            className="primary w-full"
                        />
                    </div>
                )}

                <ButtonSm
                    text={t("openPipelineMetricsWindow")}
                    iconClass="externallink-icon"
                    onClick={handleOpenPipelineMetrics}
                    className="secondary w-full"
                />

                <ToggleComponent
                    text={t("logPipelineTimes")}
                    isToggled={logPipelineTimes}
                    onToggle={handleLogPipelineTimesToggle}
                    disabled={isLoading}
                />
            </div>
        </div>
    );
};

export default RTPPipelineActionsFlyout;
