"""Hand-in of certify report files through the skellycertify relay (ep-certification-integration.md R1 to R5).

The backend sends. A file goes out only after the person viewed it and chose "send": the request names the
reports, the note and the SHA-256 of the file the person saw, and the file is rebuilt and must match. The
accepted bytes go to `<base data folder>/certify/outbox/` before the network call, and only those bytes are ever
sent. A relay error with `retry: true` keeps the file for the next backend start; after the first send and 3
retries failed, or on `retry: false` (413, 422 and the app-bug codes), the issue form is offered instead. A 200
marks the reports covered in skellytracker with the issue address and deletes the outbox copy.
"""

import hashlib
import json
import logging
import os
import re
import threading
from pathlib import Path

import requests

from freemocap.system.certify.report_file import ReportFileError, app_block, build_report_file, scrub_note
from freemocap.system.default_paths import get_default_freemocap_base_folder_path

logger = logging.getLogger(__name__)

RELAY_URL = "https://skellycertify-relay.dom-dd0.workers.dev"  # R5: empty means relay off, issue form only
RELAY_URL_ENV_VAR = "FREEMOCAP_CERTIFY_RELAY_URL"
RELAY_REPOSITORY = "domisjustanumber/skellycertify"
RELAY_MAX_BYTES = 262_144
MAX_FAILED_ATTEMPTS = 4  # the first send and 3 retries (R1)
TIMEOUT_SECONDS = (5, 30)  # connect, read
ISSUE_URL = re.compile(rf"^https://github\.com/{re.escape(RELAY_REPOSITORY)}/issues/([1-9][0-9]{{0,9}})$")
ERROR_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DETAIL_MAX_CHARS = 200

_send_lock = threading.Lock()  # one POST at a time: the start-up retry and a send route never race on one entry


class HandInError(Exception):
    """A hand-in request that cannot go ahead: `relay-off`, `file-changed` or `unknown-report`."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def relay_url() -> str:
    """The relay address: the environment variable when it is set (also to empty), else the constant."""
    return os.environ.get(RELAY_URL_ENV_VAR, RELAY_URL).strip().rstrip("/")


def issue_url_or_none(value: object) -> str | None:
    """`value` when it is the https address of an issue of the relay's repository on github.com, else None."""
    return value if isinstance(value, str) and ISSUE_URL.match(value) else None


def certify_folder() -> Path:
    return Path(get_default_freemocap_base_folder_path()) / "certify"


def outbox_folder() -> Path:
    return certify_folder() / "outbox"


def report_file_for(report_ids: list[str], note: str | None) -> tuple[str, bytes]:
    """The file name and bytes of the report file that would be sent for these reports and this note."""
    import skellytracker

    modules = []
    for report_id in dict.fromkeys(report_ids):
        try:
            module = skellytracker.read_report(report_id)
            modules.append((str(module.get("created_utc") or ""), report_id, module))
        except ValueError:
            raise HandInError("unknown-report", f"{report_id!r} is not a report of this host") from None
    # The relay finds duplicates by the file's SHA-256: the same reports give the same bytes in any caller order.
    modules.sort(key=lambda row: row[:2])
    return build_report_file([row[2] for row in modules], scrub_note(note), app_block())


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _accept(report_ids: list[str], note: str | None, sha256: str) -> tuple[str, bytes]:
    """The file the person viewed, rebuilt; it is kept as the local record (decision 10)."""
    name, body = report_file_for(report_ids, note)
    if hashlib.sha256(body).hexdigest() != sha256:
        raise HandInError("file-changed", "the report file is not the file that was viewed; view it again")
    _write(certify_folder() / name, body)
    return name, body


