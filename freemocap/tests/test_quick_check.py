"""The quick check of one EP on one GPU: the job in a real spawn child with a stand-in for skellytracker's `certify`,
the busy rule both ways, the `certification` field of `app_state`, the routes and F4's refused start."""
import multiprocessing
import os
import time
import types
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.app.freemocap_application import FreemocapApplication
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.streaming.message_model import CertificationPair, CertificationRun, PipelineHold
from freemocap.system.certify.quick_check import QuickCheckManager, StartRefused

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
                         seconds_estimate=42, holds=holds)


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


# - The busy rule: no check while a pipeline runs, and every pipeline start is refused while a check runs -

def test_a_check_is_refused_while_a_pipeline_runs_and_names_it(manager):
    with pytest.raises(StartRefused) as refused:
        _start(manager, certify_fail, holds=(PipelineHold("posthoc", "abc123"),))
    assert refused.value.status == 409 and refused.value.detail["code"] == "pipelines-running"
    assert refused.value.detail["gpu_held_by"] == [{"kind": "posthoc", "id": "abc123"}]
    assert not manager.running


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


def test_pipeline_holds_name_every_running_pipeline():
    alive, dead = SimpleNamespace(id="rt1", alive=True), SimpleNamespace(id="rt0", alive=False)
    app = SimpleNamespace(
        realtime_pipeline_manager=SimpleNamespace(pipelines={"rt1": alive, "rt0": dead}),
        startup_status=SimpleNamespace(snapshot=lambda: {"status": "running", "pipeline_id": None}, task_id="startup:1"),
        posthoc_pipeline_manager=SimpleNamespace(pipelines={"ph1": SimpleNamespace(alive=True), "ph0": SimpleNamespace(alive=False)}),
    )
    cameras = {"camera_groups": {"g1": {"recording_in_progress": True}, "g2": {"recording_in_progress": False}}}
    assert FreemocapApplication.pipeline_holds(app, cameras) == (
        PipelineHold("realtime", "rt1"), PipelineHold("realtime", "startup:1"),
        PipelineHold("recording", "g1"), PipelineHold("posthoc", "ph1"))
