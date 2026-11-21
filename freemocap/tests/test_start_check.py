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
from freemocap import certification
from freemocap.system.certify import start_check
from freemocap.system.certify.quick_check import QuickCheckManager, StartRefused

PATH = re.compile(r"(?:\b[A-Za-z]:[\\/]|\\\\[^\\\s]|/(?:home|Users|root)/|~[\\/])")  # privacy rule 1


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(tmp_path))  # a spawn child inherits it
    return tmp_path


@pytest.fixture
def no_blender(monkeypatch):
    monkeypatch.setattr(certification, "_blender", lambda cancelled, path=None: ("not-run", "not-installed", {"found": False}))


@pytest.fixture
def no_posthoc(monkeypatch):
    monkeypatch.setattr(certification, "_posthoc", lambda cancelled, cleanup, media, test_media_dir: ("not-run", "models-missing", None))


# - freemocap's own checks -

def test_the_quick_level_runs_its_seven_checks_in_order_and_obeys_the_report_format(base, no_blender):
    """The real checks, the post-hoc session on skellytracker's bundled frames and models included (about 10 s)."""
    messages = []
    report = certification.certify("quick", messages.append, None, ui_remote=False)
    assert [row["name"] for row in report["checks"]] == list(certification.QUICK_CHECKS)
    rows = {row["name"]: row for row in report["checks"]}
    assert rows["spawn-child"]["result"] == "pass" and rows["bundle-imports"]["result"] == "pass", rows
    assert rows["bundle-imports"]["numbers"] == {"failed": [], "from_bundle": None}  # not frozen
    assert rows["data-folder"]["result"] == "pass" and rows["data-folder"]["numbers"]["free_bytes"] > 0
    posthoc = rows["posthoc-session"]
    if posthoc["reason"] != "models-missing":  # an installed skellytracker without its model files
        assert (posthoc["result"], posthoc["reason"]) == ("pass", None), posthoc
        assert posthoc["numbers"]["frames"] == 3 and set(posthoc["numbers"]["execution_providers"]) == {"person", "wholebody"}
        assert report["test_media"] == [certification._frames_media(None)]
    assert report["cleanup"] == []
    assert [path.name for path in base.iterdir()] == ["certify"]  # the probe file and the session's work folder are gone
    assert [path.name for path in (base / "certify").iterdir()] == ["reports"]
    assert [path.name for path in (base / "certify" / "reports").iterdir()] == [f"{report['id']}.json"]
    assert rows["install-facts"]["result"] == "record-only" and rows["install-facts"]["numbers"]["ui_remote"] is False
    assert rows["build-identity"]["result"] in ("pass", "record-only")
    assert report["schema"] == "skellycertify.report/1.6.0" and report["kind"] == "quick"
    # format 1.6.0, 3.3: null while skellytracker's GPU query at the pin gives no shared memory
    assert all(gpu["shared_memory_bytes"] is None or gpu["shared_memory_bytes"] >= 0 for gpu in report["host"]["gpus"])
    # format 1.5.0: one `component` item for each check that ran, named as its check's `module`; format 1.6.0: a Blender
    # that is not installed is `skipped` with `not-installed`
    assert report["summary"] == [{"group": "component", "name": row["module"], "device": None, "result": row["result"]}
                                 for row in report["checks"] if row["result"] != "not-run"] + [
        {"group": "component", "name": "Blender", "device": None, "result": "skipped", "reason": "not-installed"}]
    assert [item["name"] for item in report["summary"]][:4] == ["Build identity", "Child process", "Bundle imports", "Data folder"]
    assert report["package"]["name"] == "freemocap" and re.fullmatch(r"[0-9a-f-]{36}", report["id"])
    assert report["evidence"]["valid"] is (not report["evidence"]["reasons"])
    assert messages[0]["state"] == "starting" and messages[-1]["state"] == "done" and messages[-1]["done"] == 7
    assert not PATH.search(json.dumps(report)), "no path in a report (privacy rule 1)"
    assert certification.module_result(report) == ("pass", None)


