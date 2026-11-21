"""freemocap's level full, the benchmark on the sample recording (fifth grilling, "Full benchmark"): its plan, its checks
with stand-ins for the download, the post-hoc sessions and Blender, the clean-up rules, and the options that
`run_full_check` passes. Nothing is downloaded and no session runs: the archive is a tiny recording made here."""
import hashlib
import io
import multiprocessing
import zipfile
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from freemocap import certification
from freemocap.system.certify import start_check
from freemocap.tools.datasets.catalog import download as real_download  # before the guard and the stand-in wrap it

PAIRS = [("fake-ep@10de-2484-0", "fake-ep", "gpu:10de:2484:0", "Fake EP"), ("cpu", "cpu", None, "CPU")]
STAGES = {"inference.process_batch.images=3": {"total_s": 0.3, "ms_per_frame": 100.0, "fps": 10.0},
          "graph.load_and_track": {"total_s": 0.6, "ms_per_frame": 200.0, "fps": 5.0},
          "graph.annotate_camera_0": {"total_s": 0.1, "ms_per_frame": 33.3, "fps": 30.0}}


def _archive_bytes(folder: Path) -> bytes:
    """A recording of three cameras with four frames each and its calibration, zipped as the sample is."""
    source = folder / "freemocap_sample_data"
    (source / "synchronized_videos").mkdir(parents=True)
    (source / "freemocap_sample_data_camera_calibration.toml").write_text("[cam_0]\n")
    for camera in range(3):
        writer = cv2.VideoWriter(str(source / "synchronized_videos" / f"cam{camera}.mp4"), cv2.VideoWriter_fourcc(*"mp4v"),
                                 30.0, (64, 48))
        for _ in range(4):
            writer.write(np.zeros((48, 64, 3), np.uint8))
        writer.release()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(folder).as_posix())
    return buffer.getvalue()


@pytest.fixture
def bench(tmp_path, monkeypatch):
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(tmp_path / "data"))
    monkeypatch.setenv("FREEMOCAP_TEST_MEDIA_DIR", str(tmp_path / "media"))
    payload = _archive_bytes(tmp_path / "make")
    sha = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(certification, "SAMPLE_RECORDING", {**certification.SAMPLE_RECORDING, "bytes": len(payload), "sha256": sha})
    monkeypatch.setattr(certification, "BENCHMARK_FRAMES", 3)
    monkeypatch.setattr(certification, "_pairs", lambda: list(PAIRS))
    monkeypatch.setattr(certification, "_usable_labels", lambda: {"cpu"})  # the fake EP did not pass skellytracker's checks
    monkeypatch.setattr(certification, "_blender_path", lambda path: None)
    state = SimpleNamespace(media=tmp_path / "media", payload=payload, sha=sha, downloads=[], sessions=[], result="pass",
                            cancel=multiprocessing.Event())

    def download(url, path, cancelled=None):
        state.downloads.append(url)
        path.write_bytes(state.payload)
        return hashlib.sha256(state.payload).hexdigest()

    def benchmark(cancelled, recording, label, key, device_key):
        frames = [int(cv2.VideoCapture(str(video)).get(cv2.CAP_PROP_FRAME_COUNT))
                  for video in sorted((recording / "synchronized_videos").glob("*.mp4"))]
        state.sessions.append((label, key, device_key, frames, sorted(path.name for path in recording.iterdir())))
        (recording.parent / label).mkdir()  # its processing output
        if state.result == "cancel":
            state.cancel.set()
            return "not-run", "cancelled", None
        return state.result, None if state.result == "pass" else "session-failed", {"frames": 3, "stages": STAGES}

    monkeypatch.setattr("freemocap.tools.datasets.catalog.download", download)
    monkeypatch.setattr(certification, "_benchmark", benchmark)
    return state


def _counted(names) -> int:
    return sum(name.count(":") <= 1 for name in names)  # the count rule of the full benchmark (`_counted`)


def test_the_full_plan_lists_the_download_until_the_archive_is_in_the_test_media_folder(bench):
    plan = certification.certify_plan("full", test_media_dir=bench.media)
    names = ["data-folder", "recording", "posthoc:fake-ep@10de-2484-0", "posthoc:cpu", "blender"]
    assert plan["details"]["checks"] == names and plan["total"] == _counted(names) == 5
    [item] = plan["downloads"]
    assert item == {"name": "freemocap_sample_data.zip", "bytes": len(bench.payload), "sha256": bench.sha,
                    "source": "https://github.com/freemocap/skellysamples/releases/download/sample_data_v06_12_25/freemocap_sample_data.zip"}
    assert plan["risks"] == [] and plan["seconds_estimate"] == (certification.DOWNLOAD_SECONDS + certification.PREPARE_SECONDS
                                                                + 2 * certification.PAIR_SECONDS)
    assert not bench.media.exists(), "the plan downloads nothing and writes nothing"
    bench.media.mkdir()
    (bench.media / f"{bench.sha}.zip").write_bytes(bench.payload)
    present = certification.certify_plan("full", test_media_dir=bench.media)
    assert present["downloads"] == [] and present["seconds_estimate"] == plan["seconds_estimate"] - certification.DOWNLOAD_SECONDS


