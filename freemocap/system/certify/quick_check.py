"""The quick check of one EP on one GPU (F9): skellytracker's `certify("quick")` in a child process, one at a time.

The child runs `certify("quick", progress, cancel, execution_providers=[key], device=device_key, pipeline=P)` with P the
user's detector pipeline. Progress comes back through a queue, cancel is a `multiprocessing.Event`, and the latest
complete progress message is the job state (decision 9). A check is refused while anything that does work runs
(pipelines, recording, cameras, sync and export jobs), and every such start is refused while a check runs (F7, decision
20, H1); both sides check and register under one lock (H2). Nothing is queued (F8).

The job reuses the posthoc worker machinery (`BaseNode`, `WorkerRegistry`, `PipelineIPC`), as `SyncJob` does. The
child must not be daemonic: `certify()` runs its probe and image run in `spawn` children of its own.

The full benchmark (fifth grilling, "Full benchmark") is the same job at level full: every package's `certify("full")`
in the run order (`start_check.run_full_check`), started only once the start check passed, with the same refusals, crash
record and cancel. Its progress has one row per EP and GPU (`_full_rows`) and a count of every package's finished checks.
"""
import logging
import multiprocessing
import multiprocessing.queues
import multiprocessing.synchronize
import os
import socket
import threading
import time
from collections.abc import Callable, Collection
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
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
    CertificationRunRow,
    CertificationSnapshot,
    PendingReport,
    PipelineHold,
    StartCheckResult,
)
from freemocap.system.certify import crash_record
from freemocap.system.certify.start_check import REPORTED_ONLY

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


def _full_rows(message: dict, items: tuple[CertificationItem, ...]) -> tuple[CertificationRunRow, ...]:
    """A full benchmark's progress rows from one package's progress message: for skellytracker one per EP on a GPU and one
    for the CPU, by the label before the first `:` of its check names; for freemocap one per check, its `posthoc:<label>`
    rows named by skellytracker's label of the pair; one for any other package."""
    package = str(message.get("package"))
    step = message.get("step") if message.get("state") == "running" and isinstance(message.get("step"), dict) else {}
    group = (lambda name: name.split(":")[0]) if package == "skellytracker" else (lambda name: name) \
        if package == "freemocap" else (lambda name: package)
    groups: dict[str, list[dict]] = {}
    for row in message.get("checks") or ():
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            groups.setdefault(group(row["name"]), []).append(row)
    rows = []
    for name, checks in groups.items():
        results = [check.get("result") for check in checks]
        rollup = next((check.get("result") for check in checks if check["name"] == name), None)
        pair = package == "skellytracker" or name.startswith("posthoc:")
        label = name.split(":")[-1]
        key, device_key = (label.split("@")[0], None) if pair else (None, None)
        if pair and "@" in label:
            from skellytracker.certification import check_label
            device_key = next((item.device_key for item in items
                               if item.execution_provider == key and check_label(key, item.device_key) == label), None)
        # partly-done: some of its checks ended and the rest come later in the run (the CPU's timings follow the pairs)
        state = "running" if isinstance(step.get("name"), str) and group(step["name"]) == name \
            else "done" if None not in results else "waiting" if set(results) == {None} else "partly-done"
        # a row with no roll-up check (the CPU) takes no result from its reported-only checks (owner, Q62)
        counted = [check.get("result") for check in checks if not REPORTED_ONLY.match(check["name"])] or results
        result = rollup or next((result for result in ("fail", "pass", "record-only", "not-run") if result in counted), None)
        if any(check.get("crashed") for check in checks):  # a crashed timing check fails its row, not its pair (owner: TBC)
            result = "fail"
        source = next((check for check in checks if check["name"] == name), None)             or next((check for check in checks if check.get("result") == result), {})
        rows.append(CertificationRunRow(name=name, package=package, execution_provider=key, device_key=device_key,
                                        state=state, result=result if state == "done" else None,
                                        reason=source.get("reason") if state == "done" and result == "not-run" else None))
    return tuple(rows)


def _ended(message: dict, crashed: bool, cancelled: Collection[str] = ()) -> dict:
    """A package's newest progress message as its run ended, for the final rows: each unfinished check `not-run`, and the
    running one `fail` after a crash, as the crash record has them, marked so that its row reads failed. `cancelled`: the
    checks that had not ended when a cancel was asked; those that ended `not-run` get the reason `cancelled` (progress
    messages carry no reasons)."""
    step = message.get("step") if crashed and message.get("state") == "running" else None
    step = step.get("name") if isinstance(step, dict) else None

    def end(row):
        if not isinstance(row, dict):
            return row
        if row.get("name") == step:
            return {**row, "result": "fail", "crashed": True}
        row = {**row, "result": "not-run"} if row.get("result") is None else row
        return {**row, "reason": "cancelled"} if row["result"] == "not-run" and row.get("name") in cancelled else row
    return {**message, "state": "done", "checks": [end(row) for row in message.get("checks") or ()]}