def test_a_cancel_makes_every_check_not_run_and_the_run_not_a_pass(base, no_blender):
    cancel = multiprocessing.Event()
    cancel.set()
    report = certification.certify("quick", None, cancel)
    assert {(row["result"], row["reason"]) for row in report["checks"]} == {("not-run", "cancelled")}
    assert "cancelled" in report["evidence"]["reasons"]
    assert certification.module_result(report) == ("not-run", "cancelled")


def test_a_spawn_child_with_no_answer_stops_the_rest(base, no_blender, monkeypatch):
    monkeypatch.setattr(certification, "_spawn_imports", lambda cancelled: (None, "crashed"))
    rows = {row["name"]: row for row in certification.certify("quick")["checks"]}
    assert (rows["spawn-child"]["result"], rows["spawn-child"]["reason"]) == ("fail", "crashed")
    assert {(rows[name]["result"], rows[name]["reason"]) for name in certification.QUICK_CHECKS[2:]} == {("not-run", "spawn-failed")}


def test_the_blender_check_uses_the_chosen_path_else_the_best_guess(tmp_path, monkeypatch):
    chosen = tmp_path / "blender.exe"
    chosen.write_text("")
    ran = []
    monkeypatch.setattr("freemocap.core.blender.runtime.run_external", lambda command, **kwargs: ran.append(command[0]) or
                        SimpleNamespace(stdout="Blender 4.2.1"))
    monkeypatch.setattr("freemocap.core.blender.runtime.get_best_guess_of_blender_path", lambda: None)
    assert certification._blender(lambda: False, str(chosen))[2]["version_major"] == 4 and ran == [str(chosen)]
    assert certification._blender(lambda: False)[:2] == ("not-run", "not-installed")  # no path chosen and no guess


def test_a_data_folder_that_cannot_be_written_fails_with_the_class_name(tmp_path, monkeypatch):
    blocked = tmp_path / "a-file"
    blocked.write_text("")
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(blocked))
    result, reason, numbers = certification._data_folder()
    assert result == "fail" and re.fullmatch(r"[A-Za-z]+Error", reason) and numbers == {}


def test_the_quick_plan_counts_its_seven_checks_and_a_bad_level_raises(base):
    """The level full: test_recording_benchmark.py."""
    plan = certification.certify_plan("quick")
    assert plan["details"]["checks"] == list(certification.QUICK_CHECKS)
    # format 2.6: `total` counts the checks that run, and a quick plan has no risks and no download
    assert (plan["total"], plan["risks"], plan["downloads"]) == (7, [], [])
    assert certification.certify_plan("quick", ui_remote=True, blender_exe_path=None) == plan
    with pytest.raises(ValueError):
        certification.certify("medium")


# - freemocap's own reports: kept with skellytracker's states (J13, J18) -

ISSUE = "https://github.com/domisjustanumber/skellycertify/issues/7"
PASSED = ({"failed": [], "from_bundle": None}, None)


def _keep(created: str, results: dict, kind: str = "quick") -> str:
    """A report in freemocap's store with these check results, as `certify()` keeps one."""
    import uuid
    report_id = str(uuid.uuid4())
    certification._write_json(certification.reports_dir() / f"{report_id}.json", {
        "schema": certification.SCHEMA, "id": report_id, "kind": kind, "created_utc": created,
        "checks": [{"name": name, "result": result, "reason": None} for name, result in results.items()],
        "evidence": {"valid": False, "reasons": ["no-commit"]}})
    return report_id


