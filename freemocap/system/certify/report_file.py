"""The certify report file: one Markdown file that merges module reports (skellycertify report format 1.2.0, section 4).

`build_report_file()` is pure: the same module reports, note and app block give the same bytes, so the file the
person views is the file that is sent. It refuses a file that breaks privacy rules 1 to 11 of section 6, the rules
the relay checks; `scrub_note()` applies rules 12 and 13 to the person's note before the file is built.
"""

import getpass
import json
import re
import socket
import subprocess
import textwrap
from functools import cache
from pathlib import Path

import freemocap
from freemocap.build_info import BUILD_GIT_SHA

SCHEMA = "skellycertify.report/1.2.0"  # 1.2.0: the Markdown part is the short summary for a person (spec 4.2)
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


def _row(cells: list[str]) -> str:
    return "|" + "|".join(f" {cell} " if cell else " " for cell in cells) + "|"


def _result(result: object) -> str:
    """`pass`, `fail` or `record` (the display of `record-only`); empty for no result."""
    return "record" if result == "record-only" else _cell(result)


def gpu_display_name(name: object) -> str:
    """A GPU name for the Markdown only (spec 4.2 display names): `NVIDIA GeForce RTX 3070` -> `NVIDIA RTX 3070`."""
    return _cell(re.sub(r"\((?i:R|TM)\)|\b(?:GeForce|Radeon|Arc|Graphics|GPU|Series)\b", " ", str(name or "")))


def cpu_display_name(name: object) -> str:
    """A CPU name for the Markdown only: no (R), (TM), generation prefix, clock speed or core-count suffix."""
    return _cell(re.sub(r"\((?i:R|TM)\)|\b\d+(?:st|nd|rd|th) Gen\b|\b(?:CPU )?@ ?[\d.]+ ?GHz|\b\d+-Core Processor\b",
                        " ", str(name or "")))


def os_display_name(label: object) -> str:
    """`os.label` without the edition words `Home` and `Pro`."""
    return _cell(re.sub(r"\b(?:Home|Pro)\b", " ", str(label or "")))


def _gb(size: object) -> str:
    return f"{round(size / 2**30)} GB" if isinstance(size, int) and size >= 2**30 else ""


def _host_lines(hosts: list[dict]) -> list[str]:
    """The one system list of the file (spec 4.2 item 3): each value from the first host that has its key."""
    os_label = next((host["os"]["label"] for host in hosts if (host.get("os") or {}).get("label")), None)
    cpu = next((host["cpu"]["name"] for host in hosts if (host.get("cpu") or {}).get("name")), None)
    ram = next((_gb(host["memory_bytes"]) for host in hosts if _gb(host.get("memory_bytes"))), None)
    return [line for line in (os_label and f"- OS: {os_display_name(os_label)}", cpu and f"- CPU: {cpu_display_name(cpu)}",
                              ram and f"- RAM: {ram}") if line]


def _gpu_cell(gpu: dict) -> str:
    return " ".join(filter(None, (gpu_display_name(gpu.get("name")), _gb(gpu.get("vram_bytes")))))


