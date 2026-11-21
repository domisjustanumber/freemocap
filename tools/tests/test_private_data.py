"""No tracked file contains private data (decision 0001).

The test strings are built from parts, so that this file does not contain the patterns that it checks.
"""

from __future__ import annotations

from pathlib import Path

import check_private_data as cpd
import pytest

REPO_ROOT = Path(cpd.__file__).resolve().parents[1]

USER = "al" + "ice"


def kinds(text: str, terms: list[str] | None = None) -> list[str]:
    return [f.kind for f in cpd.scan_text("doc.md", text, terms or [])]


def test_repository_has_no_private_data() -> None:
    assert [str(f) for f in cpd.check(REPO_ROOT)] == []


@pytest.mark.parametrize(
    "text",
    [
        "C:" + "\\Users\\" + USER + "\\GitHub\\repo",
        "c:" + "/Users/" + USER + "/GitHub",
        "/ho" + "me/" + USER + "/repo",
        "/Us" + "ers/" + USER.title() + "/repo",
    ],
)
def test_user_paths_are_reported(text: str) -> None:
    assert kinds(text) == ["user path"]


@pytest.mark.parametrize(
    "text",
    [
        "C:" + "\\Users\\<you>\\GitHub",
        "/ho" + "me/$USER/repo",
        "C:" + "\\Users\\%USERNAME%",
        "../OpenMMLab-Exporter/notes",
    ],
)
def test_placeholders_and_relative_paths_pass(text: str) -> None:
    assert kinds(text) == []


def test_email_addresses_are_reported_except_the_allowlist() -> None:
    at = "@"
    assert kinds(USER + at + "gmail.com") == ["email address"]
    assert kinds("a" + at + "example.com b" + at + "x.invalid") == []
    assert kinds("123+" + USER + at + "users.noreply.github.com") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("192." + "168.1.20", ["private IP address"]),
        ("10." + "0.0.5", ["private IP address"]),
        ("172." + "20.3.4", ["private IP address"]),
        ("172." + "32.3.4", []),
        ("onnxruntime 1.20.1", []),
        ("TensorRT 10." + "0.1.6.post1", []),
        ("v10." + "0.0.5", []),
    ],
)
def test_private_ip_addresses(text: str, expected: list[str]) -> None:
    assert kinds(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "hf" + "_" + "a" * 34,
        "gh" + "p_" + "B" * 36,
        "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "sk" + "-ant-" + "x" * 30,
        "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
    ],
)
def test_tokens_are_reported(text: str) -> None:
    assert kinds(text) == ["token"]


def test_private_terms_are_reported_without_the_term(tmp_path: Path) -> None:
    findings = cpd.scan_text("doc.md", "run on " + "Gera" + "ld today", ["gerald"])
    assert [str(f) for f in findings] == ["doc.md:1: private term: <from .private-terms>"]


def test_private_terms_file_is_read_without_comments(tmp_path: Path) -> None:
    (tmp_path / cpd.PRIVATE_TERMS).write_text("# hosts\nmyhost\n\n  other  \n", encoding="utf-8")
    assert cpd.private_terms(tmp_path) == ["myhost", "other"]


def test_private_terms_file_is_ignored_by_git() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert cpd.PRIVATE_TERMS in gitignore
