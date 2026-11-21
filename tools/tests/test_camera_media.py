"""No commit adds a camera recording or a camera frame, except a golden reference file (decision 0001)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import check_camera_media as ccm
import pytest

REPO_ROOT = Path(ccm.__file__).resolve().parents[1]

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"
MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00"
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 "
TS = b"".join(b"\x47" + bytes(187) for _ in range(3))

RECORDINGS = (
    ".mp4 .mkv .mka .avi .mov .webm .m4v .m4a .wav .flac .opus .ogg .mp3 .mcap .h264 .h265 .mjpeg .mjpg .y4m .yuv"
)
FRAMES = ".jpg .jpeg .jpe .raw .bayer .dng .bmp .tif .tiff .ppm .pgm"


def refused(tmp_path: Path, files: dict[str, bytes], golden: tuple[str, ...] = ("golden/",)) -> list[str]:
    for name, data in files.items():
        path = tmp_path / name.replace("\\", "/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return [line.split(":")[0] for line in ccm.check(list(files), tmp_path, golden)[0]]


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)  # noqa: S603, S607


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "core.hooksPath", str(tmp_path / "no-hooks"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def commit(root: Path, files: dict[str, bytes]) -> None:
    for name, data in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    git(root, "add", *files)
    git(root, "commit", "-q", "-m", "add")


def test_repository_has_no_camera_media() -> None:
    assert ccm.check(ccm.tracked_files(REPO_ROOT), REPO_ROOT)[0] == []


def test_the_lists_hold_each_required_type() -> None:
    assert set(RECORDINGS.split()) <= ccm.RECORDING_SUFFIXES
    assert set(FRAMES.split()) <= ccm.FRAME_SUFFIXES
    assert {".npy", ".npz", ".png", ".gif", ".webp", ".svg", ".ts"}.isdisjoint(
        ccm.RECORDING_SUFFIXES | ccm.FRAME_SUFFIXES
    )


@pytest.mark.parametrize("suffix", (RECORDINGS + " " + FRAMES).split())
def test_each_type_is_refused_by_extension(tmp_path: Path, suffix: str) -> None:
    assert refused(tmp_path, {f"data/clip{suffix}": b"x", f"data/UPPER{suffix.upper()}": b"x"}) == [
        f"data/UPPER{suffix.upper()}",
        f"data/clip{suffix}",
    ]


@pytest.mark.parametrize(("name", "data"), [("notes.dat", JPEG), ("results/clip", MP4), ("photo.png", JPEG)])
def test_a_renamed_jpeg_or_mp4_is_refused_by_its_first_bytes(tmp_path: Path, name: str, data: bytes) -> None:
    assert refused(tmp_path, {name: data}) == [name]


def test_typescript_passes_and_a_transport_stream_is_refused(tmp_path: Path) -> None:
    assert refused(tmp_path, {"src/app.ts": b"export const a = 1;\n" * 30, "cap/clip.ts": TS}) == ["cap/clip.ts"]


def test_golden_paths_are_allowed_and_only_they(tmp_path: Path) -> None:
    files = {
        "golden/G01/cam0.mkv": MP4,
        "golden/frame.jpg": JPEG,
        "not_golden/x.mkv": b"x",
        "docs/golden_frame.jpg": JPEG,
        "tests/golden/x.mkv": b"x",
    }
    assert refused(tmp_path, files) == ["docs/golden_frame.jpg", "not_golden/x.mkv", "tests/golden/x.mkv"]


def test_an_empty_golden_list_allows_nothing(tmp_path: Path) -> None:
    lines = ccm.check(["golden/a.mkv"], tmp_path, ())[0]
    assert lines == [
        "golden/a.mkv: camera recording (.mkv): do not commit camera recordings or camera frames"
        " (see AGENTS.md, Private Data); only golden reference files are allowed (golden paths: none in this repo)"
    ]


def test_windows_separators(tmp_path: Path) -> None:
    assert refused(tmp_path, {"golden\\G01\\a.mkv": b"x", "media\\a.mkv": b"x"}) == ["media/a.mkv"]


@pytest.mark.parametrize(
    ("name", "data"),
    [("chart.png", b"\x89PNG\r\n\x1a\n"), ("ui.webp", WEBP), ("plot.svg", b"<svg/>"), ("array.npy", b"\x93NUMPY")],
)
def test_charts_screenshots_and_arrays_pass(tmp_path: Path, name: str, data: bytes) -> None:
    assert refused(tmp_path, {name: data}) == []


def test_an_image_gets_a_reminder_that_does_not_block(tmp_path: Path) -> None:
    (tmp_path / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    assert ccm.check(["chart.png", "a.npy"], tmp_path) == (
        [],
        ["chart.png: reminder: an image that shows a camera image is a camera frame; do not commit it"],
    )


def test_staged_mode_checks_only_the_commit_and_all_mode_lists_history(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit(repo, {"old/clip.mp4": MP4})
    (repo / "notes.md").write_text("text\n", encoding="utf-8")
    git(repo, "add", "notes.md")
    assert ccm.main(["check_camera_media.py"]) == 0
    assert "camera media: no findings (1 files)" in capsys.readouterr().out
    assert ccm.main(["check_camera_media.py", "--all"]) == 1
    assert capsys.readouterr().out.startswith("old/clip.mp4: camera recording (.mp4)")


def test_staged_mode_refuses_a_new_frame(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "frame.dat").write_bytes(JPEG)
    git(repo, "add", "frame.dat")
    assert ccm.main(["check_camera_media.py"]) == 1
    assert capsys.readouterr().out.startswith("frame.dat: JPEG frame (.dat)")


def test_a_file_that_the_commit_deletes_is_not_checked(repo: Path) -> None:
    commit(repo, {"old/clip.mp4": MP4})
    git(repo, "rm", "-q", "old/clip.mp4")
    assert ccm.staged_files(repo) == []
    assert ccm.main(["check_camera_media.py"]) == 0


def test_file_mode_and_exit_codes(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    assert ccm.main(["check_camera_media.py", "chart.png"]) == 0
    assert capsys.readouterr().out.startswith("chart.png: reminder:")
    assert ccm.main(["check_camera_media.py", "chart.png", "x.wav"]) == 1
    with pytest.raises(SystemExit) as stop:
        ccm.main(["check_camera_media.py", "--all", "chart.png"])
    assert stop.value.code == 2
