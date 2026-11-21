"""freemocap's own certify checks (skellycertify report format 1.6.0; ep-certification-integration.md, "freemocap's own
checks"): only what freemocap owns. No check uses a camera. Only `posthoc-session` loads models, on the EP that the app
selects by default, and it runs on skellytracker's bundled test frames (`certify_frames`), downloading none.

    import freemocap
    plan = freemocap.certify_plan("quick")          # show the plan, then get the consent of the person
    report = freemocap.certify("quick", progress=show, cancel=event)

`certify(level, progress, cancel, *, ui_remote=None, blender_exe_path=None)` returns freemocap's module report;
`certify_plan(level)` takes the same options and gives its plan. `import freemocap` does not import this module: the
two names load it on first use. The level `quick` runs the seven checks below within `QUICK_BUDGET_SECONDS`.

The level `full` (fifth grilling, "Full benchmark") is the end-to-end post-hoc benchmark on the freemocap sample
recording: `data-folder` (write access only), `recording` (the archive `<sha256>.zip` in the shared test media folder,
report format 2.8, downloaded only when absent; extracted and cut to `BENCHMARK_FRAMES` frames in freemocap's work folder
`<base data folder>/certify/benchmark`), one `posthoc:<label>` for each EP and GPU that skellytracker's full plan runs and
the CPU, each in its own spawn child through the app's post-hoc session (`MocapPipeline`, as `posthoc-session`), then
`blender` (the app's Blender export of one finished recording, only when Blender is installed). The pairs run in the
staging order: no reviewed pass first, then the known-fastest (the first reviewed pair in skellytracker's preference
order), then the CPU, then the rest. A pair runs only when skellytracker's status calls it usable after skellytracker's
own run (a pass in this run or a reviewed pass, and no failed check here). Timings are summary items of the group
`benchmark` (ms/frame and FPS of each stage, measured by the post-hoc session's `PerformanceReport` and read with the
dataset tools' `parse_performance` and `normalized_stages`); a slow result never fails. ms/frame is the stage's total time
over the run divided by the synchronized frames, so it is the time of one frame set, one frame of each camera of the
recording (three in the sample; format 3.7), and FPS is frame sets per second. With `remove_data` (the app passes
it only when the earlier packages succeeded), a run with no failed check and no cancel removes the work folder, and the
archive when this run downloaded it.

`posthoc-session` (report format 2.7 rule 3) proves freemocap's side around the tracker, in its own spawn child: the app's
post-hoc session (`MocapPipeline`, as the backend starts it) reads a 3-frame video of the bundled frames, hands each frame
to skellytracker's run and writes the observations to the recording's Parquet file, from which the check reads the run
record back. skellytracker's own quick run proves its pipeline on these frames. A realtime session check is not built:
freemocap's pub/sub refuses to start a realtime pipeline outside the backend's main process, and certify runs in a child.

Each check of freemocap's own module has `module` set to the name of its part (`COMPONENTS`; a `posthoc:<label>` check
has the EP's name) and, when it ran, one summary item of the group `component` with its result (format 1.5.0, 3.7). A
check that did not run has no item, and neither has Blender when it is not installed.

freemocap's reason codes (report format 5.4), besides the common ones (`models-missing`, `test-media-missing`,
`over-budget`, `timed-out`, `crashed`, `hung-at-exit`):
- `spawn-failed`: the spawn child of `spawn-child` gave no answer, so the later checks did not run.
- `import-failed`: a module of the bundle did not import in the spawn child (`numbers.failed` names them).
- `not-found`: no Blender executable was found.
- `session-failed`: the post-hoc session ended without completing.
- `bad-hash`: the recording archive's SHA-256 is not the expected one (format 2.6); a downloaded one is deleted.
- `recording-missing`: the recording was not ready, so the post-hoc benchmarks and the Blender export did not run.
- `ep-not-passed`: skellytracker's status does not call the EP on that GPU usable after its checks of this run.
- `not-installed`: Blender is not installed ("Blender: not installed"); the benchmark never installs it.
- `reason-lost`: in the report of an interrupted run (`system/certify/crash_record.py`), a check that ended before the
  crash; the progress kept its result, not its reason.
- an exception class name, for example `PermissionError`: the step raised it (never its message).

The hand-in list, with the shapes of skellytracker's (`pending_reports`, `read_report`, `mark_reports`): `certify()`
keeps each report with a check that ended `pass` or `fail` in `<base data folder>/certify/reports/<id>.json`, and its
hand-in state in `<base data folder>/certify/hand-in.json`. A new quick report deletes each older report of a pass that
it repeats, when the person did not hand that report in. Until the commit of a freemocap build is on a pushed branch of
freemocap's public repository (report format 9), the reviewer treats its module as a record only (`commit-not-public`).
"""
import importlib
import importlib.util
import json
import logging
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from queue import Empty

import freemocap

logger = logging.getLogger(__name__)

SCHEMA = "skellycertify.report/1.6.0"  # `summary`: the `component` items, and at `full` the `benchmark` items
SCHEMA_PREFIX = "skellycertify.report/1."
REPORT_STATES = ("pending", "opened", "covered")  # as skellytracker's: `opened` = issue form opened, `covered` = an issue holds it
REPORT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")  # a safe file name only; ids are v4 UUIDs, never parsed
QUICK_CHECKS = ("build-identity", "spawn-child", "bundle-imports", "data-folder", "posthoc-session", "install-facts", "blender")
FULL_CHECKS = ("data-folder", "recording")  # then one `posthoc:<label>` for each pair, then `blender`
COMPONENTS = {"build-identity": "Build identity", "spawn-child": "Child process", "bundle-imports": "Bundle imports",
              "data-folder": "Data folder", "posthoc-session": "Post-hoc session", "install-facts": "Install facts",
              "recording": "Sample recording", "blender": "Blender"}  # check -> `module` and `component` item name