def _read_entry(sha256: str) -> dict | None:
    try:
        meta = json.loads((outbox_folder() / f"{sha256}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def _drop_entries(report_ids: list[str], keep: str | None = None) -> None:
    """Delete each outbox entry that holds one of these reports, except `keep`: a newer choice replaces it."""
    for path in outbox_folder().glob("*.json"):
        meta = _read_entry(path.stem)
        if path.stem != keep and meta is not None and set(meta.get("report_ids") or ()) & set(report_ids):
            for stale in (path, path.with_suffix(".md")):
                stale.unlink(missing_ok=True)


def outbox_entries() -> list[dict]:
    """Each outbox entry with its retry state, the oldest file name first."""
    entries = []
    for path in outbox_folder().glob("*.json"):
        meta = _read_entry(path.stem)
        if meta is None or not SHA256.match(path.stem) or not path.with_suffix(".md").is_file():
            continue
        error, failed = meta.get("last_error"), int(meta.get("failed_attempts") or 0)
        gave_up = error is not None and (not error.get("retry") or failed >= MAX_FAILED_ATTEMPTS)
        entries.append({"sha256": path.stem, "file_name": str(meta.get("file_name")),
                        "report_ids": [str(i) for i in meta.get("report_ids") or ()], "failed_attempts": failed,
                        "last_error": error, "retry_pending": not gave_up, "offer_issue_form": gave_up})
    return sorted(entries, key=lambda entry: (entry["file_name"], entry["sha256"]))


def _relay_error(response: requests.Response) -> dict:
    """The relay's `{error, retry, detail}` as plain data; a body that is not that shape is a `bad-response` to retry."""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("retry"), bool) and isinstance(body.get("error"), str) \
            and ERROR_CODE.match(body["error"]):
        detail = body.get("detail")
        return {"status": response.status_code, "error": body["error"], "retry": body["retry"],
                "detail": None if detail is None else str(detail)[:DETAIL_MAX_CHARS]}
    return {"status": response.status_code, "error": "bad-response", "retry": True, "detail": None}


def _accepted(response: requests.Response) -> dict | None:
    """The relay's 200 body when its issue address is an issue of the expected repository, else None."""
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    url = issue_url_or_none(body.get("issue_url"))
    number = body.get("issue_number")
    if url is None or type(number) is not int or number != int(ISSUE_URL.match(url).group(1)):
        return None
    return {"issue_url": url, "issue_number": body["issue_number"], "duplicate": body.get("duplicate") is True}


def _outcome(state: str, error: dict | None = None, accepted: dict | None = None, offer: bool = False) -> dict:
    accepted = accepted or {}
    return {"state": state, "issue_url": accepted.get("issue_url"), "issue_number": accepted.get("issue_number"),
            "duplicate": accepted.get("duplicate", False), "error": error, "offer_issue_form": offer}


def send_entry(sha256: str) -> dict:
    """POST one outbox file to the relay and act on the answer. The outcome `state` is `covered`, `kept` (the file
    stays for the next start) or `refused` (never retried; the issue form is offered)."""
    import skellytracker

    with _send_lock:
        meta = _read_entry(sha256)
        if meta is None:
            raise HandInError("unknown-report", "that file is not in the outbox")
        url = relay_url()
        if not url:
            raise HandInError("relay-off", "the relay is off; use the issue form")
        body = (outbox_folder() / f"{sha256}.md").read_bytes()
        try:
            response = requests.post(f"{url}/reports", data=body, timeout=TIMEOUT_SECONDS, allow_redirects=False,
                                     headers={"Content-Type": "text/markdown; charset=utf-8"})
        except requests.RequestException as error:
            failure = {"status": None, "error": "network", "retry": True, "detail": type(error).__name__}
        else:
            accepted = _accepted(response) if response.status_code == 200 else None
            if accepted is not None:
                known = {row["report_id"] for row in skellytracker.pending_reports(include_handed_in=True)}
                ids = [report_id for report_id in meta.get("report_ids") or () if report_id in known]
                if ids:
                    skellytracker.mark_reports(ids, "covered", reference=accepted["issue_url"])
                for path in (outbox_folder() / f"{sha256}.json", outbox_folder() / f"{sha256}.md"):
                    path.unlink(missing_ok=True)
                logger.info("Certify report %s handed in as issue %s", sha256[:12], accepted["issue_number"])
                return _outcome("covered", accepted=accepted)
            failure = _relay_error(response) if response.status_code != 200 else \
                {"status": 200, "error": "bad-response", "retry": True, "detail": None}
        meta["failed_attempts"] = int(meta.get("failed_attempts") or 0) + 1
        meta["last_error"] = failure
        _write(outbox_folder() / f"{sha256}.json", json.dumps(meta, indent=1).encode("utf-8"))
        logger.warning("Certify report %s not handed in: %s %s (retry %s)", sha256[:12], failure["status"],
                       failure["error"], failure["retry"])
        gave_up = not failure["retry"] or meta["failed_attempts"] >= MAX_FAILED_ATTEMPTS
        return _outcome("kept" if failure["retry"] else "refused", error=failure, offer=gave_up)


def send_report(report_ids: list[str], note: str | None, sha256: str) -> dict:
    """The person's "send": keep the accepted file in the outbox, then send it."""
    if not relay_url():
        raise HandInError("relay-off", "the relay is off; use the issue form")
    name, body = _accept(report_ids, note, sha256)
    if len(body) > RELAY_MAX_BYTES:
        return _outcome("refused", offer=True, error={"status": None, "error": "too-large", "retry": False,
                                                      "detail": f"the limit is {RELAY_MAX_BYTES} bytes"})
    ids = list(dict.fromkeys(report_ids))
    _drop_entries(ids, keep=sha256)
    if _read_entry(sha256) is None:
        _write(outbox_folder() / f"{sha256}.md", body)
        _write(outbox_folder() / f"{sha256}.json",
               json.dumps({"file_name": name, "report_ids": ids, "failed_attempts": 0, "last_error": None},
                          indent=1).encode("utf-8"))
    return send_entry(sha256)


def mark_opened(report_ids: list[str], note: str | None, sha256: str) -> None:
    """The person saved this file and opened the issue form: the reports are handed in, with no link."""
    import skellytracker

    _accept(report_ids, note, sha256)
    ids = list(dict.fromkeys(report_ids))
    _drop_entries(ids)
    skellytracker.mark_reports(ids, "opened")


def retry_outbox() -> None:
    """At backend start: send each kept file again, as it was accepted (R1, R3)."""
    if not relay_url():
        return
    for entry in outbox_entries():
        if entry["retry_pending"]:
            try:
                send_entry(entry["sha256"])
            except Exception:  # one entry must not stop the others or the backend
                logger.exception("A kept certify report could not be sent again")


def start_outbox_retry() -> None:
    """Retry the outbox on a daemon thread so that start-up and shutdown never wait on the network."""
    threading.Thread(target=retry_outbox, name="CertifyOutboxRetry", daemon=True).start()
