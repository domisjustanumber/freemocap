"""The quick check of one EP on one GPU (F9): skellytracker's `certify("quick")` in a child process, one at a time.

The child runs `certify("quick", progress, cancel, execution_providers=[key], device=device_key, pipeline=P)` with P the
user's detector pipeline. Progress comes back through a queue, cancel is a `multiprocessing.Event`, and the latest
complete progress message is the job state (decision 9). A check is refused while any pipeline runs, and every
pipeline start is refused while a check runs (F7, decision 20); nothing is queued (F8).

The job reuses the posthoc worker machinery (`BaseNode`, `WorkerRegistry`, `PipelineIPC`), as `SyncJob` does. The
child must not be daemonic: `certify()` runs its probe and image run in `spawn` children of its own.
"""
import logging
import multiprocessing
import multiprocessing.queues
import multiprocessing.synchronize
import socket
import threading
import time
from dataclasses import dataclass, field, replace
from multiprocessing.sharedctypes import Synchronized
from queue import Empty

from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.core.pipeline.abcs.base_node_abc import BaseNode
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.streaming.message_model import (
    CertificationAuto,
    CertificationHost,
    CertificationItem,
    CertificationPair,
    CertificationResult,
    CertificationRun,
    CertificationSnapshot,
    PendingReport,
    PipelineHold,
)

logger = logging.getLogger(__name__)

STATUS_REFRESH_SECONDS = 5.0  # the store can also change outside a check (a CLI check, an install, unclean exits)
CANCEL_GRACE_SECONDS = 5.0  # a set cancel stops certify()'s own child within about a second, then it writes its report


class StartRefused(Exception):
    """A refused start, of a check or of a pipeline. `status` is the HTTP status, `detail` the self-describing body."""

    def __init__(self, status: int, detail: dict) -> None:
        super().__init__(detail["message"])
        self.status = status
        self.detail = detail


def refuse_unavailable_execution_provider(execution_provider: str | None, device_key: str | None) -> None:
    """F4: refuse a run start on a chosen EP and GPU that skellytracker refuses (`EpUnavailableError`), with the EP key,
    the device key, the EP row's reason code and the pair's check facts, so the UI can offer the quick check. Auto
    (None) is not checked here: it runs only what can start. Nothing switches to CPU.

    `reason_code` is the EP row's (`PackStatus.reason_code`); it is None when the EP can run on another GPU, and then
    `check` holds the facts of the refused GPU. An unknown key is left to the run, as before.
    """
    if execution_provider in (None, "auto"):
        return
    from skellytracker.core import eps
    from skellytracker.core.errors import EpRequestError, EpUnavailableError
    try:
        eps.check_start(execution_provider, device=device_key)
    except EpRequestError:
        return
    except EpUnavailableError as error:
        row = next((row for row in eps.status().eps if row.key == execution_provider), None)
        check = next((check for check in row.checks if check.device_key == device_key), None) if row else None
        raise StartRefused(409, {
            "code": "execution-provider-unavailable", "message": error.message,
            "execution_provider": execution_provider, "device_key": device_key,
            "reason_code": row.reason_code if row else None,
            "check": None if check is None else {"certified": check.certified, "local_result": check.local_result,
                                                 "local_cause": check.local_cause, "usable": check.usable}}) from None


def _report_result(report: dict) -> tuple[str, str | None]:
    """The EP check's result and reason: the one check whose name has no `:` (decision 9's reader rule)."""
    row = next((row for row in report.get("checks", ()) if ":" not in str(row.get("name"))), None)
    if row is None:
        reasons = (report.get("evidence") or {}).get("reasons") or [None]
        return "not-run", reasons[0]
    return str(row.get("result")), row.get("reason")


