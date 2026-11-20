"""The certify report file against skellycertify's contract (report format 1.2.0, section 4).

`fixtures/certify/*.md` are copies of skellycertify `relay/samples/` at `33c6c19` (`valid-quick.md` at `3609369`;
`valid.md` at `c8f8f35`, format 1.2.0, which `build_report_file` reproduces byte for byte).
When the skellycertify checkout and node are present, the relay's own validator (`relay/src/report.js`, `relay/src/privacy.js`) checks the built file.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from freemocap.system.certify import report_file
from freemocap.system.certify.report_file import ReportFileError, build_report_file, privacy_rule, scrub_note

FIXTURES = Path(__file__).parent / "fixtures" / "certify"
RELAY_SRC = Path(__file__).resolve().parents[3] / "skellycertify" / "relay" / "src"


def _sample(name: str) -> tuple[str, dict]:
    text = (FIXTURES / name).read_text(encoding="utf-8").replace("\r\n", "\n")
    return text, json.loads(text.split("```json\n")[1].rsplit("```", 1)[0])


def _relay_verdict(body: bytes) -> dict:
    """The relay's parse and privacy verdict on `body`, from its own JavaScript."""
    script = (f"import {{parseReport}} from '{(RELAY_SRC / 'report.js').as_uri()}';"
              f"import {{privacyRule}} from '{(RELAY_SRC / 'privacy.js').as_uri()}';"
              "let t='';process.stdin.setEncoding('utf8');process.stdin.on('data',c=>t+=c);process.stdin.on('end',()=>{"
              "try{const r=parseReport(t);console.log(JSON.stringify({rule:privacyRule(r.markdown,r.data)}));}"
              "catch(e){console.log(JSON.stringify({refused:e.code,detail:e.detail}));}});")
    result = subprocess.run(["node", "--input-type=module", "-e", script], input=body, capture_output=True, timeout=60,
                            check=True)
    return json.loads(result.stdout)


HOST = {"os": {"name": "Windows", "label": "Windows 11 Home 26H2"}, "cpu": {"name": "Intel(R) Core(TM) i7-14700K"},
        "memory_bytes": 68388003840,
        "gpus": [{"vendor": "nvidia", "name": "NVIDIA GeForce RTX 3070", "id": "10de:2484", "vram_bytes": 8589934592},
                 {"vendor": "intel", "name": "Intel(R) UHD Graphics 770", "id": "8086:a780", "vram_bytes": 134217728}]}
SUMMARY = [{"group": "ep", "name": "TensorRT RTX", "device": "10de:2484", "result": "pass"},
           {"group": "gpu-jpeg", "name": "TensorRT RTX", "device": "10de:2484", "result": "pass"},
           {"group": "ep", "name": "CUDA", "device": "10de:2484", "result": "pass"},
           {"group": "gpu-jpeg", "name": "CUDA", "device": "10de:2484", "result": "fail"},
           {"group": "ep", "name": "DirectML", "device": "10de:2484", "result": "pass"},
           {"group": "ep", "name": "DirectML", "device": "8086:a780", "result": "pass"},
           {"group": "ep", "name": "CPU", "device": None, "result": "record-only"}]
TABLE = """| GPU | Module | Result |
|---|---|---|
| NVIDIA RTX 3070 8 GB | TensorRT RTX | pass |
| NVIDIA RTX 3070 8 GB | TensorRT RTX GPU decode | pass |
| NVIDIA RTX 3070 8 GB | CUDA | pass |
| NVIDIA RTX 3070 8 GB | CUDA GPU decode | fail |
| NVIDIA RTX 3070 8 GB | DirectML | pass |
| Intel UHD 770 | DirectML | pass |
| - | CPU | record |
"""
SYSTEM = "- OS: Windows 11 26H2\n- CPU: Intel Core i7-14700K\n- RAM: 64 GB\n"


def _module(name="skellytracker", created="2026-11-20T00:25:51Z", checks=(), summary=SUMMARY, host=HOST, valid=True):
    module = {"schema": "skellycertify.report/1.2.0", "package": {"name": name, "version": "2.0.0"}, "kind": "full",
              "created_utc": created, "host": host, "checks": list(checks),
              "evidence": {"valid": valid, "reasons": [] if valid else ["modified-tree"]}}
    return module if summary is None else {**module, "summary": summary}


def _head(body: bytes) -> str:
    return body.decode("utf-8").split("\n## Data\n")[0]


def test_one_module_all_pass_prints_the_short_summary():
    name, body = build_report_file([_module(checks=[{"name": "x", "result": "pass", "reason": None}])], None, None)
    assert name == "certify-report-20261120T002551Z.md"
    assert _head(body) == ("# Certify report\n\nskellytracker 2.0.0 · full run · 2026-11-20 00:25 UTC · valid as evidence\n\n"
                           f"{SYSTEM}\n{TABLE}\nCameras: not checked on this system.\n")
    assert json.loads(body.decode("utf-8").split("```json\n")[1].rsplit("```", 1)[0])["schema"] == report_file.SCHEMA


