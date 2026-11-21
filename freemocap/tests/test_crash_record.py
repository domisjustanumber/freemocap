"""The crash record of a certify run: written while a check runs, removed after an ordinary end, and found at launch or
after a dead child it becomes an incomplete report, the crashed pair's failure, and nothing that runs again."""
import json
import multiprocessing
import os
import time

import pytest
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap import certification
from freemocap.core.streaming.message_model import CertificationPair, CertificationResult, StartCheckResult
from freemocap.system.certify import crash_record, start_check
from freemocap.system.certify.quick_check import QuickCheckManager
from freemocap.system.certify.relay import report_file_for

EP, DEVICE = "fake-ep", "gpu:10de:2484:0"
LABEL = "fake-ep@10de-2484-0"
RUNNING = {"package": "skellytracker", "kind": "quick", "state": "running", "step": {"name": f"{LABEL}:video"},
           "checks": [{"name": "cpu:video", "result": "pass"}, {"name": "cpu:live", "result": "not-run"},
                      {"name": f"{LABEL}:probe", "result": "pass"}, {"name": f"{LABEL}:video", "result": None},
                      {"name": f"{LABEL}:live", "result": None}, {"name": LABEL, "result": None}],
           "done": 3, "total": 6, "seconds_left": 9}


def certify_until_cancelled(level, progress, cancel, **options):
    progress(RUNNING)
    while not cancel.is_set():
        time.sleep(0.05)
    return {"checks": [{"name": LABEL, "result": "not-run", "reason": "cancelled"}], "evidence": {"reasons": ["cancelled"]}}


def certify_crash(level, progress, cancel, **options):
    progress(RUNNING)
    time.sleep(1.0)  # the backend's refresh takes the message before the child dies
    os._exit(3)


@pytest.fixture
def failures(monkeypatch):
    calls = []
    monkeypatch.setattr(crash_record, "record_provider_failure", lambda check, created: calls.append(check))
    yield calls
    crash_record.remove()
    start_check.record_path().unlink(missing_ok=True)


def _manager(**options):
    flag = multiprocessing.Value("b", False)
    return QuickCheckManager(global_kill_flag=flag, worker_registry=WorkerRegistry(global_kill_flag=flag,
                             worker_mode=WorkerMode.PROCESS), read_status=lambda: ("host", (), None, ()),
                             read_start_needed=lambda: True, **options)


def _run_until_ended(manager, certify, until=lambda manager: False):
    manager.certify = certify
    manager.start(pair=CertificationPair(EP, DEVICE), detector_type="rtmpose", rtmpose_model_name=None,
                  seconds_estimate=None, holds=lambda: ())
    assert crash_record.read()["message"] is None  # written before the first check
    deadline = time.monotonic() + 60
    while manager.running and time.monotonic() < deadline:
        manager.refresh()
        if until(manager):
            manager.cancel()
        time.sleep(0.2)
    assert not manager.running


def _crashed_reports() -> dict:
    """Each interrupted run's report of freemocap's hand-in list, by id."""
    reports = (certification.read_report(row["report_id"]) for row in certification.pending_reports())
    return {report["id"]: report for report in reports if "interrupted" in report["evidence"]["reasons"]}


def _new_report(before: dict) -> dict:
    (report,) = [report for report_id, report in _crashed_reports().items() if report_id not in before]
    return report


def test_the_record_names_the_running_check_and_an_ordinary_end_removes_it(failures):
    manager = _manager()
    seen = []

    def running(manager):
        record = crash_record.read()
        if record and record["message"]:
            seen.append(record)
            return True
        return False

    before = _crashed_reports()
    _run_until_ended(manager, certify_until_cancelled, running)
    assert seen[0]["message"]["step"]["name"] == f"{LABEL}:video"
    assert seen[0]["pair"] == {"execution_provider": EP, "device_key": DEVICE} and seen[0]["level"] == "quick"
    assert crash_record.read() is None and not crash_record.path().exists()
    assert _crashed_reports().keys() == before.keys() and failures == []
    manager.shutdown()


def test_a_child_that_dies_keeps_the_same_record_as_a_crash_of_the_app(failures):
    manager, before = _manager(), _crashed_reports()
    _run_until_ended(manager, certify_crash)
    assert (manager.last_result.result, manager.last_result.reason) == ("crashed", "exit-code-3")
    assert not crash_record.path().exists()
    report = _new_report(before)
    crashed = next(check for check in report["checks"] if check["name"] == f"{LABEL}:video")
    assert crashed == {"name": f"{LABEL}:video", "result": "fail", "reason": "crashed", "numbers": {"exit_code": 3}}
    assert failures == [f"{LABEL}:video"]
    manager.shutdown()


