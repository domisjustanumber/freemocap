"""Every relative link in each `AGENTS.md`, `decisions/`, `specs/`, `notes/` and `.claude/skills/` resolves, except in the frozen proposal records."""

import shutil
import subprocess
from pathlib import Path

import pytest
from check_links import anchors, check_file, github_slug, links, markdown_files

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "path",
    markdown_files(REPO_ROOT),
    ids=lambda p: p.relative_to(REPO_ROOT).as_posix(),
)
def test_relative_links_resolve(path: Path) -> None:
    assert check_file(path, REPO_ROOT) == []


@pytest.mark.parametrize(
    ("heading", "slug"),
    [
        ("`input.resize`", "inputresize"),
        (
            "`base` — inherit from another sidecar and override",
            "base--inherit-from-another-sidecar-and-override",
        ),
        (
            "`packed_keypoints` (bottom-up packed rows)",
            "packed_keypoints-bottom-up-packed-rows",
        ),
        ("Changes in this revision (`1.0`)", "changes-in-this-revision-10"),
        ("`sizes.<size>.onnx.batch_artifacts`", "sizessizeonnxbatch_artifacts"),
        ("Text <em>tag</em> here", "text-tag-here"),
    ],
)
def test_github_slug(heading: str, slug: str) -> None:
    assert github_slug(heading) == slug


def test_repeated_headings_get_suffixes(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("# Notes\n\n## Notes\n\n## Notes\n", encoding="utf-8")
    assert anchors(doc) == {"notes", "notes-1", "notes-2"}


def test_links_in_code_are_skipped(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "See [real](other.md).\n\n```yaml\nx: [a](missing.md)\n```\n\n`[b](missing.md)`\n",
        encoding="utf-8",
    )
    assert links(doc) == [(1, "other.md")]


def test_broken_file_and_anchor_are_reported(tmp_path: Path) -> None:
    (tmp_path / "target.md").write_text("# Present\n", encoding="utf-8")
    doc = tmp_path / "doc.md"
    doc.write_text(
        "[ok](target.md#present) [bad](target.md#absent) [gone](none.md) [web](https://example.com)\n",
        encoding="utf-8",
    )
    errors = check_file(doc, tmp_path)
    assert errors == [
        "doc.md:1: missing anchor target.md#absent",
        "doc.md:1: missing file none.md",
    ]


SHA = "6b6a5c57580bdbce34088ebc54a7ba0f130d318c"


def test_github_links_in_notes_must_pin_a_full_sha(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    doc = tmp_path / "notes" / "doc.md"
    doc.write_text(
        f"[a](https://github.com/o/r/blob/{SHA}/x.py#L3) "
        "[b](https://github.com/o/r/blob/main/x.py) "
        "[c](https://github.com/o/r/commit/6b6a5c5) "
        "[d](https://github.com/o/r/pull/12)\n",
        encoding="utf-8",
    )
    assert check_file(doc, tmp_path) == [
        "notes/doc.md:1: GitHub link must pin a full SHA: https://github.com/o/r/blob/main/x.py",
        "notes/doc.md:1: GitHub link must pin a full SHA: https://github.com/o/r/commit/6b6a5c5",
    ]


def test_github_branch_links_outside_the_pinned_scope_pass(tmp_path: Path) -> None:
    (tmp_path / "specs").mkdir()
    doc = tmp_path / "specs" / "doc.md"
    doc.write_text("[b](https://github.com/o/r/tree/master/spec)\n", encoding="utf-8")
    assert check_file(doc, tmp_path) == []


def test_nested_agents_files_are_checked_and_pinned(tmp_path: Path) -> None:
    for folder in ("pkg/a/b", ".venv/lib", "plans"):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "AGENTS.md").write_text(
            "[b](https://github.com/o/r/blob/main/x.py)\n", encoding="utf-8"
        )
    doc = tmp_path / "pkg" / "a" / "b" / "AGENTS.md"
    assert markdown_files(tmp_path) == [doc]
    assert check_file(doc, tmp_path) == [
        "pkg/a/b/AGENTS.md:1: GitHub link must pin a full SHA: https://github.com/o/r/blob/main/x.py"
    ]


def test_decision_logs_in_any_folder_are_checked_and_pinned(tmp_path: Path) -> None:
    for folder in ("decisions", "m/decisions", ".hidden/decisions", "plans/decisions", "decisions/plans"):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "x.md").write_text(
            "[b](https://github.com/o/r/blob/main/x.py)\n", encoding="utf-8"
        )
    docs = [tmp_path / "decisions" / "x.md", tmp_path / "m" / "decisions" / "x.md"]
    assert markdown_files(tmp_path) == docs
    for doc in docs:
        rel = doc.relative_to(tmp_path).as_posix()
        assert check_file(doc, tmp_path) == [
            f"{rel}:1: GitHub link must pin a full SHA: https://github.com/o/r/blob/main/x.py"
        ]


def test_proposal_records_are_skipped(tmp_path: Path) -> None:
    records = tmp_path / "specs" / "model-sidecar" / "proposals"
    (records / "slug").mkdir(parents=True)
    for doc in (records / "README.md", records / "slug" / "proposal.md"):
        doc.write_text("[gone](gone.md)\n", encoding="utf-8")
    assert markdown_files(tmp_path) == [records / "README.md"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on the PATH")
def test_files_that_git_ignores_are_skipped(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)  # noqa: S603, S607
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    folders = ("ui/decisions", "ui/node_modules/pkg", "ui/node_modules/pkg/decisions", "specs/node_modules/pkg")
    for folder in folders:
        (tmp_path / folder).mkdir(parents=True)
        for name in ("AGENTS.md", "x.md"):
            (tmp_path / folder / name).write_text("[gone](gone.md)\n", encoding="utf-8")
    log = tmp_path / "ui" / "decisions"
    assert markdown_files(tmp_path) == [log / "AGENTS.md", log / "x.md"]
