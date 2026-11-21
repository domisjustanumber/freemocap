"""Install and remove of a Windows ML EP (F15 step 5): the job with stand-ins for skellytracker's install and remove,
the busy rule both ways, the `certification` fields, the routes, and skellytracker's real `install()` with a stand-in
for Windows ML. Nothing here installs, downloads or removes a real package."""
import multiprocessing
import threading
import time
from types import SimpleNamespace

import cbor2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.core.streaming.message_model import (
    AppStateMessage, CertificationItem, CertificationPair, CertificationRun, CertificationSnapshot, EpPackResult, PipelineHold,
    encode_message,
)
from freemocap.system.certify import ep_packs
from freemocap.system.certify.ep_packs import EpPackManager
from freemocap.system.certify.quick_check import QuickCheckManager, StartRefused

KEY = "amdgpu"


def _checks(**options) -> QuickCheckManager:
    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value("b", False), worker_mode=WorkerMode.PROCESS)
    return QuickCheckManager(global_kill_flag=multiprocessing.Value("b", False), worker_registry=registry,
                             read_status=lambda: ("host", (), None, ()), _start_needed=False, **options)


class Gate:
    """A stand-in for skellytracker's work that reports progress and ends when released or cancelled."""

    def __init__(self, result="done"):
        self.release, self.result, self.seen_cancel = threading.Event(), result, None

    def __call__(self, key, progress, cancel):
        progress(SimpleNamespace(phase="download", fraction=None))
        progress(SimpleNamespace(phase="download", fraction=0.25))
        while not (self.release.is_set() or cancel.is_set()):
            time.sleep(0.01)
        self.seen_cancel = cancel.is_set()
        return EpPackResult("install", key, "cancelled" if cancel.is_set() else self.result)


def _manager(gate=None, **work) -> EpPackManager:
    return EpPackManager(quick_checks=_checks(), work={"install": gate or Gate(), "remove": gate or Gate(), **work})


def _holds(manager, *others):
    return lambda: (*others, *manager.quick_checks.claims)


def _until_ended(manager, timeout=10.0):
    deadline = time.monotonic() + timeout
    while manager.run is not None and time.monotonic() < deadline:
        manager.refresh()
        time.sleep(0.01)
    assert manager.run is None, "the job did not end"


def test_an_install_shows_its_progress_and_on_its_end_frees_the_rule_and_rereads_the_status():
    gate = Gate()
    manager = _manager(gate)
    run = manager.start("install", KEY, _holds(manager))
    assert (run.action, run.execution_provider, run.phase) == ("install", KEY, None)
    deadline = time.monotonic() + 5
    while manager.run.fraction is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert (manager.run.phase, manager.run.fraction) == ("download", 0.25)
    assert manager.quick_checks.claims == [PipelineHold("ep-pack", KEY)]
    manager.refresh()
    assert manager.run is not None  # still running: refresh reaps only an ended job
    manager.quick_checks.refresh()
    read_at = manager.quick_checks._parts_read_at
    gate.release.set()
    _until_ended(manager)
    assert manager.last_result == EpPackResult("install", KEY, "done") and manager.quick_checks.claims == []
    manager.quick_checks.refresh()
    assert manager.quick_checks._parts_read_at > read_at  # read again at once, not after 5 s


def test_cancel_reaches_skellytrackers_cancel_and_the_end_says_cancelled():
    gate = Gate()
    manager = _manager(gate)
    manager.start("install", KEY, _holds(manager))
    assert manager.cancel().execution_provider == KEY
    _until_ended(manager)
    assert gate.seen_cancel and manager.last_result.result == "cancelled"
    assert manager.cancel() is None  # nothing runs: nothing to cancel


def test_an_error_in_the_work_gives_only_its_class_name():
    def broken(key, progress, cancel):
        raise OSError("C:/Users/someone/secret path")
    manager = _manager(install=broken)
    manager.start("install", KEY, _holds(manager))
    _until_ended(manager)
    assert manager.last_result == EpPackResult("install", KEY, "error", "OSError")


def test_an_install_is_refused_while_other_work_or_a_check_runs():
    manager = _manager()
    with pytest.raises(StartRefused) as busy:
        manager.start("install", KEY, _holds(manager, PipelineHold("cameras", "g1")))
    assert busy.value.detail["code"] == "pipelines-running"
    assert busy.value.detail["gpu_held_by"] == [{"kind": "cameras", "id": "g1"}]
    manager.quick_checks.job = object()
    manager.quick_checks.run = CertificationRun(items=(CertificationPair("other-ep", "gpu:0"),))
    with pytest.raises(StartRefused) as checking:
        manager.start("remove", KEY, _holds(manager))
    assert checking.value.detail["code"] == "quick-check-running"
    assert manager.run is None and manager.quick_checks.claims == []