def test_a_failed_check_adds_the_failed_table_and_the_note_is_quoted_and_escaped():
    module = _module(checks=[{"name": "directml@8086-a780-0", "result": "fail", "reason": "image-mismatch"},
                             {"name": "y", "result": "pass", "reason": None}], valid=False)
    text = _head(build_report_file([module], "works | elsewhere\n# ![x](y)", None)[1])
    assert "· not valid as evidence: modified-tree" in text
    assert ("Failed checks:\n\n| Module | Check | Reason |\n|---|---|---|\n"
            "| skellytracker | directml@8086-a780-0 | image-mismatch |\n\n") in text
    assert text.endswith("Note of the person:\n\n> works \\| elsewhere\n> \\# \\!\\[x\\](y)\n")
    assert "Failed checks:" not in _head(build_report_file([_module()], None, None)[1])


def test_two_modules_of_two_packages_print_the_system_once_and_a_line_for_each_module():
    camera = {"group": "camera", "name": "Logitech C922", "device": "046d:085c", "result": "fail"}
    modules = [_module(), _module("skellycam", "2026-11-19T10:00:00Z", summary=[camera], valid=False)]
    name, body = build_report_file(modules, "a ``` b", {"name": "freemocap", "version": "2.0.0", "commit": None})
    text = body.decode("utf-8")
    assert name == "certify-report-20261119T100000Z.md"
    assert text.startswith("# Certify report\n\nfreemocap 2.0.0 · 2026-11-19 10:00 UTC\n\n"
                           "- skellytracker 2.0.0 · full run · valid as evidence\n"
                           "- skellycam 2.0.0 · full run · not valid as evidence: modified-tree\n\n- OS: ")
    assert text.count("- CPU:") == 1 and "| Camera | Result |\n|---|---|\n| Logitech C922 | fail |\n" in text
    assert text.endswith("\n````\n") and "\n````json\n" in text and "\r" not in text
    assert json.loads(text.split("````json\n")[1].rsplit("````", 1)[0])["note"] == "a ``` b"
    own = _module("freemocap", summary=None, valid=False, host={key: HOST[key] for key in ("os", "cpu", "memory_bytes")})
    assert _head(build_report_file([own, _module()], None, {"name": "freemocap", "version": "2.0.0"})[1]) == (
        "# Certify report\n\nfreemocap 2.0.0 · 2026-11-20 00:25 UTC\n\n"
        "- freemocap 2.0.0 · full run · not valid as evidence: modified-tree\n"
        "- skellytracker 2.0.0 · full run · valid as evidence\n\n"
        f"{SYSTEM}\n{TABLE}\nCameras: not checked on this system.\n")


def test_display_names_shorten_only_the_markdown():
    assert report_file.gpu_display_name("NVIDIA GeForce RTX 3070") == "NVIDIA RTX 3070"
    assert report_file.gpu_display_name("Intel(R) UHD Graphics 770") == "Intel UHD 770"
    assert report_file.gpu_display_name("Intel(R) Arc(TM) A770 Graphics") == "Intel A770"
    assert report_file.gpu_display_name("AMD Radeon RX 7800 XT") == "AMD RX 7800 XT"
    assert report_file.cpu_display_name("Intel(R) Core(TM) i7-14700K") == "Intel Core i7-14700K"
    assert report_file.cpu_display_name("13th Gen Intel(R) Core(TM) i9-13900K") == "Intel Core i9-13900K"
    assert report_file.cpu_display_name("Intel(R) Core(TM) i7-8700 CPU @ 3.20GHz") == "Intel Core i7-8700"
    assert report_file.cpu_display_name("AMD Ryzen 7 7700X 8-Core Processor") == "AMD Ryzen 7 7700X"
    assert report_file.os_display_name("Windows 11 Home 26H2") == report_file.os_display_name("Windows 11 Pro 26H2") \
        == "Windows 11 26H2"
    _, body = build_report_file([_module()], None, None)
    assert '"NVIDIA GeForce RTX 3070"' in body.decode("utf-8")  # the JSON keeps the driver's name


def test_a_gpu_that_no_ep_item_names_gets_one_not_checked_row():
    none = _head(build_report_file([_module(summary=None), _module(summary=[])], None, None)[1])
    assert none.endswith(f"{SYSTEM}\n| GPU | Module | Result |\n|---|---|---|\n| NVIDIA RTX 3070 8 GB | | not checked |\n"
                         "| Intel UHD 770 | | not checked |\n\nCameras: not checked on this system.\n")
    one = _head(build_report_file([_module(summary=SUMMARY[2:3])], None, None)[1])
    assert ("| GPU | Module | Result |\n|---|---|---|\n| NVIDIA RTX 3070 8 GB | CUDA | pass |\n"
            "| Intel UHD 770 | | not checked |\n\n") in one
    bare = _head(build_report_file([_module(summary=None, host={"cpu": HOST["cpu"]})], None, None)[1])
    assert "| GPU |" not in bare and "- CPU: Intel Core i7-14700K\n\nCameras:" in bare


