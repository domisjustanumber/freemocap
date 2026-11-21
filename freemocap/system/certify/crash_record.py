"""The crash record of a certify run (fifth grilling, "Crash, both levels"): the running check outlives a crash of the app.

While a check runs, `<base data folder>/certify/running-check.json` holds `{"level", "pair", "created_utc", "message"}`:
the run's level, its EP and GPU (None: the start check), its start, and the newest progress message (each is the
complete state; its `step` names the running check). It is replaced at each new message and removed when the run ends
in any ordinary way. A file found at launch, or left by a certify child that died, becomes the module report of an
interrupted run (report format 2.5): the running check `fail` with `crashed`, each finished check with its result (the
progress holds no reasons: a `fail` or `not-run` gets `reason-lost`), each other check `not-run` with `interrupted`. It
joins freemocap's hand-in list. At level quick a crashed check of an EP on a GPU is stored as skellytracker's failed
quick check of that pair, so Auto never chooses it; at level full only a crashed probe or video check is. A start check
that crashed in freemocap's own part is recorded in `start-check.json` for the current version set, so it is not asked
for again until a package version changes (owner, Q59). Nothing runs again by itself.
"""
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

REASON_LOST = "reason-lost"


def path() -> Path:
    from freemocap.system.certify.relay import certify_folder
    return certify_folder() / "running-check.json"


def write(record: dict) -> None:
    from freemocap.certification import _write_json
    try:
        _write_json(path(), record)
    except OSError:  # an unwritable data folder must not stop the check; only the crash record is lost
        logger.warning("The crash record of the running check could not be written", exc_info=True)


def remove() -> None:
    try:
        path().unlink(missing_ok=True)
    except OSError:
        logger.warning("The crash record of the ended check could not be removed", exc_info=True)


def read() -> dict | None:
    from freemocap.certification import _read_json
    record = _read_json(path())
    return record if isinstance(record, dict) else None


def interrupted_report(record: dict, exit_code: int | None = None) -> tuple[dict | None, str | None]:
    """The module report of the interrupted run (None when no check was listed yet), and the crashed check's name."""
    from freemocap import certification
    from freemocap.system.certify.start_check import version_set
    message = record.get("message") if isinstance(record.get("message"), dict) else {}
    rows = [row for row in message.get("checks") or () if isinstance(row, dict) and isinstance(row.get("name"), str)]
    step = message.get("step") if message.get("state") == "running" and isinstance(message.get("step"), dict) else {}
    crashed = next((row["name"] for row in rows if row["name"] == step.get("name") and row.get("result") is None), None)
    if not rows:
        return None, crashed
    checks = []
    for row in rows:
        if row.get("result") is not None:
            checks.append({"name": row["name"], "result": row["result"],
                           "reason": REASON_LOST if row["result"] in ("fail", "not-run") else None})
        elif row["name"] == crashed:
            checks.append({"name": crashed, "result": "fail", "reason": "crashed",
                           **({"numbers": {"exit_code": exit_code}} if exit_code is not None else {})})
        else:
            checks.append({"name": row["name"], "result": "not-run", "reason": "interrupted"})
    name = message.get("package") or "freemocap"
    media = certification.interrupted_media(checks) if name == "freemocap" else []
    if name == "freemocap":
        package, reasons = certification._identity()
    else:  # the package's own commit and tree state are not in its progress
        package, reasons = ({"name": name, "version": version_set().get(name), "commit": None, "tree_modified": None},
                            ["no-commit", "modified-tree"])
    return {"schema": certification.SCHEMA, "id": str(uuid.uuid4()), "package": package, "kind": record.get("level"),
            "created_utc": record.get("created_utc"), "host": certification._host(), "checks": checks,
            **({"test_media": media} if media else {}), "evidence": {"valid": False, "reasons": [*reasons, "interrupted"]}}, crashed


def record_provider_failure(check: str, created: str) -> None:
    """Store a crashed check of an EP on a GPU (`<ep>@<device>` or one of its `:` parts) as the failed quick check of
    that pair, by skellytracker's own writer; the CPU and freemocap's checks have no pair."""
    label = check.split(":")[0]
    if "@" not in label:
        return
    key = label.split("@")[0]
    import skellytracker.certification as tracker
    from skellytracker.core.eps import certification, evidence, store
    from skellytracker.core.eps.catalog import load_catalog
    from skellytracker.core.system.host import gpu_device_keys, probe_host
    catalog, host = load_catalog(), probe_host()
    for device_key, gpu in gpu_device_keys(host):
        if tracker._label(key, device_key) == label:
            # shortcut: skellytracker's private label rule and local-result writer, as its quick check calls them; ask
            # skellytracker for a public call to record a failed pair.
            tracker._record(certification, store, evidence, catalog, host, key, gpu, "fail", "", (), created, {})


def recover(record: dict, exit_code: int | None = None) -> str | None:
    """Keep the interrupted run's report and, at level quick, the crashed pair's failure; return the crashed package.
    It never raises: a crash record must not stop the app."""
    try:
        report, crashed = interrupted_report(record, exit_code)
        if report is not None:
            from freemocap.certification import _write_json, reports_dir
            _write_json(reports_dir() / f"{report['id']}.json", report)
        # At level full only a crashed probe or video check fails its pair, as a failure of either does (fifth grilling).
        if crashed is not None and (record.get("level") == "quick" or crashed.endswith((":probe", ":video"))):
            record_provider_failure(crashed, str(record.get("created_utc")))
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        if record.get("level") == "quick" and record.get("pair") is None and                 (message.get("package") or "freemocap") == "freemocap":  # the start check, in freemocap's own part
            from freemocap.system.certify.start_check import record_crash
            record_crash(crashed)
    except Exception:  # noqa: BLE001
        logger.exception("The crash record of a certify run could not be kept")
    message = record.get("message")
    return message.get("package") if isinstance(message, dict) else None
