"""The certify report file against skellycertify's contract (report format 1.6.0, section 4).

`fixtures/certify/valid.md`, `valid-quick.md` and `refused-privacy.md` are copies of skellycertify `relay/samples/` at
`9e6d575` (format 1.4.0, unchanged at `0966552`, format 1.5.0, and at `ba9a071`, format 1.6.0); `build_report_file`
reproduces the two valid files byte for byte but for the file's schema id, which is now 1.6.0. `valid-component.md` is
freemocap's own: the writer built it (format 1.6.0) from a freemocap module with `component` items (Blender `skipped`
with `not-installed`) and a `test_media` list, and the first skellytracker module of `valid-quick.md`.
When the skellycertify checkout and node are present, the relay's own validator (`relay/src/report.js`, `relay/src/privacy.js`) checks the built file.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from freemocap.system.certify import report_file
from freemocap.system.certify.report_file import ReportFileError, build_report_file, clean_note, privacy_rule, scrub_note

FIXTURES = Path(__file__).parent / "fixtures" / "certify"
RELAY_SRC = Path(__file__).resolve().parents[3] / "skellycertify" / "relay" / "src"
# The UI's `cleanNote` test reads the same cases, so the two cleanings cannot drift apart unnoticed.
CLEAN_NOTE_CASES = json.loads((Path(__file__).parents[2] / "freemocap-ui" / "src" / "services" / "server"
                               / "clean-note-cases.json").read_text(encoding="utf-8"))


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
    module = {"schema": "skellycertify.report/1.4.0", "package": {"name": name, "version": "2.0.0"}, "kind": "full",
              "created_utc": created, "host": host, "checks": list(checks),
              "evidence": {"valid": valid, "reasons": [] if valid else ["modified-tree"]}}
    return module if summary is None else {**module, "summary": summary}


def _as_1_6_0(sample: str) -> str:
    """A 1.4.0 sample as the writer builds it now: the file's own schema id is 1.6.0, each module keeps its own."""
    return sample.replace('{\n "schema": "skellycertify.report/1.4.0",', '{\n "schema": "skellycertify.report/1.6.0",', 1)


def _head(body: bytes) -> str:
    return body.decode("utf-8").split("\n## Data\n")[0]


def test_one_module_all_pass_prints_the_short_summary():
    name, body = build_report_file([_module(checks=[{"name": "x", "result": "pass", "reason": None}])], None, None)
    assert name == "certify-report-20261120T002551Z.md"
    assert _head(body) == ("# Certify report\n\nskellytracker 2.0.0 · full run · 2026-11-20 00:25 UTC · valid as evidence\n\n"
                           f"{SYSTEM}\n{TABLE}\nCameras: not checked on this system.\n")
    assert json.loads(body.decode("utf-8").split("```json\n")[1].rsplit("```", 1)[0])["schema"] == report_file.SCHEMA


def test_a_failed_check_adds_the_failed_table_and_the_note_is_cleaned_and_quoted():
    module = _module(checks=[{"name": "directml@8086-a780-0", "result": "fail", "reason": "image-mismatch"},
                             {"name": "y", "result": "pass", "reason": None}], valid=False)
    text = _head(build_report_file([module], "works | elsewhere\n# ![x](y) a_b", None)[1])
    assert "· not valid as evidence: modified-tree" in text
    assert ("Checks that did not pass:\n\n| Package | Module | Test | Result | Reason |\n|---|---|---|---|---|\n"
            "| skellytracker | | directml@8086-a780-0 | fail | image-mismatch |\n\n") in text
    assert text.endswith("Note of the person:\n\n> works   elsewhere\n>     x (y) a\\_b\n")
    assert "Checks that did not pass:" not in _head(build_report_file([_module()], None, None)[1])