def test_the_system_list_takes_each_value_from_the_first_host_that_has_it():
    text = _head(build_report_file([_module(summary=None, host={"cpu": {"name": "AMD Ryzen 7 7700X 8-Core Processor"}}),
                                    _module()], None, None)[1])
    assert "\n- OS: Windows 11 26H2\n- CPU: AMD Ryzen 7 7700X\n- RAM: 64 GB\n\n" in text


def test_a_long_note_line_is_wrapped_under_the_2000_character_rule():
    _, body = build_report_file([_module()], "word " * 399 + "x" * 4, None)
    assert max(len(line) for line in _head(body).splitlines()) <= 2000


def test_the_valid_sample_is_the_file_the_writer_builds_from_its_own_data():
    text, data = _sample("valid.md")
    assert build_report_file(data["modules"], data["note"], data["app"])[1].decode("utf-8") == text


def test_the_note_and_the_privacy_rules_refuse_a_file():
    _, data = _sample("valid.md")
    with pytest.raises(ReportFileError) as long_note:
        build_report_file(data["modules"], "x" * 2001, data["app"])
    assert long_note.value.code == "bad-note"
    with pytest.raises(ReportFileError) as email:
        build_report_file(data["modules"], "write to someone@example.org", data["app"])
    assert (email.value.code, email.value.detail) == ("privacy-rule", "5")
    _, refused = _sample("refused-privacy.md")
    assert privacy_rule([], refused) == 1
    assert privacy_rule(["![image](x)"], data) == 8
    assert privacy_rule([], {"modules": [], "note": None, "serial": "1"}) == 2


def test_scrub_note_removes_paths_and_this_hosts_names(monkeypatch):
    monkeypatch.setattr(report_file.getpass, "getuser", lambda: "alice")
    monkeypatch.setattr(report_file.socket, "gethostname", lambda: "ALICE-PC")
    note = scrub_note("  Alice ran it on alice-pc from C:\\Users\\alice\\freemocap_data, malice stays\r\n")
    assert note == "<private> ran it on <private> from <path>, malice stays"
    assert scrub_note("   ") is None and scrub_note(None) is None


@pytest.mark.skipif(not RELAY_SRC.is_dir() or shutil.which("node") is None,
                    reason="needs the skellycertify checkout beside freemocap and node")
def test_the_relay_validator_accepts_the_built_file():
    _, data = _sample("valid.md")
    module = copy.deepcopy(data["modules"][0])
    module["created_utc"] = "2026-11-21T00:00:00Z"
    _, body = build_report_file([data["modules"][0], module], "two runs | `ticks`", report_file.app_block())
    assert _relay_verdict(body) == {"rule": 0}
    assert _relay_verdict(body.replace(b"Windows 11 Home 26H2", b"C:\\\\Users\\\\x"))["rule"] == 1


def test_modules_with_ids_declare_1_2_0_and_pass_through_unchanged():
    _, data = _sample("valid-quick.md")  # two quick reports of one package, each with a v4 UUID id
    modules = copy.deepcopy(data["modules"])
    _, body = build_report_file(modules, data["note"], data["app"])
    text = body.decode("utf-8")
    assert text.startswith("# Certify report\n\nfreemocap 2.0.0 · 2026-11-19 10:00 UTC\n\n- skellytracker ")
    built = json.loads(text.split("```json\n")[1].rsplit("```", 1)[0])
    assert built["schema"] == "skellycertify.report/1.2.0" and built["modules"] == data["modules"]
    if RELAY_SRC.is_dir() and shutil.which("node") is not None:
        assert _relay_verdict(body) == {"rule": 0}
        bad_id = body.replace(b"3f2b8c1e-9a4d-4e7b-b6a1-0c5d2e8f7a90", b"quick-20261119T100000Z")
        assert _relay_verdict(bad_id)["refused"] == "bad-value"


def test_freemocaps_own_modules_obey_the_privacy_rules_and_the_relay_validator_beside_skellytrackers(tmp_path, monkeypatch):
    """freemocap's real `certify()` with stand-ins for the spawn child and Blender, quick and full, in one file with two
    skellytracker modules (one file may hold modules of two packages)."""
    from freemocap import certification

    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(tmp_path))
    monkeypatch.setattr(certification, "_spawn_imports", lambda cancelled: ({"failed": [], "from_bundle": None}, None))
    monkeypatch.setattr(certification, "_blender", lambda cancelled, path=None: (
        "record-only", None, {"found": True, "version_major": 5, "version_minor": 2, "version_patch": 3}))
    quick, full = certification.certify("quick", ui_remote=False), certification.certify("full")
    assert "partial-run" in full["evidence"]["reasons"] and full["evidence"]["valid"] is False
    _, data = _sample("valid-quick.md")
    # build_report_file applies freemocap's Python copy of privacy rules 1 to 11 and raises on a break
    _, body = build_report_file([quick, full, *data["modules"]], "freemocap and skellytracker", report_file.app_block())
    built = json.loads(body.decode("utf-8").split("```json\n")[1].rsplit("```", 1)[0])
    assert built["schema"] == "skellycertify.report/1.2.0" and built["modules"][:2] == [quick, full]
    if RELAY_SRC.is_dir() and shutil.which("node") is not None:
        assert _relay_verdict(body) == {"rule": 0}