@dataclass
class QuickCheckJob(BaseNode):
    pair: CertificationPair = field(default_factory=CertificationPair)
    progress_subscription: multiprocessing.queues.Queue | None = None
    result_subscription: multiprocessing.queues.Queue | None = None
    cancel: multiprocessing.synchronize.Event | None = None
    progress_received: int = 0

    @classmethod
    def create(cls, *, pair: CertificationPair, detector_type: str, rtmpose_model_name: str | None,
               worker_registry: WorkerRegistry, global_kill_flag: Synchronized, certify=None) -> "QuickCheckJob":
        """`certify` replaces `skellytracker.certify` in the child (a module-level function, for tests)."""
        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag, heartbeat_timestamp=worker_registry.heartbeat_timestamp)
        progress_queue: multiprocessing.queues.Queue = multiprocessing.Queue()
        result_queue: multiprocessing.queues.Queue = multiprocessing.Queue()
        cancel = multiprocessing.Event()
        # shortcut: the app's default start method (spawn on Windows and macOS, as decision 9 asks); Linux forks
        # until skellycam's ManagedProcess takes a context.
        shutdown_self_flag, worker = cls._create_worker(
            owner_shutdown_flag=ipc.pipeline_shutdown_flag, worker_mode=WorkerMode.PROCESS, target=cls._run,
            name=f"QuickCheck-{ipc.pipeline_id}", worker_registry=worker_registry, log_queue=ipc.ws_queue, daemon=False,
            kwargs=dict(ipc=ipc, execution_provider=pair.execution_provider, device_key=pair.device_key,
                        detector_type=detector_type, rtmpose_model_name=rtmpose_model_name,
                        progress_pub=progress_queue, result_pub=result_queue, cancel=cancel, certify=certify))
        return cls(shutdown_self_flag=shutdown_self_flag, worker=worker, pair=pair, progress_subscription=progress_queue,
                   result_subscription=result_queue, cancel=cancel)

    @staticmethod
    def _run(*, ipc: PipelineIPC, execution_provider: str, device_key: str | None, detector_type: str,
             rtmpose_model_name: str | None, progress_pub, result_pub, cancel, shutdown_self_flag: Synchronized,
             certify=None) -> None:
        # certify() gets a threading.Event that mirrors the cross-process one: skellytracker's inner functions are
        # annotated `threading.Event` and its beartype checks refuse a multiprocessing.Event in a source run.
        local_cancel = threading.Event()

        def watch() -> None:  # a cancel, a stop, or the backend's exit or death ends certify() and its children
            parent = multiprocessing.parent_process()
            # Poll, never `cancel.wait()`: a process that dies while waiting on a multiprocessing.Event makes the next
            # `set()` block forever (its Condition waits for the dead waiter to wake).
            while not local_cancel.is_set():
                if (cancel.is_set() or shutdown_self_flag.value or not ipc.should_continue
                        or (parent is not None and not parent.is_alive())):
                    local_cancel.set()
                time.sleep(0.2)

        threading.Thread(target=watch, name="QuickCheckWatch", daemon=True).start()
        try:
            if certify is None:
                from skellytracker import certify
            from freemocap.core.tracking.pipeline_runs import load_detector_pipeline
            report = certify("quick", progress_pub.put, local_cancel, execution_providers=[execution_provider],
                             device=device_key, pipeline=load_detector_pipeline(detector_type, rtmpose_model_name))
            result_pub.put(_report_result(report))
        except Exception as error:  # noqa: BLE001 - the class name only: an error text can hold a path
            logger.exception("The quick check of %s on %s raised", execution_provider, device_key)
            result_pub.put(("error", type(error).__name__))

    def drain_progress(self) -> dict | None:
        """The newest of the waiting progress messages (each is the complete state), or None."""
        latest = None
        while True:
            try:
                latest = self.progress_subscription.get_nowait()
            except (Empty, OSError, ValueError):
                return latest
            self.progress_received += 1

    def poll_result(self) -> tuple[str, str | None] | None:
        try:
            return self.result_subscription.get_nowait()
        except (Empty, OSError, ValueError):
            return None

    def end(self) -> None:
        """Cancel, give certify() time to stop its own children and write its report, then end the process tree."""
        self.cancel.set()
        self.worker.join(timeout=CANCEL_GRACE_SECONDS)
        if self.worker.is_alive() and self.worker.pid is not None:
            import psutil
            try:
                parent = psutil.Process(self.worker.pid)
                for child in parent.children(recursive=True):
                    child.kill()
            except psutil.Error:
                pass
        self.shutdown()


def status_parts(status, pending: list[dict]) -> tuple[CertificationHost, tuple[CertificationItem, ...],
                                                       CertificationAuto, tuple[PendingReport, ...]]:
    """The parts of the `certification` field that come from skellytracker's `eps.status()` and hand-in list."""
    host = CertificationHost(name=socket.gethostname(), os=status.host.os_label or status.host.os_name)
    items = tuple(CertificationItem(execution_provider=row.key, label=row.label, device_key=check.device_key,
                                    device_name=check.name, certified=check.certified, local_result=check.local_result,
                                    local_cause=check.local_cause, usable=check.usable, reason_code=row.reason_code,
                                    reason=row.reason)
                  for row in status.eps for check in row.checks)
    performance = status.performance
    auto = CertificationAuto(execution_provider=performance.chosen.ep_key, device_key=performance.chosen.device_key,
                             needs_check=tuple(CertificationPair(c.ep_key, c.device_key)
                                               for c in performance.skipped if c.needs_check))
    reports = tuple(PendingReport(report_id=row["report_id"], has_failure=bool(row["has_failure"])) for row in pending)
    return host, items, auto, reports


def read_status_parts():
    import skellytracker
    from freemocap.core.tracking.execution_providers import execution_provider_status
    return status_parts(execution_provider_status(), skellytracker.pending_reports())


