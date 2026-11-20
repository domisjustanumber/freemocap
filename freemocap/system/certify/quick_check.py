"""The quick check of one EP on one GPU (F9): skellytracker's `certify("quick")` in a child process, one at a time.

The child runs `certify("quick", progress, cancel, execution_providers=[key], device=device_key, pipeline=P)` with P the
user's detector pipeline. Progress comes back through a queue, cancel is a `multiprocessing.Event`, and the latest
complete progress message is the job state (decision 9). A check is refused while anything that does work runs
(pipelines, recording, cameras, sync and export jobs), and every such start is refused while a check runs (F7, decision
20, H1); both sides check and register under one lock (H2). Nothing is queued (F8).

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
from collections.abc import Callable
from contextlib import contextmanager
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
    StartCheckResult,
)

logger = logging.getLogger(__name__)

STATUS_REFRESH_SECONDS = 5.0  # the store can also change outside a check (a CLI check, an install, unclean exits)
CANCEL_GRACE_SECONDS = 5.0  # a set cancel stops certify()'s own child within about a second, then it writes its report
# The starts refused while the start check is required (claim kinds), with their words in the refusal.
START_CHECK_GATED = {"cameras": "cameras", "realtime": "processing", "posthoc": "processing"}


class StartRefused(Exception):
    """A refused start, of a check or of a pipeline. `status` is the HTTP status, `detail` the self-describing body."""

    def __init__(self, status: int, detail: dict) -> None:
        super().__init__(detail["message"])
        self.status = status
        self.detail = detail


def refuse_unavailable_execution_provider(execution_provider: str | None, device_key: str | None) -> None:
    """F4: refuse a run start on a chosen EP and GPU that skellytracker refuses (`EpUnavailableError`), with the EP key,
    the device key of the refused GPU, its reason code and its check facts, so the UI can offer the quick check. Auto
    (None) is not checked here: it runs only what can start. Nothing switches to CPU.

    A refusal of the check rule names the GPU, also when no device was chosen; `reason_code` is that GPU's
    (`DeviceCheck.reason_code`: the check rule's code, or the EP state's, e.g. `not-installed`), else the EP row's. An
    unknown key is left to the run, as before.
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
        device_key = error.device_key or device_key
        row = next((row for row in eps.status().eps if row.key == execution_provider), None)
        check = next((check for check in row.checks if check.device_key == device_key), None) if row else None
        raise StartRefused(409, {
            "code": "execution-provider-unavailable", "message": error.message,
            "execution_provider": execution_provider, "device_key": device_key,
            "reason_code": error.reason_code or (check.reason_code if check else row.reason_code if row else None),
            "check": None if check is None else {"certified": check.certified, "local_result": check.local_result,
                                                 "local_cause": check.local_cause, "usable": check.usable}}) from None


def _what(pair: CertificationPair | None, items: tuple[CertificationItem, ...] = ()) -> str:
    """The check in words: the EP and GPU by skellytracker's labels when its status has the pair, else by their keys."""
    if pair is None:
        return "the start check"
    item = next((item for item in items
                 if (item.execution_provider, item.device_key) == (pair.execution_provider, pair.device_key)), None)
    return (f"the quick check of {item.label if item else pair.execution_provider} on "
            f"{item and item.device_name or pair.device_key}")


def _report_result(report: dict) -> tuple[str, str | None]:
    """The EP check's result and reason: the one check whose name has no `:` (decision 9's reader rule)."""
    row = next((row for row in report.get("checks", ()) if ":" not in str(row.get("name"))), None)
    if row is None:
        reasons = (report.get("evidence") or {}).get("reasons") or [None]
        return "not-run", reasons[0]
    return str(row.get("result")), row.get("reason")