def test_a_not_run_check_has_a_row_only_when_a_partial_or_failed_item_names_its_module():
    camera = [{"group": "camera", "name": "Logitech C922", "device": "046d:085c", "result": "partial"},
              {"group": "camera", "name": "Razer Kiyo", "device": "1532:0e05", "result": "skipped", "reason": "busy"}]
    checks = [{"name": "set-fps", "module": "Logitech C922", "result": "fail", "reason": "timed-out"},
              {"name": "record-30s", "module": "Logitech C922", "result": "not-run", "reason": "over-budget"},
              {"name": "open", "module": "Razer Kiyo", "result": "not-run", "reason": "camera-busy"},
              {"name": "usb3", "result": "not-run", "reason": "no-usb3"}]
    sections = [{"id": "1", "name": "cameras", "result": "fail", "reason": "timed-out"},
                {"id": "2", "name": "crashed-part", "result": "fail", "reason": "crashed"}]
    module = _module("skellycam", checks=[{**check, "section": "1"} for check in checks], summary=camera)
    text = _head(build_report_file([{**module, "sections": sections}], None, None)[1])
    assert "| Logitech C922 | partial |\n| Razer Kiyo | skipped (busy) |\n" in text
    assert text.endswith("Checks that did not pass:\n\n| Package | Module | Test | Result | Reason |\n|---|---|---|---|---|\n"
                         "| skellycam | Logitech C922 | set-fps | fail | timed-out |\n"
                         "| skellycam | Logitech C922 | record-30s | not run | over-budget |\n"
                         "| skellycam | | crashed-part | fail | crashed |\n")


def test_a_cancelled_or_interrupted_module_reads_incomplete_and_skipped_items_say_why():
    reviewed = [{"group": "ep", "name": "CUDA", "device": "10de:2484", "result": "skipped", "reason": "reviewed"},
                {"group": "ep", "name": "DirectML", "device": "10de:2484", "result": "partial", "gate": "dml:gate"}]
    cancelled = {**_module(summary=reviewed), "evidence": {"valid": False, "reasons": ["cancelled"]}}
    text = _head(build_report_file([cancelled], None, None)[1])
    assert "· full run · 2026-11-20 00:25 UTC · incomplete · not valid as evidence: cancelled\n" in text
    assert ("| NVIDIA RTX 3070 8 GB | CUDA | skipped (already reviewed) |\n"
            "| NVIDIA RTX 3070 8 GB | DirectML | partial |\n") in text
    interrupted = {**_module("skellycam"), "evidence": {"valid": False, "reasons": ["modified-tree", "interrupted"]}}
    listed = _head(build_report_file([_module(), interrupted], None, {"name": "freemocap", "version": "2.0.0"})[1])
    assert ("- skellytracker 2.0.0 · full run · valid as evidence\n"
            "- skellycam 2.0.0 · full run · incomplete · not valid as evidence: modified-tree, interrupted\n") in listed


def test_benchmark_items_give_the_benchmark_table_after_the_gpu_table():
    bench = [{"group": "benchmark", "name": "CUDA", "device": "10de:2484", "stage": "pipeline-1", "ms_per_frame": 12.44,
              "fps": 80},
             {"group": "benchmark", "name": "CPU", "device": None, "stage": "blender-export", "ms_per_frame": 95, "fps": 10.55}]
    text = _head(build_report_file([_module(summary=SUMMARY + bench)], None, None)[1])
    assert (f"{TABLE}\n| GPU | Module | Stage | ms/frame | FPS |\n|---|---|---|---|---|\n"
            "| NVIDIA RTX 3070 8 GB | CUDA | pipeline-1 | 12.4 | 80.0 |\n| - | CPU | blender-export | 95.0 | 10.6 |\n\n"
            "Cameras:") in text
    assert "| Stage |" not in _head(build_report_file([_module()], None, None)[1])


def test_private_and_path_markers_show_without_angle_brackets_in_the_markdown():
    host = {**HOST, "os": {"name": "Linux", "label": "<private> Linux 24.04"}, "cpu": {"name": "<path> CPU"}}
    _, body = build_report_file([_module(host=host)], None, None)
    head = _head(body)
    assert "- OS: private Linux 24.04\n- CPU: path CPU\n" in head and "<" not in head
    assert '"<private> Linux 24.04"' in body.decode("utf-8")  # the JSON keeps the value