def test_while_an_install_runs_every_start_a_check_and_another_install_are_refused():
    gate = Gate()
    manager = _manager(gate)
    checks = manager.quick_checks
    manager.start("install", KEY, _holds(manager))
    for kind in ("realtime", "recording", "cameras", "posthoc", "sync", "export"):
        with pytest.raises(StartRefused) as refused:
            checks.claim(kind)
        assert refused.value.detail["code"] == "ep-pack-running" and refused.value.detail["execution_provider"] == KEY
        assert kind in refused.value.detail["message"]
    with pytest.raises(StartRefused) as second:
        manager.start("remove", "migraphx", _holds(manager))
    assert second.value.detail["code"] == "ep-pack-running"
    with pytest.raises(StartRefused) as check:
        checks.start(pair=CertificationPair("other-ep", "gpu:0"), detector_type="rtmpose", rtmpose_model_name=None,
                     seconds_estimate=None, holds=_holds(manager))
    assert check.value.detail["code"] == "pipelines-running"
    assert check.value.detail["gpu_held_by"] == [{"kind": "ep-pack", "id": KEY}]
    gate.release.set()
    _until_ended(manager)
    checks.release(checks.claim("realtime"))  # admitted again once the install ended


def test_refusals_name_the_provider_pack_and_its_ep_by_name():
    """Owner, Q74: "provider pack install" and the EP's display name, never the kind `ep-pack` or the EP's key."""
    gate = Gate()
    manager = _manager(gate)
    checks = manager.quick_checks
    checks.read_status = lambda: ("host", (CertificationItem(execution_provider=KEY, label="AMD GPU", device_key="gpu:0"),),
                                  None, ())
    checks.refresh()
    manager.start("install", KEY, _holds(manager))
    with pytest.raises(StartRefused) as second:
        manager.start("install", KEY, _holds(manager))
    assert second.value.detail["message"] == ("An install or remove of the AMD GPU EP is running; the provider pack install "
                                              "start was refused. Start again when it ends.")
    with pytest.raises(StartRefused) as check:
        checks.start(pair=CertificationPair("other-ep", "gpu:0"), detector_type="rtmpose", rtmpose_model_name=None,
                     seconds_estimate=None, holds=_holds(manager))
    assert check.value.detail["message"] == ("The quick check cannot start while other work runs: the provider pack install "
                                             "or remove of AMD GPU. Stop it first.")
    gate.release.set()
    _until_ended(manager)
    with pytest.raises(StartRefused) as busy:
        manager.start("remove", KEY, _holds(manager, PipelineHold("cameras", "g1")))
    assert busy.value.detail["message"] == ("The provider pack remove of AMD GPU cannot start while other work runs: "
                                            "cameras g1. Stop it first.")


def test_shutdown_cancels_a_running_install():
    gate = Gate()
    manager = _manager(gate)
    manager.start("install", KEY, _holds(manager))
    manager.shutdown()
    assert gate.seen_cancel


# - skellytracker's results, mapped as they come -

def test_install_and_remove_results_map_skellytrackers_records(monkeypatch):
    from skellytracker.core import eps
    from skellytracker.core.eps.records import InstallPlan, InstallResult, RemoveResult
    plan = InstallPlan(windows_ml_keys=(KEY,))
    monkeypatch.setattr(eps, "plan_install", lambda keys: plan if keys == [KEY] else None)
    results = iter([InstallResult(ok=(KEY,)), InstallResult(cancelled=(KEY,)),
                    InstallResult(failed=((KEY, "failed", "The Windows ML package of the EP 'amdgpu' did not install"),))])
    monkeypatch.setattr(eps, "install", lambda given, *, progress, cancel: given is plan and next(results))
    assert [ep_packs._install(KEY, None, None) for _ in range(3)] == [
        EpPackResult("install", KEY, "done"), EpPackResult("install", KEY, "cancelled"),
        EpPackResult("install", KEY, "failed", "failed", "The Windows ML package of the EP 'amdgpu' did not install")]
    removes = iter([RemoveResult(removed=("Pkg_1.0_x64__abcdefghijklm",)), RemoveResult(was_present=True),
                    RemoveResult(failed=((None, "no-record"),)),
                    RemoveResult(failed=(("A", "package-not-removed"), ("B", "package-not-removed")))])
    monkeypatch.setattr(eps, "remove", lambda *, execution_provider: next(removes))
    assert [ep_packs._remove(KEY, None, None) for _ in range(4)] == [
        EpPackResult("remove", KEY, "done"), EpPackResult("remove", KEY, "done", "was-present"),
        EpPackResult("remove", KEY, "failed", "no-record"), EpPackResult("remove", KEY, "failed", "package-not-removed")]