SAMPLE_RECORDING = {"name": "freemocap_sample_data.zip", "bytes": 166958457, "sha256":
                    "c23d6a24f9ed8cca74bccf171128543d661b47e5780df5b446d60063ac4acf4f"}  # its `source`: catalog.SAMPLE_DATA
# 300 frames (10 s of the 30 fps sample, three cameras): measured on one Windows PC (i7-14700K, RTX 3070, 2026-11-21), the CPU
# pair took 40 s from start to end (post-hoc session 35.8 s, its tracking 82 ms/frame), in the 30 to 60 s that the owner set.
BENCHMARK_FRAMES = 300
BENCHMARK_STAGES = (("inference.process_batch", "inference"), ("graph.load_and_track", "tracking"),
                    ("graph.match_and_triangulate", "triangulation"), ("graph.filter_trajectories", "filtering"),
                    ("graph.reconstruct_skeletons", "reconstruction"), ("graph.save_spatial", "saving"),
                    ("export.channel_exports", "exports"))  # PerformanceReport stage (name prefix) -> `stage` of the item
# Estimates from the same measurement: the download at about 8 MB/s (2.4 s there), the extraction and cut (5.4 s), one
# pair (24 s DirectML on the RTX 3070, 40 s CPU, 67 s DirectML on the UHD 770) and the Blender export (11.6 s).
DOWNLOAD_SECONDS, PREPARE_SECONDS, PAIR_SECONDS, BLENDER_SECONDS = 20, 10, 45, 20
PAIR_TIMEOUT_SECONDS, BLENDER_EXPORT_TIMEOUT_SECONDS = 600, 600
# skellytracker first: it sets ONNX Runtime's telemetry switch before onnxruntime is imported (decision 3).
BUNDLE_MODULES = ("numpy", "cv2", "pyarrow", "av", "scipy", "numba", "skellyforge", "skellytracker", "onnxruntime")
OPTIONAL_MODULES = ("numba",)  # imported only when shipped
SPAWN_TIMEOUT_SECONDS = 120
# A session child ends its pipeline cleanly in 0.6 to 1.3 s after a stop (RTX 3070, DirectML, 2026-11-21). A kill of its
# worker instead counts as an unclean exit of the EP in skellytracker; two in a row mark the EP as failed on this PC.
STOP_GRACE_SECONDS = 1.5
BLENDER_TIMEOUT_SECONDS = 30
QUICK_BUDGET_SECONDS = 25  # freemocap's share of the level quick (owner, Q53 to Q56; raised from 15 s, Q58)
POSTHOC_SECONDS = 10  # its estimate (8.5 to 9.1 s measured on one Windows PC, CPU): it starts only when it fits the budget
POSTHOC_TIMEOUT_SECONDS = 30
POSTHOC_FRAMES = 3
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _check_level(level: str) -> None:
    if level not in ("quick", "full"):
        raise ValueError(f"level must be 'quick' or 'full', not {level!r}")


def certify_plan(level: str, *, ui_remote: bool | None = None, blender_exe_path: str | None = None,
                 test_media_dir: str | os.PathLike | None = None, remove_data: bool = False) -> dict:
    """What `certify(level)` runs: no change outside freemocap's data folder and the test media folder, no question, no
    risk to a device. `total` counts the checks that run. At `quick`: its seven checks, no download, and the budget that
    `posthoc-session` keeps to. At `full`: its checks for the pairs of this system, the sample recording in `downloads`
    when it is not yet in the test media folder, and the measured estimate. It takes the options of `certify` (report
    format 2.2)."""
    _check_level(level)
    if level == "quick":
        return {"package": "freemocap", "kind": level, "seconds_estimate": QUICK_BUDGET_SECONDS, "total": len(QUICK_CHECKS),
                "risks": [], "downloads": [], "system_changes": [], "questions": [], "details": {"checks": list(QUICK_CHECKS)}}
    pairs = _pairs()
    names = _full_names(pairs)
    present = _archive(test_media_dir).is_file()
    seconds = (0 if present else DOWNLOAD_SECONDS) + PREPARE_SECONDS + PAIR_SECONDS * len(pairs) + \
        (BLENDER_SECONDS if _blender_path(blender_exe_path) else 0)
    return {"package": "freemocap", "kind": level, "seconds_estimate": seconds, "total": len(names), "risks": [],
            "downloads": [] if present else [_download_item()], "system_changes": [], "questions": [],
            "details": {"checks": names}}


def _download_item() -> dict:
    from freemocap.tools.datasets.catalog import SAMPLE_DATA
    return {**SAMPLE_RECORDING, "source": SAMPLE_DATA.url}


def _archive(test_media_dir) -> Path:
    """The sample recording's archive by the name rule of format 2.8; with no test media folder, in freemocap's own."""
    folder = Path(test_media_dir) if test_media_dir is not None else reports_dir().parent / "media"
    return folder / f"{SAMPLE_RECORDING['sha256']}.zip"


def _work() -> Path:
    return reports_dir().parent / "benchmark"


def _full_names(pairs: list[tuple]) -> list[str]:
    return [*FULL_CHECKS, *(f"posthoc:{label}" for label, *_ in pairs), "blender"]


