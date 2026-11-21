"""The commit-msg check warns about AI attribution and never stops a commit (decision 0001).

The test strings are built from parts, so that this file does not contain the email addresses that
the private-data check reports.
"""

from __future__ import annotations

from pathlib import Path

import check_ai_attribution as caa
import pytest

AT = "@"


@pytest.mark.parametrize(
    "line",
    [
        "Co-Authored-By: Claude Opus 5.5 <noreply" + AT + "anthropic.com>",
        "Co-authored-by: Cursor <cursoragent" + AT + "cursor.com>",
        "Co-authored-by: Copilot <1+Copilot" + AT + "users.noreply.github.com>",
        "Signed-off-by: Codex <codex" + AT + "openai.com>",
        "Assisted-by: any tool",
        "Generated-by: a script",
        "\N{ROBOT FACE} Generated with [Claude Code](https://claude.com/claude-code)",
        "Generated with Gemini",
    ],
)
def test_ai_attribution_is_found(line: str) -> None:
    assert caa.find(f"Fix the decode\n\n{line}\n") == [(3, line)]


@pytest.mark.parametrize(
    "message",
    [
        "Fix the decode\n\nCo-Authored-By: Jane Doe <jane" + AT + "example.com>\n",
        "Fix the decode\n\nSigned-off-by: Jane Doe <jane" + AT + "example.com>\n",
        "Add the RTMW sidecar for the wholebody model\n",
        "Warn about AI attribution in commit messages\n",
        "Fix the decode\n# Co-Authored-By: Claude, in a git comment line\n",
    ],
)
def test_other_messages_are_not_reported(message: str) -> None:
    assert caa.find(message) == []


def test_hook_warns_and_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text("Fix the decode\n\nCo-Authored-By: Claude <noreply" + AT + "anthropic.com>\n")
    assert caa.main(["check_ai_attribution.py", str(path)]) == 0
    out = capsys.readouterr().out
    assert "WARNING: AI attribution" in out
    assert "tell the user" in out


def test_hook_is_silent_for_a_clean_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text("Fix the decode\n")
    assert caa.main(["check_ai_attribution.py", str(path)]) == 0
    assert capsys.readouterr().out == ""