def test_own_reports_are_kept_with_the_hand_in_states_and_not_sent_makes_them_pending(base, no_blender, no_posthoc,
                                                                                     monkeypatch):
    monkeypatch.setattr(certification, "_spawn_imports", lambda cancelled: ({"failed": ["cv2-ImportError"], "from_bundle": None}, None))
    failed = certification.certify("quick")
    [row] = certification.pending_reports()
    assert row == {"report_id": failed["id"], "package": "freemocap", "kind": "quick", "created_utc": failed["created_utc"], "has_failure": True,
                   "evidence_valid": failed["evidence"]["valid"], "state": "pending", "reference": None}
    assert certification.read_report(failed["id"]) == failed
    certification.mark_reports([failed["id"]], "covered", reference=ISSUE)
    assert certification.pending_reports() == []
    [row] = certification.pending_reports(include_handed_in=True)
    assert (row["state"], row["reference"]) == ("covered", ISSUE)
    certification.mark_reports([failed["id"]], "opened")
    assert [(row["state"], row["reference"]) for row in certification.pending_reports(True)] == [("opened", None)]
    certification.mark_reports([failed["id"]], "pending")  # "Not sent", also from opened or covered
    assert [(row["state"], row["reference"]) for row in certification.pending_reports()] == [("pending", None)]
    for ids, state, reference in (([failed["id"]], "sent", None), (["no-such-report"], "covered", None),
                                  ([failed["id"]], "pending", ISSUE), (failed["id"], "opened", None)):
        with pytest.raises(ValueError):
            certification.mark_reports(ids, state, reference=reference)
    assert [row["state"] for row in certification.pending_reports(True)] == ["pending"], "a refused mark changes nothing"
    with pytest.raises(ValueError):
        certification.read_report("../start-check")
    cancel = multiprocessing.Event()
    cancel.set()
    certification.certify("quick", None, cancel)
    assert len(list(certification.reports_dir().glob("*.json"))) == 1, "a run with no pass or fail is not kept"


def test_a_new_quick_pass_prunes_older_passes_not_handed_in(base):
    old = _keep("2026-11-19T10:00:00Z", {"spawn-child": "pass", "data-folder": "pass"})
    smaller = _keep("2026-11-19T10:30:00Z", {"spawn-child": "pass"})
    handed_in = _keep("2026-11-19T11:00:00Z", {"spawn-child": "pass", "data-folder": "pass"})
    failure = _keep("2026-11-19T12:00:00Z", {"spawn-child": "pass", "data-folder": "fail"})
    full = _keep("2026-11-19T09:00:00Z", {"spawn-child": "pass", "data-folder": "pass"}, kind="full")
    other = _keep("2026-11-19T09:30:00Z", {"blender": "pass"})  # a pass that no newer report repeats
    newest = _keep("2026-11-19T13:00:00Z", {"spawn-child": "pass", "data-folder": "pass"})
    certification.mark_reports([handed_in], "opened")
    certification._prune_reports()
    kept = {path.stem for path in certification.reports_dir().glob("*.json")}
    assert kept == {handed_in, failure, full, other, newest} and not kept & {old, smaller}


def test_each_quick_pass_of_certify_replaces_the_one_before(base, no_blender, no_posthoc, monkeypatch):
    monkeypatch.setattr(certification, "_spawn_imports", lambda cancelled: PASSED)
    certification.certify("quick")
    certification.certify("quick")
    assert len(certification.pending_reports()) == 1


def test_a_data_folder_that_cannot_be_written_still_gives_the_report(tmp_path, no_blender, no_posthoc, monkeypatch):
    blocked = tmp_path / "a-file"
    blocked.write_text("")
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(blocked))
    monkeypatch.setattr(certification, "_spawn_imports", lambda cancelled: PASSED)
    report = certification.certify("quick")
    assert {row["name"]: row["result"] for row in report["checks"]}["data-folder"] == "fail"


def test_import_freemocap_loads_no_certification_and_the_two_names_resolve_lazily():
    import subprocess
    import sys
    script = ("import sys, freemocap; assert 'freemocap.certification' not in sys.modules; "
              "from freemocap import certify, certify_plan; import freemocap.certification as c; "
              "assert certify is c.certify and certify_plan is c.certify_plan and freemocap.certify is c.certify")
    subprocess.run([sys.executable, "-c", script], check=True, timeout=120)


# - Whether the start check is needed -

def test_a_local_pass_stops_the_start_check_until_a_version_changes(base, monkeypatch):
    assert start_check.start_check_needed()
    start_check.record_pass({"checks": []})
    assert not start_check.start_check_needed()
    assert json.loads((base / "certify" / "start-check.json").read_text())["versions"] == start_check.version_set()
    versions = start_check.version_set()
    monkeypatch.setattr(start_check, "version_set", lambda: {**versions, "skellytracker": "9.9.9"})
    assert start_check.start_check_needed()