def _markdown(modules: list[dict], note: str | None, app: dict | None, created: str) -> list[str]:
    """The Markdown part before `## Data`: the short summary for a person (spec 4.2 items 1 to 7)."""
    def run(module: dict) -> str:
        package = module.get("package") or {}
        return f"{_cell(package.get('name'))} {_cell(package.get('version'))} · {_cell(module.get('kind'))} run"

    def validity(module: dict) -> str:
        evidence = module.get("evidence") or {}
        if evidence.get("valid"):
            return "valid as evidence"
        return "not valid as evidence: " + ", ".join(_cell(reason) for reason in evidence.get("reasons") or ())

    def when(time: str) -> str:
        return f"{time[:10]} {time[11:16]} UTC"

    lines = ["# Certify report", ""]
    if app is None and len(modules) == 1:
        lines += [f"{run(modules[0])} · {when(modules[0]['created_utc'])} · {validity(modules[0])}", ""]
    else:
        lines += [" · ".join(([f"{_cell(app.get('name'))} {_cell(app.get('version'))}"] if app else []) + [when(created)]),
                  "", *(f"- {run(module)} · {validity(module)}" for module in modules), ""]
    hosts = [module.get("host") or {} for module in modules]
    lines += [*_host_lines(hosts), ""]
    # The writer prints the summary items; it never computes them from checks (spec 3.7).
    items = [(index, item) for index, module in enumerate(modules) for item in module.get("summary") or ()
             if isinstance(item, dict)]
    eps = []
    for index, item in items:
        if item.get("group") != "ep":
            continue
        gpus = {gpu.get("id"): gpu for gpu in hosts[index].get("gpus") or ()}
        device = item.get("device")
        cell = _gpu_cell(gpus.get(device, {"name": device})) if device else "-"
        eps.append(_row([cell, _cell(item.get("name")), _result(item.get("result"))]))
        eps += [_row([cell, f"{_cell(item.get('name'))} GPU decode", _result(decode.get("result"))])
                for other, decode in items if other == index and decode.get("group") == "gpu-jpeg"
                and (decode.get("name"), decode.get("device")) == (item.get("name"), device)]
    named = {item.get("device") for _, item in items if item.get("group") == "ep"}
    unchecked = {}  # spec 4.2 item 4: one `not checked` row for each GPU id of the file that no `ep` item names
    for host in hosts:
        for gpu in host.get("gpus") or ():
            if gpu.get("id") not in named:
                unchecked.setdefault(gpu.get("id"), _row([_gpu_cell(gpu), "", "not checked"]))
    eps += unchecked.values()
    if eps:
        lines += ["| GPU | Module | Result |", "|---|---|---|", *eps, ""]
    cameras = [_row([_cell(item.get("name")), _result(item.get("result"))]) for _, item in items
               if item.get("group") == "camera"]
    lines += ["| Camera | Result |", "|---|---|", *cameras, ""] if cameras else ["Cameras: not checked on this system.", ""]
    failed = []  # spec 4.2 item 6: a row for each failed section, or for each failed check of a module with no sections
    for module in modules:
        name = _cell((module.get("package") or {}).get("name"))
        for row in (module.get("sections") if "sections" in module else module.get("checks")) or ():
            if row.get("result") == "fail":
                failed.append(_row([name, _cell(row.get("name")), _cell(row.get("reason"))]))
    if failed:
        lines += ["Failed checks:", "", "| Module | Check | Reason |", "|---|---|---|", *failed, ""]
    if note is not None:
        # Markdown characters escaped so the note shows as typed; wrapped so no line passes the 2000-character rule.
        quoted = [re.sub(r"([\\`*_\[\]<>!|~#])", r"\\\1", chunk)
                  for line in note.replace("\r\n", "\n").replace("\r", "\n").split("\n")
                  for chunk in textwrap.wrap(line, 900) or [""]]
        lines += ["Note of the person:", "", *(f"> {line}".rstrip() for line in quoted), ""]
    return lines[:-1]


def build_report_file(modules: list[dict], note: str | None, app: dict | None) -> tuple[str, bytes]:
    """The file name and the UTF-8 bytes of the report file (section 4.2) that holds `modules` in their order.

    The name and the time line use the earliest `created_utc` of the modules. A module with no `summary` gives no EP
    and no camera row (spec 3.7).
    """
    if not modules:
        raise ReportFileError("bad-module", "a report file holds at least one module report")
    if note is not None and len(note) > NOTE_MAX_CHARS:
        raise ReportFileError("bad-note", f"the note has more than {NOTE_MAX_CHARS} characters")
    times = [module.get("created_utc") for module in modules]
    if not all(isinstance(time, str) and CREATED_UTC.match(time) for time in times):
        raise ReportFileError("bad-module", "each module report needs created_utc as YYYY-MM-DDTHH:MM:SSZ")
    created = min(times)
    lines = _markdown(modules, note, app, created)
    data = {"schema": SCHEMA, "app": app, "modules": modules, "note": note}
    rule = privacy_rule(lines, data)
    if rule:
        raise ReportFileError("privacy-rule", str(rule))
    text = json.dumps(data, indent=1, ensure_ascii=False)
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", text)), default=0))
    lines += ["", "## Data", "", f"{fence}json", text, fence]
    year, month, day, hour, minute, second = CREATED_UTC.match(created).groups()
    return f"certify-report-{year}{month}{day}T{hour}{minute}{second}Z.md", ("\n".join(lines) + "\n").encode("utf-8")
