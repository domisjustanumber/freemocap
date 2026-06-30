"""
RealtimePipelineManager: lifecycle manager for long-lived realtime pipelines.

At most one global realtime pipeline runs at a time. Responsibilities:
  - Creating/updating the sole realtime pipeline via _apply_pipeline_config
  - Streaming aggregated frontend payloads
  - Recording orchestration (start/stop)
  - Orderly shutdown
"""
import asyncio
import logging
import multiprocessing
import multiprocessing.synchronize
from dataclasses import dataclass, field

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.abcs.pipeline_manager_abc import PipelineManagerABC
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_camera_selection import camera_ids_for_realtime_pipeline
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_error import RealtimePipelineErrorMessage
from freemocap.core.pipeline.realtime.realtime_pipeline_lifecycle import skeleton_session_config_changed
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt
from freemocap.core.viz.frontend_payload import FrontendImagePacket

logger = logging.getLogger(__name__)


@dataclass
class RealtimePipelineManager(PipelineManagerABC):
    """
    Manages the lifecycle of realtime (camera-bound) pipelines.

    Holds at most one global realtime pipeline. Starting a new session
  shuts down any existing pipeline when recreate is required.
    """

    worker_registry: WorkerRegistry
    lock: multiprocessing.synchronize.Lock = field(default_factory=multiprocessing.Lock)
    lifecycle_lock: multiprocessing.synchronize.Lock = field(default_factory=multiprocessing.Lock)
    pipelines: dict[PipelineIdString, RealtimePipeline] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Pipeline CRUD
    # ------------------------------------------------------------------

    def create_pipeline(
        self,
        *,
        camera_group: CameraGroup,
        pipeline_config: RealtimePipelineConfig,
        realtime_camera_ids: list[CameraIdString] | None = None,
    ) -> RealtimePipeline:
        return self._apply_pipeline_config(
            camera_group=camera_group,
            pipeline_config=pipeline_config,
            realtime_camera_ids=realtime_camera_ids,
        )

    def update_pipeline_config(
        self,
        *,
        pipeline_id: PipelineIdString,
        new_config: RealtimePipelineConfig,
    ) -> RealtimePipeline:
        with self.lock:
            pipeline = self.pipelines[pipeline_id]
            camera_group = pipeline.camera_group
            realtime_camera_ids = list(pipeline.camera_ids)
        return self._apply_pipeline_config(
            camera_group=camera_group,
            pipeline_config=new_config,
            realtime_camera_ids=realtime_camera_ids,
        )

    def get_pipeline(self) -> RealtimePipeline | None:
        with self.lock:
            return self._get_realtime_pipeline()

    def has_active_realtime_pipeline(self) -> bool:
        """True when a sole alive pipeline is registered (realtime streaming path)."""
        with self.lock:
            pipeline = self._get_realtime_pipeline()
        return pipeline is not None and pipeline.alive

    def _get_realtime_pipeline(self) -> RealtimePipeline | None:
        if len(self.pipelines) > 1:
            logger.warning(
                "Multiple realtime pipelines detected during read; awaiting apply cleanup"
            )
            return None
        return next(iter(self.pipelines.values()), None)

    def _snapshot_and_clear_duplicate_pipelines(
        self,
    ) -> tuple[RealtimePipeline | None, list[RealtimePipeline]]:
        """Return the sole pipeline, or remove legacy duplicates and return them for shutdown."""
        if not self.pipelines:
            return None, []
        if len(self.pipelines) == 1:
            return next(iter(self.pipelines.values())), []
        logger.warning(
            "Multiple realtime pipelines (%d) — shutting down all",
            len(self.pipelines),
        )
        duplicates = list(self.pipelines.values())
        self.pipelines.clear()
        return None, duplicates

    def _apply_pipeline_config(
        self,
        *,
        camera_group: CameraGroup,
        pipeline_config: RealtimePipelineConfig,
        realtime_camera_ids: list[CameraIdString] | None = None,
    ) -> RealtimePipeline:
        """Apply realtime pipeline. Caller must ensure len(resolved cameras) >= 1."""
        with self.lifecycle_lock:
            ordered_ids = camera_ids_for_realtime_pipeline(camera_group, realtime_camera_ids)
            desired_cameras = set(ordered_ids)
            if len(desired_cameras) < 1:
                raise ValueError("At least one realtime camera is required")

            with self.lock:
                existing, duplicates = self._snapshot_and_clear_duplicate_pipelines()

            for duplicate in duplicates:
                duplicate.shutdown()

            needs_recreate = (
                existing is None
                or not existing.alive
                or existing.camera_group_id != camera_group.id
                or set(existing.camera_ids) != desired_cameras
                or skeleton_session_config_changed(existing.config, pipeline_config)
            )

            if needs_recreate:
                with self.lock:
                    if existing is not None and existing.id in self.pipelines:
                        del self.pipelines[existing.id]
                if existing is not None:
                    existing.shutdown()

                pipeline = RealtimePipeline.create(
                    pipeline_config=pipeline_config,
                    camera_group=camera_group,
                    worker_registry=self.worker_registry,
                    realtime_camera_ids=realtime_camera_ids,
                )
                pipeline.start()
                with self.lock:
                    self.pipelines.clear()
                    self.pipelines[pipeline.id] = pipeline
                logger.info(
                    f"Created RealtimePipeline [{pipeline.id}] "
                    f"for camera group [{pipeline.camera_group_id}]"
                )
                return pipeline

            existing.update_config(pipeline_config)
            logger.info(
                f"Updated RealtimePipeline [{existing.id}] config via pubsub"
            )
            return existing

    # ------------------------------------------------------------------
    # Frontend payload streaming
    # ------------------------------------------------------------------

    async def wait_for_any_result_ready(self, timeout: float = 0.5) -> None:
        """Wait until at least one active pipeline has a processed frame ready."""
        with self.lock:
            alive = [p for p in self.pipelines.values() if p.alive]
        if not alive:
            await asyncio.sleep(0.01)
            return
        tasks = [asyncio.create_task(p.wait_for_result_ready(timeout)) for p in alive]
        _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()

    def get_latest_frontend_payloads(
            self,
            if_newer_than: FrameNumberInt,
    ) -> list[FrontendImagePacket]:
        with self.lock:
            pipeline = self._get_realtime_pipeline()
        if pipeline is None:
            return []
        packet = pipeline.get_latest_frontend_payload(if_newer_than=if_newer_than)
        if packet is not None:
            return [packet]
        return []

    def get_realtime_error_updates(self) -> list[RealtimePipelineErrorMessage]:
        with self.lock:
            pipeline = self._get_realtime_pipeline()
        if pipeline is None:
            return []
        return pipeline.drain_pipeline_errors()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def pause_unpause_all(self) -> None:
        with self.lock:
            pipeline = self._get_realtime_pipeline()
        if pipeline is not None:
            pipeline.camera_group.pause_unpause()

    def shutdown(self) -> None:
        with self.lifecycle_lock:
            with self.lock:
                snapshot = list(self.pipelines.values())
                self.pipelines.clear()
            for pipeline in snapshot:
                pipeline.shutdown()
        logger.info("RealtimePipelineManager: all pipelines shut down")