def test_a_crash_marker_skips_the_start_check_but_is_no_pass_for_the_full_benchmark(base, monkeypatch):
    start_check.record_crash("posthoc-session")
    assert not start_check.start_check_needed() and start_check.start_check_needed(crash_skips=False)  # owner, Q79
    start_check.record_pass({"checks": []})  # a later pass overwrites the marker
    assert not start_check.start_check_needed(crash_skips=False)
    start_check.record_crash("posthoc-session")
    monkeypatch.setattr(start_check, "REVIEWED_OS_ROWS", ({**start_check.os_key(), "kind": "full"},))
    assert not start_check.start_check_needed(crash_skips=False), "a reviewed row still admits the full benchmark"
    monkeypatch.setattr(start_check, "REVIEWED_OS_ROWS", ())
    monkeypatch.setattr(start_check, "_has_checks", lambda: False)
    assert not start_check.start_check_needed(crash_skips=False), "so does nothing to check"


def test_a_reviewed_row_for_this_machine_stops_the_start_check(base, monkeypatch):
    key = start_check.os_key()
    assert key["freemocap"].count(".") == 1 and key["build_family"]
    monkeypatch.setattr(start_check, "REVIEWED_OS_ROWS", ({**key, "kind": "quick"},))
    assert start_check.start_check_needed(), "only a full report gives a reviewed row"
    monkeypatch.setattr(start_check, "REVIEWED_OS_ROWS", ({**key, "kind": "full", "issue": 1, "reviewed": "2026-11-19"},))
    assert not start_check.start_check_needed()


def test_the_start_check_is_not_needed_when_no_packages_quick_plan_has_a_check_to_run(base, monkeypatch):
    import skellytracker
    tracker = {"package": "skellytracker", "total": 0, "details": {"checks": ["dml@x-0"], "not_run": {}}}
    monkeypatch.setattr(certification, "certify_plan", lambda level: {"package": "freemocap", "total": 0})
    monkeypatch.setattr(skellytracker, "certify_plan", lambda level: tracker)
    assert not start_check.start_check_needed(), "a plan's total counts, not its listed checks"
    tracker["total"] = 6
    assert start_check.start_check_needed()
    tracker["total"] = 0
    monkeypatch.setattr(certification, "certify_plan", lambda level: {"package": "freemocap", "total": 6})
    assert start_check.start_check_needed()


# - The job, in a real spawn child (module-level stand-ins, so the child can import them) -

def own_pass(level, progress, cancel, *, ui_remote, blender_exe_path=None, **options):
    progress({"package": "freemocap", "kind": level, "state": "done", "step": None, "checks": [], "done": 6, "total": 6,
              "seconds_left": None})
    return {"checks": [{"name": "spawn-child", "result": "pass", "reason": None}], "evidence": {"reasons": []}}


def own_fail(level, progress, cancel, *, ui_remote, blender_exe_path=None, **options):
    return {"checks": [{"name": "data-folder", "result": "fail", "reason": "PermissionError"}], "evidence": {"reasons": []}}


def own_until_cancelled(level, progress, cancel, *, ui_remote, blender_exe_path=None, **options):
    while not cancel.is_set():
        time.sleep(0.05)
    return {"checks": [{"name": "spawn-child", "result": "not-run", "reason": "cancelled"}], "evidence": {"reasons": ["cancelled"]}}


def tracker_quick(level, progress, cancel, **options):
    # no EP named: every GPU EP with no reviewed row, field-test ones included
    assert level == "quick" and set(options) == {"test_media_dir", "abandon"}
    progress({"package": "skellytracker", "kind": level, "state": "running", "step": None, "checks": [], "done": 1,
              "total": 3, "seconds_left": 9})
    return {"checks": [{"name": "cpu:video", "result": "pass", "reason": None}, {"name": "cpu:live", "result": "pass", "reason": None},
                       {"name": "dml@x-0:probe", "result": "pass", "reason": None},
                       {"name": "dml@x-0:video", "result": "fail", "reason": "keypoints-differ"},
                       {"name": "dml@x-0:live", "result": "not-run", "reason": "video-not-passed"},
                       {"name": "dml@x-0", "result": "fail", "reason": "keypoints-differ"}], "evidence": {"reasons": []}}


