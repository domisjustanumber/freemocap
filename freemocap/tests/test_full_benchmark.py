"""The full benchmark (fifth grilling, "Full benchmark"): its plan route for the consent step, its refusal before the start
check passed, the lock of every start while it runs, a cancel that leaves an incomplete report in the share list, and its
crash record at level full. Both packages' `certify` are stand-ins: nothing is downloaded and the real level full never
runs."""
import contextlib
import multiprocessing
import os
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap import certification
from freemocap.core.streaming.message_model import CertificationHost, CertificationItem, CertificationRun, StartCheckResult
from freemocap.system.certify import crash_record
from freemocap.system.certify.quick_check import QuickCheckJob, QuickCheckManager, StartRefused, _counted, _full_rows
from freemocap.system.certify.relay import hand_in_reports, report_file_for

EP, DEVICE = "fake-ep", "gpu:10de:2484:0"
LABEL = "fake-ep@10de-2484-0"
CHECKS = ["cpu:video", "cpu:live", f"{LABEL}:probe", f"{LABEL}:video", f"{LABEL}:live", f"{LABEL}:pipeline-1",
          f"{LABEL}:jpeg", LABEL, "cpu:pipeline-1"]


def _message(step: str | None, done: int) -> dict:
    return {"package": "skellytracker", "kind": "full", "state": "running", "step": step and {"name": step},
            "checks": [{"name": name, "result": "pass" if index < done else None} for index, name in enumerate(CHECKS)],
            "done": done, "total": len(CHECKS), "seconds_left": 60}


def tracker_until_cancelled(level, progress, cancel, **options):
    """skellytracker's level full until a cancel, then its cancelled report in its own store, as `certify()` writes it."""
    assert level == "full" and set(options) == {"test_media_dir"}  # nothing overrides the package's own staging
    progress(_message(f"{LABEL}:video", 3))
    while not cancel.is_set():
        time.sleep(0.05)
    from skellytracker.core.eps.certification import reports_dir
    report = {"schema": certification.SCHEMA, "id": str(uuid.uuid4()), "kind": "full",
              "package": {"name": "skellytracker", "version": "2.0.0", "commit": None, "tree_modified": None},
              "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": certification._host(),
              "checks": [{"name": name, "result": "pass" if index < 3 else "not-run", "reason": None if index < 3 else "cancelled",
                          "module": "CPU"} for index, name in enumerate(CHECKS)],
              "cleanup": [], "evidence": {"valid": False, "reasons": ["no-commit", "cancelled"]}}
    certification._write_json(reports_dir() / f"{report['id']}.json", report)
    return report


def tracker_crash(level, progress, cancel, **options):
    import os
    progress(_message(f"{LABEL}:pipeline-1", 5))
    time.sleep(1.0)  # the backend's refresh takes the message before the child dies
    os._exit(3)


def tracker_marks_its_report(level, progress, cancel, **options):
    """skellytracker's level full until a cancel, then a mark where its cancelled report would be written."""
    progress(_message(f"{LABEL}:video", 3))
    while not cancel.is_set():
        time.sleep(0.05)
    (Path(os.environ["FREEMOCAP_BASE_FOLDER"]) / "cancelled-report").write_text("written")
    return {}


def own_stand_in(level, progress, cancel, **options):
    """freemocap's level full in the job's child: a stand-in, so that no test runs the real one (it downloads the sample)."""
    return {"checks": [], "evidence": {"reasons": []}}


def backend_that_dies(pids):
    """A backend that starts the full benchmark's child and dies while it runs."""
    from skellylogs.handlers.websocket_log_queue_handler import create_websocket_log_queue
    create_websocket_log_queue()  # as the backend does at its start
    flag = multiprocessing.Value("b", False)
    job = QuickCheckJob.create(pair=None, detector_type="rtmpose", rtmpose_model_name=None, global_kill_flag=flag,
                               worker_registry=WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.PROCESS),
                               certify=tracker_marks_its_report, own_certify=own_stand_in, level="full")
    job.start()
    job.progress_subscription.get(timeout=120)  # certify() runs
    pids.put(job.worker.pid)
    time.sleep(0.5)  # the queue's feeder hands the pid over before the exit
    os._exit(9)


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(tmp_path))  # a spawn child inherits it
    monkeypatch.setenv("FREEMOCAP_TEST_MEDIA_DIR", str(tmp_path / "test-media"))
    return tmp_path