def _counted(message: dict, not_counted: frozenset[str] = frozenset()) -> tuple[int, int]:
    """(done, total) of the checks that a package's `certify_plan("full")["total"]` counts: names with at most one `:`
    (skellytracker's `<label>:jpeg:<name>` and `<check>:exit` rows are parts of one check), and none of a pair that the
    plan lists as not running (`details.not_run`, whose checks the report still lists)."""
    rows = [row for row in message.get("checks") or () if isinstance(row, dict) and isinstance(row.get("name"), str)
            and row["name"].count(":") <= 1 and row["name"].split(":")[0] not in not_counted]
    return sum(row.get("result") is not None for row in rows), len(rows)


def _report_result(report: dict) -> tuple[str, str | None]:
    """The EP check's result and reason: the one check whose name has no `:` (decision 9's reader rule)."""
    row = next((row for row in report.get("checks", ()) if ":" not in str(row.get("name"))), None)
    if row is None:
        reasons = (report.get("evidence") or {}).get("reasons") or [None]
        return "not-run", reasons[0]
    return str(row.get("result")), row.get("reason")


def _end_orphan() -> None:
    """The backend died: end now with certify()'s own children and write no report. The backend's crash record becomes
    the run's one report at the next launch; a cancel here would write a second, `cancelled` one. shortcut: what
    skellytracker's certify() undoes on a cancel (a field-test EP's opt-in during its check) stays until its `abandon`
    reaches freemocap's pin (`_abandonable`)."""
    import psutil
    try:
        for child in psutil.Process().children(recursive=True):
            child.kill()
    except psutil.Error:
        pass
    os._exit(1)


def _abandonable(certify, abandon: threading.Event, running: threading.Event):
    """`certify` given `abandon` (format 1.6.0, 2.4): while it runs, a backend's death sets `abandon` instead of ending the
    child at once, so the run stops its sessions as for a cancel and writes nothing; then the child ends."""
    def run(*args, **options):
        running.set()
        try:
            return certify(*args, abandon=abandon, **options)
        finally:
            running.clear()
            if abandon.is_set():
                _end_orphan()
    return run