def _pairs() -> list[tuple[str, str, str | None, str]]:
    """`(label, ep key, device key, module)` of each EP and GPU that skellytracker's full plan runs, and of the CPU, in the
    staging order (fifth grilling): no reviewed pass first, then the known-fastest, then the CPU, then the rest. The
    reviewed state is `DeviceCheck.certified`; the known-fastest is the first reviewed pair in the order of `status().eps`,
    which skellytracker gives as its order of preference. Core keeps no EP knowledge of its own."""
    import skellytracker
    from skellytracker.certification import SUMMARY_NAMES, _label  # shortcut: skellytracker's private label rule, as crash_record
    from freemocap.core.tracking.execution_providers import execution_provider_status
    details = skellytracker.certify_plan("full")["details"]
    runs = set(details["checks"]) - set(details["not_run"])
    rows = execution_provider_status().eps
    gpu = [(_label(row.key, check.device_key), row.key, check.device_key, SUMMARY_NAMES.get(row.key, row.key), check.certified)
           for row in rows for check in row.checks if _label(row.key, check.device_key) in runs]
    cpu = [(_label(row.key, None), row.key, None, SUMMARY_NAMES.get(row.key, row.key)) for row in rows
           if not row.uses_gpu and row.usable]
    unknown = [pair[:4] for pair in gpu if not pair[4]]
    known = [pair[:4] for pair in gpu if pair[4]]
    return [*unknown, *known[:1], *cpu, *known[1:]]


def _usable_labels() -> set[str]:
    """The labels that skellytracker's status calls usable now: after its checks of this run, its pass or a reviewed pass."""
    from skellytracker.certification import _label
    from freemocap.core.tracking.execution_providers import execution_provider_status
    rows = execution_provider_status().eps
    return {_label(row.key, check.device_key) for row in rows for check in row.checks if check.usable} | \
        {_label(row.key, None) for row in rows if not row.uses_gpu and row.usable}


def _blender_path(blender_exe_path: str | None) -> str | None:
    from freemocap.core.blender.runtime import executable
    try:
        return str(executable(blender_exe_path))
    except ValueError:
        return None


def _import_child(queue, modules: tuple[str, ...]) -> None:
    """The spawn child: import each module of the bundle and answer which failed and whether all came from the bundle."""
    failed, files = [], []
    for name in modules:
        if name in OPTIONAL_MODULES and importlib.util.find_spec(name) is None:
            continue
        try:
            files.append(getattr(importlib.import_module(name), "__file__", None))
        except Exception as error:  # noqa: BLE001 - the class name only
            failed.append(f"{name}-{type(error).__name__}")
    bundle = getattr(sys, "_MEIPASS", None)
    from_bundle = None if bundle is None else all(
        file is not None and Path(file).resolve().is_relative_to(Path(bundle).resolve()) for file in files)
    queue.put({"failed": failed, "from_bundle": from_bundle})


def _spawn_imports(cancelled) -> tuple[dict | None, str | None]:
    return _spawn(_import_child, (BUNDLE_MODULES,), "freemocap-certify-imports", SPAWN_TIMEOUT_SECONDS, cancelled)


_stop = None  # in a spawn child of `_spawn`: the event its parent sets to ask it to end


def _stopping() -> bool:
    return _stop is not None and _stop.is_set()


def _stoppable(target, stop, queue, *args) -> None:
    global _stop  # noqa: PLW0603 - one parent per spawn child
    _stop = stop
    target(queue, *args)


def _spawn(target, args: tuple, name: str, timeout: int | float, cancelled) -> tuple[dict | None, str | None]:
    """Run `target(queue, *args)` in a `spawn` child: (its answer, None) or (None, the reason it gave none). A child that
    is still alive at the end is asked to end (`_stopping()`), and after `STOP_GRACE_SECONDS` killed with the processes
    it started."""
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    stop = context.Event()
    child = context.Process(target=_stoppable, args=(target, stop, queue, *args), name=name)
    child.start()
    deadline, answer, reason = time.monotonic() + timeout, None, None
    try:
        while answer is None:
            try:
                answer = queue.get(timeout=0.2)
            except Empty:
                if cancelled():
                    reason = "cancelled"
                elif time.monotonic() > deadline:
                    reason = "timed-out"
                elif not child.is_alive():
                    reason = "crashed"
                if reason:
                    return None, reason
        child.join(timeout=10)
        return (answer, None) if child.exitcode == 0 else (None, "hung-at-exit" if child.is_alive() else "crashed")
    finally:
        if child.is_alive():
            stop.set()
            child.join(timeout=STOP_GRACE_SECONDS)
        if child.is_alive():
            import psutil
            try:
                descendants = psutil.Process(child.pid).children(recursive=True)  # a session's worker processes
            except psutil.Error:
                descendants = []
            child.kill()
            child.join()
            for process in descendants:
                try:
                    process.kill()
                except psutil.Error:
                    pass


# - The post-hoc session check, on skellytracker's bundled frames -

def _models_missing(detector_type: str, rtmpose_model_name: str | None) -> bool:
    """skellytracker's rule for its own `models-missing`: the pipeline check warns of a missing dependency."""
    from skellytracker.core.pipelines import check_pipeline
    from freemocap.core.tracking.pipeline_runs import load_detector_pipeline
    check = check_pipeline(load_detector_pipeline(detector_type, rtmpose_model_name))
    return any(warning.code == "missing_dependency" for warning in check.warnings)


def _posthoc_session(frames: list[bytes], work: Path) -> dict:
    """The app's post-hoc session on a recording of `frames` (JPEG bytes) in `work`, up to its observations (one
    camera: no calibration and no 3D), then the run record that it wrote to the recording's Parquet file."""
    import cv2
    import numpy as np
    from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
    config = PosthocMocapPipelineConfig(stop_stage="observations")  # the app's defaults otherwise
    if _models_missing(config.detector_type, config.rtmpose_model_name):
        return {"result": "not-run", "reason": "models-missing"}
    recording = work / "certify_recording"
    (recording / "synchronized_videos").mkdir(parents=True)
    images = [cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR) for frame in frames]
    writer = cv2.VideoWriter(str(recording / "synchronized_videos" / "camera_0.avi"), cv2.VideoWriter_fourcc(*"MJPG"), 30.0,
                             images[0].shape[1::-1])
    try:
        for image in images:
            writer.write(image)
    finally:
        writer.release()
    if not _session(recording, config):
        return {"result": "fail", "reason": "session-failed"}
    return {"result": "pass", "reason": None, "numbers": {"frames": len(images), "execution_providers": _providers(recording)}}