@pytest.fixture
def failures(monkeypatch):
    calls = []
    monkeypatch.setattr(crash_record, "record_provider_failure", lambda check, created: calls.append(check))
    yield calls
    crash_record.remove()


def _manager(certify, needed=False):
    flag = multiprocessing.Value("b", False)
    items = (CertificationItem(execution_provider=EP, label="Fake EP", device_key=DEVICE, device_name="GPU 1"),)
    return QuickCheckManager(global_kill_flag=flag, worker_registry=WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.PROCESS),
                             read_status=lambda: (CertificationHost(), items, None, ()), read_start_needed=lambda: needed,
                             certify=certify, own_certify=own_stand_in)


def _start(manager, remove_data=True):
    return manager.start(pair=None, detector_type="rtmpose", rtmpose_model_name=None, seconds_estimate=333,
                         holds=lambda: (), level="full", remove_data=remove_data)


def _wait(manager, until, seconds=60):
    deadline = time.monotonic() + seconds
    while not until() and time.monotonic() < deadline:
        time.sleep(0.2)
        manager.refresh()
    assert until()


def test_the_progress_has_one_row_per_ep_and_gpu_with_its_state_and_result():
    items = (CertificationItem(execution_provider=EP, label="Fake EP", device_key=DEVICE),)
    rows = _full_rows(_message(f"{LABEL}:live", 4), items)
    assert [(row.name, row.execution_provider, row.device_key, row.state, row.result) for row in rows] == [
        ("cpu", "cpu", None, "partly-done", None), (LABEL, EP, DEVICE, "running", None)]  # the CPU's timings come later
    assert _full_rows(_message(None, 0), items)[0].state == "waiting"
    ended = {**_message(None, len(CHECKS)), "state": "done"}
    ended["checks"][3]["result"] = "fail"  # its video check failed; the EP check gives the row's result
    ended["checks"][7]["result"] = "fail"
    assert [(row.state, row.result) for row in _full_rows(ended, items)] == [("done", "pass"), ("done", "fail")]
    # freemocap's checks: a row each, its benchmark of a pair named by the pair, apart from skellytracker's by its package
    names = ["data-folder", "recording", f"posthoc:{LABEL}", "posthoc:cpu", "blender"]
    own = _full_rows({"package": "freemocap", "state": "running", "step": {"name": "posthoc:cpu"},
                      "checks": [{"name": name, "result": "pass" if index < 3 else None} for index, name in enumerate(names)]},
                     items)
    assert [(row.package, row.name, row.execution_provider, row.device_key, row.state, row.result) for row in own] == [
        ("freemocap", "data-folder", None, None, "done", "pass"), ("freemocap", "recording", None, None, "done", "pass"),
        ("freemocap", f"posthoc:{LABEL}", EP, DEVICE, "done", "pass"), ("freemocap", "posthoc:cpu", "cpu", None, "running", None),
        ("freemocap", "blender", None, None, "waiting", None)]
    assert len(own) == _counted({"checks": [{"name": name} for name in names]})[1], "a row for each counted check"


def test_the_count_of_checks_counts_what_the_plan_counts_and_never_passes_its_total():
    """skellytracker's plan counts each check of a pair that runs and the CPU's; a JPEG run adds its own checks
    `<label>:jpeg:<name>` and a child's `<check>:exit` to the report, and a pair the plan does not run is still listed."""
    other = "fake-ep@1002-73bf-0"  # a pair the plan lists in `details.not_run`
    message = _message(None, len(CHECKS))
    jpeg = message["checks"].index({"name": f"{LABEL}:jpeg", "result": "pass"}) + 1
    message["checks"][jpeg:jpeg] = [{"name": f"{LABEL}:jpeg:{part}.{index}", "result": "pass"}
                                    for part in ("cpu_decode", "gpu_decode") for index in range(33)]
    message["checks"] += [{"name": f"{LABEL}:video:exit", "result": "record-only"},
                          *({"name": name, "result": None} for name in (f"{other}:probe", f"{other}:video", other))]
    assert _counted(message, frozenset({other})) == (len(CHECKS), len(CHECKS))
    assert _counted(_message(f"{LABEL}:video", 3)) == (3, len(CHECKS))


