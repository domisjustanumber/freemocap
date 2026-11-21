"""The certify report file: one Markdown file that merges module reports (skellycertify report format 1.6.0, section 4).

`build_report_file()` is pure: the same module reports, note and app block give the same bytes, so the file the
person views is the file that is sent. It refuses a file that breaks privacy rules 1 to 11 of section 6, the rules
the relay checks; `scrub_note()` applies rules 12 and 13 to the person's note before the file is built, and
`clean_note()` (rules 18 and 20) cleans whatever note reaches `build_report_file()`.

The file declares 1.6.0, the format of its layout. Each module report keeps its own schema id: a module of an older
1.x report (one kept from an earlier version of a package) is a module the reader of major version 1 accepts (spec 8),
and the JSON block holds each report as its package wrote it.
"""

import getpass
import json
import re
import socket
import subprocess
import textwrap
import unicodedata
from functools import cache
from pathlib import Path

import freemocap
from freemocap.build_info import BUILD_GIT_SHA

SCHEMA = "skellycertify.report/1.6.0"  # the file declares the format of its Markdown layout (spec 4.1, 4.2)
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
# Rules 17, 18 and 20 as relay/src/privacy.js and issue.js state them (re.ASCII: JavaScript's \b and \d without `u`).
NOTE_KEPT = frozenset(" \n.,:;_+=()'%/?·-")  # rule 18, besides the Unicode categories L, M and N
LINK_RE = re.compile(r"://|www\.", re.ASCII | re.IGNORECASE)
MARKUP_RE = re.compile(r"(\])(?=[(:])|(:)(?=//)|(www)(?=\.)", re.ASCII | re.IGNORECASE)  # rule 17 less `<`
IPV4_PART = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IPV4_RE = re.compile(rf"\b(?:{IPV4_PART}\.){{3}}{IPV4_PART}\b", re.ASCII)


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


def _no_ipv4(text: str) -> str:
    """Each IPv4-looking string (rule 20) with its dots as spaces, again until none is left (`1.2.3.4.5.6.7`)."""
    while (spaced := IPV4_RE.sub(lambda match: match.group().replace(".", " "), text)) != text:
        text = spaced
    return text


def clean_note(note: str | None) -> str | None:
    """A clean note (rule 18): each character the relay does not keep as a space, then each `://` and `www.` removed
    until none is left; then no IPv4-looking string (rule 20). The UI mirrors it as `cleanNote` (shared test cases)."""
    if note is None:
        return None
    note = "".join(c if c in NOTE_KEPT or unicodedata.category(c)[0] in "LMN" else " " for c in note)
    while LINK_RE.search(note):
        note = LINK_RE.sub("", note)
    return _no_ipv4(note)


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


def _harmless(line: str) -> str:
    """Markdown text that rules 17 and 20 accept: `](`, `]:`, `://` and `www.` split by a space, and an IPv4-looking
    string (a four-part version, say) with spaces for dots. Only the readable part changes; the JSON keeps each value."""
    return _no_ipv4(MARKUP_RE.sub(r"\1\2\3 ", line))


def _cell(value: object) -> str:
    """One table cell or value of a line: one line, a `|` escaped, no `<` or `>` (rule 17: `<private>` shows as
    `private`), harmless."""
    return _harmless(" ".join(str("" if value is None else value).split()).replace("|", "\\|").replace("<", "").replace(">", ""))


def _row(cells: list[str]) -> str:
    return "|" + "|".join(f" {cell} " if cell else " " for cell in cells) + "|"


SKIPPED = {"busy": "skipped (busy)", "reviewed": "skipped (already reviewed)", "not-installed": "skipped (not installed)"}


def _result(item: dict) -> str:
    """The display of a summary item's result (spec 4.2): `record` for `record-only`, `skipped (<why>)` for `skipped`."""
    result = item.get("result")
    if result == "skipped":
        return SKIPPED.get(item.get("reason"), "skipped")
    return "record" if result == "record-only" else _cell(result)


def _figure(value: object) -> str:
    """A benchmark number with one decimal place."""
    return f"{value:.1f}" if isinstance(value, (int, float)) and not isinstance(value, bool) else _cell(value)


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


def incomplete(module: dict) -> bool:
    """The module's run did not end: its evidence reasons hold `cancelled` or `interrupted` (spec 4.2 part 2)."""
    reasons = (module.get("evidence") or {}).get("reasons") or ()
    return "cancelled" in reasons or "interrupted" in reasons