@dataclass
class QuickCheckJob(BaseNode):
    pair: CertificationPair | None = None  # None: the start check of every package (start_check.py)
    progress_subscription: multiprocessing.queues.Queue | None = None
    result_subscription: multiprocessing.queues.Queue | None = None
    cancel: multiprocessing.synchronize.Event | None = None
    progress_received: int = 0

    @classmethod
    def create(cls, *, pair: CertificationPair | None, detector_type: str, rtmpose_model_name: str | None,
               worker_registry: WorkerRegistry, global_kill_flag: Synchronized, certify=None, own_certify=None,
               ui_remote: bool | None = None, blender_exe_path: str | None = None) -> "QuickCheckJob":
        """`certify` and `own_certify` replace `skellytracker.certify` and freemocap's own in the child (module-level
        functions, for tests)."""
        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag, heartbeat_timestamp=worker_registry.heartbeat_timestamp)
        progress_queue: multiprocessing.queues.Queue = multiprocessing.Queue()
        result_queue: multiprocessing.queues.Queue = multiprocessing.Queue()
        cancel = multiprocessing.Event()
        # shortcut: the app's default start method (spawn on Windows and macOS, as decision 9 asks); Linux forks
        # until skellycam's ManagedProcess takes a context.
        shutdown_self_flag, worker = cls._create_worker(
            owner_shutdown_flag=ipc.pipeline_shutdown_flag, worker_mode=WorkerMode.PROCESS, target=cls._run,
            name=f"QuickCheck-{ipc.pipeline_id}", worker_registry=worker_registry, log_queue=ipc.ws_queue, daemon=False,
            kwargs=dict(ipc=ipc, execution_provider=pair and pair.execution_provider, device_key=pair and pair.device_key,
                        detector_type=detector_type, rtmpose_model_name=rtmpose_model_name,
                        progress_pub=progress_queue, result_pub=result_queue, cancel=cancel, certify=certify,
                        own_certify=own_certify, ui_remote=ui_remote, blender_exe_path=blender_exe_path))
        return cls(shutdown_self_flag=shutdown_self_flag, worker=worker, pair=pair, progress_subscription=progress_queue,
                   result_subscription=result_queue, cancel=cancel)

    @staticmethod
    def _run(*, ipc: PipelineIPC, execution_provider: str | None, device_key: str | None, detector_type: str,
             rtmpose_model_name: str | None, progress_pub, result_pub, cancel, shutdown_self_flag: Synchronized,
             certify=None, own_certify=None, ui_remote: bool | None = None, blender_exe_path: str | None = None) -> None:
        def watch() -> None:  # a stop, or the backend's exit or death, sets the cancel that certify() polls
            parent = multiprocessing.parent_process()
            # Poll, never `cancel.wait()`: a process that dies while waiting on a multiprocessing.Event makes the next
            # `set()` block forever (its Condition waits for the dead waiter to wake).
            while not cancel.is_set():
                if shutdown_self_flag.value or not ipc.should_continue or (parent is not None and not parent.is_alive()):
                    cancel.set()
                time.sleep(0.2)

        threading.Thread(target=watch, name="QuickCheckWatch", daemon=True).start()
        try:
            if execution_provider is None:
                from freemocap.system.certify.start_check import run_start_check
                result_pub.put(run_start_check(progress_pub.put, cancel, ui_remote=ui_remote, blender_exe_path=blender_exe_path,
                                               own_certify=own_certify,
                                               certify=certify))
                return
            if certify is None:
                from skellytracker import certify
            from freemocap.core.tracking.pipeline_runs import load_detector_pipeline
            report = certify("quick", progress_pub.put, cancel, execution_providers=[execution_provider],
                             device=device_key, pipeline=load_detector_pipeline(detector_type, rtmpose_model_name))
            result_pub.put(_report_result(report))
        except Exception as error:  # noqa: BLE001 - the class name only: an error text can hold a path
            logger.exception("The quick check of %s on %s raised", execution_provider or "every package", device_key)
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

    def poll_result(self) -> tuple | None:  # (result, reason), or ("start", per-package rows)
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
    """The parts of the `certification` field that come from skellytracker's `eps.status()` and the hand-in list."""
    host = CertificationHost(name=socket.gethostname(), os=status.host.os_label or status.host.os_name)
    items = tuple(CertificationItem(execution_provider=row.key, label=row.label, device_key=check.device_key,
                                    device_name=check.name, certified=check.certified, local_result=check.local_result,
                                    local_cause=check.local_cause, usable=check.usable, reason_code=check.reason_code,
                                    reason=row.reason)
                  for row in status.eps for check in row.checks)
    performance = status.performance
    auto = CertificationAuto(execution_provider=performance.chosen.ep_key, device_key=performance.chosen.device_key,
                             needs_check=tuple(CertificationPair(c.ep_key, c.device_key)
                                               for c in performance.skipped if c.needs_check))
    reports = tuple(PendingReport(report_id=row["report_id"], has_failure=bool(row["has_failure"])) for row in pending)
    return host, items, auto, reports


