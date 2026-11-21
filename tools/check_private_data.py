#!/usr/bin/env python3
"""Check the repo files for private data (decision 0001).

Usage::

    python tools/check_private_data.py [ROOT]

The tool reads each text file that git tracks, and each new file that git does not ignore. It skips
generated lock files. It reports:

- an absolute path in a user folder (``C:\\Users\\<name>``, ``/home/<name>``, ``/Users/<Name>``);
- an email address that is not on the allowlist. The allowlist keeps ``noreply@anthropic.com``, so
  that a document can name the AI attribution that the rules forbid;
- a private IPv4 address (``10.x.x.x``, ``172.16.x.x`` to ``172.31.x.x``, ``192.168.x.x``);
- a token with a known prefix, or a private-key header;
- a term of the local, untracked file ``.private-terms`` (one term on each line, ``#`` starts a
  comment). Use it for a hostname or a user name. Git must ignore it: a tracked list publishes
  the terms.

A placeholder such as ``C:\\Users\\<you>`` or ``/home/$USER`` is not reported. Standard library only.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PRIVATE_TERMS = ".private-terms"
# Generated lock files hold four-part package versions that look like private IP addresses.
SKIPPED_SUFFIXES = (".lock",)

# Reserved example domains (RFC 2606, RFC 6761), GitHub noreply addresses and public project contacts.
ALLOWED_EMAIL_DOMAINS = re.compile(
    r"(?:^|\.)(?:example\.(?:com|org|net)|invalid|test|localhost|users\.noreply\.github\.com)$",
    re.IGNORECASE,
)
# Add the public contact address of the project here, for example the one in pyproject.toml.
ALLOWED_EMAILS = {"noreply@anthropic.com", "info@freemocap.org"}

PLACEHOLDER = r"(?![<{%$])"
PATTERNS = {
    "user path": re.compile(
        rf"[A-Za-z]:[\\/]+Users[\\/]+{PLACEHOLDER}[\w.-]+"
        rf"|/home/{PLACEHOLDER}[A-Za-z_][\w.-]*"
        rf"|/Users/{PLACEHOLDER}[A-Z][\w.-]*"
    ),
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "private IP address": re.compile(
        r"(?<![\w.])(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?![\w.])"
    ),
    "token": re.compile(
        r"\b(?:hf_[A-Za-z0-9]{30,}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|github_pat_\w{20,}"
        r"|AKIA[0-9A-Z]{16}|sk-ant-[\w-]{20,}|sk-[A-Za-z0-9]{40,}|dckr_pat_[\w-]{20,})"
        r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    ),
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.kind}: {self.text}"


def repo_files(root: Path) -> list[Path]:
    """Tracked files and new files that git does not ignore, without generated lock files."""
    git = shutil.which("git")
    if git is None:
        raise SystemExit("git is not on the PATH")
    out = subprocess.run(  # noqa: S603
        [git, "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        check=True,
    )
    names = sorted({n for n in out.stdout.decode("utf-8").split("\0") if n})
    return [
        root / n for n in names if (root / n).is_file() and not n.endswith(SKIPPED_SUFFIXES)
    ]


def text_of(path: Path) -> str | None:
    """The text of a file, or None for a binary file."""
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="ignore")


def private_terms(root: Path) -> list[str]:
    path = root / PRIVATE_TERMS
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [t.strip() for t in lines if t.strip() and not t.strip().startswith("#")]


def is_allowed_email(address: str) -> bool:
    domain = address.rsplit("@", 1)[1]
    return address.lower() in ALLOWED_EMAILS or bool(ALLOWED_EMAIL_DOMAINS.search(domain))


def scan_text(rel: str, text: str, terms: list[str]) -> list[Finding]:
    findings = []
    lowered_terms = [(t, t.lower()) for t in terms]
    for number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                if kind == "email address" and is_allowed_email(match.group(0)):
                    continue
                findings.append(Finding(rel, number, kind, match.group(0)))
        lowered = line.lower()
        findings.extend(
            Finding(rel, number, "private term", "<from .private-terms>")
            for _, term in lowered_terms
            if term in lowered
        )
    return findings


def check(root: Path) -> list[Finding]:
    terms = private_terms(root)
    findings = []
    for path in repo_files(root):
        rel = path.relative_to(root).as_posix()
        if rel == PRIVATE_TERMS:
            continue
        text = text_of(path)
        if text is not None:
            findings.extend(scan_text(rel, text, terms))
    return findings


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    findings = check(root)
    if findings:
        print("\n".join(str(f) for f in findings))
        return 1
    print(f"private data: no findings ({len(repo_files(root))} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
