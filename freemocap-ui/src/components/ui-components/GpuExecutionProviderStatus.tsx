import React, {useCallback, useLayoutEffect, useRef, useState} from 'react';
import {useAppSelector} from '@/store/hooks';
import {selectDisplayedExecutionProvider, selectGpuCapabilities} from '@/store/slices/realtime';
import {executionProviderShortLabel} from '@/types/gpu-capabilities';
import GpuCapabilitiesSummary from '@/components/ui-components/GpuCapabilitiesSummary';

const VIEWPORT_PADDING_PX = 8;

export const GpuExecutionProviderStatus: React.FC = () => {
    const gpuCapabilities = useAppSelector(selectGpuCapabilities);
    const displayedProvider = useAppSelector(selectDisplayedExecutionProvider);
    const tooltipRef = useRef<HTMLDivElement>(null);
    const [isHovered, setIsHovered] = useState(false);
    const [shiftX, setShiftX] = useState(0);

    const label = executionProviderShortLabel(displayedProvider);

    const clampTooltipToViewport = useCallback(() => {
        const tooltip = tooltipRef.current;
        if (!tooltip) return;

        const rect = tooltip.getBoundingClientRect();
        let delta = 0;

        if (rect.left < VIEWPORT_PADDING_PX) {
            delta = VIEWPORT_PADDING_PX - rect.left;
        } else if (rect.right > window.innerWidth - VIEWPORT_PADDING_PX) {
            delta = window.innerWidth - VIEWPORT_PADDING_PX - rect.right;
        }

        setShiftX(delta);
    }, []);

    useLayoutEffect(() => {
        if (!isHovered) {
            setShiftX(0);
            return;
        }
        clampTooltipToViewport();
    }, [isHovered, clampTooltipToViewport, gpuCapabilities, displayedProvider, label]);

    const tooltipTransform =
        shiftX !== 0
            ? `translateX(${shiftX}px) translateY(-4px)`
            : undefined;

    return (
        <div
            className="tooltip-wrapper pos-rel flex-inline gpu-ep-status-tooltip"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            <div className="camera-config-chip flex flex-row items-center gap-1">
                <span className="icon settings-icon icon-size-16" />
                <p className="text sm text-gray text-nowrap">{label}</p>
            </div>

            <div
                ref={tooltipRef}
                className="tooltip-container elevated-sharp pos-bottom-left p-01 br-2 bg-dark"
                style={tooltipTransform ? {transform: tooltipTransform} : undefined}
            >
                <div className="tooltip-inner br-1 pl-2 pr-2 pt-1 pb-1 border-1 border-mid-black border-solid flex flex-col gap-1">
                    <GpuCapabilitiesSummary />
                </div>
            </div>
        </div>
    );
};

export default GpuExecutionProviderStatus;