@dataclass
class QuickCheckJob(BaseNode):
    pair: CertificationPair | None = None  # None: the start check of every package (start_check.py)
    progress_subscription: multiprocessing.queues.Queue | None = None
    result_subscription: multiprocessing.queues.Queue | None = None
    cancel: multiprocessing.synchronize.Event | None = None
    progress_received: int = 0
    record: dict | None = None  # the crash record's content (crash_record.py)
    level: str = "quick"
    packages: dict = field(default_factory=dict)  # level full: each package's newest progress message
    not_counted: frozenset[str] = frozenset()  # level full: the check labels that the plans list as not running
    cancelled: dict = field(default_factory=dict)  # level full: each package's checks that had not ended at the cancel

    @classmethod
    def create(cls, *, pair: CertificationPair | None, detector_type: str, rtmpose_model_name: str | None,
               worker_registry: WorkerRegistry, global_kill_flag: Synchronized, certify=None, own_certify=None,
               ui_remote: bool | None = None, blender_exe_path: str | None = None, level: str = "quick",
               remove_data: bool = False) -> "QuickCheckJob":
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
                        own_certify=own_certify, ui_remote=ui_remote, blender_exe_path=blender_exe_path, level=level,
                        remove_data=remove_data))
        return cls(shutdown_self_flag=shutdown_self_flag, worker=worker, pair=pair, progress_subscription=progress_queue,
                   result_subscription=result_queue, cancel=cancel, level=level)

    @staticmethod
    def _run(*, ipc: PipelineIPC, execution_provider: str | None, device_key: str | None, detector_type: str,
             rtmpose_model_name: str | None, progress_pub, result_pub, cancel, shutdown_self_flag: Synchronized,
             certify=None, own_certify=None, ui_remote: bool | None = None, blender_exe_path: str | None = None,
             level: str = "quick", remove_data: bool = False) -> None:
        abandon, running = threading.Event(), threading.Event()
        from freemocap.certification import certify as freemocap_certify
        own_certify = _abandonable(own_certify or freemocap_certify, abandon, running)
        if certify is None:
            from skellytracker import certify
        # skellytracker at the pin 346b77eb takes no `abandon`; at the next pin move this one line passes it:
        # certify = _abandonable(certify, abandon, running)

        def watch() -> None:  # a stop or the backend's exit sets the cancel that certify() polls; its death abandons the run
            parent = multiprocessing.parent_process()
            abandoned = None
            # Poll, never `cancel.wait()`: a process that dies while waiting on a multiprocessing.Event makes the next
            # `set()` block forever (its Condition waits for the dead waiter to wake).
            while True:
                if abandoned is None and parent is not None and not parent.is_alive():
                    abandoned = time.monotonic()
                    abandon.set()
                # a certify() that takes no `abandon` (or none running) ends at once; one that does gets the cancel's grace
                if abandoned is not None and (not running.is_set() or time.monotonic() - abandoned > CANCEL_GRACE_SECONDS):
                    _end_orphan()
                if not cancel.is_set() and (shutdown_self_flag.value or not ipc.should_continue):
                    cancel.set()
                time.sleep(0.2)

        threading.Thread(target=watch, name="QuickCheckWatch", daemon=True).start()

        def publish(result) -> None:
            # Each queue has its own feeder thread: flush every progress message (the last one says each check ended)
            # into its pipe before the result, which the backend reads first and then ends the run.
            progress_pub.close()
            progress_pub.join_thread()
            result_pub.put(result)

        try:
            if level == "full":
                from freemocap.system.certify.start_check import run_full_check
                publish(run_full_check(progress_pub.put, cancel, remove_data=remove_data,
                                       blender_exe_path=blender_exe_path, own_certify=own_certify, certify=certify))
                return
            if execution_provider is None:
                from freemocap.system.certify.start_check import run_start_check
                publish(run_start_check(progress_pub.put, cancel, ui_remote=ui_remote, blender_exe_path=blender_exe_path,
                                        own_certify=own_certify, certify=certify))
                return
            from freemocap.core.tracking.pipeline_runs import load_detector_pipeline
            report = certify("quick", progress_pub.put, cancel, execution_providers=[execution_provider],
                             device=device_key, pipeline=load_detector_pipeline(detector_type, rtmpose_model_name))
            publish(_report_result(report))
        except Exception as error:  # noqa: BLE001 - the class name only: an error text can hold a path
            logger.exception("The quick check of %s on %s raised", execution_provider or "every package", device_key)
            publish(("error", type(error).__name__))

    def drain_progress(self) -> dict | None:
        """The newest of the waiting progress messages (each is the complete state of its package), or None; at level
        full each package's newest goes to `packages`, so one package's last message is not lost to the next's first."""
        latest = None
        while True:
            try:
                latest = self.progress_subscription.get_nowait()
            except (Empty, OSError, ValueError):
                return latest
            self.progress_received += 1
            if self.level == "full":
                self.packages[latest.get("package")] = latest

    def poll_result(self) -> tuple | None:  # (result, reason), or ("start", per-package rows)
        try:
            return self.result_subscription.get_nowait()
        except (Empty, OSError, ValueError):
            return None

    def end(self) -> None:
        """Cancel, give certify() time to stop its own children and write its report, then end the process tree."""
        # A child that died while its watch thread held the Event's lock makes `set()` block forever; a dead child needs
        # no cancel. shortcut: a death between this check and `set()` can still block; a timed lock would close that gap.
        if self.worker.is_alive():
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
    full_results: tuple[StartCheckResult, ...] = ()  # how the last full benchmark of this server session ended
    full_rows: tuple[CertificationRunRow, ...] = ()  # its rows as it ended, until the next one starts
    read_start_needed: object = None  # tests: a stand-in for `start_check.start_check_needed`
    read_full_needed: object = None  # tests: a stand-in for it with `crash_skips=False`; else `read_start_needed`'s answer
    _start_needed: bool | None = None  # None until the first status read: the gated starts are refused until then
    _full_needed: bool | None = None  # the same, but a crash marker is no pass: the full benchmark's gate (owner, Q79)
    _parts: tuple | None = None
    _parts_read_at: float = 0.0

    def __post_init__(self) -> None:
        """A crash record left by the last server session: that check crashed. Its report is kept, the gated starts
        are released as after any ended start check, and nothing runs again by itself."""
        record = crash_record.read()
        if record is None:
            return
        package = crash_record.recover(record)
        crash_record.remove()
        pair = record.get("pair")
        if record.get("level") == "full":
            self.full_results = (StartCheckResult(package, "fail", "crashed"),)
        elif isinstance(pair, dict):
            self.last_result = CertificationResult(str(pair.get("execution_provider")), pair.get("device_key"), "fail",
                                                   "crashed")
        else:
            self.start_results, self.start_released = (StartCheckResult(package, "fail", "crashed"),), True
        logger.warning("A certify check of %s crashed in the last server session; its report is kept", package)

    @property
    def running(self) -> bool:
        return self.job is not None

    @property
    def start_required(self) -> bool:
        return self._start_needed is not False and not self.start_released

    def refuse_pipeline_start(self, kind: str) -> None:
        """F7, H1: a start of work is refused while a check runs, and a camera or pipeline start while the start check is
        required. The refusal is this request's answer, not a stored gate."""
        if kind in START_CHECK_GATED and self.start_required:
            raise StartRefused(409, {
                "code": "start-check-required",
                "message": "FreeMoCap is still starting; try again in a moment." if self._start_needed is None
                else f"FreeMoCap must finish its system checks before {START_CHECK_GATED[kind]} can start."})
        run = self.run
        if run is not None:
            item = run.items[0] if run.items else None
            raise StartRefused(409, {
                "code": "quick-check-running",
                "message": f"{self.describe_run(run)} is running; the {kind} start was refused. Start again when the "
                           "check ends.",
                "run": {"execution_provider": item and item.execution_provider, "device_key": item and item.device_key,
                        "done": run.done, "total": run.total}})
        for hold in self.claims:  # an EP pack install or remove refuses every start too (F16, H1); see ep_packs.py
            if hold.kind == "ep-pack":
                raise StartRefused(409, {
                    "code": "ep-pack-running", "execution_provider": hold.id,
                    "message": f"An install or remove of the {self.ep_name(hold.id)} EP is running; the {kind} start was "
                               "refused. "
                               "Start again when it ends."})

    def describe(self, pair: CertificationPair | None) -> str:
        """`_what` with the labels of the cached status, capitalised for the start of a sentence."""
        text = _what(pair, self._parts[1] if self._parts else ())
        return text[0].upper() + text[1:]  # not str.capitalize(): it lowercases the labels

    def ep_name(self, key: str) -> str:
        """An EP's name by skellytracker's label in the cached status, else its key (owner, Q74)."""
        return next((item.label for item in (self._parts[1] if self._parts else ()) if item.execution_provider == key
                     and item.label), key)

    def held_text(self, held: tuple[PipelineHold, ...]) -> str:
        """The running work in a refusal: an EP pack's by its EP's name (owner, Q74), any other by its kind and id."""
        return ", ".join(f"the provider pack install or remove of {self.ep_name(hold.id)}" if hold.kind == "ep-pack"
                         else f"{hold.kind} {hold.id}" for hold in held)

    def describe_run(self, run: CertificationRun) -> str:
        return "The full benchmark" if run.level == "full" else self.describe(run.items[0] if run.items else None)

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
              ui_remote: bool | None = None, blender_exe_path: str | None = None, level: str = "quick",
              remove_data: bool = False, not_counted: Collection[str] = ()) -> CertificationRun:
        """`holds` lists what runs (claims included); it is read under the admission lock and must not take it.
        `pair` None starts the start check of every package; `level` full the full benchmark (`pair` None), with
        `remove_data` the person's clean-up choice and `not_counted` the labels its plans list as not running."""
        what = "full benchmark" if level == "full" else "quick check"
        with self.lock:
            with self.admission_lock:
                if self.run is not None:
                    running = self.run.items[0] if self.run.items else None
                    raise StartRefused(409, {
                        "code": "quick-check-running",
                        "message": f"{self.describe_run(self.run)} is running; the {what} start was refused. Start "
                                   "again when the check ends.",
                        "run": {"execution_provider": running and running.execution_provider,
                                "device_key": running and running.device_key}})
                if level == "full" and self._full_needed is not False:  # a fact of now: a real pass is recorded (Q79)
                    raise StartRefused(409, {
                        "code": "start-check-not-passed",
                        "message": "The full benchmark can start once the start check has passed on this system."})
                held = holds()
                if held:  # the names `pipelines-running` and `gpu_held_by` are historical: they cover all work (H1)
                    raise StartRefused(409, {
                        "code": "pipelines-running",
                        "message": f"The {what} cannot start while other work runs: {self.held_text(held)}. Stop it "
                                   "first.",
                        "gpu_held_by": [{"kind": hold.kind, "id": hold.id} for hold in held]})
                self.run = CertificationRun(level=level, items=(pair,) if pair else (), seconds_estimate=seconds_estimate)
                if level == "full":
                    self.full_rows = ()
            try:  # the spawn is outside the admission lock; the run set above refuses other starts meanwhile
                job = QuickCheckJob.create(pair=pair, detector_type=detector_type, rtmpose_model_name=rtmpose_model_name,
                                           worker_registry=self.worker_registry, global_kill_flag=self.global_kill_flag,
                                           certify=self.certify, own_certify=self.own_certify, ui_remote=ui_remote,
                                           blender_exe_path=blender_exe_path, level=level, remove_data=remove_data)
                job.start()
            except BaseException:
                self.run = None
                raise
            job.record = {"level": level, "pair": asdict(pair) if pair else None,
                          "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "message": None}
            crash_record.write(job.record)
            job.not_counted = frozenset(not_counted)
            self.job = job
            logger.info("%s started", self.describe_run(self.run))
            return self.run

    def cancel(self) -> CertificationRun | None:
        """Ask the running check to stop; it ends within about a second and its report says `cancelled`."""
        with self.lock:
            if self.job is not None:
                self.job.cancel.set()
                self.job.cancelled = {package: {row.get("name") for row in message.get("checks") or ()
                                                if isinstance(row, dict) and row.get("result") is None}
                                      for package, message in self.job.packages.items()}
                self.run = replace(self.run, state="cancelling")  # the UI's lock of a full benchmark ends at once
            return self.run

    def refresh(self) -> None:
        """Take the newest progress, reap an ended check, and re-read the store after a check and every few seconds."""
        ended = False
        with self.lock:
            job = self.job
            if job is not None:
                result = job.poll_result()  # before the drain: the progress sent before the result is then taken too
                message = job.drain_progress()
                if message is not None:
                    job.record["message"] = message
                    crash_record.write(job.record)
                    done, total, rows = int(message.get("done", 0)), message.get("total"), ()
                    if job.level == "full":  # every package so far, counted as their plans count
                        counts = [_counted(package, job.not_counted) for package in job.packages.values()]
                        done, total = sum(done for done, _ in counts), sum(total for _, total in counts)
                        rows = tuple(row for package in job.packages.values()
                                     for row in _full_rows(package, self._parts[1] if self._parts else ()))
                    self.run = replace(self.run, state="cancelling" if job.cancel.is_set() else str(message.get("state")),
                                       done=done, total=total, package=message.get("package"), rows=rows)
                if result is None and not job.is_alive:
                    result = job.poll_result()  # a result sent just before the exit
                    if result is None:
                        result = ("crashed", f"exit-code-{job.worker.exitcode}")
                if result is not None:
                    if job.pair is not None:
                        self.last_result = CertificationResult(job.pair.execution_provider, job.pair.device_key, *result)
                    elif job.level == "full":  # ("full", per-package results), or a crash or error of the whole child
                        self.full_results = tuple(StartCheckResult(*row) for row in result[1]) if result[0] == "full" \
                            else (StartCheckResult(None, *result),)
                        crashed = result[0] == "crashed"  # after a crash the unfinished checks stay `not-run`
                        self.full_rows = tuple(row for name, package in job.packages.items() for row in _full_rows(
                            _ended(package, crashed, () if crashed else job.cancelled.get(name, ())),
                            self._parts[1] if self._parts else ()))
                    else:  # ("start", per-package results), or a crash or error of the whole child
                        self.start_results = tuple(StartCheckResult(*row) for row in result[1]) if result[0] == "start" \
                            else (StartCheckResult(None, *result),)
                        self.start_released |= all(row.reason != "cancelled" for row in self.start_results)
                    self.job, self.run, ended = None, None, True
                    logger.info("%s ended: %s (%d progress messages)", "The full benchmark" if job.level == "full"
                                else _what(job.pair).capitalize(), result, job.progress_received)
        if ended:
            job.end()
            if result[0] == "crashed":  # the child died: the same record as after a crash of the app
                crash_record.recover(job.record, job.worker.exitcode)
            crash_record.remove()
        if ended or self._parts is None or time.monotonic() - self._parts_read_at >= STATUS_REFRESH_SECONDS:
            try:
                parts = self.read_status()
                from freemocap.system.certify.start_check import start_check_needed
                needed = self.read_start_needed or start_check_needed
                full = self.read_full_needed or (needed if self.read_start_needed else
                                                 lambda: start_check_needed(crash_skips=False))
                self._start_needed = needed()
                self._full_needed = self._start_needed or full()
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
                                     start_results=self.start_results, full_results=self.full_results,
                                     full_rows=self.full_rows)

    def shutdown(self) -> None:
        with self.lock:
            job, self.job, self.run = self.job, None, None
        if job is not None:
            logger.info("Ending %s for the backend's exit", _what(job.pair))
            job.end()
            crash_record.remove()
