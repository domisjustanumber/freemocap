"""The certify report file: one Markdown file that merges module reports (skellycertify report format 1.1.0, section 4).

`build_report_file()` is pure: the same module reports, note and app block give the same bytes, so the file the
person views is the file that is sent. It refuses a file that breaks privacy rules 1 to 11 of section 6, the rules
the relay checks; `scrub_note()` applies rules 12 and 13 to the person's note before the file is built.
"""

import getpass
import json
import re
import socket
import subprocess
from functools import cache
from pathlib import Path

import freemocap
from freemocap.build_info import BUILD_GIT_SHA

SCHEMA = "skellycertify.report/1.0.0"
SCHEMA_WITH_IDS = "skellycertify.report/1.1.0"  # 1.1.0 adds the optional module `id` (a v4 UUID)
NOTE_MAX_CHARS = 2000
COMMIT = re.compile(r"^[0-9a-f]{40}$")
CREATED_UTC = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$")

# Privacy rules 1 to 11 (report-format.md section 6), as skellycertify relay/src/privacy.js checks them.
PATH_RE = re.compile(r"(?:\b[A-Za-z]:[\\/]|\\\\[^\\\s]|/(?:home|Users|root)/|~[\\/])", re.ASCII)
PRIVATE_KEYS = frozenset({"hostname", "host_name", "node", "user", "username", "user_name", "email", "serial",
                          "serial_number", "uuid", "mac", "mac_address", "bus_id", "pci_bus_id", "luid", "ip",
                          "ip_address"})
PCI_RE = re.compile(r"\b(?:[0-9a-fA-F]{4}:)?[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]\b", re.ASCII)
MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", re.ASCII)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
                      r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}", re.ASCII)
MEDIA_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".mp4", ".avi", ".mkv", ".mov",
                    ".webm", ".wav", ".mp3", ".flac")
REASON_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
TRACEBACK = "Traceback (most recent call last)"
NOTE_PATH_RE = re.compile(PATH_RE.pattern + r"[^\s\"'|,;]*", re.ASCII)


class ReportFileError(ValueError):
    """The file cannot be made: `code` is `bad-note`, `bad-module` or `privacy-rule` (with the rule number)."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@cache
def app_block() -> dict:
    """`app` of the report file: freemocap's version and the commit CI wrote, else git's in a source tree, else None."""
    commit = BUILD_GIT_SHA if COMMIT.match(BUILD_GIT_SHA) else None
    if commit is None:
        try:
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(freemocap.__file__).parent, capture_output=True,
                                  text=True, timeout=5).stdout.strip()
            commit = head if COMMIT.match(head) else None
        except (OSError, subprocess.SubprocessError):
            commit = None
    return {"name": "freemocap", "version": freemocap.__version__, "commit": commit}


def scrub_note(note: str | None) -> str | None:
    """The note with paths as `<path>` and this host's user and host names as `<private>` (rules 12 and 13)."""
    if note is None or not note.strip():
        return None
    note = NOTE_PATH_RE.sub("<path>", note.strip().replace("\r\n", "\n").replace("\r", "\n"))
    names = set()
    for read in (getpass.getuser, socket.gethostname):
        try:
            names.add(read())
        except Exception:  # an unreadable name cannot be in the note through this host
            pass
    for name in sorted((name for name in names if name), key=len, reverse=True):
        note = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "<private>", note, flags=re.IGNORECASE)
    return note


def _string_rule(text: str) -> int:
    if PATH_RE.search(text):
        return 1
    if PCI_RE.search(text):
        return 3
    if MAC_RE.search(text):
        return 4
    if EMAIL_RE.search(text):
        return 5
    if len(text) > NOTE_MAX_CHARS:
        return 6
    if text.lower().endswith(MEDIA_EXTENSIONS):
        return 7
    if TRACEBACK in text:
        return 10
    return 0