def _session(recording: Path, config) -> bool:
    """Run the app's post-hoc session (`MocapPipeline`, as the backend starts it) on `recording`; true when it completed.
    It waits for the worker's end, so its `PerformanceReport` is logged before it returns."""
    from skellycam.core.ipc.process_management.managed_worker import WorkerMode
    from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    from skellylogs.handlers.websocket_log_queue_handler import create_websocket_log_queue
    from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline
    from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase
    create_websocket_log_queue()  # each pipeline's IPC takes the app's log queue; nothing reads it in this child
    if _stopping():
        return False
    flag = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.PROCESS)  # as the app's backend makes it
    registry.start_heartbeat()
    try:
        pipeline = MocapPipeline.create(pipeline_id="certify", config=config, worker_registry=registry, global_kill_flag=flag,
                                        recording_info=RecordingInfo(recording_name=recording.name,
                                                                     recording_directory=str(recording.parent)))
        pipeline.start()
        ended = (AggregatorPhase.COMPLETE, AggregatorPhase.FAILED)
        phase = lambda: next((item.phase for item in pipeline.get_progress_messages()  # noqa: E731
                              if item.pipeline_id == pipeline.id), None)
        try:
            while pipeline.alive and phase() not in ended and not _stopping():
                time.sleep(0.02)
            deadline = time.monotonic() + 30
            while pipeline.alive and time.monotonic() < deadline and not _stopping():  # it logs its timings as it ends
                time.sleep(0.02)
        finally:
            pipeline.shutdown()
    finally:
        registry.shutdown_all()
    return phase() == AggregatorPhase.COMPLETE  # the newest message, also one sent just before the worker ended


def _providers(recording: Path) -> dict:
    """The EP of each model of the run, as the session wrote it to the recording's Parquet file."""
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
    from freemocap.system.recording_structure.recording_structure import RecordingStructure
    metadata = read_metadata(path=RecordingStructure(base_directory=recording.parent, recording_name=recording.name).data_parquet_path)
    saved = next(item for name, item in metadata.runs[0].sources.items() if name.startswith("keypoint_model:"))
    return {node: model["execution_provider"] for node, model in saved.definition["skellytracker"]["models"].items()}


def _posthoc_child(queue, frames: list[bytes], work: str) -> None:
    """The spawn child of `posthoc-session`: its answer, `{"result", "reason", "numbers"?}`."""
    try:
        answer = _posthoc_session(frames, Path(work))
    except Exception as error:  # noqa: BLE001 - the class name only: an error text can hold a path
        logger.exception("freemocap's post-hoc session check raised")
        answer = {"result": "fail", "reason": type(error).__name__}
    queue.put(answer)


def _posthoc(cancelled, cleanup: list) -> tuple[str, str | None, dict | None]:
    """Run `posthoc-session` in its own spawn child, with scratch files in a work folder of freemocap's certify folder that
    is removed afterwards; a removal that fails is a row of `cleanup` (report format 2.5)."""
    from skellytracker.certification import certify_frames
    from skellytracker.core.eps.certification import FramesUnavailableError
    try:
        frames = certify_frames()  # hash checked; the quick level downloads nothing
    except FramesUnavailableError:
        return "not-run", "test-media-missing", None
    started = time.monotonic()
    try:
        reports_dir().parent.mkdir(parents=True, exist_ok=True)
        work = tempfile.mkdtemp(prefix="work-", dir=reports_dir().parent)
    except OSError as error:
        return "fail", type(error).__name__, None
    try:
        answer, reason = _spawn(_posthoc_child, (frames[:POSTHOC_FRAMES], work), "freemocap-certify-posthoc",
                                POSTHOC_TIMEOUT_SECONDS, cancelled)
    finally:
        try:
            shutil.rmtree(work)
        except OSError as error:
            cleanup.append({"name": "posthoc-session:work-folder", "result": "fail", "reason": type(error).__name__})
    if answer is None:
        return ("not-run" if reason == "cancelled" else "fail"), reason, None
    return answer["result"], answer["reason"], {**answer.get("numbers", {}), "seconds": round(time.monotonic() - started, 3)}


# - The full benchmark on the sample recording -

def _sha256(path: Path) -> str:
    import hashlib
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _cut(source: Path, target: Path, frames: int, cancelled) -> None:
    """A copy of the recording `source` with its first `frames` frames, in the codec of the sample (MPEG-4, `mp4v`)."""
    import cv2
    from concurrent.futures import CancelledError
    videos = target / "synchronized_videos"
    videos.mkdir(parents=True)
    for file in source.iterdir():
        if file.is_file():  # the calibration TOML and the board
            shutil.copy2(file, target / file.name)
    for video in sorted((source / "synchronized_videos").glob("*.mp4")):
        capture, writer = cv2.VideoCapture(str(video)), None
        try:
            for _ in range(frames):
                if cancelled():
                    raise CancelledError("cancelled")
                ok, image = capture.read()
                if not ok:
                    raise ValueError("the recording has fewer frames than the benchmark")
                if writer is None:
                    writer = cv2.VideoWriter(str(videos / video.name), cv2.VideoWriter_fourcc(*"mp4v"),
                                             capture.get(cv2.CAP_PROP_FPS) or 30.0, image.shape[1::-1])
                writer.write(image)
        finally:
            capture.release()
            if writer is not None:
                writer.release()