def test_ipv4_looking_values_and_link_markup_are_harmless_only_in_the_markdown():
    host = {**HOST, "os": {"name": "Linux", "label": "Ubuntu 24.04.1 kernel 6.8.0.45"},
            "gpus": [{**HOST["gpus"][0], "name": "Test GPU 1.2.3.4.5.6.7"}]}
    camera = {"group": "camera", "name": "see https://x](y) WWW.z ]:", "device": "046d:085c", "result": "fail"}
    _, body = build_report_file([_module(host=host, summary=SUMMARY + [camera])], None, None)
    head, text = _head(body), body.decode("utf-8")
    assert "- OS: Ubuntu 24.04.1 kernel 6 8 0 45\n" in head and "| Test 1 2 3 4 5 6 7 8 GB | CUDA | pass |" in head
    assert "| see https: //x] (y) WWW .z ] : | fail |" in head
    assert all(f'"{value}"' in text for value in ("Ubuntu 24.04.1 kernel 6.8.0.45", "Test GPU 1.2.3.4.5.6.7",
                                                  "see https://x](y) WWW.z ]:"))  # the JSON keeps each value
    if RELAY_SRC.is_dir() and shutil.which("node") is not None:
        assert _relay_verdict(body) == {"rule": 0}


def test_two_modules_of_two_packages_print_the_system_once_and_a_line_for_each_module():
    camera = {"group": "camera", "name": "Logitech C922", "device": "046d:085c", "result": "fail"}
    ticks = _module(checks=[{"name": "a ``` b", "result": "pass", "reason": None}])  # the fence outgrows a run of ticks
    modules = [ticks, _module("skellycam", "2026-11-19T10:00:00Z", summary=[camera], valid=False)]
    name, body = build_report_file(modules, "a ``` b", {"name": "freemocap", "version": "2.0.0", "commit": None})
    text = body.decode("utf-8")
    assert name == "certify-report-20261119T100000Z.md"
    assert text.startswith("# Certify report\n\nfreemocap 2.0.0 · 2026-11-19 10:00 UTC\n\n"
                           "- skellytracker 2.0.0 · full run · valid as evidence\n"
                           "- skellycam 2.0.0 · full run · not valid as evidence: modified-tree\n\n- OS: ")
    assert text.count("- CPU:") == 1 and "| Camera | Result |\n|---|---|\n| Logitech C922 | fail |\n" in text
    assert text.endswith("\n````\n") and "\n````json\n" in text and "\r" not in text
    assert json.loads(text.split("````json\n")[1].rsplit("````", 1)[0])["note"] == "a     b"
    own = _module("freemocap", summary=None, valid=False, host={key: HOST[key] for key in ("os", "cpu", "memory_bytes")})
    assert _head(build_report_file([own, _module()], None, {"name": "freemocap", "version": "2.0.0"})[1]) == (
        "# Certify report\n\nfreemocap 2.0.0 · 2026-11-20 00:25 UTC\n\n"
        "- freemocap 2.0.0 · full run · not valid as evidence: modified-tree\n"
        "- skellytracker 2.0.0 · full run · valid as evidence\n\n"
        f"{SYSTEM}\n{TABLE}\nCameras: not checked on this system.\n")


def test_a_file_with_two_reports_of_one_package_takes_the_oldest_time_in_its_name_and_header():
    """Spec 4.2 (format 1.6.0): the oldest `created_utc` of the module reports, whatever their order in the file."""
    modules = [_module(created="2026-11-21T09:30:00Z"), _module(created="2026-11-20T23:05:59Z")]
    name, body = build_report_file(modules, None, {"name": "freemocap", "version": "2.0.0", "commit": None})
    assert name == "certify-report-20261120T230559Z.md"
    assert body.decode("utf-8").startswith("# Certify report\n\nfreemocap 2.0.0 · 2026-11-20 23:05 UTC\n\n")


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
    assert build_report_file(data["modules"], data["note"], data["app"])[1].decode("utf-8") == _as_1_6_0(text)