def read_status_parts():
    from freemocap.core.tracking.execution_providers import execution_provider_status
    from freemocap.system.certify.relay import hand_in_reports
    return status_parts(execution_provider_status(), hand_in_reports())  # freemocap's and skellytracker's


@dataclass
class QuickCheckManager:
    """At most one quick check, its state and the cached skellytracker status for the `certification` field."""
    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    lock: threading.Lock = field(default_factory=threading.Lock)
    # H2: the check's admission and every other start check and register under this lock, held only for that step.
    # A threading lock: the check starts in a thread-pool route, the other starts on the event loop or in threads.
    admission_lock: threading.Lock = field(default_factory=threading.Lock)
    claims: list[PipelineHold] = field(default_factory=list)  # starts admitted and not yet returned
    job: QuickCheckJob | None = None
    run: CertificationRun | None = None
    last_result: CertificationResult | None = None
    read_status: object = read_status_parts
    certify: object = None  # tests only: a module-level stand-in for `skellytracker.certify`
    own_certify: object = None  # tests only: a module-level stand-in for freemocap's own `certify`
    start_results: tuple[StartCheckResult, ...] = ()  # how the last start check of this server session ended
    start_released: bool = False  # a start check ended other than by a cancel in this server session (decision 14)
    read_start_needed: object = None  # tests: a stand-in for `start_check.start_check_needed`
    _start_needed: bool = False
    _parts: tuple | None = None
    _parts_read_at: float = 0.0

    @property
    def running(self) -> bool:
        return self.job is not None

    @property
    def start_required(self) -> bool:
        return self._start_needed and not self.start_released

    def refuse_pipeline_start(self, kind: str) -> None:
        """F7, H1: a start of work is refused while a check runs, and a camera or pipeline start while the start check is
        required. The refusal is this request's answer, not a stored gate."""
        if kind in START_CHECK_GATED and self.start_required:
            raise StartRefused(409, {
                "code": "start-check-required",
                "message": f"FreeMoCap must finish its system checks before {START_CHECK_GATED[kind]} can start."})
        run = self.run
        if run is not None:
            item = run.items[0] if run.items else None
            raise StartRefused(409, {
                "code": "quick-check-running",
                "message": f"{self.describe(item)} is running; the {kind} start was refused. Start again when the "
                           "check ends.",
                "run": {"execution_provider": item and item.execution_provider, "device_key": item and item.device_key,
                        "done": run.done, "total": run.total}})
        for hold in self.claims:  # an EP pack install or remove refuses every start too (F16, H1); see ep_packs.py
            if hold.kind == "ep-pack":
                raise StartRefused(409, {
                    "code": "ep-pack-running", "execution_provider": hold.id,
                    "message": f"An install or remove of the {hold.id} EP is running; the {kind} start was refused. "
                               "Start again when it ends."})

    def describe(self, pair: CertificationPair | None) -> str:
        """`_what` with the labels of the cached status, capitalised for the start of a sentence."""
        text = _what(pair, self._parts[1] if self._parts else ())
        return text[0].upper() + text[1:]  # not str.capitalize(): it lowercases the labels

    def status_changed(self) -> None:
        """Read skellytracker's status again at the next refresh (an EP pack install or remove ended)."""
        self._parts_read_at = float("-inf")

    def claim(self, kind: str) -> PipelineHold:
        """H2: refuse while a check runs, else register a claim that a check's admission sees until `release`."""
        with self.admission_lock:
            self.refuse_pipeline_start(kind)
            claim = PipelineHold(kind, "starting")
            self.claims.append(claim)
            return claim

    def release(self, claim: PipelineHold) -> None:
        with self.admission_lock:
            self.claims.remove(claim)

    @contextmanager
    def admit(self, kind: str):
        """Run one start of work under a claim: by its end the work itself is listed by `holds`, or it failed."""
        claim = self.claim(kind)
        try:
            yield
        finally:
            self.release(claim)

    def start(self, *, pair: CertificationPair | None, detector_type: str, rtmpose_model_name: str | None,
              seconds_estimate: int | None, holds: Callable[[], tuple[PipelineHold, ...]],
              ui_remote: bool | None = None, blender_exe_path: str | None = None) -> CertificationRun:
        """`holds` lists what runs (claims included); it is read under the admission lock and must not take it.
        `pair` None starts the start check of every package."""
        with self.lock:
            with self.admission_lock:
                if self.run is not None:
                    running = self.run.items[0] if self.run.items else None
                    raise StartRefused(409, {
                        "code": "quick-check-running",
                        "message": f"{self.describe(running)} is running; the quick check start was refused. Start "
                                   "again when the check ends.",
                        "run": {"execution_provider": running and running.execution_provider,
                                "device_key": running and running.device_key}})
                held = holds()
                if held:  # the names `pipelines-running` and `gpu_held_by` are historical: they cover all work (H1)
                    raise StartRefused(409, {
                        "code": "pipelines-running",
                        "message": "A quick check cannot start while other work runs: "
                                   + ", ".join(f"{hold.kind} {hold.id}" for hold in held) + ". Stop it first.",
                        "gpu_held_by": [{"kind": hold.kind, "id": hold.id} for hold in held]})
                self.run = CertificationRun(level="quick", items=(pair,) if pair else (), seconds_estimate=seconds_estimate)
            try:  # the spawn is outside the admission lock; the run set above refuses other starts meanwhile
                job = QuickCheckJob.create(pair=pair, detector_type=detector_type, rtmpose_model_name=rtmpose_model_name,
                                           worker_registry=self.worker_registry, global_kill_flag=self.global_kill_flag,
                                           certify=self.certify, own_certify=self.own_certify, ui_remote=ui_remote,
                                           blender_exe_path=blender_exe_path)
                job.start()
            except BaseException:
                self.run = None
                raise
            self.job = job
            logger.info("%s started", _what(pair).capitalize())
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
                                       total=message.get("total"), package=message.get("package"))
                result = job.poll_result()
                if result is None and not job.is_alive:
                    result = job.poll_result()  # a result sent just before the exit
                    if result is None:
                        result = ("crashed", f"exit-code-{job.worker.exitcode}")
                if result is not None:
                    if job.pair is not None:
                        self.last_result = CertificationResult(job.pair.execution_provider, job.pair.device_key, *result)
                    else:  # ("start", per-package results), or a crash or error of the whole child
                        self.start_results = tuple(StartCheckResult(*row) for row in result[1]) if result[0] == "start" \
                            else (StartCheckResult(None, *result),)
                        self.start_released |= all(row.reason != "cancelled" for row in self.start_results)
                    self.job, self.run, ended = None, None, True
                    logger.info("%s ended: %s (%d progress messages)", _what(job.pair).capitalize(), result,
                                job.progress_received)
        if ended:
            job.end()
        if ended or self._parts is None or time.monotonic() - self._parts_read_at >= STATUS_REFRESH_SECONDS:
            try:
                parts = self.read_status()
                from freemocap.system.certify.start_check import start_check_needed
                self._start_needed = (self.read_start_needed or start_check_needed)()
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
                                     gpu_held_by=holds, pending_reports=reports,
                                     start_required=self.start_required,
                                     start_results=self.start_results)

    def shutdown(self) -> None:
        with self.lock:
            job, self.job, self.run = self.job, None, None
        if job is not None:
            logger.info("Ending %s for the backend's exit", _what(job.pair))
            job.end()
