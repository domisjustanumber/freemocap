"""The start check (decisions 12 to 15 and 17): every package's quick check of this machine, and whether the UI needs it.

The UI needs it while freemocap's OS-level item has no reviewed row and no local quick pass for the current version set
(freemocap, skellycam, skellytracker), some package's quick plan has a check to run (report format 2.6: `total` above 0),
and no start check finished in this server session (decision 14: any finished check, pass or fail, releases the UI; a
cancel does not). skellycam's `certify()` is not built, so only freemocap's item
counts; GPU EPs never do (decision 15).

`run_start_check` runs in the quick check's spawn child: freemocap's own checks, then skellytracker's `certify("quick")`
with no EP named (every GPU EP with no reviewed row, the field-test ones included: a pass is their opt-in, decision 17).
A pass of freemocap's checks is recorded under `<base data folder>/certify/start-check.json`, and so is a start check
that crashed in freemocap's own part (`crash_record.recover`). `run_full_check` runs the
full benchmark in the same child, every package's level full in turn.
"""
import importlib.metadata
import json
import logging
import platform
import re
from functools import cache
from pathlib import Path

import freemocap

logger = logging.getLogger(__name__)

# Decision 12: the reviewed rows "this OS is certified for freemocap", each from a `full` report reviewed on an issue:
# {"os_name", "os_release", "os_arch", "build_family", "freemocap": "<major>.<minor>", "kind": "full", "issue", "reviewed"}.
# A new freemocap minor or OS build family needs a new row. None is reviewed yet.
REVIEWED_OS_ROWS: tuple[dict, ...] = ()
KEY_FIELDS = ("os_name", "os_release", "os_arch", "build_family", "freemocap")


@cache  # read every few seconds by the status refresh; neither changes while the backend runs
def os_key() -> dict:
    """The key of a reviewed row for this machine and freemocap version. The build family is the Windows build (one per
    feature update), the macOS major version, or the Linux distribution and version."""
    from skellytracker.core.system.host import probe_host
    host = probe_host()
    if host.os_name == "Linux":
        release = platform.freedesktop_os_release()
        family = f"{release.get('ID', 'linux')}-{release.get('VERSION_ID', '')}"
    elif host.os_name == "Darwin":
        family = str(host.os_build or "").split(".")[0]
    else:
        family = str(host.os_build)
    return {"os_name": host.os_name, "os_release": host.os_release, "os_arch": host.arch.lower(), "build_family": family,
            "freemocap": ".".join(freemocap.__version__.split(".")[:2])}


@cache
def version_set() -> dict:
    def version(name: str) -> str | None:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return None
    return {"freemocap": freemocap.__version__, "skellycam": version("skellycam"), "skellytracker": version("skellytracker")}


def record_path() -> Path:
    from freemocap.system.certify.relay import certify_folder
    return certify_folder() / "start-check.json"


def _has_checks() -> bool:
    """Some package's quick plan has a check to run: the app never asks for a run that checks nothing (format 2.6, 2.7)."""
    from freemocap.certification import certify_plan
    if certify_plan("quick")["total"] > 0:
        return True
    try:
        import skellytracker
        return skellytracker.certify_plan("quick")["total"] > 0
    except Exception:  # noqa: BLE001 - an unreadable plan must not keep the app "still starting"; ask as before
        logger.exception("skellytracker's quick plan could not be read")
        return True


def start_check_needed() -> bool:
    """No reviewed row matches this machine, no local pass was recorded for the current version set, and some package's
    quick plan has a check to run."""
    key = os_key()
    if any(row.get("kind") == "full" and all(row.get(name) == key[name] for name in KEY_FIELDS) for row in REVIEWED_OS_ROWS):
        return False
    try:
        record = json.loads(record_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = None
    if isinstance(record, dict) and record.get("versions") == version_set():
        return False
    return _has_checks()


def record_pass(report: dict) -> None:
    """Keep freemocap's passed module report with the version set and the OS key (decision 13)."""
    _write_record({"report": report})


def record_crash(check: str | None) -> None:
    """A start check that crashed in freemocap's own part is not asked for again until a package version changes (owner,
    Q59); its report stays in the hand-in list and the Certification button still runs the check."""
    _write_record({"crashed": check})


def _write_record(entry: dict) -> None:
    path = record_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"versions": version_set(), "os": os_key(), **entry}, indent=1), encoding="utf-8")
    temporary.replace(path)


