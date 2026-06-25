import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from freemocap.system.gpu_capabilities_cache import build_gpu_capabilities_snapshot

logger = logging.getLogger(__name__)

system_router = APIRouter(prefix="/system", tags=["System"])


class GpuCapabilitiesResponse(BaseModel):
    gpus: list[dict] = Field(default_factory=list)
    execution_providers: dict = Field(default_factory=dict)
    detection_models: list[dict] = Field(default_factory=list)
    pose_models: list[dict] = Field(default_factory=list)
    mode_defaults: dict[str, dict[str, str]] = Field(default_factory=dict)


@system_router.get(
    "/gpu",
    summary="GPU, execution provider, and RTMPose model catalog",
)
async def gpu_capabilities_endpoint() -> GpuCapabilitiesResponse:
    snapshot = build_gpu_capabilities_snapshot()
    return GpuCapabilitiesResponse(**snapshot.to_dict())