def _markdown(modules: list[dict], note: str | None, app: dict | None, created: str) -> list[str]:
    """The Markdown part before `## Data`: the short summary for a person (spec 4.2 parts 1 to 9)."""
    def run(module: dict) -> str:
        package = module.get("package") or {}
        return f"{_cell(package.get('name'))} {_cell(package.get('version'))} · {_cell(module.get('kind'))} run"

    def validity(module: dict) -> str:
        evidence = module.get("evidence") or {}
        reasons = evidence.get("reasons") or ()
        unfinished = "incomplete · " if incomplete(module) else ""
        if evidence.get("valid"):
            return unfinished + "valid as evidence"
        return unfinished + "not valid as evidence: " + ", ".join(_cell(reason) for reason in reasons)

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
    def gpu_of(index: int, item: dict) -> str:  # the GPU of the same module report whose id is `device`; `-` for none
        device = item.get("device")
        gpus = {gpu.get("id"): gpu for gpu in hosts[index].get("gpus") or ()}
        return _gpu_cell(gpus.get(device, {"name": device})) if device else "-"

    eps = []
    for index, item in items:
        if item.get("group") != "ep":
            continue
        cell = gpu_of(index, item)
        eps.append(_row([cell, _cell(item.get("name")), _result(item)]))
        eps += [_row([cell, f"{_cell(item.get('name'))} GPU decode", _result(decode)])
                for other, decode in items if other == index and decode.get("group") == "gpu-jpeg"
                and (decode.get("name"), decode.get("device")) == (item.get("name"), item.get("device"))]
    named = {item.get("device") for _, item in items if item.get("group") == "ep"}
    unchecked = {}  # spec 4.2 item 4: one `not checked` row for each GPU id of the file that no `ep` item names
    for host in hosts:
        for gpu in host.get("gpus") or ():
            if gpu.get("id") not in named:
                unchecked.setdefault(gpu.get("id"), _row([_gpu_cell(gpu), "", "not checked"]))
    eps += unchecked.values()
    if eps:
        lines += ["| GPU | Module | Result |", "|---|---|---|", *eps, ""]
    benchmarks = [_row([gpu_of(index, item), _cell(item.get("name")), _cell(item.get("stage")), _figure(item.get("ms_per_frame")),
                        _figure(item.get("fps"))]) for index, item in items if item.get("group") == "benchmark"]
    if benchmarks:
        lines += ["| GPU | Module | Stage | ms/frame | FPS |", "|---|---|---|---|---|", *benchmarks, ""]
    components = [_row([_cell(item.get("name")), _result(item)]) for _, item in items if item.get("group") == "component"]
    if components:  # spec 4.2 part 6
        lines += ["| Module | Result |", "|---|---|", *components, ""]
    cameras = [_row([_cell(item.get("name")), _result(item)]) for _, item in items if item.get("group") == "camera"]
    lines += ["| Camera | Result |", "|---|---|", *cameras, ""] if cameras else ["Cameras: not checked on this system.", ""]
    # Spec 4.2 part 8: each failed check, each not-run check whose `module` names a partial or failed item of its module
    # report (not every check that cannot run here), then each failed section with no check of its own.
    rows = []
    for index, module in enumerate(modules):
        name = _cell((module.get("package") or {}).get("name"))
        open_items = {item.get("name") for other, item in items if other == index and item.get("result") in ("partial", "fail")}
        checks = [check for check in module.get("checks") or () if isinstance(check, dict)]
        with_checks = {check.get("section") for check in checks}
        for row in [*(check for check in checks if check.get("result") == "fail"
                      or (check.get("result") == "not-run" and check.get("module") in open_items)),
                    *(section for section in module.get("sections") or ()
                      if isinstance(section, dict) and section.get("result") == "fail" and section.get("id") not in with_checks)]:
            rows.append(_row([name, _cell(row.get("module")), _cell(row.get("name")),
                              "fail" if row.get("result") == "fail" else "not run", _cell(row.get("reason"))]))
    if rows:
        lines += ["Checks that did not pass:", "", "| Package | Module | Test | Result | Reason |", "|---|---|---|---|---|",
                  *rows, ""]
    if note is not None:
        # A clean note's one Markdown character, `_`, escaped so it shows as typed; wrapped under the 2000-character rule.
        quoted = [chunk.replace("_", "\\_") for line in note.split("\n") for chunk in textwrap.wrap(line, 900) or [""]]
        # Harmless again: the escape or a wrap can put a word boundary next to a number of the note.
        lines += ["Note of the person:", "", *(_harmless(f"> {line}".rstrip()) for line in quoted), ""]
    return lines[:-1]


def build_report_file(modules: list[dict], note: str | None, app: dict | None) -> tuple[str, bytes]:
    """The file name and the UTF-8 bytes of the report file (section 4.2) that holds `modules` in their order.

    The name and the time line use the earliest `created_utc` of the modules. A module with no `summary` gives no row
    to the GPU, benchmark, component or camera table (spec 3.7).
    """
    if not modules:
        raise ReportFileError("bad-module", "a report file holds at least one module report")
    note = clean_note(note)  # whatever a client sent, the file holds a clean note; only its length is refused
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