def _recording(cancelled, test_media_dir) -> tuple[str, str | None, dict, Path | None]:
    """The `recording` check: the archive in the test media folder (downloaded when absent, hash checked), extracted and
    cut to `BENCHMARK_FRAMES` frames in a new work folder. `numbers.downloaded` tells the clean-up what this run fetched."""
    from concurrent.futures import CancelledError
    from freemocap.tools.datasets.catalog import SAMPLE_DATA, download, extract_recording
    archive, numbers = _archive(test_media_dir), {"downloaded": False, "frames": BENCHMARK_FRAMES}
    started = time.monotonic()
    try:
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.is_file():
            if _sha256(archive) != SAMPLE_RECORDING["sha256"]:
                return "fail", "bad-hash", numbers, None  # never used, never removed: it was there before the run
        else:
            partial = archive.with_name(f"{archive.name}.{uuid.uuid4().hex}.part")
            try:
                if download(SAMPLE_DATA.url, partial, cancelled) != SAMPLE_RECORDING["sha256"]:
                    return "fail", "bad-hash", numbers, None
                os.replace(partial, archive)
            finally:
                partial.unlink(missing_ok=True)  # a partial or wrong file is never kept
            numbers.update(downloaded=True, download_seconds=round(time.monotonic() - started, 3))
        work = _work()
        if work.exists():
            shutil.rmtree(work)  # the work folder of an earlier run
        work.mkdir(parents=True)
        source = extract_recording(archive, work / "source", "the sample recording")
        _cut(source, work / "recording", BENCHMARK_FRAMES, cancelled)
        shutil.rmtree(work / "source")
        numbers["seconds"] = round(time.monotonic() - started, 3)
        return "pass", None, numbers, work / "recording"
    except CancelledError:
        return "not-run", "cancelled", numbers, None
    except Exception as error:  # noqa: BLE001 - the class name only: an error text can hold a path
        logger.exception("freemocap's benchmark recording could not be prepared")
        return "fail", type(error).__name__, numbers, None


def _benchmark_session(recording: Path, execution_provider: str, device_key: str | None) -> dict:
    """The app's post-hoc session on the cut recording on one EP and GPU, to its exports (no Blender), with the timings
    of its `PerformanceReport` per stage, read as `machine_benchmarks.py` reads them."""
    from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
    from freemocap.tools.datasets.reporting import normalized_stages, parse_performance
    config = PosthocMocapPipelineConfig(execution_provider=execution_provider, execution_device=device_key,
                                        calibration_toml_path=str(next(recording.glob("*.toml"))), export_to_blender=False)
    if _models_missing(config.detector_type, config.rtmpose_model_name):
        return {"result": "not-run", "reason": "models-missing"}
    lines: list[str] = []
    handler = logging.Handler(logging.INFO)
    handler.emit = lambda record: lines.append(record.getMessage())
    timings = logging.getLogger("freemocap.core.pipeline.performance_report")
    timings.setLevel(logging.INFO)  # a spawn child has no logging set up
    timings.addHandler(handler)
    try:
        if not _session(recording, config):
            return {"result": "fail", "reason": "session-failed"}
    finally:
        timings.removeHandler(handler)
    report = next(report for report in parse_performance(lines) if report["source"] == "structured")
    stages = {name: {"total_s": round(stage["total_s"], 4), "ms_per_frame": stage["amortized_ms_per_frame"],
                     "fps": stage["synchronized_frames_per_second"]} for name, stage in normalized_stages(report)}
    return {"result": "pass", "reason": None, "numbers": {
        "frames": report["frames"], "images": report["images"], "wall_seconds": round(report["elapsed_s"], 3),
        "startup_seconds": (stages.get("inference.session_setup") or {}).get("total_s"), "stages": stages,
        "execution_providers": _providers(recording)}}


def _benchmark_child(queue, recording: str, execution_provider: str, device_key: str | None) -> None:
    try:
        answer = _benchmark_session(Path(recording), execution_provider, device_key)
    except Exception as error:  # noqa: BLE001 - the class name only
        logger.exception("freemocap's post-hoc benchmark raised")
        answer = {"result": "fail", "reason": type(error).__name__}
    queue.put(answer)


def _benchmark(cancelled, recording: Path, label: str, execution_provider: str, device_key: str | None):
    """One `posthoc:<label>` check in its own spawn child, on a fresh copy of the cut recording."""
    target = recording.parent / label
    try:
        shutil.copytree(recording, target)
    except OSError as error:
        return "fail", type(error).__name__, None
    answer, reason = _spawn(_benchmark_child, (str(target), execution_provider, device_key), "freemocap-certify-benchmark",
                            PAIR_TIMEOUT_SECONDS, cancelled)
    if answer is None:
        return ("not-run" if reason == "cancelled" else "fail"), reason, None
    return answer["result"], answer["reason"], answer.get("numbers")


def _blender_child(queue, recording: str, blender: str) -> None:
    """The app's Blender export (`export_to_blender`, the defaults of the post-hoc settings), timed."""
    try:
        from freemocap.core.blender.export_to_blender import export_to_blender
        from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
        config = PosthocMocapPipelineConfig()
        started = time.perf_counter()
        export_to_blender(recording_folder_path=recording, blender_exe_path=blender, open_file_on_completion=False,
                          route=config.blender_import_route, package=config.blender_package,
                          run_id=config.base_run_id, blender_export_config=config.blender_export.model_dump())
        seconds = time.perf_counter() - started
        queue.put({"result": "record-only", "reason": None, "numbers": {"seconds": round(seconds, 3)}})
    except Exception as error:  # noqa: BLE001 - the class name only
        logger.exception("freemocap's Blender export benchmark raised")
        queue.put({"result": "fail", "reason": type(error).__name__})


def _blender_export(cancelled, recording: Path, blender: str):
    answer, reason = _spawn(_blender_child, (str(recording), blender), "freemocap-certify-blender",
                            BLENDER_EXPORT_TIMEOUT_SECONDS, cancelled)
    if answer is None:
        return ("not-run" if reason == "cancelled" else "fail"), reason, None
    return answer["result"], answer["reason"], answer.get("numbers")


