"""Structured realtime pipeline startup/runtime error payloads."""

from __future__ import annotations

from dataclasses import dataclass, field

from skellytracker.utilities.gpu_utils.ort_session_utils import OnnxExecutionProviderStartupError

from freemocap.core.types.type_overloads import PipelineIdString


@dataclass
class RealtimePipelineErrorMessage:
    """Recoverable realtime pipeline failure surfaced to the UI."""

    message_type: str = "realtime_pipeline_error"
    pipeline_id: PipelineIdString = ""
    node_kind: str = "skeleton_inference"
    requested_execution_provider: str | None = None
    expected_ort_provider: str | None = None
    active_ort_providers: list[str] = field(default_factory=list)
    active_execution_provider: str | None = None
    model_label: str | None = None
    device_id: int | None = None
    error_type: str = "execution_provider_startup"
    message: str = ""
    install_hint: str | None = None
    recoverable: bool = True
    detector_model: str | None = None
    pose_model: str | None = None
    batch_size: int | None = None

    @classmethod
    def from_ep_startup_error(
        cls,
        *,
        pipeline_id: PipelineIdString,
        error: OnnxExecutionProviderStartupError,
        node_kind: str = "skeleton_inference",
        detector_model: str | None = None,
        pose_model: str | None = None,
        batch_size: int | None = None,
    ) -> "RealtimePipelineErrorMessage":
        return cls(
            pipeline_id=pipeline_id,
            node_kind=node_kind,
            requested_execution_provider=error.requested_provider,
            expected_ort_provider=error.expected_ort_provider,
            active_ort_providers=list(error.active_ort_providers),
            model_label=error.model_label,
            device_id=error.device_id,
            error_type="execution_provider_startup",
            message=str(error),
            install_hint=error.install_hint,
            detector_model=detector_model,
            pose_model=pose_model,
            batch_size=batch_size,
        )

    @classmethod
    def from_config_error(
        cls,
        *,
        pipeline_id: PipelineIdString,
        message: str,
        node_kind: str = "skeleton_inference",
        error_type: str = "config_error",
    ) -> "RealtimePipelineErrorMessage":
        return cls(
            pipeline_id=pipeline_id,
            node_kind=node_kind,
            error_type=error_type,
            message=message,
        )
