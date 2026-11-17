import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

onnx_router = APIRouter(prefix="/onnx", tags=["ONNX"])


class ExecutionProviderDevice(BaseModel):
    key: str
    name: str | None
    vram_total_bytes: int | None


class ExecutionProviderOption(BaseModel):
    key: str
    label: str
    description: str
    usable: bool
    install_hint: str | None
    uses_gpu: bool
    devices: list[ExecutionProviderDevice]


class ExecutionProviderOffer(BaseModel):
    """An offer of skellytracker's Auto recommendation for this host, as `InstallOffer` gives it."""
    kind: str
    ep_key: str | None
    download_bytes: int | None
    disk_bytes: int | None
    licence_url: str | None
    note: str | None


class AvailableExecutionProvidersResponse(BaseModel):
    providers: list[ExecutionProviderOption]
    detector_takes_execution_provider: dict[str, bool]
    auto_offers: list[ExecutionProviderOffer]


@onnx_router.get("/execution_providers")
def get_available_execution_providers() -> AvailableExecutionProvidersResponse:
    """Each EP of this host as skellytracker gives it, in its order, whether each detector takes an EP, and the offers
    of skellytracker's Auto recommendation (install a pack, update a driver).

    The run checks its EP again when it starts."""
    try:
        from freemocap.core.tracking.execution_providers import execution_provider_status
        from freemocap.core.tracking.pipeline_runs import PIPELINE_KEYS, detector_takes_execution_provider
        status = execution_provider_status()
        return AvailableExecutionProvidersResponse(
            providers=[ExecutionProviderOption(
                key=row.key, label=row.label, description=row.description, usable=row.usable,
                install_hint=row.install_hint, uses_gpu=row.uses_gpu,
                devices=[ExecutionProviderDevice(key=device.device_key, name=device.name, vram_total_bytes=device.vram_total_bytes)
                         for device in row.devices]) for row in status.eps],
            detector_takes_execution_provider={detector: detector_takes_execution_provider(detector) for detector in PIPELINE_KEYS},
            auto_offers=[ExecutionProviderOffer(kind=offer.kind, ep_key=offer.ep_key, download_bytes=offer.download_bytes,
                disk_bytes=offer.disk_bytes, licence_url=offer.licence_url, note=offer.note)
                for offer in status.performance.offers])
    except Exception as e:
        logger.exception(f"Error listing ONNX execution providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ExecutionProviderSuggestion(BaseModel):
    saved: str
    suggested: str | None


@onnx_router.get("/execution_providers/suggestion")
def get_execution_provider_suggestion(saved: str) -> ExecutionProviderSuggestion:
    """The EP key that replaces a key saved by FreeMoCap before skellytracker 2, as skellytracker suggests it on this
    host; `suggested` None means Auto."""
    from freemocap.core.tracking.execution_providers import suggested_execution_provider
    return ExecutionProviderSuggestion(saved=saved, suggested=suggested_execution_provider(saved))


@onnx_router.get("/session_providers")
def get_session_providers() -> list[dict]:
    """For each live or posthoc run, the EP the user selected and each model node as skellytracker reports it:
    key, version, sidecar_sha256, size, precision, the applied `execution_provider` and `device`. Empty models
    means the run has not started yet, or runs no model."""
    from freemocap.app.freemocap_application import get_freemocap_app
    return get_freemocap_app().inference_service.provider_status()