def _component_items(checks: list[dict]) -> list[dict]:
    """The `component` summary items (format 1.5.0, 3.7): one for each check of freemocap's own module that ran, with its
    result; none for a `not-run` check, and none for Blender when it is not installed (`not-found` at quick)."""
    return [{"group": "component", "name": row["module"], "device": None, "result": row["result"]} for row in checks
            if row["name"] in COMPONENTS and row["result"] in ("pass", "fail", "record-only") and row["reason"] != "not-found"]


def _benchmark_items(checks: list[dict], pairs: list[tuple], frames: int) -> list[dict]:
    """The `benchmark` summary items (format 3.7): each stage of each passed pair, then the Blender export."""
    from skellytracker.core.eps import evidence
    from skellytracker.core.system.host import gpu_device_keys
    gpus = dict(gpu_device_keys())
    rows = {row["name"]: row for row in checks}
    items = []
    for label, _, device_key, module in pairs:
        row = rows[f"posthoc:{label}"]
        if row["result"] != "pass":
            continue
        device = evidence.gpu_id(gpus.get(device_key)) if device_key else None
        for prefix, stage in BENCHMARK_STAGES:
            timed = next((value for name, value in row["numbers"]["stages"].items() if name.startswith(prefix)), None)
            if timed and timed["ms_per_frame"] is not None and timed["fps"] is not None:
                items.append({"group": "benchmark", "name": module, "device": device, "stage": stage,
                              "ms_per_frame": round(timed["ms_per_frame"], 3), "fps": round(timed["fps"], 3)})
    blender = rows.get("blender") or {}
    if blender.get("result") == "record-only" and (blender.get("numbers") or {}).get("seconds"):
        seconds = blender["numbers"]["seconds"]
        items.append({"group": "benchmark", "name": "Blender", "device": None, "stage": "export",
                      "ms_per_frame": round(1000 * seconds / frames, 3), "fps": round(frames / seconds, 3)})
    return items


def remove_benchmark_data(downloaded: bool, test_media_dir) -> list[dict]:
    """Remove the work folder, and the archive when this run downloaded it; a removal that fails is a `cleanup` row."""
    rows = []
    for name, path in (("work-folder", _work()), *((("recording", _archive(test_media_dir)),) if downloaded else ())):
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        except OSError as error:
            rows.append({"name": f"benchmark:{name}", "result": "fail", "reason": type(error).__name__})
    return rows


def _identity() -> tuple[dict, list[str]]:
    from freemocap.build_info import BUILD_TREE_MODIFIED
    from freemocap.system.certify.report_file import app_block
    app = app_block()
    package = {"name": "freemocap", "version": app["version"], "commit": app["commit"], "tree_modified": BUILD_TREE_MODIFIED}
    reasons = [code for code, bad in (("no-version", not SEMVER.match(str(package["version"]))),
                                      ("no-commit", not COMMIT.match(str(package["commit"]))),
                                      ("modified-tree", BUILD_TREE_MODIFIED is not False)) if bad]
    return package, reasons


