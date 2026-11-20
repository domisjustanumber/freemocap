"""The start check (F15 step 4): freemocap's own quick checks, the record of a local pass and whether the UI needs the
check, the start check job in a real spawn child with stand-ins for both packages' `certify`, and its routes."""
import json
import multiprocessing
import re
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.core.streaming.message_model import CertificationHost, PipelineHold
from freemocap.system.certify import own_checks, start_check
from freemocap.system.certify.quick_check import QuickCheckManager, StartRefused

PATH = re.compile(r"(?:\b[A-Za-z]:[\\/]|\\\\[^\\\s]|/(?:home|Users|root)/|~[\\/])")  # privacy rule 1


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(tmp_path))  # a spawn child inherits it
    return tmp_path


@pytest.fixture
def no_blender(monkeypatch):
    monkeypatch.setattr(own_checks, "_blender", lambda cancelled, path=None: ("record-only", "not-found", {"found": False}))


# - freemocap's own checks -

def test_the_quick_level_runs_its_six_checks_in_order_and_obeys_the_report_format(base, no_blender):
    messages = []
    report = own_checks.certify("quick", messages.append, None, ui_remote=False)
    assert [row["name"] for row in report["checks"]] == list(own_checks.QUICK_CHECKS)
    rows = {row["name"]: row for row in report["checks"]}
    assert rows["spawn-child"]["result"] == "pass" and rows["bundle-imports"]["result"] == "pass", rows
    assert rows["bundle-imports"]["numbers"] == {"failed": [], "from_bundle": None}  # not frozen
    assert rows["data-folder"]["result"] == "pass" and rows["data-folder"]["numbers"]["free_bytes"] > 0
    assert list(base.iterdir()) == []  # the probe file is gone
    assert rows["install-facts"]["result"] == "record-only" and rows["install-facts"]["numbers"]["ui_remote"] is False
    assert rows["build-identity"]["result"] in ("pass", "record-only")
    assert report["schema"] == "skellycertify.report/1.1.0" and report["kind"] == "quick"
    assert report["package"]["name"] == "freemocap" and re.fullmatch(r"[0-9a-f-]{36}", report["id"])
    assert report["evidence"]["valid"] is (not report["evidence"]["reasons"])
    assert messages[0]["state"] == "starting" and messages[-1]["state"] == "done" and messages[-1]["done"] == 6
    assert not PATH.search(json.dumps(report)), "no path in a report (privacy rule 1)"
    assert own_checks.module_result(report) == ("pass", None)


def test_a_cancel_makes_every_check_not_run_and_the_run_not_a_pass(base, no_blender):
    cancel = multiprocessing.Event()
    cancel.set()
    report = own_checks.certify("quick", None, cancel)
    assert {(row["result"], row["reason"]) for row in report["checks"]} == {("not-run", "cancelled")}
    assert "cancelled" in report["evidence"]["reasons"]
    assert own_checks.module_result(report) == ("not-run", "cancelled")


def test_a_spawn_child_with_no_answer_stops_the_rest(base, no_blender, monkeypatch):
    monkeypatch.setattr(own_checks, "_spawn_imports", lambda cancelled: (None, "crashed"))
    rows = {row["name"]: row for row in own_checks.certify("quick")["checks"]}
    assert (rows["spawn-child"]["result"], rows["spawn-child"]["reason"]) == ("fail", "crashed")
    assert {(rows[name]["result"], rows[name]["reason"]) for name in own_checks.QUICK_CHECKS[2:]} == {("not-run", "spawn-failed")}


def test_the_blender_check_uses_the_chosen_path_else_the_best_guess(tmp_path, monkeypatch):
    chosen = tmp_path / "blender.exe"
    chosen.write_text("")
    ran = []
    monkeypatch.setattr("freemocap.core.blender.runtime.run_external", lambda command, **kwargs: ran.append(command[0]) or
                        SimpleNamespace(stdout="Blender 4.2.1"))
    monkeypatch.setattr("freemocap.core.blender.runtime.get_best_guess_of_blender_path", lambda: None)
    assert own_checks._blender(lambda: False, str(chosen))[2]["version_major"] == 4 and ran == [str(chosen)]
    assert own_checks._blender(lambda: False)[1] == "not-found"  # no path chosen and no guess


