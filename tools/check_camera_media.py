#!/usr/bin/env python3
"""Refuse camera recordings and camera frames in a commit (decision 0001).

Usage::

    python tools/check_camera_media.py [FILE ...]   # the given files, as the pre-commit hook gives them
    python tools/check_camera_media.py              # the files that the commit adds or changes
    python tools/check_camera_media.py --all        # each tracked file

A camera recording (video or audio) or a camera frame (a still image or a raw frame from a camera)
is large, and it can contain private information. The tool refuses such a file, one line for each
file, and exits 1. It finds the file by its extension (``RECORDING_SUFFIXES``, ``FRAME_SUFFIXES``)
and by its first bytes (``MAGIC``), so that a renamed video or JPEG is also refused.

- The one exception is a golden reference file. Its path starts with an item of ``GOLDEN_PATHS``.
  Set this list for the repo. The default is ``golden/``.
- A ``.ts`` file is a TypeScript file unless its first bytes are an MPEG transport stream.
- A NumPy or array dump is a measurement. The tool does not refuse it.
- A PNG, GIF, WebP or SVG file can be a chart, a diagram or a screenshot. The tool does not refuse
  it. When a commit adds or changes one, the tool prints a reminder: a screenshot that shows a
  camera image is a camera frame.
- The default mode and the file mode check only the files of the commit. A file that is already in
  the history does not stop an unrelated commit. ``--all`` lists each tracked file that the rule
  refuses. A file that the commit deletes is not checked.

Exit codes: 0 when no file is refused, 1 when a file is refused, 2 for a usage error. Standard
library only.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

# The path prefixes of the golden reference files. Set them for the repo. An empty tuple allows none.
GOLDEN_PATHS: tuple[str, ...] = ()

RECORDING_SUFFIXES = frozenset(
    ".mp4 .mkv .mka .avi .mov .webm .m4v .m4a .wav .flac .opus .ogg .mp3 .mcap"
    " .h264 .h265 .mjpeg .mjpg .y4m .yuv".split()
)
FRAME_SUFFIXES = frozenset(".jpg .jpeg .jpe .raw .bayer .dng .bmp .tif .tiff .ppm .pgm".split())
REMINDER_SUFFIXES = frozenset(".png .gif .webp .svg".split())

# (offset, bytes, kind). The ``ftyp`` box is the MP4, MOV, M4A and M4V family. RIFF needs its form type.
MAGIC = (
    (0, b"\xff\xd8\xff", "JPEG frame"),
    (4, b"ftyp", "MP4 or QuickTime recording"),
    (0, b"\x1a\x45\xdf\xa3", "Matroska or WebM recording"),
    (0, b"\x89MCAP", "MCAP recording"),
    (0, b"OggS", "Ogg recording"),
    (0, b"fLaC", "FLAC recording"),
    (0, b"ID3", "MP3 recording"),
    (0, b"YUV4MPEG2", "Y4M recording"),
    (8, b"AVI ", "AVI recording"),
    (8, b"WAVE", "WAV recording"),
    (0, b"II*\x00", "TIFF frame"),
    (0, b"MM\x00*", "TIFF frame"),
)
TS_PACKET = 188
HEAD_SIZE = 2 * TS_PACKET + 1


def git(root: Path, *args: str) -> list[str]:
    exe = shutil.which("git")
    if exe is None:
        raise SystemExit("git is not on the PATH")
    out = subprocess.run([exe, "-C", str(root), *args], capture_output=True, check=True)  # noqa: S603
    return [n for n in out.stdout.decode("utf-8").split("\0") if n]


def staged_files(root: Path) -> list[str]:
    """The files that the commit adds or changes. Deleted files are not in the list."""
    return git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z")


def tracked_files(root: Path) -> list[str]:
    return git(root, "ls-files", "-z")


def normalize(path: str) -> str:
    """A repo-relative path with ``/`` separators, also for a path that Windows gives."""
    return PurePosixPath(path.replace("\\", "/")).as_posix()


def is_golden(rel: str, golden: tuple[str, ...]) -> bool:
    return any(rel.startswith(prefix) for prefix in golden)


def kind_by_content(head: bytes) -> str | None:
    for offset, magic, kind in MAGIC:
        if head[offset : offset + len(magic)] == magic and (offset != 8 or head.startswith(b"RIFF")):
            return kind
    if len(head) >= HEAD_SIZE and head[0] == head[TS_PACKET] == head[2 * TS_PACKET] == 0x47:
        return "MPEG transport stream recording"
    return None


def kind_of(rel: str, root: Path) -> str | None:
    """The kind of camera media that the file is, or None."""
    suffix = PurePosixPath(rel).suffix.lower()
    if suffix in RECORDING_SUFFIXES:
        return f"camera recording ({suffix})"
    if suffix in FRAME_SUFFIXES:
        return f"camera frame ({suffix})"
    # shortcut: reads the working-tree file, not the staged blob; pre-commit stashes unstaged changes,
    # so they agree under pre-commit. Read the blob with `git cat-file` if a plain hook needs it.
    path = root / rel
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        kind = kind_by_content(stream.read(HEAD_SIZE))
    return f"{kind} ({suffix or 'no extension'})" if kind else None


def check(paths: list[str], root: Path, golden: tuple[str, ...] = GOLDEN_PATHS) -> tuple[list[str], list[str]]:
    """The refusal lines and the reminder lines for the given repo-relative paths."""
    refused, reminders = [], []
    for rel in sorted({normalize(p) for p in paths}):
        if is_golden(rel, golden):
            continue
        kind = kind_of(rel, root)
        if kind:
            allowed = ", ".join(golden) if golden else "none in this repo"
            refused.append(
                f"{rel}: {kind}: do not commit camera recordings or camera frames (see AGENTS.md, Private Data);"
                f" only golden reference files are allowed (golden paths: {allowed})"
            )
        elif PurePosixPath(rel).suffix.lower() in REMINDER_SUFFIXES:
            reminders.append(
                f"{rel}: reminder: an image that shows a camera image is a camera frame; do not commit it"
            )
    return refused, reminders


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Refuse camera recordings and camera frames.")
    parser.add_argument("files", nargs="*", help="repo-relative files; default: the files of the commit")
    parser.add_argument("--all", action="store_true", help="check each tracked file")
    args = parser.parse_args(argv[1:])
    if args.all and args.files:
        parser.error("give --all or files, not both")
    root = Path.cwd()
    paths = tracked_files(root) if args.all else args.files or staged_files(root)
    refused, reminders = check(paths, root)
    for line in [] if args.all else reminders:
        print(line)
    if refused:
        print("\n".join(refused))
        return 1
    print(f"camera media: no findings ({len(paths)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
