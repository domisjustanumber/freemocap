"""freemocap's `posthoc-session` and `realtime-session` quick checks: their not-run reasons, the time budget, their
child's failures, the removal of the post-hoc work folder and the fresh copy of the app. The post-hoc pass path on the real
frames and models is in test_start_check.py; the realtime one is the `slow` test at the end."""
import json
import os
import sys
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
    monkeypatch.setattr(certification, "_fresh_app", lambda command, timeout, cancelled: (
        {"result": "not-run", "reason": "models-missing"}, None))

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
    assert (rows["realtime-session"]["result"], rows["realtime-session"]["reason"]) == ("not-run", "test-media-missing")
    assert certification.module_result(report) == ("pass", None) and report["test_media"] == []


@pytest.mark.parametrize("ending", [(None, "crashed"), ({"result": "pass", "reason": None}, None)])
@pytest.mark.parametrize("shared", [False, True])
def test_the_frames_file_the_session_ran_on_is_listed_with_the_hash_of_the_bytes_of_its_frames(quick, monkeypatch, tmp_path,
                                                                                               ending, shared):
    """Format 3.9 (owner: "it's very important to know which files the test ran on"): the frames given to the session's
    child are the first frames of the file whose SHA-256 and size `test_media` lists, computed here from its bytes: the
    shared folder's when it holds the file (`shared`, the file skellytracker's run reads too), else the package's."""
    import hashlib
    import io
    import zipfile
    from skellytracker.core.eps.certification import frames_file, frames_record
    data = frames_file({"frames": frames_record()})  # the bundled file, as skellytracker reads it
    media = tmp_path / "test-media"
    media.mkdir()
    if shared:
        (media / f"{hashlib.sha256(data).hexdigest()}.zip").write_bytes(data)
    given = []
    monkeypatch.setattr(certification, "_spawn", lambda target, args, *rest: given.append(args[0]) or ending)
    report = certification.certify("quick", test_media_dir=str(media))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert given == [[archive.read(name) for name in sorted(archive.namelist())][:certification.POSTHOC_FRAMES]]
    assert report["test_media"] == [{"name": "quick_frames.zip", "sha256": hashlib.sha256(data).hexdigest(),
                                     "bytes": len(data), "source": "shared" if shared else "bundled"}]


def test_a_session_that_does_not_fit_the_budget_is_over_budget_and_not_started(quick, monkeypatch):
    monkeypatch.setattr(certification, "QUICK_BUDGET_SECONDS", certification.POSTHOC_SECONDS - 1)
    monkeypatch.setattr(certification, "_spawn", lambda *args: pytest.fail("started"))
    monkeypatch.setattr(certification, "_fresh_app", lambda *args: pytest.fail("started"))
    rows, report = quick()
    assert (rows["posthoc-session"]["result"], rows["posthoc-session"]["reason"]) == ("not-run", "over-budget")
    assert (rows["realtime-session"]["result"], rows["realtime-session"]["reason"]) == ("not-run", "over-budget")
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
    # its child got the frames before the cancel: they are listed, as a crash record lists a crashed session's
    assert [item["name"] for item in report["test_media"]] == ["quick_frames.zip"]
    assert [path.name for path in certification.reports_dir().glob("*.json")] == ([] if abandoned else [f"{report['id']}.json"])


# - The realtime session check: its fresh copy of the app -

FRESH_APP = certification._fresh_app  # the real one: the `quick` fixture stands in for it


def fresh(code: str, timeout=30, cancelled=lambda: False):
    """`_fresh_app` with a stand-in for the app: this interpreter running `code`."""
    return FRESH_APP([sys.executable, "-c", code], timeout, cancelled)


def ends_itself(ended) -> str:
    """A stand-in copy that ends by itself once its stdin closes, as `realtime_session_main` does."""
    return ("import pathlib, time\nfrom freemocap.certification import _stdin_closed\n"
            "while not _stdin_closed(): time.sleep(0.02)\n"
            f"pathlib.Path({str(ended)!r}).write_text('')\n")


@pytest.fixture
def short_grace(monkeypatch):
    monkeypatch.setattr(certification, "REALTIME_STOP_GRACE_SECONDS", 0.5)


def test_the_fresh_copy_is_a_main_process_and_its_json_line_among_other_output_is_its_answer():
    """A spawn child fails the guard of `PubSubTopicManager.create`; a fresh copy has no multiprocessing parent."""
    code = ("import json, multiprocessing; print('a line of a library'); print('{not json'); "
            "print(json.dumps({'result': 'pass', 'reason': None, 'main': multiprocessing.parent_process() is None}))")
    assert fresh(code) == ({"result": "pass", "reason": None, "main": True}, None)