def test_a_data_folder_that_cannot_be_written_fails_with_the_class_name(tmp_path, monkeypatch):
    blocked = tmp_path / "a-file"
    blocked.write_text("")
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(blocked))
    result, reason, numbers = own_checks._data_folder()
    assert result == "fail" and re.fullmatch(r"[A-Za-z]+Error", reason) and numbers == {}


def test_the_full_level_is_not_built_and_a_bad_level_raises():
    assert {(row["result"], row["reason"]) for row in own_checks.certify("full")["checks"]} == {("not-run", "not-built")}
    assert own_checks.certify_plan("quick")["details"]["checks"] == list(own_checks.QUICK_CHECKS)
    with pytest.raises(ValueError):
        own_checks.certify("medium")


# - Whether the start check is needed -

def test_a_local_pass_stops_the_start_check_until_a_version_changes(base, monkeypatch):
    assert start_check.start_check_needed()
    start_check.record_pass({"checks": []})
    assert not start_check.start_check_needed()
    assert json.loads((base / "certify" / "start-check.json").read_text())["versions"] == start_check.version_set()
    versions = start_check.version_set()
    monkeypatch.setattr(start_check, "version_set", lambda: {**versions, "skellytracker": "9.9.9"})
    assert start_check.start_check_needed()


def test_a_reviewed_row_for_this_machine_stops_the_start_check(base, monkeypatch):
    key = start_check.os_key()
    assert key["freemocap"].count(".") == 1 and key["build_family"]
    monkeypatch.setattr(start_check, "REVIEWED_OS_ROWS", ({**key, "kind": "quick"},))
    assert start_check.start_check_needed(), "only a full report gives a reviewed row"
    monkeypatch.setattr(start_check, "REVIEWED_OS_ROWS", ({**key, "kind": "full", "issue": 1, "reviewed": "2026-11-19"},))
    assert not start_check.start_check_needed()


# - The job, in a real spawn child (module-level stand-ins, so the child can import them) -

def own_pass(level, progress, cancel, *, ui_remote, blender_exe_path=None):
    progress({"package": "freemocap", "kind": level, "state": "done", "step": None, "checks": [], "done": 6, "total": 6,
              "seconds_left": None})
    return {"checks": [{"name": "spawn-child", "result": "pass", "reason": None}], "evidence": {"reasons": []}}


def own_fail(level, progress, cancel, *, ui_remote, blender_exe_path=None):
    return {"checks": [{"name": "data-folder", "result": "fail", "reason": "PermissionError"}], "evidence": {"reasons": []}}


def own_until_cancelled(level, progress, cancel, *, ui_remote, blender_exe_path=None):
    while not cancel.is_set():
        time.sleep(0.05)
    return {"checks": [{"name": "spawn-child", "result": "not-run", "reason": "cancelled"}], "evidence": {"reasons": ["cancelled"]}}


def tracker_quick(level, progress, cancel, **options):
    assert level == "quick" and options == {}  # no EP named: every GPU EP with no reviewed row, field-test ones included
    progress({"package": "skellytracker", "kind": level, "state": "running", "step": None, "checks": [], "done": 1,
              "total": 3, "seconds_left": 9})
    return {"checks": [{"name": "dml@x-0:probe", "result": "pass", "reason": None},
                       {"name": "dml@x-0", "result": "fail", "reason": "image-not-passed"}], "evidence": {"reasons": []}}


def _manager(own, needed=True):
    flag = multiprocessing.Value("b", False)
    return QuickCheckManager(global_kill_flag=flag, worker_registry=WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.PROCESS),
                             read_status=lambda: (CertificationHost(), (), None, ()), read_start_needed=lambda: needed,
                             own_certify=own, certify=tracker_quick)


def _run_to_end(manager, cancel_when_running=False):
    packages = []
    manager.refresh()
    manager.start(pair=None, detector_type="rtmpose", rtmpose_model_name=None, seconds_estimate=120, holds=lambda: ())
    deadline = time.monotonic() + 60
    while manager.running and time.monotonic() < deadline:
        if cancel_when_running:
            manager.cancel()
        time.sleep(0.3)
        manager.refresh()
        packages.append(manager.run and manager.run.package)
    assert not manager.running
    return packages


