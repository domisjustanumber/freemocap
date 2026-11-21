"""freemocap's `posthoc-session` quick check: its not-run reasons, the time budget, its spawn child's failures and the
removal of its work folder. The pass path on the real frames and models is in test_start_check.py."""
import os
import time
from types import SimpleNamespace

import pytest

from freemocap import certification


def crash(queue):  # module-level: the spawn child imports it
    os._exit(3)


def hang(queue):
    time.sleep(60)


def session_child(queue, ended: str):  # a pair child: it ends its session when asked, as `_session` does
    while not certification._stopping():
        time.sleep(0.02)
    open(ended, "w").close()


@pytest.fixture
def quick(tmp_path, monkeypatch):
    """`certify("quick")` with the spawn child and Blender stood in; each call gives the rows by name and the report."""
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(tmp_path))
    monkeypatch.setattr(certification, "_spawn_imports", lambda cancelled: ({"failed": [], "from_bundle": None}, None))
    monkeypatch.setattr(certification, "_blender", lambda cancelled, path=None: ("not-run", "not-installed", {"found": False}))

    def run():
        report = certification.certify("quick")
        return {row["name"]: row for row in report["checks"]}, report
    return run


def answer(result, reason=None):
    return lambda target, args, name, timeout, cancelled: ({"result": result, "reason": reason}, None)


def test_models_missing_is_not_run_and_does_not_fail_the_module(quick, monkeypatch, tmp_path):
    import skellytracker.core.pipelines as pipelines
    monkeypatch.setattr(pipelines, "check_pipeline", lambda config: SimpleNamespace(warnings=[SimpleNamespace(code="missing_dependency")]))
    assert certification._posthoc_session([], tmp_path) == {"result": "not-run", "reason": "models-missing"}
    monkeypatch.setattr(certification, "_spawn", answer("not-run", "models-missing"))
    rows, report = quick()
    assert (rows["posthoc-session"]["result"], rows["posthoc-session"]["reason"]) == ("not-run", "models-missing")
    assert certification.module_result(report) == ("pass", None) and report["test_media"] == []  # it used no frame
    assert sorted(path.name for path in (tmp_path / "certify").iterdir()) == ["reports"], "the work folder is removed"


def test_missing_or_damaged_frames_are_test_media_missing(quick, monkeypatch):
    import skellytracker.certification
    from skellytracker.core.eps.certification import FramesUnavailableError

    def unavailable(test_media_dir=None):
        raise FramesUnavailableError("absent")
    monkeypatch.setattr(skellytracker.certification, "certify_frames", unavailable)
    rows, report = quick()
    assert (rows["posthoc-session"]["result"], rows["posthoc-session"]["reason"]) == ("not-run", "test-media-missing")
    assert certification.module_result(report) == ("pass", None) and report["test_media"] == []


@pytest.mark.parametrize("ending", [(None, "crashed"), ({"result": "pass", "reason": None}, None)])
def test_the_frames_file_the_session_ran_on_is_listed_with_the_hash_of_the_bytes_of_its_frames(quick, monkeypatch, ending):
    """Format 3.9 (owner: "it's very important to know which files the test ran on"): the frames given to the session's
    child are the first frames of the bundled file whose SHA-256 and size `test_media` lists, computed here from its bytes."""
    import hashlib
    import io
    import zipfile
    from skellytracker.core.eps.certification import frames_file, frames_record
    given = []
    monkeypatch.setattr(certification, "_spawn", lambda target, args, *rest: given.append(args[0]) or ending)
    rows, report = quick()
    data = frames_file({"frames": frames_record()})  # the bundled file, as skellytracker reads it
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert given == [[archive.read(name) for name in sorted(archive.namelist())][:certification.POSTHOC_FRAMES]]
    assert report["test_media"] == [{"name": "quick_frames.zip", "sha256": hashlib.sha256(data).hexdigest(),
                                     "bytes": len(data), "source": "bundled"}]