@pytest.mark.parametrize("code,reason", [
    ("import os; os._exit(3)", "crashed"),
    ("import json, os; print(json.dumps({'result': 'pass', 'reason': None}), flush=True); os._exit(1)", "crashed"),
    ("import time; time.sleep(60)", "timed-out")])
def test_a_fresh_copy_with_no_answer_or_a_bad_exit_gives_its_reason(short_grace, code, reason):
    started = time.monotonic()
    assert fresh(code, timeout=2) == (None, reason)
    assert time.monotonic() - started < 2 + 0.5 + 3


def test_a_cancel_closes_the_copys_stdin_so_it_ends_by_itself_and_one_that_does_not_is_killed(tmp_path, short_grace):
    """A kill of the copy while its models are loaded on a GPU EP counts as an unclean exit in skellytracker; the copy
    polls `_stdin_closed` (a peek: a blocked read stalls DLL loading on Windows) and ends by itself."""
    ended, started = tmp_path / "ended", time.monotonic()
    cancelled = lambda: time.monotonic() - started > 0.5  # noqa: E731
    assert fresh(ends_itself(ended), cancelled=cancelled) == (None, "cancelled")
    assert ended.exists(), "the copy ended by itself, not by a kill"
    started = time.monotonic()
    assert fresh("import time; time.sleep(60)", cancelled=cancelled) == (None, "cancelled")
    assert time.monotonic() - started < 0.5 + 0.5 + 3


