"""The quick check of one EP on one GPU: the job in a real spawn child with a stand-in for skellytracker's `certify`,
the busy rule both ways, the `certification` field of `app_state`, the routes and F4's refused start."""
import multiprocessing
import os
import threading
import time
import types
from types import SimpleNamespace

import cbor2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.app.freemocap_application import FreemocapApplication
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.streaming.message_model import (
    AppStateMessage, CertificationPair, CertificationRun, PipelineHold, encode_message,
)
from freemocap.system.certify import quick_check
from freemocap.system.certify.quick_check import QuickCheckManager, StartRefused, status_parts

EP, DEVICE = "fake-ep", "gpu:10de:2484:0"
LABEL = "fake-ep@10de-2484-0"


# - Stand-ins for `skellytracker.certify`, run in the spawn child (module level, so the child can import them) -

def _report(result, reason=None):
    return {"checks": [{"name": f"{LABEL}:probe", "result": result, "reason": reason},
                       {"name": LABEL, "result": result, "reason": reason}], "evidence": {"reasons": []}}


def _progress(progress, done, total=5, state="running"):
    progress({"package": "skellytracker", "kind": "quick", "state": state, "step": None, "checks": [],
              "done": done, "total": total, "seconds_left": 0})


def certify_pass(level, progress, cancel, *, execution_providers, device, pipeline):
    assert (level, execution_providers, device) == ("quick", [EP], DEVICE) and pipeline is not None
    for done in range(40):  # far faster than skellytracker's 10 a second: the backend keeps only the newest
        _progress(progress, min(done, 5))
        time.sleep(0.01)
    return _report("pass")


def certify_fail(level, progress, cancel, **options):
    _progress(progress, 5, state="done")
    return _report("fail", "probe-l3-failed")


def certify_until_cancelled(level, progress, cancel, **options):
    _progress(progress, 1)
    while not cancel.is_set():
        time.sleep(0.05)
    return _report("not-run", "cancelled")


def certify_crash(level, progress, cancel, **options):
    _progress(progress, 1)
    os._exit(3)


def certify_raise(level, progress, cancel, **options):
    raise RuntimeError("C:/Users/someone/private path")


def _checks(**options):
    flag = multiprocessing.Value("b", False)
    return QuickCheckManager(global_kill_flag=flag, worker_registry=WorkerRegistry(global_kill_flag=flag,
                             worker_mode=WorkerMode.PROCESS), **options)


@pytest.fixture
def manager():
    registry = WorkerRegistry(global_kill_flag=multiprocessing.Value("b", False), worker_mode=WorkerMode.PROCESS)
    reads = []
    created = QuickCheckManager(global_kill_flag=multiprocessing.Value("b", False), worker_registry=registry,
                                read_status=lambda: reads.append(time.monotonic()) or ("host", (), None, ()))
    created.status_reads = reads
    yield created
    created.shutdown()


def _start(manager, certify, holds=()):
    manager.certify = certify
    return manager.start(pair=CertificationPair(EP, DEVICE), detector_type="rtmpose", rtmpose_model_name=None,
                         seconds_estimate=42, holds=holds if callable(holds) else lambda: holds)


def _until_ended(manager, timeout=60.0):
    runs = []
    deadline = time.monotonic() + timeout
    while manager.running and time.monotonic() < deadline:
        manager.refresh()
        runs.append(manager.run)
        time.sleep(0.5)  # the collector's period
    assert not manager.running, "the check did not end"
    return runs


def test_a_passed_check_keeps_the_newest_progress_and_rereads_the_store_at_once(manager):
    run = _start(manager, certify_pass)
    assert (run.state, run.done, run.total, run.seconds_estimate) == ("starting", 0, None, 42)
    reads_before = len(manager.status_reads)
    runs = _until_ended(manager)
    seen = [r for r in runs if r is not None]
    assert all(r.done <= 5 and r.total in (None, 5) for r in seen)
    assert len({(r.state, r.done) for r in seen}) < 40  # the child sent 40 complete states; only the newest is kept
    assert manager.last_result.result == "pass" and manager.last_result.reason is None
    assert manager.run is None
    assert len(manager.status_reads) > reads_before  # the store is read again when the check ends