def test_a_session_that_does_not_fit_the_budget_is_over_budget_and_not_started(quick, monkeypatch):
    monkeypatch.setattr(certification, "QUICK_BUDGET_SECONDS", certification.POSTHOC_SECONDS - 1)
    monkeypatch.setattr(certification, "_spawn", lambda *args: pytest.fail("started"))
    rows, report = quick()
    assert (rows["posthoc-session"]["result"], rows["posthoc-session"]["reason"]) == ("not-run", "over-budget")
    assert report["test_media"] == []
    assert certification.module_result(report) == ("pass", None)


@pytest.mark.parametrize("reason", ["crashed", "timed-out", "hung-at-exit"])
def test_a_child_that_gives_no_answer_fails_the_check_with_its_reason(quick, monkeypatch, reason):
    monkeypatch.setattr(certification, "_spawn", lambda *args: (None, reason))
    rows, report = quick()
    assert (rows["posthoc-session"]["result"], rows["posthoc-session"]["reason"]) == ("fail", reason)
    assert certification.module_result(report) == ("fail", "posthoc-session")


def test_the_spawn_child_reports_a_crash_and_a_time_out():
    assert certification._spawn(crash, (), "freemocap-certify-test", 30, lambda: False) == (None, "crashed")
    started = time.monotonic()
    assert certification._spawn(hang, (), "freemocap-certify-test", 1, lambda: False) == (None, "timed-out")
    assert time.monotonic() - started < 30


def test_a_cancel_lets_the_child_end_its_session_itself_and_kills_one_that_does_not(tmp_path):
    """A kill of a session's worker counts as an unclean exit of its EP in skellytracker; the child ends it first."""
    ended, started = tmp_path / "ended", time.monotonic()
    cancelled = lambda: time.monotonic() - started > 0.5  # noqa: E731
    assert certification._spawn(session_child, (str(ended),), "freemocap-certify-test", 30, cancelled) == (None, "cancelled")
    assert ended.exists(), "the child ended by itself, not by a kill"
    started = time.monotonic()
    assert certification._spawn(hang, (), "freemocap-certify-test", 30, cancelled) == (None, "cancelled")
    assert time.monotonic() - started < 0.5 + certification.STOP_GRACE_SECONDS + 1.5


def test_a_work_folder_that_cannot_be_removed_is_a_cleanup_row(quick, monkeypatch):
    monkeypatch.setattr(certification, "_spawn", answer("pass"))
    monkeypatch.setattr(certification.shutil, "rmtree", lambda path: (_ for _ in ()).throw(PermissionError(path)))
    rows, report = quick()
    assert rows["posthoc-session"]["result"] == "pass"
    assert report["cleanup"] == [{"name": "posthoc-session:work-folder", "result": "fail", "reason": "PermissionError"}]


@pytest.mark.parametrize("abandoned", [True, False])
def test_an_abandon_ends_the_session_as_a_cancel_does_wins_over_the_cancel_and_keeps_no_report(quick, monkeypatch, tmp_path,
                                                                                              abandoned):
    """Format 1.6.0, 2.4: the caller is gone, so the run stops its session as for a cancel (the child ends it itself)
    and keeps no report; a cancel alone keeps its report of the checks that passed."""
    import threading
    abandon, cancel, ended = threading.Event(), threading.Event(), tmp_path / "ended"
    real = certification._spawn

    def spawn(target, args, name, timeout, cancelled):
        cancel.set()
        if abandoned:
            abandon.set()
        return real(session_child, (str(ended),), name, timeout, cancelled)
    monkeypatch.setattr(certification, "_spawn", spawn)
    report = certification.certify("quick", None, cancel, abandon=abandon)
    rows = {row["name"]: row for row in report["checks"]}
    assert (rows["posthoc-session"]["result"], rows["posthoc-session"]["reason"]) == ("not-run", "cancelled")
    assert rows["data-folder"]["result"] == "pass" and ended.exists(), "the session ended by itself, not by a kill"
    assert [path.name for path in certification.reports_dir().glob("*.json")] == ([] if abandoned else [f"{report['id']}.json"])