def test_the_start_check_runs_both_packages_records_freemocaps_pass_and_releases_the_ui(base):
    manager = _manager(own_pass)
    try:
        manager.refresh()
        assert manager.snapshot(()).start_required
        _run_to_end(manager)
        assert [(row.package, row.result, row.reason) for row in manager.start_results] == [
            ("freemocap", "pass", None), ("skellytracker", "fail", "dml@x-0")]
        assert not manager.snapshot(()).start_required, "a finished check releases the UI, pass or fail"
        assert manager.last_result is None, "the EP quick check's result stays as it was"
        assert (base / "certify" / "start-check.json").is_file()
    finally:
        manager.shutdown()


def test_a_failed_start_check_releases_the_ui_but_records_no_pass(base):
    manager = _manager(own_fail)
    try:
        _run_to_end(manager)
        assert manager.start_results[0].result == "fail" and manager.start_results[0].reason == "data-folder"
        assert not manager.snapshot(()).start_required
        assert not (base / "certify" / "start-check.json").exists()
    finally:
        manager.shutdown()


def test_a_cancelled_start_check_keeps_the_ui_grey_and_skips_skellytracker(base):
    manager = _manager(own_until_cancelled)
    try:
        _run_to_end(manager, cancel_when_running=True)
        assert [(row.package, row.result, row.reason) for row in manager.start_results] == [
            ("freemocap", "not-run", "cancelled"), ("skellytracker", "not-run", "cancelled")]
        assert manager.snapshot(()).start_required
    finally:
        manager.shutdown()


def test_every_start_is_refused_while_the_start_check_runs_and_it_is_refused_while_work_runs(base):
    manager = _manager(own_until_cancelled)
    try:
        with pytest.raises(StartRefused) as refused:
            manager.start(pair=None, detector_type="rtmpose", rtmpose_model_name=None, seconds_estimate=1,
                          holds=lambda: (PipelineHold("cameras", "g1"),))
        assert refused.value.detail["code"] == "pipelines-running"
        manager.start(pair=None, detector_type="rtmpose", rtmpose_model_name=None, seconds_estimate=1, holds=lambda: ())
        with pytest.raises(StartRefused) as refused:
            manager.claim("recording")
        assert refused.value.detail["code"] == "quick-check-running"
        assert refused.value.detail["message"].startswith("The start check is running")
        assert refused.value.detail["run"]["execution_provider"] is None
    finally:
        manager.shutdown()


# - Routes -

def test_the_start_check_routes_give_each_packages_plan_and_start_or_refuse(monkeypatch):
    import skellytracker
    from freemocap.api.http.certify import quick_check_router as module
    monkeypatch.setattr(skellytracker, "certify_plan", lambda level: {
        "package": "skellytracker", "kind": level, "seconds_estimate": 90, "downloads": [], "system_changes": [],
        "questions": [], "details": {"execution_providers": ["dml"], "checks": ["dml@x-0"], "not_run": {}}})
    started = []

    def start(**kwargs):
        if kwargs["holds"]():
            raise StartRefused(409, {"code": "pipelines-running", "message": "busy", "gpu_held_by": []})
        started.append(kwargs)
        from freemocap.core.streaming.message_model import CertificationRun
        return CertificationRun(seconds_estimate=kwargs["seconds_estimate"])

    application = SimpleNamespace(holds=(), quick_checks=SimpleNamespace(start=start))
    application.pipeline_holds = lambda: application.holds
    monkeypatch.setattr("freemocap.app.freemocap_application.get_freemocap_app", lambda: application)
    app = FastAPI()
    app.include_router(module.quick_check_router)
    client = TestClient(app)
    plan = client.get("/certify/start_check/plan").json()
    assert [(row["package"], row["checks"]) for row in plan["packages"]] == [
        ("freemocap", list(own_checks.QUICK_CHECKS)), ("skellytracker", ["dml@x-0"])]
    application.holds = (PipelineHold("realtime", "rt1"),)
    assert client.post("/certify/start_check").status_code == 409
    application.holds = ()
    accepted = client.post("/certify/start_check")
    assert accepted.status_code == 202 and accepted.json()["items"] == [] and accepted.json()["seconds_estimate"] == 120
    assert started[0]["pair"] is None and started[0]["ui_remote"] is True  # the test client's host is not loopback
    assert client.post("/certify/start_check", json={"blenderExePath": "C:/Blender/blender.exe"}).status_code == 202
    assert started[0]["blender_exe_path"] is None and started[1]["blender_exe_path"] == "C:/Blender/blender.exe"