def test_skellytrackers_real_install_passes_progress_and_cancel_to_windows_ml(monkeypatch):
    """skellytracker's `install()` with only `windows_ml.install` replaced: a cancel during the install is reported as
    cancelled, as a Windows ML stop is; the store is not touched."""
    from skellytracker.core import eps
    from skellytracker.core.eps import _download, installer
    started = threading.Event()

    def windows_ml_install(key, *, progress, cancel):
        progress(SimpleNamespace(phase="download", fraction=0.5))
        started.set()
        while not cancel.is_set():
            time.sleep(0.01)
        raise _download.CancelledError(key)

    monkeypatch.setattr(installer.windows_ml, "install", windows_ml_install)
    monkeypatch.setattr(eps, "plan_install", lambda keys: installer.InstallPlan(windows_ml_keys=tuple(keys)))
    manager = EpPackManager(quick_checks=_checks())
    manager.start("install", KEY, _holds(manager))
    assert started.wait(10) and manager.run.fraction == 0.5
    manager.cancel()
    _until_ended(manager)
    assert manager.last_result == EpPackResult("install", KEY, "cancelled")


# - The `certification` fields -

def test_the_pack_fields_ride_certification_and_decode_on_their_own():
    manager = _manager()
    assert manager.add_to(None) is None  # nothing is claimed before the first status read
    snapshot = manager.add_to(CertificationSnapshot())
    assert snapshot.pack_run is None and snapshot.last_pack_result is None
    manager.run = ep_packs.EpPackRun("install", KEY, "download", 0.5)
    manager.last_result = EpPackResult("remove", "migraphx", "failed", "no-record")
    message = cbor2.loads(encode_message(AppStateMessage.from_state_dict(
        server_pid=7, state={"certification": manager.add_to(CertificationSnapshot())})))
    certification = message["state"]["certification"]
    assert certification["pack_run"] == {"action": "install", "execution_provider": KEY, "phase": "download", "fraction": 0.5}
    assert certification["last_pack_result"] == {"action": "remove", "execution_provider": "migraphx", "result": "failed",
                                                 "reason": "no-record"}


# - Routes -

def _row(key=KEY, source="windows-ml", state="not_installed"):
    return SimpleNamespace(key=key, label=key.upper(), source=source, state=state)


@pytest.fixture
def route_client(monkeypatch):
    from skellytracker.core import eps
    from skellytracker.core.errors import EpUnavailableError
    from freemocap.api.http.certify import ep_pack_router as module
    rows = [_row(), _row("other-ep", "azure", "ready"), _row("migraphx", state="ready")]
    monkeypatch.setattr("freemocap.core.tracking.execution_providers.execution_provider_rows", lambda: rows)
    refused = set()

    def plan_install(keys):
        if keys[0] in refused:
            raise EpUnavailableError(f"The EP '{keys[0]}' is not available: it is in a field test.")
        return eps.InstallPlan(windows_ml_keys=tuple(keys))

    monkeypatch.setattr(eps, "plan_install", plan_install)
    gate = Gate()
    manager = _manager(gate)
    application = SimpleNamespace(ep_packs=manager, holds=())
    application.pipeline_holds = lambda: (*application.holds, *manager.quick_checks.claims)
    monkeypatch.setattr("freemocap.app.freemocap_application.get_freemocap_app", lambda: application)
    app = FastAPI()
    app.include_router(module.ep_pack_router)
    yield TestClient(app), application, rows, refused, gate
    gate.release.set()
    manager.shutdown()


def test_routes_install_remove_cancel_and_refuse(route_client):
    client, application, rows, refused, gate = route_client
    assert client.delete("/certify/ep_pack").json() == {"run": None}
    assert client.post("/certify/ep_pack/install", json={"execution_provider": "other-ep"}).json()["detail"]["code"] \
        == "not-windows-ml"
    installed = client.post("/certify/ep_pack/install", json={"execution_provider": "migraphx"})
    assert installed.status_code == 409 and installed.json()["detail"]["code"] == "cannot-install"
    refused.add(KEY)
    field_test = client.post("/certify/ep_pack/install", json={"execution_provider": KEY})
    assert field_test.status_code == 409 and "field test" in field_test.json()["detail"]["message"]
    refused.clear()
    application.holds = (PipelineHold("realtime", "rt1"),)
    busy = client.post("/certify/ep_pack/install", json={"execution_provider": KEY})
    assert busy.status_code == 409 and busy.json()["detail"]["gpu_held_by"] == [{"kind": "realtime", "id": "rt1"}]
    application.holds = ()

    accepted = client.post("/certify/ep_pack/install", json={"execution_provider": KEY})
    assert accepted.status_code == 202, accepted.text
    assert accepted.json() == {"action": "install", "execution_provider": KEY, "phase": None, "fraction": None}
    again = client.post("/certify/ep_pack/remove", json={"execution_provider": "migraphx"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "ep-pack-running"
    assert client.delete("/certify/ep_pack").json()["run"]["execution_provider"] == KEY
    _until_ended(application.ep_packs)

    removed = client.post("/certify/ep_pack/remove", json={"execution_provider": "migraphx"})
    assert removed.status_code == 202 and removed.json()["action"] == "remove"