def test_the_start_check_passes_the_test_media_folder_to_both_packages_and_writes_nothing_there(base, monkeypatch):
    """The quick level downloads and writes nothing there; skellytracker reads its own frames file when the folder does
    not hold it (format 2.8), so it always gets the folder."""
    media = base / "test-media"
    monkeypatch.setenv("FREEMOCAP_TEST_MEDIA_DIR", str(media))
    calls = []

    def tracker(level, progress, cancel, **options):
        calls.append(("skellytracker", options))
        return {"checks": [{"name": "cpu:video", "result": "pass"}], "evidence": {"reasons": []}}

    def own(level, progress, cancel, **options):
        calls.append(("freemocap", options))
        return own_fail(level, progress, cancel, **options)

    start_check.run_start_check(lambda message: None, multiprocessing.Event(), ui_remote=False, own_certify=own,
                                certify=tracker)
    assert calls == [("freemocap", {"ui_remote": False, "blender_exe_path": None, "test_media_dir": str(media)}),
                     ("skellytracker", {"test_media_dir": str(media)})]
    assert not media.exists(), "the quick level writes nothing in the shared folder"


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
            ("freemocap", "pass", None), ("skellytracker", "fail", "dml@x-0:video")]
        assert not manager.snapshot(()).start_required, "a finished check releases the UI, pass or fail"
        assert manager.last_result is None, "the EP quick check's result stays as it was"
        assert "crashed" not in json.loads((base / "certify" / "start-check.json").read_text(encoding="utf-8")), \
            "skellytracker's failure writes no freemocap marker (owner, Q80)"
    finally:
        manager.shutdown()


def test_a_failed_freemocap_check_releases_the_ui_and_skips_the_start_check_for_this_version_set(base):
    manager = _manager(own_fail)
    try:
        _run_to_end(manager)
        assert manager.start_results[0].result == "fail" and manager.start_results[0].reason == "data-folder"
        assert not manager.snapshot(()).start_required
        # owner, Q80: the marker of Q59, not a pass, so the start check is not asked again at the next launch
        record = json.loads((base / "certify" / "start-check.json").read_text(encoding="utf-8"))
        assert record["crashed"] == "data-folder" and "report" not in record
        assert not start_check.start_check_needed() and start_check.start_check_needed(crash_skips=False)
    finally:
        manager.shutdown()


def test_freemocaps_check_that_raises_writes_the_marker_as_a_failed_one(base):
    """The coordinator's reading of Q80, for the owner to confirm: an `error` (an exception) is a `fail` here."""
    def own_raises(level, progress, cancel, **options):
        raise PermissionError("C:/private")

    def tracker(level, progress, cancel, **options):
        return {"checks": [{"name": "cpu:video", "result": "pass"}], "evidence": {"reasons": []}}
    assert start_check.run_start_check(lambda message: None, multiprocessing.Event(), ui_remote=False, own_certify=own_raises,
                                       certify=tracker) == ("start", (("freemocap", "error", "PermissionError"),
                                                                      ("skellytracker", "pass", None)))
    assert json.loads(start_check.record_path().read_text(encoding="utf-8"))["crashed"] == "PermissionError"
    assert not start_check.start_check_needed() and start_check.start_check_needed(crash_skips=False)


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


def test_camera_and_pipeline_starts_are_refused_while_the_start_check_is_required_and_the_check_can_start(base):
    import asyncio
    from freemocap.app.freemocap_application import FreemocapApplication
    manager = _manager(own_until_cancelled)
    try:
        manager.refresh()
        assert manager.snapshot(()).start_required
        for kind, words in (("cameras", "cameras"), ("realtime", "processing"), ("posthoc", "processing")):
            with pytest.raises(StartRefused) as refused:
                manager.claim(kind)
            assert refused.value.detail == {"code": "start-check-required", "message":
                                            f"FreeMoCap must finish its system checks before {words} can start."}
        application = SimpleNamespace(quick_checks=manager)  # the application's own admission points use these kinds
        for start in (FreemocapApplication.create_or_update_realtime_pipeline, FreemocapApplication.create_posthoc_mocap_pipeline,
                      FreemocapApplication.create_posthoc_calibration_pipeline):
            with pytest.raises(StartRefused, match="before processing can start"):
                asyncio.run(start.__wrapped__(application, None, None))  # unwrapped: no type check of the stand-ins
        assert manager.claims == []
        manager.start(pair=None, detector_type="rtmpose", rtmpose_model_name=None, seconds_estimate=1, holds=lambda: ())
        assert manager.running, "the start check itself is how the requirement clears"
    finally:
        manager.shutdown()