@dataclass
class QuickCheckManager:
    """At most one quick check, its state and the cached skellytracker status for the `certification` field."""
    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    lock: threading.Lock = field(default_factory=threading.Lock)
    job: QuickCheckJob | None = None
    run: CertificationRun | None = None
    last_result: CertificationResult | None = None
    read_status: object = read_status_parts
    certify: object = None  # tests only: a module-level stand-in for `skellytracker.certify`
    _parts: tuple | None = None
    _parts_read_at: float = 0.0

    @property
    def running(self) -> bool:
        return self.job is not None

    def refuse_pipeline_start(self, kind: str) -> None:
        """F7: a pipeline start is refused while a check runs. The refusal is this request's answer, not a stored gate."""
        run = self.run
        if run is not None:
            item = run.items[0]
            raise StartRefused(409, {
                "code": "quick-check-running",
                "message": f"A quick check of {item.execution_provider} on {item.device_key} is running; the {kind} start "
                           "was refused. Start again when the check ends.",
                "run": {"execution_provider": item.execution_provider, "device_key": item.device_key,
                        "done": run.done, "total": run.total}})

    def start(self, *, pair: CertificationPair, detector_type: str, rtmpose_model_name: str | None,
              seconds_estimate: int | None, holds: tuple[PipelineHold, ...]) -> CertificationRun:
        with self.lock:
            if self.job is not None:
                running = self.run.items[0]
                raise StartRefused(409, {
                    "code": "quick-check-running",
                    "message": f"A quick check of {running.execution_provider} on {running.device_key} is already running.",
                    "run": {"execution_provider": running.execution_provider, "device_key": running.device_key}})
            if holds:
                raise StartRefused(409, {
                    "code": "pipelines-running",
                    "message": "A quick check cannot start while a pipeline runs: "
                               + ", ".join(f"{hold.kind} {hold.id}" for hold in holds) + ". Stop it first.",
                    "gpu_held_by": [{"kind": hold.kind, "id": hold.id} for hold in holds]})
            job = QuickCheckJob.create(pair=pair, detector_type=detector_type, rtmpose_model_name=rtmpose_model_name,
                                       worker_registry=self.worker_registry, global_kill_flag=self.global_kill_flag,
                                       certify=self.certify)
            job.start()
            self.job = job
            self.run = CertificationRun(level="quick", items=(pair,), seconds_estimate=seconds_estimate)
            logger.info("Quick check of %s on %s started", pair.execution_provider, pair.device_key)
            return self.run

    def cancel(self) -> CertificationRun | None:
        """Ask the running check to stop; it ends within about a second and its report says `cancelled`."""
        with self.lock:
            if self.job is not None:
                self.job.cancel.set()
            return self.run

    def refresh(self) -> None:
        """Take the newest progress, reap an ended check, and re-read the store after a check and every few seconds."""
        ended = False
        with self.lock:
            job = self.job
            if job is not None:
                message = job.drain_progress()
                if message is not None:
                    self.run = replace(self.run, state=str(message.get("state")), done=int(message.get("done", 0)),
                                       total=message.get("total"))
                result = job.poll_result()
                if result is None and not job.is_alive:
                    result = job.poll_result()  # a result sent just before the exit
                    if result is None:
                        result = ("crashed", f"exit-code-{job.worker.exitcode}")
                if result is not None:
                    self.last_result = CertificationResult(job.pair.execution_provider, job.pair.device_key, *result)
                    self.job, self.run, ended = None, None, True
                    logger.info("Quick check of %s on %s ended: %s %s (%d progress messages)", job.pair.execution_provider,
                                job.pair.device_key, *result, job.progress_received)
        if ended:
            job.end()
        if ended or self._parts is None or time.monotonic() - self._parts_read_at >= STATUS_REFRESH_SECONDS:
            try:
                parts = self.read_status()
            except Exception:  # noqa: BLE001 - the last good status stays; a broken store must not stop progress
                logger.exception("skellytracker's EP status could not be read for the certification state")
            else:
                self._parts, self._parts_read_at = parts, time.monotonic()

    def snapshot(self, holds: tuple[PipelineHold, ...]) -> CertificationSnapshot | None:
        parts = self._parts
        if parts is None:
            return None
        host, items, auto, reports = parts
        return CertificationSnapshot(host=host, run=self.run, last_result=self.last_result, items=items, auto=auto,
                                     gpu_held_by=holds, pending_reports=reports)

    def shutdown(self) -> None:
        with self.lock:
            job, self.job, self.run = self.job, None, None
        if job is not None:
            logger.info("Ending the quick check of %s on %s for the backend's exit", job.pair.execution_provider,
                        job.pair.device_key)
            job.end()
