"""The start check (decisions 12 to 15 and 17): every package's quick check of this machine, and whether the UI needs it.

The UI needs it while freemocap's OS-level item has no reviewed row and no local quick pass for the current version set
(freemocap, skellycam, skellytracker), some package's quick plan has a check to run (report format 2.6: `total` above 0),
and no start check finished in this server session (decision 14: any finished check, pass or fail, releases the UI; a
cancel does not). skellycam's `certify()` is not built, so only freemocap's item
counts; GPU EPs never do (decision 15).

`run_start_check` runs in the quick check's spawn child: freemocap's own checks, then skellytracker's `certify("quick")`
with no EP named (every GPU EP with no reviewed row, the field-test ones included: a pass is their opt-in, decision 17).
A pass of freemocap's checks is recorded under `<base data folder>/certify/start-check.json`. `run_full_check` runs the
full benchmark in the same child, every package's level full in turn.
"""
import importlib.metadata
import json
import logging
import platform
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
    path = record_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"versions": version_set(), "os": os_key(), "report": report}, indent=1), encoding="utf-8")
    temporary.replace(path)


def run_start_check(progress, cancel, *, ui_remote: bool | None, blender_exe_path: str | None = None, own_certify=None,
                    certify=None) -> tuple:
    """Each package's quick check in turn; `("start", ((package, result, reason), ...))`. A module that raises is
    `error` with the exception class name; after a cancel the next module is `not-run` with `cancelled`."""
    from freemocap.certification import certify as freemocap_certify, module_result
    results = []
    try:
        report = (own_certify or freemocap_certify)("quick", progress, cancel, ui_remote=ui_remote,
                                                 blender_exe_path=blender_exe_path)
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
            results.append(("skellytracker", *module_result(certify("quick", progress, cancel))))
        except Exception as error:  # noqa: BLE001
            logger.exception("skellytracker's quick check raised")
            results.append(("skellytracker", "error", type(error).__name__))
    return "start", tuple(results)


def run_full_check(progress, cancel, *, remove_data: bool, own_certify=None, certify=None) -> tuple:
    """Each package's level full in the run order (fifth grilling): skellycam (not built; it will run first), skellytracker,
    then freemocap; `("full", ((package, result, reason), ...))`. Nothing is passed that overrides a package's own
    staging. A package whose full plan has no check does not run; after a cancel each later package is `not-run` with
    `cancelled`. `remove_data`: the person's choice to remove the benchmark data after a successful run."""
    from freemocap.certification import certify as freemocap_certify, certify_plan, module_result

    def tracker(level, progress, cancel):
        from skellytracker import certify as skellytracker_certify
        return (certify or skellytracker_certify)(level, progress, cancel)

    results = []
    for package, run in (("skellytracker", tracker), ("freemocap", own_certify or freemocap_certify)):
        if package == "freemocap" and certify_plan("full")["total"] == 0:
            continue
        if cancel.is_set():
            results.append((package, "not-run", "cancelled"))
            continue
        try:
            results.append((package, *module_result(run("full", progress, cancel))))
        except Exception as error:  # noqa: BLE001 - the class name only: an error text can hold a path
            logger.exception("%s's full level raised", package)
            results.append((package, "error", type(error).__name__))
    if remove_data and all(result in ("pass", "record-only") for _, result, _ in results):
        # shortcut: no full level downloads anything or keeps processing output yet (skellytracker's uses its bundled
        # frames and has no clean-up interface; freemocap's checks are not built), so nothing is removed. Remove
        # freemocap's benchmark data here once its benchmark and the shared test media download exist.
        logger.info("The full benchmark passed; it left no benchmark data to remove")
    return "full", tuple(results)