def test_gated_starts_are_refused_until_the_first_status_read_and_the_check_can_start(base):
    manager = _manager(own_until_cancelled, needed=False)
    try:
        for kind in ("cameras", "realtime", "posthoc"):
            with pytest.raises(StartRefused) as refused:
                manager.claim(kind)
            assert refused.value.detail == {"code": "start-check-required",
                                            "message": "FreeMoCap is still starting; try again in a moment."}
        manager.release(manager.claim("recording"))  # only the gated kinds wait for the first read
        manager.refresh()
        manager.release(manager.claim("cameras"))  # this machine needs no start check
    finally:
        manager.shutdown()
    unread = _manager(own_until_cancelled)
    try:
        unread.start(pair=None, detector_type="rtmpose", rtmpose_model_name=None, seconds_estimate=1, holds=lambda: ())
        assert unread.running, "the start check stays startable before the first read"
    finally:
        unread.shutdown()


def test_camera_and_pipeline_starts_are_admitted_once_the_start_check_is_not_required(base):
    for manager in (_manager(own_pass, needed=False), _manager(own_pass)):
        manager.refresh()
        manager.start_released = manager.start_released or manager.start_required  # a start check ended other than by a cancel
        assert not manager.snapshot(()).start_required
        for kind in ("cameras", "realtime", "posthoc"):
            manager.release(manager.claim(kind))


def test_the_camera_connect_route_is_refused_while_the_start_check_is_required_and_detect_stays_open(base, monkeypatch):
    from fastapi import APIRouter
    from freemocap.api.http.certify.quick_check_router import camera_starts_admitted
    manager = _manager(own_pass)
    manager.refresh()
    monkeypatch.setattr("freemocap.app.freemocap_application.get_freemocap_app", lambda: SimpleNamespace(quick_checks=manager))
    cameras = APIRouter(prefix="/camera")  # stand-ins at skellycam's paths, gated as app.py gates skellycam's router
    for path in ("/group/apply", "/detect"):
        cameras.add_api_route(path, lambda: "ran", methods=["POST"])
    app = FastAPI()
    app.include_router(cameras, prefix="/skellycam", dependencies=[camera_starts_admitted])
    client = TestClient(app)
    refused = client.post("/skellycam/camera/group/apply")
    assert refused.status_code == 409 and refused.json()["detail"]["message"] == (
        "FreeMoCap must finish its system checks before cameras can start.")
    assert client.post("/skellycam/camera/detect").json() == "ran"
    manager.start_released = True
    assert client.post("/skellycam/camera/group/apply").json() == "ran"
    assert manager.claims == []


# - Routes -

def test_the_start_check_routes_give_each_packages_plan_and_start_or_refuse(monkeypatch):
    import skellytracker
    from freemocap.api.http.certify import quick_check_router as module
    monkeypatch.setattr(skellytracker, "certify_plan", lambda level: {
        "package": "skellytracker", "kind": level, "seconds_estimate": 90, "total": 6, "downloads": [], "system_changes": [],
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
    assert [(row["package"], row["checks"], row["total"], row["risks"]) for row in plan["packages"]] == [
        ("freemocap", list(certification.QUICK_CHECKS), 7, []), ("skellytracker", ["dml@x-0"], 6, [])]  # the plan's total, not its count of pairs
    application.holds = (PipelineHold("realtime", "rt1"),)
    assert client.post("/certify/start_check").status_code == 409
    application.holds = ()
    accepted = client.post("/certify/start_check")
    assert accepted.status_code == 202 and accepted.json()["items"] == []
    assert accepted.json()["seconds_estimate"] == certification.QUICK_BUDGET_SECONDS + 90  # the two plans' estimates
    assert started[0]["pair"] is None and started[0]["ui_remote"] is True  # the test client's host is not loopback
    assert client.post("/certify/start_check", json={"blenderExePath": "C:/Blender/blender.exe"}).status_code == 202
    assert started[0]["blender_exe_path"] is None and started[1]["blender_exe_path"] == "C:/Blender/blender.exe"