def test_a_failed_check_reports_skellytrackers_reason(manager):
    _start(manager, certify_fail)
    _until_ended(manager)
    assert (manager.last_result.result, manager.last_result.reason) == ("fail", "probe-l3-failed")


def test_cancel_stops_the_check_and_its_report_says_cancelled(manager):
    _start(manager, certify_until_cancelled)
    deadline = time.monotonic() + 60
    while manager.run.done == 0 and time.monotonic() < deadline:  # the child is running certify()
        manager.refresh()
        time.sleep(0.2)
    assert manager.cancel().items == (CertificationPair(EP, DEVICE),)
    _until_ended(manager, timeout=10)
    assert (manager.last_result.result, manager.last_result.reason) == ("not-run", "cancelled")


def test_a_child_that_dies_is_a_crash_and_frees_the_slot(manager):
    _start(manager, certify_crash)
    _until_ended(manager)
    assert manager.last_result.result == "crashed" and manager.last_result.reason == "exit-code-3"
    _start(manager, certify_fail)  # the slot is free again
    _until_ended(manager)


def test_an_error_in_certify_sends_only_its_class_name(manager):
    _start(manager, certify_raise)
    _until_ended(manager)
    assert (manager.last_result.result, manager.last_result.reason) == ("error", "RuntimeError")


def test_one_check_at_a_time(manager):
    _start(manager, certify_until_cancelled)
    with pytest.raises(StartRefused) as again:
        _start(manager, certify_fail)
    assert again.value.detail["code"] == "quick-check-running"


def test_backend_shutdown_ends_the_check_and_its_process(manager):
    _start(manager, certify_until_cancelled)
    worker = manager.job.worker
    manager.shutdown()
    assert not worker.is_alive() and not manager.running and manager.run is None


# - The busy rule: no check while other work runs, and every start of work is refused while a check runs -

def test_a_check_is_refused_while_a_pipeline_runs_and_names_it(manager):
    with pytest.raises(StartRefused) as refused:
        _start(manager, certify_fail, holds=(PipelineHold("posthoc", "abc123"),))
    assert refused.value.status == 409 and refused.value.detail["code"] == "pipelines-running"
    assert refused.value.detail["gpu_held_by"] == [{"kind": "posthoc", "id": "abc123"}]
    assert not manager.running


def test_an_admitted_start_refuses_a_check_until_it_returns(manager):
    with manager.admit("sync"):
        with pytest.raises(StartRefused) as refused:
            _start(manager, certify_fail, holds=lambda: tuple(manager.claims))
        assert refused.value.detail["gpu_held_by"] == [{"kind": "sync", "id": "starting"}]
    assert manager.claims == []
    _start(manager, certify_fail, holds=lambda: tuple(manager.claims))
    _until_ended(manager)


def test_a_start_and_a_check_admitted_at_once_cannot_both_get_through(manager):
    """H2: the check has read what runs (nothing) and not yet registered when a start asks. Without the shared
    admission lock the start is admitted at once and both run."""
    read, proceed, outcomes = threading.Event(), threading.Event(), {}

    def holds():
        snapshot = tuple(manager.claims)
        read.set()
        proceed.wait(10)
        return snapshot

    def outcome(name, attempt):
        try:
            attempt()
            outcomes[name] = "admitted"
        except StartRefused as error:
            outcomes[name] = error.detail["code"]

    check = threading.Thread(target=outcome, args=("check", lambda: _start(manager, certify_until_cancelled, holds)))
    check.start()
    assert read.wait(10)
    work = threading.Thread(target=outcome, args=("sync", lambda: manager.claim("sync")))
    work.start()
    work.join(0.5)
    proceed.set()
    check.join(60)
    work.join(10)
    assert outcomes == {"check": "admitted", "sync": "quick-check-running"}
    assert manager.claims == []


def _app_with_running_check():
    checks = _checks()
    checks.job, checks.run = object(), CertificationRun(items=(CertificationPair(EP, DEVICE),), done=2, total=5)
    return SimpleNamespace(quick_checks=checks)


def _take():
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    return RecordingInfo(recording_directory="C:/recordings", recording_name="take", mic_device_index=-1)


