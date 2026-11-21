"""Check relative Markdown links and their #anchor targets.

Anchors are generated the way GitHub does: lowercase; punctuation dropped
except `-` and `_`; each space becomes `-`; a repeated heading gets `-1`,
`-2`, ... appended. Links inside fenced code blocks and inline code are
skipped.

In each `AGENTS.md`, `notes/`, `.claude/skills/` and folder named `decisions`, a
GitHub `blob`, `tree` or `commit` link must pin a full 40-character SHA
(decision 0001).

The check skips the files in the folders of `specs/model-sidecar/proposals/`. A proposal record
is a frozen byte copy. The check covers `specs/model-sidecar/proposals/README.md` (decision 1HKJ).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_LINK = re.compile(r"(?<!!)\[(?:[^\]\[]|\[[^\]]*\])*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_INLINE_CODE = re.compile(r"`[^`]*`")
_HTML_ANCHOR = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"")
_GITHUB_REF = re.compile(
    r"^https?://github\.com/[^/]+/[^/]+/(?:blob|tree|commit)/([^/#?]+)", re.IGNORECASE
)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_PINNED_SCOPES = ("notes/", ".claude/skills/")


def _strip_inline_code(text: str) -> str:
    return _INLINE_CODE.sub("", text)


def github_slug(heading: str) -> str:
    """Return the anchor GitHub generates for a heading's text."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    # GitHub keeps the text of a code span literally (including `<...>`) and
    # drops HTML tags only outside code spans.
    parts = re.split(r"(`[^`]*`)", text)
    text = "".join(
        (
            part[1:-1]
            if len(part) > 1 and part.startswith("`") and part.endswith("`")
            else re.sub(r"<[^>]+>", "", part)
        )
        for part in parts
    )
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    """Return every anchor a Markdown file defines."""
    found: set[str] = set()
    counts: dict[str, int] = {}
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        found.update(_HTML_ANCHOR.findall(line))
        match = _HEADING.match(line)
        if not match:
            continue
        slug = github_slug(match.group(2))
        n = counts.get(slug, 0)
        counts[slug] = n + 1
        found.add(slug if n == 0 else f"{slug}-{n}")
    return found


def links(path: Path) -> list[tuple[int, str]]:
    """Return `(line_number, target)` for each link outside code."""
    result: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        text = _strip_inline_code(line)
        for pattern in (_LINK, _IMAGE):
            result.extend((number, m.group(1)) for m in pattern.finditer(text))
    return result


def needs_pinned_links(path: Path, root: Path) -> bool:
    """True when GitHub links in `path` must pin a full SHA."""
    rel = path.relative_to(root).as_posix()
    return (
        rel.rsplit("/", 1)[-1] == "AGENTS.md"
        or any(rel.startswith(scope) for scope in _PINNED_SCOPES)
        or "decisions" in rel.split("/")[:-1]
    )


def check_file(path: Path, root: Path) -> list[str]:
    """Return one error string per broken link in `path`."""
    errors: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}
    pinned = needs_pinned_links(path, root)
    for number, target in links(path):
        where = f"{path.relative_to(root).as_posix()}:{number}"
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
            ref = _GITHUB_REF.match(target)
            if pinned and ref and not _FULL_SHA.match(ref.group(1)):
                errors.append(f"{where}: GitHub link must pin a full SHA: {target}")
            continue  # http:, https:, mailto:, ...
        file_part, _, anchor = target.partition("#")
        file_part = unquote(file_part)
        dest = path if not file_part else (path.parent / file_part).resolve()
        if not dest.exists():
            errors.append(f"{where}: missing file {target}")
            continue
        if anchor and dest.suffix.lower() == ".md":
            if dest not in anchor_cache:
                anchor_cache[dest] = anchors(dest)
            if unquote(anchor) not in anchor_cache[dest]:
                errors.append(f"{where}: missing anchor {target}")
    return errors


def repo_files(root: Path) -> list[str]:
    """The POSIX paths under `root` of the tracked files, and of the new files that git keeps.

    Git ignores node_modules/, build output and the other folders in each `.gitignore`. Without git,
    or when `root` is not in a git repo, the tool walks the tree and skips only hidden folders.
    """
    git = shutil.which("git")
    if git is not None:
        done = subprocess.run(  # noqa: S603
            [git, "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            check=False,
        )
        if done.returncode == 0:
            return sorted({n for n in done.stdout.decode("utf-8").split("\0") if n})
    names = []
    for folder, dirs, found in os.walk(root):
        # .git and .venv hold no doc. .claude/ holds the skills.
        dirs[:] = sorted(d for d in dirs if d == ".claude" or not d.startswith("."))
        names.extend((Path(folder) / n).relative_to(root).as_posix() for n in sorted(found))
    return names


PROPOSAL_RECORDS = "specs/model-sidecar/proposals/"


def markdown_files(root: Path) -> list[Path]:
    """Return the tracked docs the link check covers."""
    files = []
    for rel in repo_files(root):
        parts = rel.split("/")
        if not rel.endswith(".md") or not (root / rel).is_file():
            continue
        # A proposal record is a frozen byte copy of a bundle. Its links name the spec as it was then.
        if rel.startswith(PROPOSAL_RECORDS) and rel != PROPOSAL_RECORDS + "README.md":
            continue
        if rel.startswith(("specs/", "notes/", ".claude/skills/")):
            files.append(root / rel)
        # Hidden folders and the local plans/ folder hold no tracked AGENTS.md or decision log.
        elif not any(p.startswith(".") or p == "plans" for p in parts[:-1]) and (
            parts[-1] == "AGENTS.md" or "decisions" in parts[:-1]
        ):
            files.append(root / rel)
    return files


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    paths = [Path(p).resolve() for p in argv[2:]] or markdown_files(root)
    errors = [e for p in paths for e in check_file(p, root)]
    print("\n".join(errors) if errors else f"{len(paths)} files: all links resolve")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
