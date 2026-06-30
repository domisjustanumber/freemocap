import logging

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from skellycam.core.camera_group.camera_group import CameraConfigs
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.api.http.realtime.realtime_messages import REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE
from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.realtime.realtime_camera_selection import camera_ids_for_realtime_pipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline

logger = logging.getLogger(__name__)

realtime_router = APIRouter(prefix="/realtime", tags=["Realtime Processing Pipeline"])


class RealtimePipelineConnectRequest(BaseModel):
    camera_configs: CameraConfigs|None = Field(default=None,
                                               alias="cameraConfigs",
                                               description="Camera configurations for the CameraGroup we're attaching a pipeline to. If None, use existing camera group (or throw if no camera group connected)")
    realtime_camera_ids: list[CameraIdString] | None = Field(
        default=None,
        alias="realtimeCameraIds",
        description="Subset of camera IDs to attach to pipeline nodes. Desktop UI always sends an explicit array. If None, all cameras in the group are used.",
    )
    realtime_config: RealtimePipelineConfig = Field(
        default_factory=RealtimePipelineConfig,
        description="Configuration for the realtime processing pipeline",
        alias="realtimeConfig",
        examples=[RealtimePipelineConfig()],
    )

class RealtimePipelineCreateResponse(BaseModel):
    pipeline_id: str = Field(
        description="ID of the processing pipeline",
    )
    execution_provider: str | None = Field(
        default=None,
        description="ONNX execution provider from skeleton_inference_node_config",
    )

    @classmethod
    def from_pipeline(
        cls,
        pipeline: RealtimePipeline,
        *,
        pipeline_config: RealtimePipelineConfig | None = None,
    ) -> "RealtimePipelineCreateResponse":
        cfg = pipeline_config or pipeline.config
        requested = cfg.skeleton_inference_node_config.execution_provider
        return cls(
            pipeline_id=pipeline.id,
            execution_provider=requested,
        )

class RealtimePipelineCloseResponse(BaseModel):
    success: bool
    message: str | None = None

class RealtimePipelineUpdateRequest(BaseModel):
    config: RealtimePipelineConfig = Field(default_factory=RealtimePipelineConfig, examples=[RealtimePipelineConfig()])


@realtime_router.post(
    "/apply",
    summary="Create/update a processing pipeline and attach it to a camera group",
)
async def pipeline_apply_endpoint(
    request: RealtimePipelineConnectRequest = Body(
        description="Configuration for the realtime processing pipeline",
        examples=[
            RealtimePipelineConnectRequest(),
        ],
    ),
) -> RealtimePipelineCreateResponse:
    logger.api(f"Received `realtime/apply` POST request - \n {request.model_dump_json(indent=2)}")
    app = get_freemocap_app()
    if request.camera_configs is None:
        camera_groups = app.camera_group_manager.camera_groups
        if len(camera_groups) == 0:
            raise HTTPException(
                status_code=500,
                detail="No camera groups currently connected - must provide camera configs to create a new camera group and attach a pipeline",
            )
        elif len(camera_groups) > 1:
            raise HTTPException(
                status_code=501,
                detail="Multiple camera groups not yet supported",
            )
        camera_configs = next(iter(camera_groups.values())).configs
    else:
        camera_configs = request.camera_configs

    if camera_configs is None or len(camera_configs) == 0:
        raise HTTPException(
            status_code=500,
            detail="No valid camera configs found in request or current server state",
        )

    camera_group = await app.camera_group_manager.create_or_update_camera_group(
        camera_configs=camera_configs,
    )
    resolved_ids = camera_ids_for_realtime_pipeline(
        camera_group, request.realtime_camera_ids
    )
    if len(resolved_ids) == 0:
        raise HTTPException(
            status_code=422,
            detail=REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE,
        )

    try:
        pipeline = app.realtime_pipeline_manager.create_pipeline(
            camera_group=camera_group,
            pipeline_config=request.realtime_config,
            realtime_camera_ids=request.realtime_camera_ids,
        )
        response = RealtimePipelineCreateResponse.from_pipeline(
            pipeline=pipeline,
            pipeline_config=request.realtime_config,
        )
        logger.api(f"`pipeline/connect` POST request handled successfully - \n {response.model_dump_json(indent=2)}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}",
        )


@realtime_router.delete(
    "/all/close",
    summary="Disconnect/shutdown all processing pipelines",
)
async def pipeline_close_endpoint() -> None:
    logger.api("Received `pipeline/close` DELETE request")
    try:
        get_freemocap_app().close_pipelines()
        logger.api("`pipeline/close` DELETE request handled successfully")
    except Exception as e:
        logger.error(f"Error when processing `pipeline/close` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Error when processing `pipeline/close` request: {type(e).__name__} - {e}",
        )