@pytest.mark.parametrize("start, kind", [
    (lambda app: FreemocapApplication.start_recording_all(app, recording_info=_take()), "recording"),
    (lambda app: FreemocapApplication.create_or_update_realtime_pipeline(
        app, camera_configs={}, pipeline_config=RealtimePipelineConfig()), "realtime"),
    (lambda app: FreemocapApplication.create_posthoc_calibration_pipeline(
        app, recording_info=_take(), calibration_config=PosthocCalibrationPipelineConfig()), "posthoc"),
    (lambda app: FreemocapApplication.create_posthoc_mocap_pipeline(
        app, recording_info=_take(), mocap_config=PosthocMocapPipelineConfig()), "posthoc"),
])
async def test_each_pipeline_start_is_refused_while_a_check_runs(start, kind):
    with pytest.raises(StartRefused) as refused:
        await start(_app_with_running_check())
    detail = refused.value.detail
    assert refused.value.status == 409 and detail["code"] == "quick-check-running"
    assert detail["run"] == {"execution_provider": EP, "device_key": DEVICE, "done": 2, "total": 5}
    assert kind in detail["message"]


@pytest.mark.parametrize("path, body", [
    ("/realtime/apply", {"cameraConfigs": {"cam": {}}}),
    ("/mocap/recording/start", {"mocapRecordingDirectory": "C:/recordings/take", "mocapTaskConfig": {}}),
    ("/calibration/recording/calibrate", {"calibrationRecordingDirectory": "C:/recordings/take"}),
])
def test_the_start_routes_answer_the_refusal_with_its_reason(monkeypatch, path, body):
    from freemocap.api.http.calibration import calibration_router
    from freemocap.api.http.mocap import mocap_router
    from freemocap.api.http.realtime import realtime_router
    application = _app_with_running_check()
    for name in ("start_recording_all", "create_or_update_realtime_pipeline", "create_posthoc_calibration_pipeline"):
        setattr(application, name, types.MethodType(getattr(FreemocapApplication, name), application))
    application.camera_group_manager = SimpleNamespace(camera_groups={})
    app = FastAPI()
    for module in (calibration_router, mocap_router, realtime_router):
        monkeypatch.setattr(module, "get_freemocap_app", lambda: application)
        monkeypatch.setattr(module.logger, "api", lambda *args: None, raising=False)
        app.include_router(getattr(module, module.__name__.rsplit(".", 1)[1]))
    response = TestClient(app).post(path, json=body)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "quick-check-running"


def test_pipeline_holds_name_everything_that_does_work(monkeypatch):
    from freemocap.api.http.posthoc import export_jobs
    alive = SimpleNamespace(id="rt1", alive=True, camera_group_id="g2")
    dead = SimpleNamespace(id="rt0", alive=False, camera_group_id="g3")
    checks = _checks()
    checks.claims = [PipelineHold("realtime", "starting"), PipelineHold("cameras", "starting")]
    app = SimpleNamespace(
        realtime_pipeline_manager=SimpleNamespace(pipelines={"rt1": alive, "rt0": dead}),
        startup_status=SimpleNamespace(snapshot=lambda: {"status": "running", "pipeline_id": None}, task_id="startup:1"),
        posthoc_pipeline_manager=SimpleNamespace(pipelines={"ph1": SimpleNamespace(alive=True), "ph0": SimpleNamespace(alive=False)}),
        sync_job_manager=SimpleNamespace(jobs={"s1": SimpleNamespace(is_alive=True), "s0": SimpleNamespace(is_alive=False)}),
        quick_checks=checks,
    )
    exports = tuple(SimpleNamespace(task_id=f"export:{key}", status=status)
                    for key, status in (("e1", "queued"), ("e2", "running"), ("e0", "complete")))
    monkeypatch.setattr(export_jobs, "task_state", SimpleNamespace(snapshot=lambda: (3, exports)))
    cameras = {"camera_groups": {"g1": {"recording_in_progress": True}, "g2": {"recording_in_progress": False},
                                 "g3": {"recording_in_progress": False}}}
    assert FreemocapApplication.pipeline_holds(app, cameras) == (
        PipelineHold("realtime", "rt1"), PipelineHold("realtime", "startup:1"),
        PipelineHold("recording", "g1"), PipelineHold("cameras", "g3"), PipelineHold("posthoc", "ph1"),
        PipelineHold("sync", "s1"), PipelineHold("export", "e1"), PipelineHold("export", "e2"))
    checks.claims = [PipelineHold("sync", "starting")]  # a start not yet listed by its own kind
    app.sync_job_manager.jobs = {}
    assert FreemocapApplication.pipeline_holds(app, {"camera_groups": {}})[-1] == PipelineHold("sync", "starting")