def test_the_full_benchmark_is_refused_until_the_start_check_passed(base):
    manager = _manager(tracker_until_cancelled, needed=True)
    try:
        with pytest.raises(StartRefused) as refused:
            _start(manager)  # before the first status read
        manager.refresh()
        manager.start_released = True  # a start check that failed releases the UI, but did not pass
        with pytest.raises(StartRefused) as refused:
            _start(manager)
        assert refused.value.detail == {"code": "start-check-not-passed",
                                        "message": "The full benchmark can start once the start check has passed on this system."}
        assert not manager.running and manager.run is None
    finally:
        manager.shutdown()


def test_every_start_is_refused_while_it_runs_and_a_cancel_leaves_an_incomplete_report_to_share(base, failures):
    manager = _manager(tracker_until_cancelled)
    before = {row["report_id"] for row in hand_in_reports()}
    try:
        manager.refresh()
        run = _start(manager)
        assert (run.level, run.items, run.seconds_estimate) == ("full", (), 333)
        assert crash_record.read()["level"] == "full"
        for kind in ("cameras", "recording", "realtime", "posthoc"):
            with pytest.raises(StartRefused) as refused:
                manager.claim(kind)
            assert refused.value.detail["code"] == "quick-check-running"
            assert refused.value.detail["message"] == (f"The full benchmark is running; the {kind} start was refused. "
                                                       "Start again when the check ends.")
        with pytest.raises(StartRefused, match="the quick check start was refused"):
            manager.start(pair=None, detector_type="rtmpose", rtmpose_model_name=None, seconds_estimate=1, holds=lambda: ())
        _wait(manager, lambda: manager.run is not None and manager.run.rows)
        snapshot = manager.snapshot(())
        assert snapshot.run.level == "full" and (snapshot.run.done, snapshot.run.total) == (3, len(CHECKS))
        assert [(row.name, row.state) for row in snapshot.run.rows] == [("cpu", "partly-done"), (LABEL, "running")]
        assert manager.cancel().state == "cancelling"  # the UI's lock ends at once
        _wait(manager, lambda: not manager.running)
        assert manager.full_results == (StartCheckResult("skellytracker", "not-run", "cancelled"),
                                        StartCheckResult("freemocap", "not-run", "cancelled"))  # its benchmark did not start
        assert manager.snapshot(()).full_results == manager.full_results and manager.start_results == ()
        # The rows stay as the run ended, each done, in the server's state until the next full benchmark starts.
        assert [(row.name, row.state, row.result) for row in manager.snapshot(()).full_rows] == [
            ("cpu", "done", "pass"), (LABEL, "done", "not-run")]
        assert not crash_record.path().exists() and failures == []
        manager.release(manager.claim("cameras"))  # the lock ended with the run
        (new,) = [row for row in hand_in_reports() if row["report_id"] not in before]
        assert (new["package"], new["kind"]) == ("skellytracker", "full")
        text = report_file_for([new["report_id"]], None)[1].decode("utf-8")
        assert "full run · incomplete · not valid as evidence:" in text  # the rest of its checks are `not-run`, `cancelled`
    finally:
        manager.shutdown()


def test_a_crash_during_the_full_benchmark_keeps_its_report_and_fails_no_pair_for_a_timing(base, failures):
    manager = _manager(tracker_crash)
    try:
        manager.refresh()
        _start(manager)
        _wait(manager, lambda: not manager.running)
        assert manager.full_results == (StartCheckResult(None, "crashed", "exit-code-3"),)
        assert failures == [], "a crashed timing check does not fail its pair at level full"
        assert [(row.name, row.state) for row in manager.full_rows] == [("cpu", "done"), (LABEL, "done")]
        (row,) = [row for row in certification.pending_reports() if row["kind"] == "full"]  # kept in freemocap's folder
        assert row["package"] == "skellytracker", "the share list names the report's own package, not its folder's"
        assert next(new for new in hand_in_reports() if new["report_id"] == row["report_id"])["package"] == "skellytracker"
        report = certification.read_report(row["report_id"])
        assert ("interrupted" in report["evidence"]["reasons"]
                and next(check for check in report["checks"] if check["name"] == f"{LABEL}:pipeline-1")["reason"] == "crashed")
    finally:
        manager.shutdown()


@pytest.mark.parametrize(("step", "failed"), [(f"{LABEL}:probe", [f"{LABEL}:probe"]), (f"{LABEL}:video", [f"{LABEL}:video"]),
                                              (f"{LABEL}:jpeg", []), (f"{LABEL}:pipeline-1", [])])