def test_a_successful_run_benchmarks_the_usable_pairs_and_removes_only_what_it_downloaded_and_wrote(bench):
    bench.media.mkdir()
    (bench.media / "kept-before.zip").write_bytes(b"another package's file")
    plan = certification.certify_plan("full", test_media_dir=bench.media)
    report = certification.certify("full", None, None, test_media_dir=bench.media, remove_data=True)
    rows = {row["name"]: row for row in report["checks"]}
    assert [(name, row["result"], row["reason"]) for name, row in rows.items()] == [
        ("data-folder", "pass", None), ("recording", "pass", None), ("posthoc:fake-ep@10de-2484-0", "not-run", "ep-not-passed"),
        ("posthoc:cpu", "pass", None), ("blender", "not-run", "not-installed")]
    assert _counted(rows) == plan["total"] and all(row["result"] for row in rows.values())
    assert (rows["posthoc:cpu"]["module"], rows["blender"]["module"]) == ("CPU", "Blender")
    assert rows["recording"]["numbers"]["downloaded"] is True and len(bench.downloads) == 1
    [(label, key, device, frames, files)] = bench.sessions
    assert (label, key, device, frames) == ("cpu", "cpu", None, [3, 3, 3])  # the cut recording, in the sample's codec
    assert files == ["freemocap_sample_data_camera_calibration.toml", "synchronized_videos"]
    assert report["summary"] == [{"group": "benchmark", "name": "CPU", "device": None, "stage": "inference",
                                  "ms_per_frame": 100.0, "fps": 10.0},
                                 {"group": "benchmark", "name": "CPU", "device": None, "stage": "tracking",
                                  "ms_per_frame": 200.0, "fps": 5.0}]
    assert report["cleanup"] == [] and not {"partial-run", "cancelled"} & set(report["evidence"]["reasons"])
    assert sorted(path.name for path in bench.media.iterdir()) == ["kept-before.zip"]  # the download is gone
    assert not certification._work().exists(), "the processing output is gone"
    assert [path.name for path in certification.reports_dir().iterdir()] == [f"{report['id']}.json"]  # the report stays


@pytest.mark.parametrize("ending", ["fail", "cancel", "keep"])
def test_a_failed_or_cancelled_run_or_no_clean_up_choice_removes_nothing(bench, ending):
    bench.result = ending if ending != "keep" else "pass"
    report = certification.certify("full", None, bench.cancel, test_media_dir=bench.media, remove_data=ending != "keep")
    assert (bench.media / f"{bench.sha}.zip").is_file() and (certification._work() / "cpu").is_dir()
    assert report["cleanup"] == []
    if ending == "cancel":
        assert "cancelled" in report["evidence"]["reasons"]
        assert {row["name"]: row["result"] for row in report["checks"]}["blender"] == "not-run"


def test_an_archive_that_was_there_before_stays_and_one_with_a_wrong_hash_is_never_used(bench):
    bench.media.mkdir()
    archive = bench.media / f"{bench.sha}.zip"
    archive.write_bytes(bench.payload)
    report = certification.certify("full", None, None, test_media_dir=bench.media, remove_data=True)
    assert report["checks"][1]["numbers"]["downloaded"] is False and bench.downloads == []
    assert archive.is_file() and not certification._work().exists()
    archive.write_bytes(b"not the recording")
    report = certification.certify("full", None, None, test_media_dir=bench.media, remove_data=True)
    assert [(row["name"], row["result"], row["reason"]) for row in report["checks"][1:4]] == [
        ("recording", "fail", "bad-hash"), ("posthoc:fake-ep@10de-2484-0", "not-run", "recording-missing"),
        ("posthoc:cpu", "not-run", "recording-missing")]
    assert archive.read_bytes() == b"not the recording", "a file that was there before is never removed"
    archive.unlink()
    bench.payload = b"a download with the wrong hash"
    report = certification.certify("full", None, None, test_media_dir=bench.media)
    assert (report["checks"][1]["result"], report["checks"][1]["reason"]) == ("fail", "bad-hash")
    assert list(bench.media.iterdir()) == [], "a wrong or partial download is not kept"