def test_the_routes_that_start_other_work_refuse_while_a_check_runs_and_stop_routes_stay_open(monkeypatch):
    from fastapi import APIRouter
    from skellycam.api.http.cameras.camera_router import camera_router
    from freemocap.api.http.blender.blender_router import blender_router
    from freemocap.api.http.certify.quick_check_router import _CAMERA_STARTS, camera_starts_admitted
    from freemocap.api.http.mocap.mocap_router import mocap_router
    from freemocap.api.http.posthoc.exports_router import exports_router
    from freemocap.api.http.recording_import.import_router import import_router
    from freemocap.api.http.recordings.exports_router import recording_exports_router
    application = _app_with_running_check()
    monkeypatch.setattr("freemocap.app.freemocap_application.get_freemocap_app", lambda: application)
    # Stand-ins at skellycam's paths, gated as app.py gates skellycam's router; the real paths are checked here too.
    real_paths = {route.path for route in camera_router.routes}
    assert all(any(path.endswith(start) for path in real_paths) for start in _CAMERA_STARTS)
    cameras = APIRouter(prefix="/camera")
    for path in ("/group/apply", "/group/all/record/start", "/group/close/all", "/group/all/pause"):
        cameras.add_api_route(path, lambda: "ran", methods=["POST"])
    app = FastAPI()
    for router in (mocap_router, import_router, recording_exports_router, exports_router, blender_router):
        app.include_router(router)
    app.include_router(cameras, prefix="/skellycam", dependencies=[camera_starts_admitted])
    client = TestClient(app)
    videos = {"videoPaths": ["C:/videos/a.mp4"]}
    for path, body, kind in (
        ("/mocap/recording/synchronize", videos, "sync"), ("/recording-import/synchronize", videos, "sync"),
        ("/recordings/take/exports", {"kind": "channels"}, "export"),
        ("/exports/scientific", {"recording_path": "C:/recordings/take"}, "export"),
        ("/exports/tall-csv", {"recording_path": "C:/recordings/take"}, "export"),
        ("/blender/export", {"recordingFolderPath": "C:/recordings/take"}, "export"),
        ("/skellycam/camera/group/apply", None, "cameras"),
        ("/skellycam/camera/group/all/record/start", None, "recording"),
    ):
        response = client.post(path, json=body)
        assert response.status_code == 409, (path, response.text)
        detail = response.json()["detail"]
        assert detail["code"] == "quick-check-running" and kind in detail["message"], path
    for path in ("/skellycam/camera/group/close/all", "/skellycam/camera/group/all/pause"):
        assert client.post(path).json() == "ran"
    assert client.post("/exports/jobs/nope/cancel").status_code == 404  # a cancel is never refused
    assert application.quick_checks.claims == []


# - The `certification` field -

def _status():
    check = lambda key, **facts: SimpleNamespace(device_key=key, name="GPU " + key, **{
        "certified": False, "local_result": None, "local_cause": None, "usable": False, **facts})
    rows = (
        SimpleNamespace(key=EP, label="Fake EP", reason_code=None, reason=None,
                        checks=(check(DEVICE, certified=True, usable=True),)),
        SimpleNamespace(key="other-ep", label="Other EP", reason_code="quick-check-failed", reason="its last quick check failed",
                        checks=(check(DEVICE, local_result="failed", local_cause="unclean-exits"),)),
        SimpleNamespace(key="cpu-like", label="CPU", reason_code=None, reason=None, checks=()),
    )
    performance = SimpleNamespace(chosen=SimpleNamespace(ep_key=EP, device_key=DEVICE), skipped=(
        SimpleNamespace(ep_key="new-ep", device_key=DEVICE, needs_check=True),
        SimpleNamespace(ep_key="other-ep", device_key=DEVICE, needs_check=False)))
    return SimpleNamespace(eps=rows, performance=performance, host=SimpleNamespace(os_label="Windows 11", os_name="Windows"))


