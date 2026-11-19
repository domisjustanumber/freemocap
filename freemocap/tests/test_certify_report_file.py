"""The certify report file against skellycertify's contract (report format 1.0.0, section 4).

`fixtures/certify/*.md` are copies of skellycertify `relay/samples/` at `33c6c19`. When the skellycertify checkout
and node are present, the relay's own validator (`relay/src/report.js`, `relay/src/privacy.js`) checks the built file.
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


def test_the_valid_sample_is_reproduced_byte_for_byte():
    text, data = _sample("valid.md")
    name, body = build_report_file(data["modules"], data["note"], data["app"])
    assert name == "certify-report-20261119T100000Z.md"
    # The sample has one line of prose for a person that the app does not write.
    assert body.decode("utf-8") == text.replace(
        "This file is a sample for the relay tests. It holds example values only.\n\n", "")


def test_two_modules_name_the_file_by_the_earliest_run_and_end_with_one_json_block():
    _, data = _sample("valid.md")
    later = copy.deepcopy(data["modules"][0])
    later.update(created_utc="2026-11-20T08:30:00Z", kind="quick", evidence={"valid": False, "reasons": ["no-commit"]})
    del later["sections"]
    later["checks"] = [{"name": "cuda@10de-2484-0", "result": "fail", "reason": "probe-L3-failed"}]
    name, body = build_report_file([later, data["modules"][0]], "a ``` b", data["app"])
    text = body.decode("utf-8")
    assert name == "certify-report-20261119T100000Z.md"
    assert "**skellytracker 2.0.0:** not valid as evidence: no-commit." in text
    assert "| skellytracker | cuda@10de-2484-0 | fail | probe-L3-failed |" in text
    assert text.endswith("\n````\n") and "\n````json\n" in text and "\r" not in text
    assert json.loads(text.split("````json\n")[1].rsplit("````", 1)[0])["note"] == "a ``` b"


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