def test_the_benchmark_session_reads_the_post_hoc_timings_as_the_dataset_tools_do(tmp_path, monkeypatch):
    from freemocap.core.pipeline.performance_report import PerformanceReport
    recording = tmp_path / "recording"
    recording.mkdir()
    (recording / "calibration.toml").write_text("")
    monkeypatch.setattr(certification, "_models_missing", lambda *args: False)
    monkeypatch.setattr(certification, "_providers", lambda recording: {"person": "cpu", "wholebody": "cpu"})

    def session(path, config):
        assert (config.execution_provider, config.execution_device, config.export_to_blender) == ("cpu", None, False)
        assert config.calibration_toml_path == str(recording / "calibration.toml")
        performance = PerformanceReport()
        performance.frames, performance.images = 300, 900
        performance.record("inference.session_setup", 1.5)
        performance.record("graph.load_and_track", 30.0)
        performance.log(pipeline_id="certify", outcome="complete")
        return True

    monkeypatch.setattr(certification, "_session", session)
    numbers = certification._benchmark_session(recording, "cpu", None)["numbers"]
    assert numbers["stages"]["graph.load_and_track"] == {"total_s": 30.0, "ms_per_frame": 100.0, "fps": 10.0}
    assert (numbers["frames"], numbers["images"], numbers["startup_seconds"]) == (300, 900, 1.5)
    assert numbers["execution_providers"] == {"person": "cpu", "wholebody": "cpu"}


def test_the_full_check_passes_the_test_media_folder_and_the_clean_up_choice_only_after_earlier_success(bench):
    calls = []

    def tracker(result):
        def certify(level, progress, cancel, **options):
            calls.append(("skellytracker", options))
            return {"checks": [{"name": "cpu:video", "result": result}], "evidence": {"reasons": []}}
        return certify

    def own(level, progress, cancel, **options):
        calls.append(("freemocap", options))
        return {"checks": [{"name": "recording", "result": "pass"}], "evidence": {"reasons": []}}

    media = str(bench.media)
    for result, removes in (("pass", True), ("fail", False)):
        calls.clear()
        start_check.run_full_check(lambda message: None, multiprocessing.Event(), remove_data=True, own_certify=own,
                                   certify=tracker(result), blender_exe_path="C:/chosen/blender.exe")
        assert calls == [("skellytracker", {"test_media_dir": media}),  # the Blender path chosen in settings is freemocap's
                         ("freemocap", {"test_media_dir": media, "blender_exe_path": "C:/chosen/blender.exe",
                                        "remove_data": removes})]
    from skellytracker.core.eps.certification import frames_record
    assert (bench.media / f"{frames_record()['sha256']}.zip").is_file(), "skellytracker's bundled frames, where it reads them"


class _Response:
    """`requests.get(..., stream=True)` of a download whose chunks come from `chunks()`: nothing leaves this machine."""
    def __init__(self, chunks):
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield from self.chunks()


@pytest.mark.parametrize("ending", ["broken", "cancel"])
def test_a_download_that_breaks_or_is_cancelled_keeps_no_partial_file_and_removes_nothing(bench, monkeypatch, ending):
    """The real `catalog.download` on a stand-in for `requests.get`: a broken download fails `recording` and leaves the
    pairs `not-run`; a cancel stops it between chunks; neither keeps a partial file or removes anything."""
    import time
    import requests

    def chunks():
        yield b"part of the archive"
        if ending == "broken":
            raise requests.ConnectionError("the connection dropped")
        bench.cancel.set()
        while True:
            yield b"more"

    monkeypatch.setattr("freemocap.tools.datasets.catalog.download", real_download)
    monkeypatch.setattr(requests, "get", lambda url, **options: _Response(chunks))
    bench.media.mkdir()
    (bench.media / "kept-before.zip").write_bytes(b"another package's file")
    certification._work().mkdir(parents=True)  # an earlier run's work folder
    started = time.monotonic()
    report = certification.certify("full", None, bench.cancel, test_media_dir=bench.media, remove_data=True)
    assert time.monotonic() - started < 5, "a cancel during the download ends the run promptly"
    results = [(row["name"], row["result"], row["reason"]) for row in report["checks"]]
    if ending == "broken":
        assert results == [("data-folder", "pass", None), ("recording", "fail", "ConnectionError"),
                           ("posthoc:fake-ep@10de-2484-0", "not-run", "recording-missing"),
                           ("posthoc:cpu", "not-run", "recording-missing"), ("blender", "not-run", "not-installed")]
    else:
        assert results[1:] == [("recording", "not-run", "cancelled"), ("posthoc:fake-ep@10de-2484-0", "not-run", "cancelled"),
                               ("posthoc:cpu", "not-run", "cancelled"), ("blender", "not-run", "cancelled")]
        assert "cancelled" in report["evidence"]["reasons"]
    assert sorted(path.name for path in bench.media.iterdir()) == ["kept-before.zip"], "no partial or final archive"
    assert report["cleanup"] == [] and certification._work().is_dir(), "a failed or cancelled run removes nothing"
    assert bench.sessions == []