def test_the_certification_field_is_facts_only_and_decodes_on_its_own():
    checks = _checks(read_status=lambda: status_parts(_status(), [{"report_id": "r1", "has_failure": True}]))
    assert checks.snapshot(()) is None  # nothing is claimed before the first status read
    checks.refresh()
    checks.job, checks.run = object(), CertificationRun(items=(CertificationPair(EP, DEVICE),), done=1, total=5,
                                                        seconds_estimate=30)
    snapshot = checks.snapshot((PipelineHold("recording", "g1"),))
    message = cbor2.loads(encode_message(AppStateMessage.from_state_dict(server_pid=7, state={"certification": snapshot})))
    certification = message["state"]["certification"]
    assert certification["host"]["os"] == "Windows 11"
    assert certification["run"] == {"level": "quick", "items": [{"execution_provider": EP, "device_key": DEVICE}],
                                    "state": "starting", "done": 1, "total": 5, "seconds_estimate": 30}
    assert certification["items"] == [
        {"execution_provider": EP, "label": "Fake EP", "device_key": DEVICE, "device_name": "GPU " + DEVICE,
         "certified": True, "usable": True},
        {"execution_provider": "other-ep", "label": "Other EP", "device_key": DEVICE, "device_name": "GPU " + DEVICE,
         "certified": False, "local_result": "failed", "local_cause": "unclean-exits", "usable": False,
         "reason_code": "quick-check-failed", "reason": "its last quick check failed"}]
    assert certification["auto"] == {"execution_provider": EP, "device_key": DEVICE,
                                     "needs_check": [{"execution_provider": "new-ep", "device_key": DEVICE}]}
    assert certification["gpu_held_by"] == [{"kind": "recording", "id": "g1"}]
    assert certification["pending_reports"] == [{"report_id": "r1", "has_failure": True}]
    assert "install_hint" not in str(certification) and "last_result" not in certification


def test_an_app_state_without_certification_still_encodes():
    message = cbor2.loads(encode_message(AppStateMessage.from_state_dict(server_pid=7, state={})))
    assert "certification" not in message["state"]


# - Routes -

@pytest.fixture
def route_client(monkeypatch):
    import skellytracker
    from freemocap.api.http.certify import quick_check_router as module
    started = []
    checks = _checks()

    def start(**kwargs):
        if checks.run is not None:
            raise StartRefused(409, {"code": "quick-check-running", "message": "running"})
        if kwargs["holds"]():
            raise StartRefused(409, {"code": "pipelines-running", "message": "busy",
                                     "gpu_held_by": [{"kind": h.kind, "id": h.id} for h in kwargs["holds"]()]})
        started.append(kwargs)
        checks.job, checks.run = object(), CertificationRun(items=(kwargs["pair"],), seconds_estimate=kwargs["seconds_estimate"])
        return checks.run

    application = SimpleNamespace(holds=(), quick_checks=SimpleNamespace(start=start, cancel=lambda: checks.run))
    application.pipeline_holds = lambda: application.holds
    monkeypatch.setattr("freemocap.app.freemocap_application.get_freemocap_app", lambda: application)
    plans = {"not_run": {}}

    def certify_plan(level, *, execution_providers, device):
        from skellytracker.core.errors import EpRequestError
        if execution_providers != [EP]:
            raise EpRequestError(f"{execution_providers[0]!r} is not an EP of the catalog")
        return {"seconds_estimate": 30, "downloads": [],
                "details": {"checks": [LABEL], "execution_providers": [EP], "not_run": plans["not_run"]}}

    monkeypatch.setattr(skellytracker, "certify_plan", certify_plan)
    app = FastAPI()
    app.include_router(module.quick_check_router)
    return TestClient(app), application, started, plans


