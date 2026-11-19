"""
Consolidated FastAPI app factory with proper lifecycle management.
"""
import logging
import asyncio
import multiprocessing
import sys
from contextlib import asynccontextmanager, suppress
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path
from typing import AsyncGenerator

import skellycam
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.camera_group.camera_group_manager import close_camera_groups
from starlette.responses import FileResponse

import freemocap
from freemocap.api.middleware.add_middleware import add_middleware
from freemocap.api.middleware.cors import cors
from freemocap.api.routers import SKELLYCAM_ROUTERS, FREEMOCAP_ROUTERS, APP_ROUTERS
from freemocap.api.server_constants import PROTOCOL, HOSTNAME
from freemocap.api.websocket.websocket_connect import websocket_router
from freemocap.app.freemocap_application import create_freemocap_app, get_freemocap_app
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.skeletons.tracked_skeleton_set import build_tracked_skeletons
from freemocap.system.default_paths import (
    get_default_freemocap_base_folder_path, FREEMOCAP_FAVICON_ICO_PATH
)
from freemocap.system.certify.relay import start_outbox_retry
from freemocap.system.telemetry.telemetry import initialize_telemetry, shutdown_telemetry

logger = logging.getLogger(__name__)


HOST_FIELDS = ("os_platform", "arch", "cpu_name", "cpu_physical_cores", "cpu_logical_cores", "cpu_max_frequency_hz",
               "memory_total_bytes")
GPU_FIELDS = ("name", "vendor", "vram_total_bytes", "driver_version")


def _field_lines(record, fields: tuple[str, ...], indent: str) -> list[str]:
    """The fields the record has, as skellytracker gives them."""
    values = {name: getattr(record, name, None) for name in fields}
    units = {"_bytes": lambda value: f"{value / 2**30:.1f} GiB", "_hz": lambda value: f"{value / 1e9:.2f} GHz"}
    return [f"{indent}{name}: {next((form(value) for end, form in units.items() if name.endswith(end)), value)}"
            for name, value in values.items() if value is not None]


def _log_system_info() -> None:
    def _pkg_ver(name: str) -> str:
        try:
            mod = __import__(name)
            return mod.__version__
        except Exception:
            return "n/a"

    skelly_pkgs = {
        "skellycam": _pkg_ver("skellycam"),
        "skellytracker": _pkg_ver("skellytracker"),
        "skellyforge": _pkg_ver("skellyforge"),
        "skellylogs": _pkg_ver("skellylogs"),
        "skellypings": _pkg_ver("skellypings"),
        "freemocap_blender_addon": _pkg_ver("freemocap_blender_addon"),
    }
    lines = ["", "  System info:", f"    Python:      {sys.version}", f"    FreeMoCap:   {freemocap.__version__}"]
    try:
        from skellytracker.core.eps import status
        from skellytracker.core.system import probe_host
        host = probe_host()
        lines += ["    Host:", *_field_lines(host, HOST_FIELDS, "      ")]
        for index, gpu in enumerate(host.gpus):
            lines += [f"    GPU {index}:", *_field_lines(gpu, GPU_FIELDS, "      ")]
        lines += [f"    Host probe error: {error}" for error in host.probe_errors]
        ep_status = status()
        lines += ["    Execution providers:", *(f"      {pack.key}: {pack.state}" for pack in ep_status.eps)]
        chosen = ep_status.performance.chosen
        lines.append(f"      performance recommendation: {chosen.ep_key}"
                     f"{f' on {chosen.device_key}' if chosen.device_key else ''}, {ep_status.performance.precision}")
    except Exception:  # the log of the host must not stop the server
        logger.exception("The host and execution provider status of skellytracker could not be read")
    lines += ["    Skelly Packages:", *(f"      {k}={v}" for k, v in skelly_pkgs.items())]
    logger.info("\n".join(lines))