def privacy_rule(markdown_lines: list[str], data: dict) -> int:
    """The lowest privacy rule (1 to 11) that the file breaks, or 0, as the relay computes it."""
    found = []

    def walk(value: object) -> None:
        if isinstance(value, str):
            found.append(_string_rule(value))
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for key, child in value.items():
                found.append(2 if key.lower() in PRIVATE_KEYS else _string_rule(key))
                if key == "reason" and child is not None and not (isinstance(child, str) and REASON_RE.match(child)):
                    found.append(9)
                walk(child)

    for line in markdown_lines:
        found.append(_string_rule(line))
        if "![" in line:
            found.append(8)
    walk(data)
    for module in data.get("modules") or ():
        reasons = (module.get("evidence") or {}).get("reasons") if isinstance(module, dict) else None
        if isinstance(reasons, list) and not all(isinstance(r, str) and REASON_RE.match(r) for r in reasons):
            found.append(9)
    note = data.get("note")
    if not (note is None or (isinstance(note, str) and len(note) <= NOTE_MAX_CHARS)):
        found.append(11)
    return min((rule for rule in found if rule), default=0)


def _cell(value: object) -> str:
    """One table cell: one line, a `|` escaped."""
    return " ".join(str("" if value is None else value).split()).replace("|", "\\|")


def build_report_file(modules: list[dict], note: str | None, app: dict | None) -> tuple[str, bytes]:
    """The file name and the UTF-8 bytes of the report file (section 4.2) that holds `modules` in their order.

    The name and the time line use the earliest `created_utc` of the modules. The note is only in the JSON block.
    """
    if not modules:
        raise ReportFileError("bad-module", "a report file holds at least one module report")
    if note is not None and len(note) > NOTE_MAX_CHARS:
        raise ReportFileError("bad-note", f"the note has more than {NOTE_MAX_CHARS} characters")
    times = [module.get("created_utc") for module in modules]
    if not all(isinstance(time, str) and CREATED_UTC.match(time) for time in times):
        raise ReportFileError("bad-module", "each module report needs created_utc as YYYY-MM-DDTHH:MM:SSZ")
    created = min(times)
    schema = SCHEMA_WITH_IDS if any("id" in module for module in modules) else SCHEMA
    lines = ["# Certify report", "",
             f"Schema `{schema}`, " + (f"app {_cell(app['name'])} {_cell(app['version'])}, " if app else "")
             + f"created {created} (UTC).", ""]
    for module in modules:
        package, evidence = module.get("package") or {}, module.get("evidence") or {}
        head = f"**{_cell(package.get('name'))} {_cell(package.get('version'))}:**"
        reasons = ", ".join(_cell(reason) for reason in evidence.get("reasons") or ())
        lines.append(f"{head} valid as evidence." if evidence.get("valid") else f"{head} not valid as evidence: {reasons}.")
    lines += ["", "| Module | Section | Result | Reason |", "|---|---|---|---|"]
    for module in modules:
        name = _cell((module.get("package") or {}).get("name"))
        rows = module.get("sections") if "sections" in module else module.get("checks")
        for row in rows or ():
            label = f"{row.get('id')}. {row.get('name')}" if "sections" in module else row.get("name")
            cells = (name, _cell(label), _cell(row.get("result")), _cell(row.get("reason")))
            lines.append("|" + "|".join(f" {cell} " if cell else " " for cell in cells) + "|")
    data = {"schema": schema, "app": app, "modules": modules, "note": note}
    rule = privacy_rule(lines, data)
    if rule:
        raise ReportFileError("privacy-rule", str(rule))
    text = json.dumps(data, indent=1, ensure_ascii=False)
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", text)), default=0))
    lines += ["", "## Data", "", f"{fence}json", text, fence]
    year, month, day, hour, minute, second = CREATED_UTC.match(created).groups()
    return f"certify-report-{year}{month}{day}T{hour}{minute}{second}Z.md", ("\n".join(lines) + "\n").encode("utf-8")