def test_a_record_found_at_launch_is_an_incomplete_report_and_a_failure_of_its_pair_only(failures):
    crash_record.write({"level": "quick", "pair": {"execution_provider": EP, "device_key": DEVICE},
                        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "message": RUNNING})
    before = _crashed_reports()
    manager = _manager()
    assert not crash_record.path().exists()
    assert manager.last_result == CertificationResult(EP, DEVICE, "fail", "crashed")
    assert not manager.running and manager.run is None  # nothing runs again by itself
    assert failures == [f"{LABEL}:video"]
    report = _new_report(before)
    assert [(check["name"], check["result"], check["reason"]) for check in report["checks"]] == [
        ("cpu:video", "pass", None), ("cpu:live", "not-run", "reason-lost"), (f"{LABEL}:probe", "pass", None),
        (f"{LABEL}:video", "fail", "crashed"), (f"{LABEL}:live", "not-run", "interrupted"), (LABEL, "not-run", "interrupted")]
    assert report["package"]["name"] == "skellytracker" and report["evidence"]["valid"] is False
    assert "test_media" not in report  # skellytracker's progress does not tell which file its checks read
    _, data = report_file_for([report["id"]], None)
    text = data.decode("utf-8")
    assert "skellytracker" in text and "quick run · incomplete · not valid as evidence:" in text
    assert f"| skellytracker | | {LABEL}:video | fail | crashed |" in text


def test_a_start_check_found_at_launch_releases_the_gated_starts(failures):
    message = {**RUNNING, "package": "freemocap", "step": {"name": "posthoc-session"},
               "checks": [{"name": "build-identity", "result": "pass"}, {"name": "posthoc-session", "result": None},
                          {"name": "blender", "result": None}]}
    crash_record.write({"level": "quick", "pair": None, "created_utc": "2026-11-20T10:00:00Z", "message": message})
    before = _crashed_reports()
    manager = _manager()
    manager.refresh()
    assert manager.start_results == (StartCheckResult("freemocap", "fail", "crashed"),)
    assert manager.start_released and not manager.start_required and not manager.running
    assert failures == ["posthoc-session"]  # no pair: `record_provider_failure` stores nothing for it (next test)
    report = _new_report(before)
    assert [check["result"] for check in report["checks"]] == ["pass", "fail", "not-run"]
    assert report["test_media"] == [certification._frames_media()]  # the crashed session had its frames (format 3.9)
    # owner, Q59: not asked for again until a package version changes; the report stays in the hand-in list
    record = json.loads(start_check.record_path().read_text(encoding="utf-8"))
    assert (record["versions"], record["crashed"]) == (start_check.version_set(), "posthoc-session")
    assert start_check.start_check_needed() is False
    start_check.record_path().write_text(json.dumps({**record, "versions": {**record["versions"], "freemocap": "0.0.0"}}),
                                         encoding="utf-8")
    assert start_check.start_check_needed() is start_check._has_checks()  # a new version set: asked for again


def test_a_start_check_that_crashed_in_skellytrackers_part_is_asked_for_again(failures):
    crash_record.write({"level": "quick", "pair": None, "created_utc": "2026-11-20T10:00:00Z", "message": RUNNING})
    _manager()
    assert not start_check.record_path().exists()


def test_a_crashed_gpu_check_is_skellytrackers_failed_quick_check_of_that_pair(monkeypatch, tmp_path):
    from skellytracker.core.eps import gate, store
    monkeypatch.setenv(store.STORE_VARIABLE, str(tmp_path))  # not the suite's store: other tests read this GPU's result
    from skellytracker.core.eps.catalog import load_catalog
    from skellytracker.core.system import host as host_module
    from skellytracker.core.system.records import GpuInfo
    gpu = GpuInfo(key="0000:01:00.0", vendor="nvidia", pci_bus_id="0000:01:00.0", pci_vendor_id=0x10de,
                  pci_device_id=0x2484)
    other = GpuInfo(key="0000:02:00.0", vendor="nvidia", pci_bus_id="0000:02:00.0", pci_vendor_id=0x10de,
                    pci_device_id=0x2204)
    monkeypatch.setattr(host_module, "gpu_device_keys", lambda host=None: (("gpu:10de:2484:0", gpu), ("gpu:10de:2204:0", other)))
    catalog, os_name = load_catalog(), host_module.probe_host().os_name
    key = next(key for key in catalog.keys() if catalog.device_row(key) is not None)  # a GPU EP of skellytracker's catalog
    crash_record.record_provider_failure("cpu:video", "2026-11-20T10:00:00Z")  # no pair: nothing stored
    crash_record.record_provider_failure("posthoc-session", "2026-11-20T10:00:00Z")
    assert gate.local_result(catalog, key, gpu, os_name) is None
    crash_record.record_provider_failure(f"{key}@10de-2484-0:video", "2026-11-20T10:00:00Z")
    assert gate.local_result(catalog, key, gpu, os_name) == "failed"
    assert gate.check_reason(catalog, key, gpu, os_name) == "quick-check-failed"
    assert gate.local_result(catalog, key, other, os_name) is None  # its provider on this GPU only