def test_the_app_command_is_the_built_executable_or_python_dash_m_freemocap(monkeypatch):
    assert certification._app_command("--certify-realtime", "media") == [sys.executable, "-m", "freemocap",
                                                                         "--certify-realtime", "media"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert certification._app_command("--certify-realtime") == [sys.executable, "--certify-realtime"]


@pytest.mark.parametrize("argv,folder", [(["--certify-realtime"], None), (["--certify-realtime", "media"], "media")])
def test_the_start_mode_runs_only_the_realtime_check_and_no_server(monkeypatch, argv, folder):
    import asyncio
    import freemocap.__main__ as entry
    ran = []
    monkeypatch.setattr(sys, "argv", ["freemocap", *argv])
    monkeypatch.setattr(certification, "realtime_session_main", ran.append)
    monkeypatch.setattr(asyncio, "run", lambda *args, **kwargs: pytest.fail("the server started"))
    entry.run_main()
    assert ran == [folder]


@pytest.mark.parametrize("session", [lambda frames, stopping: {"result": "pass", "reason": None, "numbers": {"frames": len(frames)}},
                                     lambda frames, stopping: 1 / 0])
def test_the_copy_prints_its_answer_as_one_json_line_after_its_exit_notice(monkeypatch, capsys, session):
    import skellytracker
    notices = []
    monkeypatch.setattr(certification, "_realtime_session", session)
    monkeypatch.setattr(skellytracker, "note_exit_requested", lambda: notices.append(True))  # it would change this process
    certification.realtime_session_main(None)
    [line] = capsys.readouterr().out.splitlines()
    assert json.loads(line) in ({"result": "pass", "reason": None, "numbers": {"frames": certification.REALTIME_FRAMES}},
                                {"result": "fail", "reason": "ZeroDivisionError"})
    assert notices == [True]


@pytest.mark.parametrize("posthoc", ["pass", "models-missing"])
def test_a_realtime_pass_has_its_numbers_and_the_frames_file_is_listed_once(quick, monkeypatch, tmp_path, posthoc):
    commands = []
    numbers = {"frames": 4, "tracked_frames": 3, "session_seconds": 5.4, "execution_providers": {"person": "x"}}
    monkeypatch.setattr(certification, "_spawn", answer(*(("pass",) if posthoc == "pass" else ("not-run", posthoc))))
    monkeypatch.setattr(certification, "_fresh_app", lambda command, timeout, cancelled: commands.append(command) or (
        {"result": "pass", "reason": None, "numbers": numbers}, None))
    report = certification.certify("quick", test_media_dir=str(tmp_path))
    rows = {row["name"]: row for row in report["checks"]}
    assert commands == [certification._app_command("--certify-realtime", str(tmp_path))]
    assert rows["realtime-session"]["result"] == "pass" and rows["realtime-session"]["module"] == "Realtime session"
    assert {key: value for key, value in rows["realtime-session"]["numbers"].items() if key != "seconds"} == numbers
    assert report["test_media"] == [certification._frames_media(str(tmp_path))]
    assert {"group": "component", "name": "Realtime session", "device": None, "result": "pass"} in report["summary"]


@pytest.mark.parametrize("ending,expected", [((None, "crashed"), ("fail", "crashed")), ((None, "timed-out"), ("fail", "timed-out")),
                                             (({"result": "fail", "reason": "untracked"}, None), ("fail", "untracked"))])
def test_a_realtime_copy_that_fails_fails_the_module_and_lists_the_frames(quick, monkeypatch, ending, expected):
    monkeypatch.setattr(certification, "_spawn", answer("not-run", "models-missing"))
    monkeypatch.setattr(certification, "_fresh_app", lambda command, timeout, cancelled: ending)
    rows, report = quick()
    assert (rows["realtime-session"]["result"], rows["realtime-session"]["reason"]) == expected
    assert certification.module_result(report) == ("fail", "realtime-session")
    assert [item["name"] for item in report["test_media"]] == ["quick_frames.zip"]


def test_a_realtime_check_that_does_not_fit_what_is_left_of_the_budget_is_over_budget(quick, monkeypatch):
    monkeypatch.setattr(certification, "_spawn", answer("pass"))
    monkeypatch.setattr(certification, "REALTIME_SECONDS", certification.QUICK_BUDGET_SECONDS + 1)
    monkeypatch.setattr(certification, "_fresh_app", lambda *args: pytest.fail("started"))
    rows, report = quick()
    assert rows["posthoc-session"]["result"] == "pass"
    assert (rows["realtime-session"]["result"], rows["realtime-session"]["reason"]) == ("not-run", "over-budget")
    assert certification.module_result(report) == ("pass", None)


@pytest.mark.parametrize("abandoned", [True, False])
def test_a_cancel_or_abandon_ends_the_realtime_copy_by_itself_and_lists_its_frames(quick, monkeypatch, tmp_path, abandoned):
    import threading
    abandon, cancel, ended = threading.Event(), threading.Event(), tmp_path / "ended"

    def fresh_app(command, timeout, cancelled):
        cancel.set()
        if abandoned:
            abandon.set()
        return FRESH_APP([sys.executable, "-c", ends_itself(ended)], timeout, cancelled)
    monkeypatch.setattr(certification, "_spawn", answer("not-run", "models-missing"))
    monkeypatch.setattr(certification, "_fresh_app", fresh_app)
    report = certification.certify("quick", None, cancel, abandon=abandon)
    rows = {row["name"]: row for row in report["checks"]}
    assert (rows["realtime-session"]["result"], rows["realtime-session"]["reason"]) == ("not-run", "cancelled")
    assert ended.exists(), "the copy ended by itself, not by a kill"
    assert [item["name"] for item in report["test_media"]] == ["quick_frames.zip"]  # the copy may have read them
    assert [path.name for path in certification.reports_dir().glob("*.json")] == ([] if abandoned else [f"{report['id']}.json"])


def test_an_interrupted_run_lists_the_frames_once_for_either_session():
    for results in ({"realtime-session": "fail"}, {"posthoc-session": "pass", "realtime-session": "pass"}):
        assert certification.interrupted_media([{"name": name, "result": result} for name, result in results.items()]) == [
            certification._frames_media(None)]
    assert certification.interrupted_media([{"name": "realtime-session", "result": "not-run"}]) == []


@pytest.mark.slow
def test_the_realtime_check_runs_the_apps_realtime_session_in_a_fresh_copy_and_leaves_no_process(tmp_path, monkeypatch):
    """The real check on skellytracker's bundled frames and models (about 9 s on CPU): a fresh copy of the app, its
    realtime pipeline on the stand-in camera group, and no process of it left behind."""
    import psutil
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(tmp_path))
    before = {process.pid for process in psutil.Process().children(recursive=True)}
    media: list = []
    result, reason, numbers = certification._realtime(lambda: False, media)
    if reason == "models-missing":
        pytest.skip("an installed skellytracker without its model files")
    assert (result, reason) == ("pass", None), numbers
    assert numbers["frames"] >= 2 and 1 <= numbers["tracked_frames"] <= certification.REALTIME_TRACKED
    assert set(numbers["execution_providers"]) == {"person", "wholebody"}
    assert media == [certification._frames_media(None)]
    assert {process.pid for process in psutil.Process().children(recursive=True)} <= before
