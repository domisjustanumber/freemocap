"""freemocap's own certify checks (skellycertify report format 1.1.0; ep-certification-integration.md, "freemocap's own
checks"): only what freemocap owns, so no check loads an EP, a model or a camera, and none uses a GPU.

    import freemocap
    plan = freemocap.certify_plan("quick")          # show the plan, then get the consent of the person
    report = freemocap.certify("quick", progress=show, cancel=event)

`certify(level, progress, cancel, *, ui_remote=None, blender_exe_path=None)` returns freemocap's module report;
`certify_plan(level)` takes the same options and gives its plan. `import freemocap` does not import this module: the
two names load it on first use. The level `quick` runs the six checks below. The level `full` (reference-posthoc,
concurrent-runs, exports, live-numbers) is not built: each of its checks is `not-run` with `not-built`, and the report
is not valid as evidence (`partial-run`, report format 7.1 statement 4) (F13, G12).

freemocap's reason codes (report format 5.4), besides the common ones:
- `spawn-failed`: the spawn child of `spawn-child` gave no answer, so the later checks did not run.
- `import-failed`: a module of the bundle did not import in the spawn child (`numbers.failed` names them).
- `not-found`: no Blender executable was found.
- an exception class name, for example `PermissionError`: the step raised it (never its message).
"""
import importlib
import importlib.util
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from queue import Empty

import freemocap

SCHEMA = "skellycertify.report/1.1.0"
QUICK_CHECKS = ("build-identity", "spawn-child", "bundle-imports", "data-folder", "install-facts", "blender")
FULL_CHECKS = ("reference-posthoc", "concurrent-runs", "exports", "live-numbers")
# skellytracker first: it sets ONNX Runtime's telemetry switch before onnxruntime is imported (decision 3).
BUNDLE_MODULES = ("numpy", "cv2", "pyarrow", "av", "scipy", "numba", "skellyforge", "skellytracker", "onnxruntime")
OPTIONAL_MODULES = ("numba",)  # imported only when shipped
SPAWN_TIMEOUT_SECONDS = 120
BLENDER_TIMEOUT_SECONDS = 30
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _check_level(level: str) -> None:
    if level not in ("quick", "full"):
        raise ValueError(f"level must be 'quick' or 'full', not {level!r}")


def certify_plan(level: str, *, ui_remote: bool | None = None, blender_exe_path: str | None = None) -> dict:
    """What `certify(level)` runs: no download, no change outside freemocap's data folder, no question. It takes the
    options of `certify` (report format 2.2); neither changes the plan."""
    _check_level(level)
    return {"package": "freemocap", "kind": level, "seconds_estimate": 30, "downloads": [], "system_changes": [],
            "questions": [], "details": {"checks": list(QUICK_CHECKS if level == "quick" else FULL_CHECKS)}}


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
    """Run `_import_child` in a `spawn` child: (its answer, None) or (None, the reason it gave none)."""
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    child = context.Process(target=_import_child, args=(queue, BUNDLE_MODULES), name="freemocap-certify-imports")
    child.start()
    deadline, answer, reason = time.monotonic() + SPAWN_TIMEOUT_SECONDS, None, None
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
            child.kill()
            child.join()


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
    from skellytracker.core.system.host import probe_host
    host = probe_host()
    arch = host.arch.lower()
    return {"os": {"name": "macOS" if host.os_name == "Darwin" else host.os_name, "release": host.os_release,
                   "version": host.os_version, "build": host.os_build, "label": host.os_label,
                   "arch": {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(arch, arch)},
            "cpu": {"name": host.cpu_name}, "memory_bytes": host.memory_total_bytes}


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
            blender_exe_path: str | None = None) -> dict:
    """Run freemocap's checks of `level` and return the module report. A check never raises; a cancel makes each check
    that did not end `not-run` with `cancelled`. `ui_remote`: whether the UI runs on another machine (None: unknown).
    `blender_exe_path`: the path chosen in Blender settings, if any."""
    _check_level(level)
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    package, reasons = _identity()
    names = QUICK_CHECKS if level == "quick" else FULL_CHECKS
    checks = [{"name": name, "result": None, "reason": None} for name in names]
    cancelled = lambda: cancel is not None and cancel.is_set()  # noqa: E731

    def send(state: str, step: str | None) -> None:
        nonlocal progress
        if progress is None:
            return
        try:
            progress({"package": "freemocap", "kind": level, "state": state, "step": step and {"name": step},
                      "checks": [{"name": row["name"], "result": row["result"]} for row in checks],
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
        if level == "full":
            record(row, "not-run", "not-built")
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
        elif name == "install-facts":
            record(row, "record-only", None, _install_facts(ui_remote))
        elif name == "blender":
            result = _blender(cancelled, blender_exe_path)
            if cancelled():
                stopped = "cancelled"
                record(row, "not-run", stopped)
            else:
                record(row, *result)
    if level == "full":  # its checks are not built, so the run did not select each check of its level (7.1 statement 4)
        reasons.append("partial-run")
    if stopped == "cancelled":
        reasons.append("cancelled")
    send("done", None)
    return {"schema": SCHEMA, "id": str(uuid.uuid4()), "package": package, "kind": level, "created_utc": created,
            "host": _host(), "checks": checks, "cleanup": [], "evidence": {"valid": not reasons, "reasons": reasons}}


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