def test_routes_plan_start_refuse_and_cancel(route_client):
    client, application, started, plans = route_client
    body = {"execution_provider": EP, "device_key": DEVICE}
    plan = client.get("/certify/quick_check/plan", params=body).json()
    assert plan == {"seconds_estimate": 30, "downloads": [], "checks": [LABEL], "not_run": {}}
    assert client.get("/certify/quick_check/plan", params={**body, "execution_provider": "nope"}).json()["detail"]["code"] \
        == "unknown-ep-or-device"
    assert client.delete("/certify/quick_check").json() == {"run": None}

    application.holds = (PipelineHold("realtime", "rt1"),)
    busy = client.post("/certify/quick_check", json=body)
    assert busy.status_code == 409 and busy.json()["detail"]["gpu_held_by"] == [{"kind": "realtime", "id": "rt1"}]
    application.holds = ()

    plans["not_run"] = {LABEL: "ep-not-installed"}
    refused = client.post("/certify/quick_check", json=body)
    assert refused.status_code == 409 and refused.json()["detail"]["reason_code"] == "ep-not-installed"
    plans["not_run"] = {}

    accepted = client.post("/certify/quick_check", json=body)
    assert accepted.status_code == 202
    assert accepted.json() == {"level": "quick", "items": [{"execution_provider": EP, "device_key": DEVICE}],
                               "state": "starting", "done": 0, "total": None, "seconds_estimate": 30}
    assert started[0]["detector_type"] == "rtmpose" and started[0]["rtmpose_model_name"] == "rtmw-x-l_256x192"
    assert client.post("/certify/quick_check", json=body).json()["detail"]["code"] == "quick-check-running"
    assert client.delete("/certify/quick_check").json()["run"]["items"] == [{"execution_provider": EP, "device_key": DEVICE}]


# - F4: a chosen EP and GPU that skellytracker refuses fails the start with the facts the UI needs -

def _refusing_eps(monkeypatch):
    from skellytracker.core import eps
    from skellytracker.core.errors import EpUnavailableError

    def check_start(execution_provider, ep_options=None, device=None):
        raise EpUnavailableError(f"The EP '{execution_provider}' cannot run on 'GPU': no quick check passed.",
                                 "Run `skellytracker-eps certify KEY --quick`.")

    row = SimpleNamespace(key=EP, reason_code="quick-check-needed", checks=(SimpleNamespace(
        device_key=DEVICE, certified=False, local_result=None, local_cause=None, usable=False),))
    monkeypatch.setattr(eps, "check_start", check_start)
    monkeypatch.setattr(eps, "status", lambda: SimpleNamespace(eps=(row,)))


def test_a_refused_ep_and_gpu_carries_the_ep_device_and_reason_code(monkeypatch):
    _refusing_eps(monkeypatch)
    quick_check.refuse_unavailable_execution_provider(None, None)  # Auto runs only what can start
    with pytest.raises(StartRefused) as refused:
        quick_check.refuse_unavailable_execution_provider(EP, DEVICE)
    assert refused.value.detail == {
        "code": "execution-provider-unavailable",
        "message": f"The EP '{EP}' cannot run on 'GPU': no quick check passed.",
        "execution_provider": EP, "device_key": DEVICE, "reason_code": "quick-check-needed",
        "check": {"certified": False, "local_result": None, "local_cause": None, "usable": False}}
    assert "skellytracker-eps" not in str(refused.value.detail)  # the CLI hint stays out of the UI


async def test_the_realtime_and_posthoc_starts_refuse_a_saved_ep_that_skellytracker_refuses(monkeypatch):
    _refusing_eps(monkeypatch)
    app = SimpleNamespace(quick_checks=_checks())
    app._create_or_update_realtime_pipeline = types.MethodType(FreemocapApplication._create_or_update_realtime_pipeline, app)
    realtime = RealtimePipelineConfig()
    realtime.skeleton_inference_node_config.execution_provider = EP
    realtime.skeleton_inference_node_config.execution_device = DEVICE
    with pytest.raises(StartRefused) as refused:
        await FreemocapApplication.create_or_update_realtime_pipeline(app, camera_configs={}, pipeline_config=realtime)
    assert refused.value.detail["execution_provider"] == EP
    posthoc = PosthocMocapPipelineConfig(execution_provider=EP, execution_device=DEVICE)
    with pytest.raises(StartRefused) as refused:
        await FreemocapApplication.create_posthoc_mocap_pipeline(app, recording_info=_take(), mocap_config=posthoc)
    assert refused.value.detail["device_key"] == DEVICE
