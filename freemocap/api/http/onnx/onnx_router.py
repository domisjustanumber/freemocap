import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

onnx_router = APIRouter(prefix="/onnx", tags=["ONNX"])


class ExecutionProviderOption(BaseModel):
    key: str
    label: str


class AvailableExecutionProvidersResponse(BaseModel):
    available: list[ExecutionProviderOption]


@onnx_router.get("/execution_providers")
def get_available_execution_providers() -> AvailableExecutionProvidersResponse:
    """The key and label of each EP usable on this host, in skellytracker's order; the run checks its EP again when it starts."""
    try:
        from freemocap.core.tracking.execution_providers import usable_execution_provider_rows
        return AvailableExecutionProvidersResponse(available=[
            ExecutionProviderOption(key=row.key, label=row.label) for row in usable_execution_provider_rows()])
    except Exception as e:
        logger.exception(f"Error listing ONNX execution providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@onnx_router.get("/session_providers")
def get_session_providers() -> list[dict]:
    """Actual loaded providers for shared live/post-hoc sessions; empty models means pending startup.

    Per-camera process sessions report the same diagnostics in their startup logs.
    """
    from freemocap.app.freemocap_application import get_freemocap_app
    return get_freemocap_app().inference_service.provider_status()
