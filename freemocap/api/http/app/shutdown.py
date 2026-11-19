"""
Clean shutdown endpoint with proper async handling.
"""
import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from skellycam.core.camera_group.camera_group_manager import close_camera_groups

logger = logging.getLogger(__name__)

shutdown_router = APIRouter(tags=["App"])


@shutdown_router.post(
    "/shutdown",
    summary="Gracefully shutdown the server",
    response_model=dict[str, str]
)
async def shutdown_server(
        request: Request,
) -> JSONResponse:
    """
    Initiate graceful server shutdown.

    This endpoint triggers a graceful shutdown of the entire FreeMoCap system,
    including all camera groups and the server itself.

    Returns:
        JSON response confirming shutdown initiation
    """
    logger.info(f"Shutdown requested via API - {request.url}")
    from skellytracker import note_exit_requested
    # First act: an ordered close is then no unclean exit of a GPU EP, even if the process is killed later.
    await asyncio.to_thread(note_exit_requested)

    # The server supervisor observes this flag and runs graceful shutdown.
    await close_camera_groups()
    request.app.state.global_kill_flag.value = True
    logger.info("Requested server shutdown")
    return JSONResponse(
        content={
            "status": "shutdown_initiated",
            "message": "Server shutting down. Goodbye! 👋"
        },
        status_code=200
    )
