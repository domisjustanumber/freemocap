"""Install and remove of a Windows ML EP (F15 step 5, F16): skellytracker's `eps.install` and `eps.remove`, one at a time.

The work runs in a thread of the backend: `install()` takes a progress callback and a cancel with `is_set()`, and both
calls run Windows' own installer, so no child process of freemocap is needed. Its progress and its end ride
`certification.pack_run` and `certification.last_pack_result` of `app_state`, as the quick check's do.

Busy rule (F16, H1): a start is admitted under the quick check's admission lock only while nothing runs, and the job
holds a claim of kind `ep-pack` until it ends, so `pipeline_holds()` lists it (a check is refused) and every other
start is refused with `ep-pack-running`. Nothing is queued.
"""
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from freemocap.core.streaming.message_model import CertificationSnapshot, EpPackResult, EpPackRun, PipelineHold
from freemocap.system.certify.quick_check import QuickCheckManager, StartRefused

logger = logging.getLogger(__name__)

EP_PACK_KIND = "ep-pack"
SHUTDOWN_GRACE_SECONDS = 5.0


def _install(key: str, progress, cancel) -> EpPackResult:
    from skellytracker.core import eps
    result = eps.install(eps.plan_install([key]), progress=progress, cancel=cancel)
    if key in result.ok:
        return EpPackResult("install", key, "done")
    if key in result.cancelled:
        return EpPackResult("install", key, "cancelled")
    failure = next((row for row in result.failed if row[0] == key), (key, "failed", None))
    return EpPackResult("install", key, "failed", failure[1], failure[2])


def _remove(key: str, progress, cancel) -> EpPackResult:
    from skellytracker.core import eps
    result = eps.remove(execution_provider=key)  # skellytracker's remove takes no cancel
    if result.failed:
        return EpPackResult("remove", key, "failed", ", ".join(dict.fromkeys(code for _, code in result.failed)))
    return EpPackResult("remove", key, "done", "was-present" if result.was_present else None)


def windows_ml_row(key: str):
    """skellytracker's status row of a Windows ML EP of this host, or None for any other key."""
    from freemocap.core.tracking.execution_providers import execution_provider_rows
    return next((row for row in execution_provider_rows() if row.key == key and row.source == "windows-ml"), None)


@dataclass
class EpPackManager:
    quick_checks: QuickCheckManager
    run: EpPackRun | None = None
    last_result: EpPackResult | None = None
    work: dict = field(default_factory=lambda: {"install": _install, "remove": _remove})  # tests replace these
    _claim: PipelineHold | None = None
    _cancel: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None
    _ended: EpPackResult | None = None

    def start(self, action: str, key: str, holds: Callable[[], tuple[PipelineHold, ...]]) -> EpPackRun:
        """`holds` lists what runs (claims included); it is read under the admission lock and must not take it."""
        checks = self.quick_checks
        with checks.admission_lock:
            checks.refuse_pipeline_start(f"provider pack {action}")  # a check, or another install or remove, runs
            held = holds()
            if held:  # `pipelines-running` and `gpu_held_by` are the historical names of any work (H1)
                raise StartRefused(409, {
                    "code": "pipelines-running",
                    "message": f"The provider pack {action} of {checks.ep_name(key)} cannot start while other work "
                               f"runs: {checks.held_text(held)}. Stop it first.",
                    "gpu_held_by": [{"kind": hold.kind, "id": hold.id} for hold in held]})
            self._claim = PipelineHold(EP_PACK_KIND, key)
            checks.claims.append(self._claim)
            run = self.run = EpPackRun(action, key)
            self._ended, self._cancel = None, threading.Event()
        self._thread = threading.Thread(target=self._work, args=(action, key, self._cancel), name=f"EpPack-{action}",
                                        daemon=True)
        try:
            self._thread.start()
        except BaseException:
            self._ended = EpPackResult(action, key, "error", "thread-not-started")
            self.refresh()
            raise
        logger.info("EP pack %s of %s started", action, key)
        return run

    def _work(self, action: str, key: str, cancel: threading.Event) -> None:
        def progress(event) -> None:
            if self.run is not None:
                self.run = replace(self.run, phase=event.phase, fraction=event.fraction)
        try:
            ended = self.work[action](key, progress, cancel)
        except Exception as error:  # noqa: BLE001 - the class name only: an error text can hold a path
            logger.exception("The EP pack %s of %s raised", action, key)
            ended = EpPackResult(action, key, "error", type(error).__name__)
        self._ended = ended

    def cancel(self) -> EpPackRun | None:
        """Ask a running install to stop (Windows ML stops when it can); a remove runs to its end."""
        self._cancel.set()
        return self.run

    def refresh(self) -> None:
        """Reap an ended job: keep how it ended, free the busy rule and have the status read again at once."""
        ended = self._ended
        if ended is None or self.run is None:
            return
        logger.info("EP pack %s of %s ended: %s %s", ended.action, ended.execution_provider, ended.result, ended.reason)
        with self.quick_checks.admission_lock:
            self.last_result, self.run, self._ended = ended, None, None
            if self._claim in self.quick_checks.claims:
                self.quick_checks.claims.remove(self._claim)
        self.quick_checks.status_changed()

    def add_to(self, snapshot: CertificationSnapshot | None) -> CertificationSnapshot | None:
        if snapshot is None:
            return None
        return replace(snapshot, pack_run=self.run, last_pack_result=self.last_result)

    def shutdown(self) -> None:
        """Cancel a running install and wait a little; a Windows install stopped by the exit leaves skellytracker's
        `pending` record, which Remove clears later."""
        self._cancel.set()
        if self._thread is not None:
            self._thread.join(timeout=SHUTDOWN_GRACE_SECONDS)