def test_a_full_benchmark_found_at_launch_fails_its_pair_only_for_a_probe_or_video_check(base, failures, step, failed):
    crash_record.write({"level": "full", "pair": None, "created_utc": "2026-11-21T10:00:00Z",
                        "message": _message(step, CHECKS.index(step))})
    manager = _manager(tracker_until_cancelled)
    assert manager.full_results == (StartCheckResult("skellytracker", "fail", "crashed"),)
    assert manager.start_results == () and not manager.start_released, "the start check's state is not touched"
    assert failures == failed and not manager.running


def test_the_full_benchmark_routes_give_the_plans_in_run_order_and_start_with_the_clean_up_choice(monkeypatch, tmp_path):
    import skellytracker
    from freemocap.api.http.certify import quick_check_router as module
    download = {"name": "test-video.mp4", "bytes": 12_000_000, "source": "https://media.example/v.mp4", "sha256": "ab" * 32}
    monkeypatch.setenv("FREEMOCAP_TEST_MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(certification, "_pairs", lambda: [])
    monkeypatch.setattr(certification, "_blender_path", lambda path: None)
    monkeypatch.setattr(skellytracker, "certify_plan", lambda level, **options: {
        "package": "skellytracker", "kind": level, "seconds_estimate": 333, "total": 38, "risks": [], "downloads": [download],
        "system_changes": [], "questions": [], "details": {"checks": [LABEL, "openvino@8086-a780-0"],
                                                           "not_run": {"openvino@8086-a780-0": "ep-not-installed"}}})
    started = []

    def start(**kwargs):
        if kwargs["holds"]():
            raise StartRefused(409, {"code": "pipelines-running", "message": "busy", "gpu_held_by": []})
        started.append(kwargs)
        return CertificationRun(level=kwargs["level"], seconds_estimate=kwargs["seconds_estimate"])

    application = SimpleNamespace(holds=(), quick_checks=SimpleNamespace(start=start))
    application.pipeline_holds = lambda: application.holds
    monkeypatch.setattr("freemocap.app.freemocap_application.get_freemocap_app", lambda: application)
    app = FastAPI()
    app.include_router(module.quick_check_router)
    client = TestClient(app)
    plan = client.get("/certify/full_benchmark/plan").json()["packages"]
    own = certification.certify_plan("full", test_media_dir=str(tmp_path))  # no pair: data-folder, recording, blender
    assert [(row["package"], row["total"], row["seconds_estimate"]) for row in plan] == [
        ("skellytracker", 38, 333), ("freemocap", 3, own["seconds_estimate"])]
    assert plan[0]["downloads"] == [download] and plan[1]["downloads"] == own["downloads"] == [certification._download_item()]
    assert client.post("/certify/full_benchmark", json={}).status_code == 422  # the clean-up choice is always sent
    application.holds = ("work",)
    refused = client.post("/certify/full_benchmark", json={"remove_data": True})
    assert refused.status_code == 409 and refused.json()["detail"]["message"] == "busy"
    application.holds = ()
    accepted = client.post("/certify/full_benchmark", json={"remove_data": False})
    assert accepted.status_code == 202 and accepted.json()["level"] == "full" and accepted.json()["rows"] == []
    assert (started[0]["level"], started[0]["remove_data"], started[0]["seconds_estimate"], started[0]["pair"]) == (
        "full", False, 333 + own["seconds_estimate"], None)  # the total of the plans' estimates
    assert started[0]["not_counted"] == ["openvino@8086-a780-0"], "the pairs the plan does not run are not counted"


def test_a_child_whose_backend_died_ends_by_itself_at_once_and_writes_no_report(base):
    """The crash record is the one report of a crash of the app: the orphaned child does not cancel into a second one."""
    import psutil
    pids = multiprocessing.Queue()
    backend = multiprocessing.Process(target=backend_that_dies, args=(pids,))
    backend.start()
    pid = pids.get(timeout=180)
    backend.join(timeout=30)
    with contextlib.suppress(psutil.NoSuchProcess):
        child = psutil.Process(pid)
        try:
            child.wait(timeout=3)  # its watch polls every 0.2 s
        except psutil.TimeoutExpired:
            child.kill()
            pytest.fail("the orphaned child did not end by itself")
    assert not (base / "cancelled-report").exists()