def run_start_check(progress, cancel, *, ui_remote: bool | None, blender_exe_path: str | None = None, own_certify=None,
                    certify=None) -> tuple:
    """Each package's quick check in turn; `("start", ((package, result, reason), ...))`. A module that raises is
    `error` with the exception class name; after a cancel the next module is `not-run` with `cancelled`. The shared test
    media folder lets a package find media already there; the quick level downloads and writes nothing in it, so
    skellytracker, which then reads its frames only from that folder, gets it only when its frames file is there."""
    from freemocap.certification import certify as freemocap_certify, module_result
    from freemocap.system.default_paths import get_test_media_dir
    media = get_test_media_dir()
    results = []
    try:
        report = (own_certify or freemocap_certify)("quick", progress, cancel, ui_remote=ui_remote,
                                                 blender_exe_path=blender_exe_path, test_media_dir=media)
        results.append(("freemocap", *module_result(report)))
        if results[0][1] == "pass":
            record_pass(report)
    except Exception as error:  # noqa: BLE001 - the class name only: an error text can hold a path
        logger.exception("freemocap's own quick check raised")
        results.append(("freemocap", "error", type(error).__name__))
    if cancel.is_set():
        results.append(("skellytracker", "not-run", "cancelled"))
    else:
        try:
            if certify is None:
                from skellytracker import certify
            options = {"test_media_dir": media} if _frames_target(media).is_file() else {}
            results.append(("skellytracker", *module_result(certify("quick", progress, cancel, **options))))
        except Exception as error:  # noqa: BLE001
            logger.exception("skellytracker's quick check raised")
            results.append(("skellytracker", "error", type(error).__name__))
    return "start", tuple(results)


def _frames_target(test_media_dir) -> Path:
    """skellytracker's test frames file in the shared test media folder, by the name rule of report format 2.8."""
    from skellytracker.core.eps.certification import frames_record
    record = frames_record()
    return Path(test_media_dir) / f"{record['sha256']}{Path(record['path']).suffix}"


def seed_test_media(test_media_dir) -> None:
    """Put skellytracker's bundled test frames file in the shared test media folder, where skellytracker's
    `certify(test_media_dir=...)` reads it; a bundled file, so the clean-up keeps it."""
    from skellytracker.core.eps.certification import frames_file, frames_record
    target = _frames_target(test_media_dir)
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_bytes(frames_file({"frames": frames_record()}))
        temporary.replace(target)


# Owner, Q62: a full benchmark's failed JPEG checks and timings are reported only. They are known by the shape of their
# names (report format 3.6: `<label>:jpeg`, `<label>:jpeg:<name>` and `<label>:pipeline-<n>`, which never change the
# pair's roll-up check), never by an EP's name.
REPORTED_ONLY = re.compile(r"^[^:]+:(?:jpeg(?::.+)?|pipeline-\d+)$")


def full_result(report: dict) -> tuple[str, str | None, tuple[str, ...]]:
    """A package's result at level full: `module_result`, except that when every failed check is reported only, the
    result of its other checks and the names of those failed checks."""
    from freemocap.certification import module_result
    checks = [check for check in report.get("checks") or () if isinstance(check, dict)]
    failed = [str(check.get("name")) for check in checks if check.get("result") == "fail"]
    reported = tuple(name for name in failed if REPORTED_ONLY.match(name))
    if not failed or len(reported) < len(failed):
        return (*module_result(report), ())
    return (*module_result({**report, "checks": [check for check in checks if check.get("result") != "fail"]}), reported)


def run_full_check(progress, cancel, *, remove_data: bool, blender_exe_path: str | None = None, own_certify=None,
                   certify=None) -> tuple:
    """Each package's level full in the run order (fifth grilling): skellycam (not built; it will run first), skellytracker,
    then freemocap; `("full", ((package, result, reason, reported_only), ...))` (`full_result`). Each gets the shared test media folder and nothing that
    overrides its own staging. A package whose full plan has no check does not run; after a cancel each later package is
    `not-run` with `cancelled`. `remove_data`: the person's choice to remove the benchmark data after a successful run;
    freemocap, which runs last, gets it only when every earlier package succeeded (skellytracker downloads and keeps
    nothing, and the frames file it reads is a bundled one). `blender_exe_path`: the path chosen in Blender settings, for
    freemocap's Blender export (None: the best guess)."""
    from freemocap.certification import certify as freemocap_certify, certify_plan
    from freemocap.system.default_paths import get_test_media_dir
    media = get_test_media_dir()

    def tracker(level, progress, cancel):
        from skellytracker import certify as skellytracker_certify
        return (certify or skellytracker_certify)(level, progress, cancel, test_media_dir=media)

    def own(level, progress, cancel):
        succeeded = all(result in ("pass", "record-only") for _, result, *_ in results)
        return (own_certify or freemocap_certify)(level, progress, cancel, test_media_dir=media,
                                                  blender_exe_path=blender_exe_path, remove_data=remove_data and succeeded)

    results = []
    for package, run in (("skellytracker", tracker), ("freemocap", own)):
        if cancel.is_set():
            results.append((package, "not-run", "cancelled"))
            continue
        if package == "freemocap" and certify_plan("full", test_media_dir=media, blender_exe_path=blender_exe_path)["total"] == 0:
            continue
        try:
            if package == "skellytracker":
                seed_test_media(media)
            results.append((package, *full_result(run("full", progress, cancel))))
        except Exception as error:  # noqa: BLE001 - the class name only: an error text can hold a path
            logger.exception("%s's full level raised", package)
            results.append((package, "error", type(error).__name__))
    return "full", tuple(results)
