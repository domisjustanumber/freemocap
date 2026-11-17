import React, {useEffect, useRef} from "react";
import {useTranslation} from "react-i18next";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import IconButton from "@/components/ui-components/IconButton";
import ButtonSm from "@/components/ui-components/ButtonSm";
import ToggleComponent from "@/components/ui-components/ToggleComponent";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {logPipelineTimesChanged} from "@/store/slices/mocap";
import {openPipelineMetricsWindow} from "@/services/electron-ipc/open-pipeline-metrics-window";

/** Pipeline actions next to the real-time processing button: the metrics window and the one saved timing setting. */
export default function RTPPipelineActionsFlyout({open, onClose}: {open: boolean; onClose: () => void}) {
    const {t} = useTranslation();
    const dispatch = useAppDispatch();
    const logPipelineTimes = useAppSelector(state => state.mocap.config.logPipelineTimes);
    const modalRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        // The gear sits outside the flyout and toggles it itself.
        const handleClickOutside = (e: MouseEvent) => {
            if (modalRef.current && !modalRef.current.parentElement?.contains(e.target as Node)) onClose();
        };
        window.addEventListener("keydown", handleKeyDown);
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            window.removeEventListener("keydown", handleKeyDown);
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div ref={modalRef} role="dialog" aria-label={t("pipelineActions")}
            className="RTP-settings-flyout pos-abs top-5 right-0 border-1 border-black elevated-sharp flex flex-col p-1 bg-dark br-2 reveal fadeIn gap-1">
            <div className="gap-1 flex flex-col right-0 p-2 bg-middark br-1 z-1">
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text={t("pipelineActions")}/>
                    <IconButton icon="close-icon" className="button sm" onClick={onClose}/>
                </div>
                <ButtonSm text={t("openPipelineMetrics")} iconClass="externallink-icon" className="secondary w-full"
                    onClick={() => { void openPipelineMetricsWindow(); onClose(); }}/>
                <ToggleComponent text={t("logPipelineTimes")} isToggled={logPipelineTimes}
                    onToggle={checked => dispatch(logPipelineTimesChanged(checked))}/>
                <p className="text sm text-gray">{t("logPipelineTimesHint")}</p>
            </div>
        </div>
    );
}