def test_component_items_give_the_component_table_after_the_benchmark_table():
    bench = [{"group": "benchmark", "name": "CPU", "device": None, "stage": "tracking", "ms_per_frame": 82, "fps": 12.2}]
    parts = [{"group": "component", "name": "Data folder", "device": None, "result": "fail"},
             {"group": "component", "name": "MediaPipe", "device": None, "result": "skipped", "reason": "reviewed"},
             {"group": "component", "name": "Blender", "device": None, "result": "skipped", "reason": "not-installed"}]
    text = _head(build_report_file([_module(summary=SUMMARY + bench + parts)], None, None)[1])
    assert ("| - | CPU | tracking | 82.0 | 12.2 |\n\n| Module | Result |\n|---|---|\n| Data folder | fail |\n"
            "| MediaPipe | skipped (already reviewed) |\n| Blender | skipped (not installed) |\n\n"
            "Cameras: not checked on this system.\n") in text
    assert f"{TABLE}\n| Module | Result |\n|---|---|\n| Data folder | fail |\n" in _head(
        build_report_file([_module(summary=SUMMARY + parts[:1])], None, None)[1]), "directly after the GPU table"
    assert "\n| Module | Result |" not in _head(build_report_file([_module()], None, None)[1])


def test_the_component_sample_is_the_file_the_writer_builds_and_the_relay_accepts_its_mixed_versions():
    text, data = _sample("valid-component.md")
    assert [module["schema"] for module in data["modules"]] == ["skellycertify.report/1.6.0", "skellycertify.report/1.4.0"]
    _, body = build_report_file(data["modules"], data["note"], data["app"])
    assert body.decode("utf-8") == text and "| Module | Result |\n|---|---|\n| Build identity | pass |\n" in text
    assert "| Install facts | record |\n| Blender | skipped (not installed) |\n\n" in text  # format 1.6.0
    assert data["modules"][0]["test_media"] == [{"name": "quick_frames.zip", "sha256":
                                                 "a973456f417eab8e24ea8aa3f118a48142aa55143af69c73ee6799cb4f94c1f4",
                                                 "bytes": 6215661, "source": "bundled"}]
    if RELAY_SRC.is_dir() and shutil.which("node") is not None:
        assert _relay_verdict(body) == {"rule": 0}
        bad = body.replace(b'"name": "quick_frames.zip"', b'"name": "media/quick_frames.zip"')
        assert _relay_verdict(bad) == {"refused": "bad-value", "detail": "report.modules[0].test_media[0].name"}


def test_the_note_and_the_privacy_rules_refuse_a_file():
    _, data = _sample("valid.md")
    with pytest.raises(ReportFileError) as long_note:
        build_report_file(data["modules"], "x" * 2001, data["app"])
    assert long_note.value.code == "bad-note"
    with pytest.raises(ReportFileError) as mac:  # the cleaning keeps ":" and digits, so a MAC address is still refused
        build_report_file(data["modules"], "adapter 00:1a:2b:3c:4d:5e", data["app"])
    assert (mac.value.code, mac.value.detail) == ("privacy-rule", "4")
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


@pytest.mark.parametrize(("note", "clean"), CLEAN_NOTE_CASES)
def test_clean_note_keeps_what_the_relay_keeps_and_nothing_else(note, clean):
    assert clean_note(note) == clean


def test_the_file_holds_the_cleaned_note_and_refuses_only_a_note_too_long_after_cleaning():
    _, data = _sample("valid.md")
    built = json.loads(build_report_file(data["modules"], "mail someone@example.org!", data["app"])[1].decode("utf-8")
                       .split("```json\n")[1].rsplit("```", 1)[0])
    assert built["note"] == "mail someone example.org " and clean_note(None) is None
    shortened = build_report_file(data["modules"], "www." + "x" * 1998, data["app"])[1].decode("utf-8")
    assert f'"note": "{"x" * 1998}"' in shortened
    with pytest.raises(ReportFileError) as long_note:
        build_report_file(data["modules"], "!" * 2001, data["app"])
    assert long_note.value.code == "bad-note"


@pytest.mark.skipif(not RELAY_SRC.is_dir() or shutil.which("node") is None,
                    reason="needs the skellycertify checkout beside freemocap and node")
def test_the_relay_validator_accepts_each_cleaned_case():
    _, data = _sample("valid.md")
    _, body = build_report_file(data["modules"], "\n".join(note for note, _ in CLEAN_NOTE_CASES), data["app"])
    assert _relay_verdict(body) == {"rule": 0}