async def collect_task_progress(app: FastAPI) -> None:
    """Collect worker state even when no client is connected."""
    try:
        while not app.state.global_kill_flag.value:
            await asyncio.to_thread(get_freemocap_app().posthoc_pipeline_manager.refresh_progress)
            await asyncio.to_thread(get_freemocap_app().sync_job_manager.refresh_progress)
            await asyncio.sleep(0.5)
    except Exception as error:
        app.state.fatal_error = error
        app.state.global_kill_flag.value = True
        raise


@asynccontextmanager
async def app_lifespan(
        app: FastAPI
) -> AsyncGenerator[None, None]:
    """
    Manage the application lifecycle.
    All startup and shutdown logic goes here.
    """
    try:
        # ===== STARTUP =====
        logger.api("FreeMoCap API starting...")
        # Required stream resources must be usable before accepting connections.
        build_tracked_skeletons(camera_node_config=CameraNodeConfig())
        _log_system_info()

        # Ensure base folder exists
        base_path = Path(get_default_freemocap_base_folder_path())
        base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Base folder: {base_path}")

        # Start anonymous usage telemetry (no-op if the user opted out)
        initialize_telemetry()

        # Send again each certify report kept after a failed hand-in (on its own thread)
        start_outbox_retry()

        app_url = f"{PROTOCOL}://{HOSTNAME}:{app.state.port}"

        logger.success(
            f"FreeMoCap API {freemocap.__version__} started successfully 💀✨\n"
            f"Swagger API docs: {app_url}/docs"
        )
        collector = asyncio.create_task(collect_task_progress(app), name="PosthocProgressCollector")
        try:
            yield
        finally:
            collector.cancel()
            with suppress(asyncio.CancelledError):
                await collector
            await get_freemocap_app().streaming_outputs.aclose()
    except Exception as error:
        app.state.fatal_error = error
        raise
    finally:
        logger.api("FreeMoCap API shutting down...")
        try:
            try:
                await close_camera_groups()
            finally:
                app.state.global_kill_flag.value = True
                try:
                    get_freemocap_app().close()
                finally:
                    shutdown_telemetry()
        except Exception as error:
            if app.state.fatal_error is None:
                app.state.fatal_error = error
            raise
        logger.info("FreeMoCap API shutdown complete")


def create_fastapi_app(
        *,
        global_kill_flag: Synchronized,
        worker_registry: WorkerRegistry,
        port: int,
) -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(lifespan=app_lifespan)

    app.state.global_kill_flag = global_kill_flag
    app.state.fatal_error = None
    app.state.worker_registry = worker_registry
    app.state.port = port
    create_freemocap_app(fastapi_app=app)
    cors(app)
    _register_routes(app)
    add_middleware(app)
    _customize_openapi(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all application routes."""

    # Root redirect
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/docs")

    # Favicon
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(FREEMOCAP_FAVICON_ICO_PATH)

    logger.api(f"\nRegistering WebSocket routes:")
    app.include_router(websocket_router)
    for route in websocket_router.routes:
        logger.api(f"\tRegistered WebSocket route: {route.path}")

    # Health, shutdown, and settings state routes (no prefix)
    for router in APP_ROUTERS:
        app.include_router(router)
        logger.api(f"Registered app router: {router.prefix or '/'}")

    for router in FREEMOCAP_ROUTERS:
        app.include_router(router, prefix=f"/{freemocap.__package_name__}")
        logger.api(f"Registered FreeMoCap router: /{freemocap.__package_name__}{router.prefix}")

    for router in SKELLYCAM_ROUTERS:
        app.include_router(router, prefix=f"/{skellycam.__package_name__}")
        logger.api(f"Registered SkellyCam router: /{skellycam.__package_name__}{router.prefix}")


def _customize_openapi(app: FastAPI) -> None:
    """Customize the OpenAPI schema."""
    from freemocap.api.openapi_tags import OPENAPI_TAGS

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title="FreeMoCap API 💀✨",
            version=freemocap.__version__,
            description=(
                f"FastAPI Backend for FreeMoCap: {freemocap.__description__}"
            ),
            routes=app.routes,
            tags=OPENAPI_TAGS,
        )

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