def _host() -> dict:
    from skellytracker.core.eps import evidence
    from skellytracker.core.system.host import probe_host
    host = probe_host()
    arch = host.arch.lower()
    return {"os": {"name": "macOS" if host.os_name == "Darwin" else host.os_name, "release": host.os_release,
                   "version": host.os_version, "build": host.os_build, "label": host.os_label,
                   "arch": {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(arch, arch)},
            "cpu": {"name": host.cpu_name}, "memory_bytes": host.memory_total_bytes,
            "gpus": [{"vendor": gpu.vendor, "name": gpu.name, "id": evidence.gpu_id(gpu), "driver_version": gpu.driver_version,
                      "vram_bytes": gpu.vram_total_bytes} for gpu in host.gpus]}  # as skellytracker's: the benchmark's GPU names


def _install_dir() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(freemocap.__file__).parent


def _data_folder() -> tuple[str, str | None, dict]:
    from freemocap.system.default_paths import get_default_freemocap_base_folder_path
    base = Path(get_default_freemocap_base_folder_path())
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / f".certify-{uuid.uuid4().hex}"
        probe.write_bytes(b"freemocap")
        same = probe.read_bytes() == b"freemocap"
        probe.unlink()
        numbers = {"free_bytes": shutil.disk_usage(base).free}
        return ("pass", None, numbers) if same else ("fail", "bad-output", numbers)
    except OSError as error:
        return "fail", type(error).__name__, {}


def _install_facts(ui_remote: bool | None) -> dict:
    from freemocap.system.default_paths import get_default_freemocap_base_folder_path
    install = _install_dir()
    paths = [str(install), get_default_freemocap_base_folder_path(), str(Path.home())]
    user_root = Path(os.environ.get("LOCALAPPDATA") or Path.home()).resolve()
    return {"install_dir_writable": os.access(install, os.W_OK),
            "per_user_install": install.resolve().is_relative_to(user_root) if getattr(sys, "frozen", False) else None,
            "path_has_space": any(" " in path for path in paths),
            "path_non_ascii": any(not path.isascii() for path in paths),
            "ui_remote": ui_remote}


def _blender(cancelled, blender_exe_path: str | None = None) -> tuple[str, str | None, dict]:
    from freemocap.core.blender.runtime import executable, run_external
    try:
        blender = executable(blender_exe_path)  # the path chosen in Blender settings, else the best guess
    except ValueError:
        return "record-only", "not-found", {"found": False}
    try:
        found = run_external([str(blender), "--version"], timeout=BLENDER_TIMEOUT_SECONDS, cancelled=cancelled,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    except Exception as error:  # noqa: BLE001 - timed out, cancelled or did not start: a record only
        return "record-only", type(error).__name__, {"found": True}
    match = re.search(r"Blender (\d+)\.(\d+)\.(\d+)", found.stdout or "")
    major, minor, patch = map(int, match.groups()) if match else (None, None, None)
    return "record-only", None, {"found": True, "version_major": major, "version_minor": minor, "version_patch": patch}


def certify(level: str, progress=None, cancel=None, *, ui_remote: bool | None = None,
            blender_exe_path: str | None = None, test_media_dir: str | os.PathLike | None = None,
            remove_data: bool = False) -> dict:
    """Run freemocap's checks of `level` and return the module report. A check never raises; a cancel makes each check
    that did not end `not-run` with `cancelled`. `ui_remote`: whether the UI runs on another machine (None: unknown).
    `blender_exe_path`: the path chosen in Blender settings, if any. `test_media_dir`: the shared test media folder
    (format 2.8). `remove_data`: at `full`, remove the benchmark data after a run with no failed check and no cancel."""
    _check_level(level)
    begun = time.monotonic()
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    package, reasons = _identity()
    pairs = _pairs() if level == "full" else []
    by_name = {f"posthoc:{label}": (label, key, device_key, module) for label, key, device_key, module in pairs}
    names = QUICK_CHECKS if level == "quick" else _full_names(pairs)
    checks = [{"name": name, "result": None, "reason": None, "module": by_name[name][3] if name in by_name else COMPONENTS[name]}
              for name in names]
    recording, usable, numbers_of = None, None, {}
    cleanup: list[dict] = []
    cancelled =lambda: cancel is not None and cancel.is_set()  # noqa: E731

    def send(state: str, step: str | None) -> None:
        nonlocal progress
        if progress is None:
            return
        try:
            progress({"package": "freemocap", "kind": level, "state": state, "step": step and {"name": step},
                      "checks": [{"name": row["name"], "result": row["result"], "reason": row["reason"]} for row in checks],
                      "done": sum(row["result"] is not None for row in checks), "total": len(checks), "seconds_left": None})
        except Exception:  # noqa: BLE001 - the contract: stop calling it and continue the run
            progress = None

    def record(row: dict, result: str, reason: str | None, numbers: dict | None = None) -> None:
        row.update(result=result, reason=reason, **({"numbers": numbers} if numbers else {}))

    send("starting", None)
    stopped = None  # the reason of every later check once the run cannot go on
    for row in checks:
        if stopped is None and cancelled():
            stopped = "cancelled"
        if stopped is not None:
            record(row, "not-run", stopped)
            continue
        send("running", row["name"])
        name = row["name"]
        if name == "recording":
            result, reason, numbers, recording = _recording(cancelled, test_media_dir)
            numbers_of["recording"] = numbers
            record(row, result, reason, numbers)
            if reason == "cancelled":
                stopped = "cancelled"
        elif name in by_name:
            label, key, device_key, _ = by_name[name]
            if usable is None and recording is not None:
                usable = _usable_labels()  # read once, after skellytracker's checks of this run
            if recording is None:
                record(row, "not-run", "recording-missing")
            elif label not in usable:
                record(row, "not-run", "ep-not-passed")
            else:
                record(row, *_benchmark(cancelled, recording, label, key, device_key))
                if row["reason"] == "cancelled":
                    stopped = "cancelled"
        elif name == "blender" and level == "full":
            blender = _blender_path(blender_exe_path)
            done = next((recording.parent / by_name[other["name"]][0] for other in checks  # a finished recording
                         if other["name"] in by_name and other["result"] == "pass"), None) if recording else None
            if blender is None:
                record(row, "not-run", "not-installed")
            elif done is None:
                record(row, "not-run", "recording-missing")
            else:
                record(row, *_blender_export(cancelled, done, blender))
                if row["reason"] == "cancelled":
                    stopped = "cancelled"
        elif name == "build-identity":
            record(row, "record-only" if reasons else "pass", reasons[0] if reasons else None,
                   {"evidence_reasons": list(reasons)})
        elif name == "spawn-child":
            started = time.monotonic()
            answer, reason = _spawn_imports(cancelled)
            record(row, "pass" if answer else "not-run" if reason == "cancelled" else "fail", reason,
                   {"seconds": round(time.monotonic() - started, 3)})
            if answer is None:
                stopped = "cancelled" if reason == "cancelled" else "spawn-failed"
        elif name == "bundle-imports":
            record(row, "fail" if answer["failed"] else "pass", "import-failed" if answer["failed"] else None,
                   {"failed": answer["failed"], "from_bundle": answer["from_bundle"]})
        elif name == "data-folder":
            record(row, *_data_folder())
        elif name == "posthoc-session":
            if time.monotonic() - begun + POSTHOC_SECONDS > QUICK_BUDGET_SECONDS:  # it would not end in the budget
                record(row, "not-run", "over-budget")
            else:
                record(row, *_posthoc(cancelled, cleanup))
                if row["reason"] == "cancelled":
                    stopped = "cancelled"
        elif name == "install-facts":
            record(row, "record-only", None, _install_facts(ui_remote))
        elif name == "blender":
            result = _blender(cancelled, blender_exe_path)
            if cancelled():
                stopped = "cancelled"
                record(row, "not-run", stopped)
            else:
                record(row, *result)
    if stopped == "cancelled":
        reasons.append("cancelled")
    if level == "full" and remove_data and stopped is None and not any(row["result"] == "fail" for row in checks):
        cleanup += remove_benchmark_data(bool(numbers_of.get("recording", {}).get("downloaded")), test_media_dir)
    report = {"schema": SCHEMA, "id": str(uuid.uuid4()), "package": package, "kind": level, "created_utc": created,
              "host": _host(), "checks": checks, "cleanup": cleanup, "evidence": {"valid": not reasons, "reasons": reasons},
              "summary": _component_items(checks) + (_benchmark_items(checks, pairs, BENCHMARK_FRAMES) if level == "full" else [])}
    if any(row["result"] in ("pass", "fail") for row in checks):  # only those reach the hand-in list
        try:
            _write_json(reports_dir() / f"{report['id']}.json", report)
            _prune_reports()
        except OSError:  # a data folder that cannot be written is the `data-folder` check's result, not a crash
            logger.warning("freemocap's certify report could not be kept", exc_info=True)
    send("done", None)
    return report


# - The hand-in list (the shapes of skellytracker's `pending_reports`, `read_report` and `mark_reports`) -

# shortcut: a lock in this process only, while the start check's child prunes and the server may mark at once. Upgrade
# to a file lock if that race ever matters (only an older pass that a newer pass repeats can be pruned then).
_store_lock = threading.Lock()


def reports_dir() -> Path:
    from freemocap.system.default_paths import get_default_freemocap_base_folder_path
    return Path(get_default_freemocap_base_folder_path()) / "certify" / "reports"


def _marks_path() -> Path:
    return reports_dir().parent / "hand-in.json"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _marks() -> dict:
    marks = _read_json(_marks_path())
    return marks if isinstance(marks, dict) else {}


def pending_reports(include_handed_in: bool = False) -> list[dict]:
    """freemocap's reports that the person did not hand in, the oldest first; with `include_handed_in`, each report in
    each state. Each row is `{"report_id", "package", "kind", "created_utc", "has_failure", "evidence_valid", "state",
    "reference"}`; `package` is the report's own (a crash record keeps skellytracker's interrupted run here too)."""
    marks, rows = _marks(), []
    for path in sorted(reports_dir().glob("*.json")):
        report = _read_json(path)
        if not isinstance(report, dict) or not str(report.get("schema")).startswith(SCHEMA_PREFIX) or not REPORT_ID.match(path.stem):
            continue
        results = {check.get("result") for check in report.get("checks", ()) if isinstance(check, dict)}
        if not results & {"pass", "fail"}:
            continue
        mark = marks.get(path.stem) if isinstance(marks.get(path.stem), dict) else {}
        state = mark.get("state") if mark.get("state") in REPORT_STATES else "pending"
        if state == "pending" or include_handed_in:
            rows.append({"report_id": path.stem, "package": str((report.get("package") or {}).get("name") or "freemocap"),
                         "kind": report.get("kind"), "created_utc": report.get("created_utc"),
                         "has_failure": "fail" in results, "evidence_valid": bool((report.get("evidence") or {}).get("valid")),
                         "state": state, "reference": mark.get("reference") if state != "pending" else None})
    return sorted(rows, key=lambda row: (row["created_utc"] or "", row["report_id"]))


def read_report(report_id: str) -> dict:
    """The module report of a row of `pending_reports()`, unchanged. An id that is not a report here raises `ValueError`."""
    report = _read_json(reports_dir() / f"{report_id}.json") if REPORT_ID.match(str(report_id)) else None
    if not isinstance(report, dict) or not str(report.get("schema")).startswith(SCHEMA_PREFIX):
        raise ValueError(f"{report_id!r} is not a report of this host")
    return report


def mark_reports(report_ids, state: str, *, reference: str | None = None) -> None:
    """Set the hand-in state: `covered` (an issue holds them, `reference` its address), `opened` (the person saved the
    file and opened the issue form) or `pending` ("Not sent": back in the list, no reference). An unknown state, an id
    that is not a report here, or a reference with `pending` raises `ValueError` and changes nothing."""
    if isinstance(report_ids, str):
        raise ValueError("report_ids is a list of report ids")
    if state not in REPORT_STATES:
        raise ValueError(f"the state must be one of {', '.join(REPORT_STATES)}, not {state!r}")
    if state == "pending" and reference is not None:
        raise ValueError("a pending report has no reference")
    ids = list(dict.fromkeys(report_ids))
    for report_id in ids:
        read_report(report_id)
    with _store_lock:
        marks = _marks()
        for report_id in ids:
            if state == "pending":
                marks.pop(report_id, None)
            else:
                marks[report_id] = {"state": state, "reference": reference}
        _write_json(_marks_path(), marks)


def _prune_reports() -> None:
    """Delete each older quick report of a pass whose passed checks newer passes repeat (as skellytracker's). A report
    stays when it has a failed check, when the person handed it in, or when it is not of the level `quick`."""
    with _store_lock:
        marks, found = _marks(), []
        for path in reports_dir().glob("*.json"):
            report = _read_json(path)
            if not isinstance(report, dict) or not str(report.get("schema")).startswith(SCHEMA_PREFIX) \
                    or path.stem in marks or report.get("kind") != "quick":
                continue
            checks = [check for check in report.get("checks", ()) if isinstance(check, dict)]
            passed = {check.get("name") for check in checks if check.get("result") == "pass"}
            if passed and not any(check.get("result") == "fail" for check in checks):
                found.append((str(report.get("created_utc") or ""), path.stem, path, passed))
        newer: set = set()
        for _, _, path, passed in sorted(found, key=lambda item: item[:2], reverse=True):
            if passed <= newer:
                try:
                    path.unlink()
                except OSError:
                    pass
            newer |= passed


def module_result(report: dict) -> tuple[str, str | None]:
    """A module report's result by the section rule (any fail, else any pass, else record-only, else not-run); a
    cancelled run is `not-run`. The reason is the first failed check's name, or the reason code of a run that did not run."""
    reasons = (report.get("evidence") or {}).get("reasons") or []
    if "cancelled" in reasons or not report.get("checks"):
        return "not-run", "cancelled" if "cancelled" in reasons else "no-check"
    for result in ("fail", "pass", "record-only", "not-run"):
        row = next((row for row in report.get("checks", ()) if row.get("result") == result), None)
        if row is not None:
            return result, row.get("name") if result == "fail" else row.get("reason") if result == "not-run" else None
    return "not-run", None  # rows with no result: not a report of this format