@pytest.mark.skipif(not RELAY_SRC.is_dir() or shutil.which("node") is None,
                    reason="needs the skellycertify checkout beside freemocap and node")
def test_the_relay_validator_accepts_the_built_file():
    _, data = _sample("valid.md")
    module = copy.deepcopy(data["modules"][0])
    module["created_utc"] = "2026-11-21T00:00:00Z"
    _, body = build_report_file([data["modules"][0], module], "two runs | `ticks`", report_file.app_block())
    assert _relay_verdict(body) == {"rule": 0}
    assert _relay_verdict(body.replace(b"Windows 11 Home 26H2", b"C:\\\\Users\\\\x"))["rule"] == 1


def test_modules_with_ids_pass_through_unchanged_in_a_file_that_declares_1_6_0():
    sample, data = _sample("valid-quick.md")  # two quick reports of one package, each with a v4 UUID id
    modules = copy.deepcopy(data["modules"])
    _, body = build_report_file(modules, data["note"], data["app"])
    text = body.decode("utf-8")
    assert text == _as_1_6_0(sample)  # its "Checks that did not pass:" table included
    built = json.loads(text.split("```json\n")[1].rsplit("```", 1)[0])
    assert built["schema"] == "skellycertify.report/1.6.0" and built["modules"] == data["modules"]
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
    monkeypatch.setattr(certification, "_posthoc", lambda cancelled, cleanup, media, test_media_dir: (
        "pass", None, {"frames": 3, "execution_providers": {"person": "cpu", "wholebody": "cpu"}, "seconds": 8.5}))
    monkeypatch.setattr(certification, "_blender", lambda cancelled, path=None: (
        "record-only", None, {"found": True, "version_major": 5, "version_minor": 2, "version_patch": 3}))
    # the level full with stand-ins for its recording, its pairs, its post-hoc session and Blender: nothing downloads
    monkeypatch.setattr(certification, "_pairs", lambda: [("cpu", "cpu", None, "CPU")])
    monkeypatch.setattr(certification, "_recording", lambda cancelled, folder, media: ("pass", None, {"downloaded": False}, tmp_path))
    monkeypatch.setattr(certification, "_usable_labels", lambda: {"cpu"})
    monkeypatch.setattr(certification, "_benchmark", lambda *args: ("pass", None, {"frames": 300, "stages": {
        "graph.load_and_track": {"total_s": 24.6, "ms_per_frame": 82.0, "fps": 12.2}}}))
    monkeypatch.setattr(certification, "_blender_path", lambda path: None)
    quick, full = certification.certify("quick", ui_remote=False), certification.certify("full")
    assert full["summary"] == [{"group": "component", "name": "Data folder", "device": None, "result": "pass"},
                               {"group": "component", "name": "Sample recording", "device": None, "result": "pass"},
                               {"group": "component", "name": "Blender", "device": None, "result": "skipped",
                                "reason": "not-installed"},
                               {"group": "benchmark", "name": "CPU", "device": None, "stage": "tracking",
                                "ms_per_frame": 82.0, "fps": 12.2}]
    _, data = _sample("valid-quick.md")
    # build_report_file applies freemocap's Python copy of privacy rules 1 to 11 and raises on a break
    _, body = build_report_file([quick, full, *data["modules"]], "freemocap and skellytracker", report_file.app_block())
    built = json.loads(body.decode("utf-8").split("```json\n")[1].rsplit("```", 1)[0])
    assert built["schema"] == "skellycertify.report/1.6.0" and built["modules"][:2] == [quick, full]
    assert quick["schema"] == full["schema"] == "skellycertify.report/1.6.0"
    head = _head(body)
    assert "| - | CPU | tracking | 82.0 | 12.2 |\n\n| Module | Result |\n|---|---|\n| Build identity |" in head
    assert "| Blender | record |" in head and "| Blender | skipped (not installed) |" in head  # quick: found; full: not
    assert head.count("| Data folder | pass |") == 2
    if RELAY_SRC.is_dir() and shutil.which("node") is not None:
        assert _relay_verdict(body) == {"rule": 0}
