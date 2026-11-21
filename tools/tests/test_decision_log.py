"""The decision log keeps its index and its size limits (decision 0001)."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

import check_decision_log as cdl

REPO_ROOT = Path(cdl.__file__).resolve().parents[1]
REPO_LOG_DIRS = cdl.LOG_DIRS
# A module log for the tests that patch LOG_DIRS. It is two folders deep.
MODULE = Path("m") / "decisions"
TO_ROOT_LOG = f"../../../{cdl.LOG_DIR.as_posix()}/{cdl.ENTRIES}"

INDEX = """# Decision log

## Index

### Active

| # | Decision | Status |
|---|----------|--------|
{active}

### Proposed

| # | Decision | Section | Status |
|---|----------|---------|--------|
{proposed}

### Evidence

| # | Decision | Status |
|---|----------|--------|
{evidence}

## Open work
"""

HISTORY = """# Historical entries

### Historical

| # | Decision | Status |
|---|----------|--------|
{historical}
"""


def make_log(
    tmp_path: Path,
    active: str = "",
    historical: str = "",
    entries: dict[str, str] | None = None,
    proposed: str = "",
    log: Path = cdl.LOG_DIR,
    evidence: str = "",
) -> Path:
    log_dir = tmp_path / log
    log_dir.mkdir(parents=True)
    (log_dir / "README.md").write_text(
        INDEX.format(active=active, proposed=proposed, evidence=evidence), encoding="utf-8"
    )
    (log_dir / cdl.HISTORICAL).write_text(HISTORY.format(historical=historical), encoding="utf-8")
    (log_dir / cdl.ENTRIES).mkdir()
    for name, text in (entries or {}).items():
        folder = log_dir / cdl.ENTRIES if cdl.ENTRY_LIKE.match(name) and name not in cdl.NOT_ENTRIES else log_dir
        (folder / name).write_text(text, encoding="utf-8")
    return tmp_path


def row(number: int | str, status: str, name: str = "x", decision: str = "Title") -> str:
    i = f"{number:04d}" if isinstance(number, int) else number
    return f"| [{i}](entries/{i}-{name}.md) | {decision} | {status} |"


def prow(number: int | str, section: str = "`a.b`", name: str = "x") -> str:
    i = f"{number:04d}" if isinstance(number, int) else number
    return f"| [{i}](entries/{i}-{name}.md) | Title | {section} | proposed |"


def proposed_entry(day: str, number: int = 1) -> str:
    return f"# {number:04d}\n\n**Status:** proposed, {day} (user).\n"


@pytest.fixture(autouse=True)
def one_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tests make only the root log, unless they patch LOG_DIRS again."""
    monkeypatch.setattr(cdl, "LOG_DIRS", (cdl.LOG_DIR,))
    monkeypatch.setattr(cdl, "OLD_LOG_DIRS", ())


def test_repository_log_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cdl, "LOG_DIRS", REPO_LOG_DIRS)
    assert cdl.check(REPO_ROOT) == []


def test_matching_index_passes(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active=row(1, "accepted"),
        historical="\n".join(
            [
                row(2, "absorbed into `AGENTS.md#5`", "y"),
                row(3, "absorbed into [`AGENTS.md#5`](../../AGENTS.md#5)", "z"),
                row(4, "absorbed into [`AGENTS.md#5`](../../AGENTS.md#5), `tools/x.py`", "w"),
            ]
        ),
        entries={"0001-x.md": "# 0001\n", "0002-y.md": "# 0002\n", "0003-z.md": "", "0004-w.md": ""},
    )
    assert cdl.check(root) == []


def test_entry_without_row_and_row_without_entry_are_reported(tmp_path: Path) -> None:
    root = make_log(
        tmp_path, active=row(1, "accepted"), entries={"0002-y.md": "# 0002\n"}
    )
    errors = cdl.check(root)
    assert "entries/0002-y.md: 0 index rows, expected 1" in errors
    assert any("row links to missing file 0001-x.md" in e for e in errors)


def test_status_must_match_its_table(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active=row(1, "superseded by 0002"),
        historical=row(2, "proposed", "y"),
        entries={"0001-x.md": "", "0002-y.md": ""},
    )
    errors = cdl.check(root)
    assert any(
        "'superseded by 0002' must not be in the Active table" in e for e in errors
    )
    assert any("'proposed' must not be in the Historical table" in e for e in errors)


def test_an_absorbed_status_links_a_heading_of_each_markdown_file(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        historical="\n".join(
            [row(1, "absorbed into [`a.md`](../a.md), `tools/x.py`"), row(2, "absorbed into `b.md`", "y")]
        ),
        entries={"0001-x.md": "", "0002-y.md": ""},
    )
    errors = cdl.check(root)
    assert any("Markdown file ../a.md with no heading anchor" in e for e in errors)
    assert any("Markdown file b.md with no heading anchor" in e for e in errors)
    assert not any("tools/x.py" in e for e in errors)


def test_an_absorbed_status_links_pyproject_only_beside_a_test(tmp_path: Path) -> None:
    """`pyproject.toml` is an absorb document only for a rule that a test checks (decision 0001)."""
    root = make_log(
        tmp_path,
        historical="\n".join(
            [
                row(1, "absorbed into [`pyproject.toml`](../pyproject.toml)"),
                row(2, "absorbed into `pyproject.toml`, `tools/x.py`", "y"),
                row(3, "absorbed into [`pyproject.toml`](../pyproject.toml), [`t`](../tools/tests/test_pins.py)", "z"),
                row(4, "absorbed into `pyproject.toml`, `skellytracker/tests/sub/test_a.py`", "w"),
            ]
        ),
        entries={"0001-x.md": "", "0002-y.md": "", "0003-z.md": "", "0004-w.md": ""},
    )
    errors = cdl.check(root)
    assert errors == [
        f"historical.md:{line}: status links pyproject.toml with no test file: link the test that checks the rule"
        for line in (7, 8)
    ]


def test_unknown_status_is_reported(tmp_path: Path) -> None:
    root = make_log(tmp_path, active=row(1, "maybe"), entries={"0001-x.md": ""})
    assert any("unknown status 'maybe'" in e for e in cdl.check(root))


def test_free_text_after_a_status_is_reported(tmp_path: Path) -> None:
    root = make_log(
        tmp_path, active=row(1, "accepted; extends 0002"), entries={"0001-x.md": ""}
    )
    assert any(
        "unknown status 'accepted; extends 0002'" in e for e in cdl.check(root)
    )


def test_superseded_by_must_name_a_decided_entry(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        proposed=prow(2, name="y"),
        historical="\n".join([row(1, "superseded by 0002"), row(3, "superseded by 0009", "z")]),
        entries={
            "0001-x.md": "",
            "0002-y.md": proposed_entry("2026-10-01", 2),
            "0003-z.md": "",
        },
    )
    errors = cdl.check(root)
    assert any("'superseded by 0002' names an entry that is 'proposed'" in e for e in errors)
    assert any("'superseded by 0009' names no other indexed entry" in e for e in errors)


def test_used_evidence_is_historical(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active="\n".join([row(1, "accepted"), row(3, "evidence; used by 0001", "z")]),
        historical=row(2, "evidence; used by 0001", "y"),
        entries={
            "0001-x.md": "",
            "0002-y.md": "**Status:** evidence; used by [0001](0001-x.md), 2026-10-24 (#1).\n",
            "0003-z.md": "",
        },
    )
    assert cdl.check(root) == [
        "README.md:10: status 'evidence; used by 0001' must not be in the Active table"
    ]


def test_evidence_entries_are_in_the_evidence_table_and_not_in_the_read_path(tmp_path: Path) -> None:
    """An `evidence` entry has its row in the Evidence table, off the read path (decision 0001)."""
    root = make_log(
        tmp_path,
        active=row(1, "accepted"),
        evidence=row(2, "evidence", "y"),
        entries={"0001-x.md": "a" * 100, "0002-y.md": "b" * 1000},
    )
    assert cdl.check(root) == []
    assert cdl.read_path_size(root) == cdl.size(root / cdl.LOG_DIR / "README.md") + 100
    root = make_log(
        tmp_path / "wrong",
        active=row(1, "evidence"),
        evidence=row(2, "accepted", "y"),
        entries={"0001-x.md": "", "0002-y.md": ""},
    )
    assert cdl.check(root) == [
        "README.md:9: status 'evidence' must not be in the Active table",
        "README.md:21: status 'accepted' must not be in the Evidence table",
    ]


def test_long_decision_cell_is_reported(tmp_path: Path) -> None:
    long = "d" * (cdl.DECISION_CELL_LIMIT + 1)
    root = make_log(
        tmp_path, active=row(1, "accepted", decision=long), entries={"0001-x.md": ""}
    )
    assert any("Decision cell has 161 characters" in e for e in cdl.check(root))


def test_proposed_row_must_be_in_the_proposed_table(tmp_path: Path) -> None:
    root = make_log(tmp_path, active=row(1, "proposed"), entries={"0001-x.md": ""})
    assert cdl.check(root) == ["README.md:9: status 'proposed' must not be in the Active table"]


def test_proposed_entries_are_not_in_the_read_path(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        proposed=prow(1),
        entries={"0001-x.md": proposed_entry("2025-01-01") + "a" * 500},
    )
    assert cdl.check(root) == []
    assert cdl.read_path_size(root) == cdl.size(root / cdl.LOG_DIR / "README.md")


@pytest.mark.parametrize(
    ("section", "valid"),
    [
        ("`post.det.selection.nms`", True),
        ("`pre.resize.rotated_roi_crop`", True),
        ("none", True),
        ("post.det.selection.nms", False),
        ("`Post.Det`", False),
        ("", False),
    ],
)
def test_section_cell_of_a_proposed_row(tmp_path: Path, section: str, valid: bool) -> None:
    root = make_log(tmp_path, proposed=prow(1, section), entries={"0001-x.md": ""})
    errors = cdl.check(root)
    assert errors == ([] if valid else [
        f"README.md:15: Section cell {section!r} is not a section ID in backticks or `none`"
    ])


def test_proposed_row_must_have_four_cells(tmp_path: Path) -> None:
    root = make_log(tmp_path, proposed=row(1, "proposed"), entries={"0001-x.md": ""})
    errors = cdl.check(root)
    assert "README.md:15: a Proposed row has the cells | # | Decision | Section | Status |" in errors


def test_done_is_historical(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active=row(1, "done"),
        historical=row(2, "done", "y"),
        entries={"0001-x.md": "", "0002-y.md": ""},
    )
    assert cdl.check(root) == ["README.md:9: status 'done' must not be in the Active table"]


def test_historical_table_must_be_in_its_file(tmp_path: Path) -> None:
    root = make_log(tmp_path)
    readme = root / cdl.LOG_DIR / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\n### Historical\n\n| # | Decision | Status |\n",
        encoding="utf-8",
    )
    assert any("the Historical table must be in historical.md" in e for e in cdl.check(root))


def test_index_files_are_not_entries(tmp_path: Path) -> None:
    root = make_log(tmp_path, entries={cdl.TEMPLATE: "# T\n", cdl.OPEN_WORK: "# O\n"})
    assert cdl.check(root) == []


def test_new_entry_over_limit_is_reported_and_old_entry_is_not(tmp_path: Path) -> None:
    big = "x" * (cdl.ENTRY_LIMIT + 1)
    old = cdl.LAST_UNLIMITED_ENTRY
    new = old + 1
    root = make_log(
        tmp_path,
        active="\n".join([row(old, "accepted"), row(new, "accepted", "y")]),
        entries={f"{old:04d}-x.md": big, f"{new:04d}-y.md": big},
    )
    errors = cdl.check(root)
    assert (
        f"entries/{new:04d}-y.md: {cdl.ENTRY_LIMIT + 1} characters, limit {cdl.ENTRY_LIMIT}"
        in errors
    )
    assert not any(e.startswith(f"{old:04d}-x.md") for e in errors)


def test_entry_limit_does_not_count_the_status_paragraph(tmp_path: Path) -> None:
    """A status change can make a full entry longer, but not too long (decision 0001)."""
    new = cdl.LAST_UNLIMITED_ENTRY + 1
    status = "**Status:** accepted, 2026-10-25 (user);\n" + "superseded by B1C2, 2026-10-29 (user). " * 20 + "\n\n"
    body = "x" * (cdl.ENTRY_LIMIT - 2)  # the blank line after the status paragraph still counts
    root = make_log(tmp_path, active=row(new, "accepted"), entries={f"{new:04d}-x.md": status + body})
    assert cdl.check(root) == []
    (root / cdl.LOG_DIR / cdl.ENTRIES / f"{new:04d}-x.md").write_text(status + body + "x", encoding="utf-8")
    assert f"entries/{new:04d}-x.md: {cdl.ENTRY_LIMIT + 1} characters, limit {cdl.ENTRY_LIMIT}" in cdl.check(root)


@pytest.mark.parametrize("gap", ["\n", "\n   \n## Decision\n"])
def test_status_exemption_does_not_take_the_body(tmp_path: Path, gap: str) -> None:
    """With no blank line after the status, or with a space-only line, the body still counts."""
    new = cdl.LAST_UNLIMITED_ENTRY + 1
    text = "# X\n\n**Status:** accepted." + gap + "x" * cdl.ENTRY_LIMIT
    root = make_log(tmp_path, active=row(new, "accepted"), entries={f"{new:04d}-x.md": text})
    assert any(e.startswith(f"entries/{new:04d}-x.md: ") for e in cdl.check(root))


def test_open_work_at_80_percent_warns_and_passes(tmp_path: Path) -> None:
    near = "w" * int(cdl.OPEN_WORK_LIMIT * 0.9)
    root = make_log(tmp_path, entries={cdl.OPEN_WORK: near})
    assert cdl.check(root) == []
    assert (
        f"{cdl.OPEN_WORK}: {len(near)} characters, 90% of the limit {cdl.OPEN_WORK_LIMIT}"
        in cdl.warnings(root)
    )


def test_entry_near_its_limit_does_not_warn(tmp_path: Path) -> None:
    new = cdl.LAST_UNLIMITED_ENTRY + 1
    near = "x" * int(cdl.ENTRY_LIMIT * 0.9)
    root = make_log(
        tmp_path, active=row(new, "accepted"), entries={f"{new:04d}-x.md": near}
    )
    assert cdl.check(root) == []
    assert not any(w.startswith(f"{new:04d}-x.md") for w in cdl.warnings(root))


def test_historical_entries_are_not_in_the_read_path(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active=row(1, "accepted"),
        historical=row(2, "rejected", "y"),
        entries={"0001-x.md": "a" * 100, "0002-y.md": "b" * 1000},
    )
    index_size = cdl.size(root / cdl.LOG_DIR / "README.md")
    assert cdl.read_path_size(root) == index_size + 100


def test_open_work_is_in_the_read_path_and_has_a_limit(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        entries={cdl.OPEN_WORK: "w" * (cdl.OPEN_WORK_LIMIT + 1)},
    )
    index_size = cdl.size(root / cdl.LOG_DIR / "README.md")
    assert cdl.read_path_size(root) == index_size + cdl.OPEN_WORK_LIMIT + 1
    assert (
        f"{cdl.OPEN_WORK}: {cdl.OPEN_WORK_LIMIT + 1} characters, limit {cdl.OPEN_WORK_LIMIT}"
        in cdl.check(root)
    )


def test_crlf_counts_as_one_character(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_bytes(b"a\r\nb\r\n")
    assert cdl.size(path) == 4


def test_two_files_with_one_number_are_reported(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active="\n".join([row(32, "accepted", "a"), row(32, "accepted", "b")]),
        entries={"0032-a.md": "# 0032\n", "0032-b.md": "# 0032\n"},
    )
    errors = cdl.check(root)
    assert "entry ID 0032 has 2 files: entries/0032-a.md, entries/0032-b.md" in errors
    assert "README.md:10: ID 0032 is also in README.md:9" in errors


def test_link_text_must_match_file_number(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active="| [0032](0033-x.md) | T | accepted |",
        entries={"0033-x.md": "# 0033\n"},
    )
    assert "README.md:9: link text 0032 does not match 0033-x.md" in cdl.check(root)


def test_link_text_in_entry_must_match_file(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active="\n".join([row(1, "accepted"), row(3, "accepted", "z")]),
        entries={
            "0001-x.md": "# 0001\n\nSee [0002](0003-z.md) and [0003](0003-z.md#decision).\n",
            "0003-z.md": "",
        },
    )
    assert cdl.check(root) == ["entries/0001-x.md:3: link text 0002 does not match 0003-z.md"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# 0032 — T\n", ["entries/0033-x.md: heading ID 0032 does not match the file name"]),
        ("# 0033 — T\n", []),
        ("", []),
    ],
)
def test_heading_number_must_match_file_number(
    tmp_path: Path, text: str, expected: list[str]
) -> None:
    root = make_log(tmp_path, active=row(33, "accepted"), entries={"0033-x.md": text})
    assert cdl.check(root) == expected


def test_gaps_in_numbers_pass(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active="\n".join([row(1, "accepted"), row(3, "accepted", "z")]),
        entries={"0001-x.md": "# 0001\n", "0003-z.md": "# 0003\n"},
    )
    assert cdl.check(root) == []


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("[0002](0002-y.md)", []),
        (
            "[0003](0003-z.md)",
            ["entries/0001-x.md: the status line does not link superseded by 0002 to 0002-y.md"],
        ),
    ],
)
def test_superseded_by_must_match_status_link(
    tmp_path: Path, link: str, expected: list[str]
) -> None:
    root = make_log(
        tmp_path,
        active="\n".join([row(2, "accepted", "y"), row(3, "accepted", "z")]),
        historical=row(1, "superseded by 0002"),
        entries={
            "0001-x.md": f"# 0001\n\n**Status:** superseded by {link}, 2026-10-24 (#1).\n",
            "0002-y.md": "",
            "0003-z.md": "",
        },
    )
    assert cdl.check(root) == expected


def test_renumbered_old_entry_keeps_size_exemption(tmp_path: Path) -> None:
    old = cdl.LAST_UNLIMITED_ENTRY
    new = old + 1
    edit = f"\n\n_Edited 2026-10-24 (#1): renumber from {old:04d}._\n"
    root = make_log(
        tmp_path,
        active=row(new, "accepted"),
        entries={f"{new:04d}-x.md": "x" * (cdl.ENTRY_LIMIT + 1) + edit},
    )
    assert cdl.check(root) == []


# Several logs: the root log and a module log, with one ID space.


@pytest.fixture
def two_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cdl, "LOG_DIRS", (cdl.LOG_DIR, MODULE))


@pytest.mark.usefixtures("two_logs")
def test_root_and_module_log_pass(tmp_path: Path) -> None:
    make_log(tmp_path, active=row("A001", "accepted"), entries={"A001-x.md": "# A001\n"})
    status = f"**Status:** superseded by [A001]({TO_ROOT_LOG}/A001-x.md), 2026-10-28 (#1).\n"
    make_log(
        tmp_path,
        active=row("B002", "accepted", "y"),
        historical=row("C003", "superseded by A001", "z"),
        entries={
            "B002-y.md": f"# B002\n\nSee [ADR-A001]({TO_ROOT_LOG}/A001-x.md).\n",
            "C003-z.md": f"# C003\n\n{status}",
        },
        log=MODULE,
    )
    assert cdl.check(tmp_path) == []


@pytest.mark.usefixtures("two_logs")
@pytest.mark.parametrize("target", ["A001-x.md", f"{TO_ROOT_LOG.upper()}/A001-x.md"])
def test_status_link_to_another_log_needs_its_path(tmp_path: Path, target: str) -> None:
    make_log(tmp_path, active=row("A001", "accepted"), entries={"A001-x.md": ""})
    make_log(
        tmp_path,
        historical=row("C003", "superseded by A001", "z"),
        entries={"C003-z.md": f"**Status:** superseded by [A001]({target}), 2026-10-28 (#1).\n"},
        log=MODULE,
    )
    assert cdl.check(tmp_path) == [
        "m/decisions/entries/C003-z.md: the status line does not link superseded by A001 to "
        f"{TO_ROOT_LOG}/A001-x.md"
    ]


@pytest.mark.usefixtures("two_logs")
@pytest.mark.parametrize(
    ("root_name", "module_name"),
    [("K7M2-a.md", "K7M2-b.md"), ("k7m2-a.md", "K7M2-b.md"), ("K7M2-a.md", "K7M2-a.md")],
)
def test_one_id_in_two_logs_fails(tmp_path: Path, root_name: str, module_name: str) -> None:
    make_log(tmp_path, active=row(root_name[:4], "accepted", root_name[5:-3]), entries={root_name: ""})
    make_log(
        tmp_path,
        active=row(module_name[:4], "accepted", module_name[5:-3]),
        entries={module_name: ""},
        log=MODULE,
    )
    errors = cdl.check(tmp_path)
    assert f"entry ID K7M2 has 2 files: entries/{root_name}, m/decisions/entries/{module_name}" in errors
    assert f"m/decisions/README.md:9: ID {module_name[:4]} is also in README.md:9" in errors


@pytest.mark.usefixtures("two_logs")
def test_module_log_labels_start_with_its_folder(tmp_path: Path) -> None:
    make_log(tmp_path)
    make_log(
        tmp_path,
        active=row("A001", "accepted") + "\n| [B002](B002-y.md) | Title |",
        entries={"A001-x.md": "# C003\n\nSee [D004](A001-x.md).\n", "E005-u.md": "", "E5LU-v.md": ""},
        log=MODULE,
    )
    errors = cdl.check(tmp_path)
    assert len(errors) == 5
    assert all(e.startswith(f"{MODULE.as_posix()}/") for e in errors), errors


@pytest.mark.usefixtures("two_logs")
def test_log_folder_without_readme_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_log(tmp_path)
    assert cdl.check(root) == ["m/decisions: the log has no README.md"]
    assert cdl.main(["check_decision_log.py", str(root)]) == 1
    assert "m/decisions: the log has no README.md" in capsys.readouterr().out


@pytest.mark.usefixtures("two_logs")
def test_read_path_has_one_total_over_all_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_log(tmp_path, active=row("A001", "accepted"), entries={"A001-x.md": "a" * 400})
    make_log(tmp_path, active=row("B002", "accepted", "y"), entries={"B002-y.md": "b" * 400}, log=MODULE)
    total = sum(cdl.size(tmp_path / log / "README.md") for log in cdl.LOG_DIRS) + 800
    assert cdl.read_path_size(tmp_path) == total
    monkeypatch.setattr(cdl, "READ_PATH_LIMIT", total - 1)
    assert cdl.check(tmp_path) == [
        f"read path (README.md, open-work.md and Active entries): {total} characters, limit {total - 1}"
    ]


@pytest.mark.usefixtures("two_logs")
def test_module_entry_near_its_limit_does_not_warn(tmp_path: Path) -> None:
    near = "x" * int(cdl.ENTRY_LIMIT * 0.9)
    make_log(tmp_path)
    make_log(tmp_path, active=row("A001", "accepted"), entries={"A001-x.md": near}, log=MODULE)
    assert cdl.check(tmp_path) == []
    assert ("m/decisions/entries/A001-x.md", len(near), cdl.ENTRY_LIMIT) in cdl.sizes(tmp_path)
    assert cdl.warnings(tmp_path) == []


# The tests of `--new`. Each git test runs in its own repo, with no user or system config.

GIT = shutil.which("git")
needs_git = pytest.mark.skipif(GIT is None, reason="git is not installed")
EMAIL = "tester" + "@" + "example.invalid"


@pytest.fixture
def git_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate git from the user: no global or system config, no `GIT_*` variable, no parent repo.

    An entry on TARGET_BRANCH wins before the other ranks. A repo can set TARGET_BRANCH to a branch
    that a test makes, for example `main` in the kit. So the tests use a name that no test makes.
    """
    monkeypatch.setattr(cdl, "TARGET_BRANCH", "target")
    for name in list(os.environ):
        if name.upper().startswith("GIT_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    return tmp_path


def git(cwd: Path, *args: str, stdin: bytes | None = None) -> None:
    subprocess.run(  # noqa: S603
        [GIT or "git", "-c", "user.name=Tester", "-c", f"user.email={EMAIL}", *args],
        cwd=cwd,
        input=stdin,
        check=True,
        capture_output=True,
    )


def entry(root: Path, name: str, log: Path = cdl.LOG_DIR) -> None:
    (root / log / cdl.ENTRIES).mkdir(parents=True, exist_ok=True)
    (root / log / cdl.ENTRIES / name).write_text(f"# {name[:4]}\n", encoding="utf-8")


def commit(root: Path, message: str) -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


def repo(root: Path) -> Path:
    """A new repo on `main` with entry 0001 committed."""
    (root / cdl.LOG_DIR).mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    entry(root, "0001-a.md")
    commit(root, "0001")
    return root


def verdicts(lines: list[str]) -> list[str]:
    return [line for line in lines if line.startswith(("keep:", "re-ID:"))]


def scripted(*ids: str) -> Callable[[], str]:
    """A draw function that gives `ids` in order."""
    queue = list(ids)

    def draw() -> str:
        return queue.pop(0)

    return draw


def test_new_id_has_a_digit_and_a_letter_in_any_position() -> None:
    draws = [cdl.new_id(set()) for _ in range(2000)]
    for found in draws:
        assert len(found) == 4
        assert set(found) <= set(cdl.ALPHABET)
        # A digit, so that no new ID reads as a word, and a letter, so that it is not an old number.
        assert not found.isdigit() and not found.isalpha(), found
        assert cdl.ENTRY_NAME.match(f"{found}-x.md")
    # Uniform over the valid IDs: 10 * (32**3 - 10**3) - 2_000 of 802_320, about 39.3%, start with a digit.
    digit_first = sum(found[0].isdigit() for found in draws) / len(draws)
    assert 0.3 < digit_first < 0.5, digit_first


def test_new_id_skips_used_ids() -> None:
    assert cdl.new_id({"K7M2", "A000"}, scripted("k7m2", "A000", "B111")) == "B111"


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("0001-x.md", True),
        ("k7m2-x.md", True),
        ("K7M2-x.md", True),
        ("z000-x.md", True),
        ("K7m2-x.md", False),
        ("I7M2-x.md", False),
        ("3K7Q-x.md", True),
        ("9A9A-x.md", True),
        ("0k7m-x.md", False),
        ("3k7q-x.md", False),
        ("i7m2-x.md", False),
        ("k7u2-x.md", False),
    ],
)
def test_entry_id_format(tmp_path: Path, name: str, valid: bool) -> None:
    root = make_log(tmp_path, entries={name: ""})
    errors = cdl.check(root)
    if valid:
        assert errors == [f"entries/{name}: 0 index rows, expected 1"]
    else:
        assert errors == [
            f"entries/{name}: the file name starts like an entry, but {name[:4]!r} is not a valid ID"
        ]


def test_letter_ids_in_rows_links_and_status(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active=row("k7m2", "accepted", "y"),
        historical=row(1, "superseded by k7m2"),
        entries={
            "0001-x.md": "# 0001\n\n**Status:** superseded by [k7m2](k7m2-y.md), 2026-10-25 (#1).\n",
            "k7m2-y.md": "# k7m2 — T\n\nSee [0001](0001-x.md).\n",
        },
    )
    assert cdl.check(root) == []


def test_digit_first_ids_in_rows_links_and_status(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active=row("3K7Q", "accepted", "y"),
        historical=row(1, "superseded by 3K7Q"),
        entries={
            "0001-x.md": "# 0001\n\n**Status:** superseded by [3K7Q](3K7Q-y.md), 2026-10-29 (#1).\n",
            "3K7Q-y.md": "# 3K7Q — T\n\nSee [ADR-0001](0001-x.md).\n",
        },
    )
    assert cdl.check(root) == []
    (root / cdl.LOG_DIR / cdl.ENTRIES / "3K7Q-y.md").write_text("# 3K7Q — T\n\n[ADR-9A9A](3K7Q-y.md)\n", encoding="utf-8")
    assert "entries/3K7Q-y.md:3: link text 9A9A does not match 3K7Q-y.md" in cdl.check(root)


def test_ids_that_differ_only_in_case_are_one_id(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active="\n".join([row("k7m2", "accepted", "y"), row("A001", "accepted", "z")]),
        historical=row(1, "superseded by K7M2"),
        entries={
            "0001-x.md": "# 0001\n\n**Status:** superseded by [K7M2](k7m2-y.md), 2026-10-28 (#1).\n",
            "k7m2-y.md": "# k7m2 — T\n",
            "A001-z.md": "# A001 — T\n\nSee [a001](A001-z.md) and [ADR-K7M2](k7m2-y.md).\n",
        },
    )
    assert cdl.check(root) == []
    (root / cdl.LOG_DIR / cdl.ENTRIES / "k7m2-y.md").write_text("# k7m2 — T\n\n[ADR-A001](k7m2-y.md)\n", encoding="utf-8")
    assert "entries/k7m2-y.md:3: link text A001 does not match k7m2-y.md" in cdl.check(root)
    (root / cdl.LOG_DIR / cdl.ENTRIES / "K7M2-w.md").write_text("# K7M2 — T\n", encoding="utf-8")
    assert "entry ID K7M2 has 2 files: entries/K7M2-w.md, entries/k7m2-y.md" in cdl.check(root)
    assert cdl.new_lines(root, scripted("K7M2", "B111"))[0] == "new: B111"


def test_re_id_keeps_size_exemption(tmp_path: Path) -> None:
    old = cdl.LAST_UNLIMITED_ENTRY
    edit = f"\n\n_Edited 2026-10-25 (#1): re-ID from {old:04d}._\n"
    root = make_log(
        tmp_path,
        active=row("k7m2", "accepted"),
        entries={"k7m2-x.md": "x" * (cdl.ENTRY_LIMIT + 1) + edit},
    )
    assert cdl.check(root) == []


def test_letter_id_has_no_size_exemption(tmp_path: Path) -> None:
    root = make_log(
        tmp_path,
        active=row("a001", "accepted"),
        entries={"a001-x.md": "x" * (cdl.ENTRY_LIMIT + 1)},
    )
    errors = cdl.check(root)
    assert f"entries/a001-x.md: {cdl.ENTRY_LIMIT + 1} characters, limit {cdl.ENTRY_LIMIT}" in errors


def test_new_without_git(git_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_log(
        git_env / "plain",
        active="\n".join([row(1, "accepted"), row(3, "accepted", "z")]),
        entries={"0001-x.md": "# 0001\n", "0003-z.md": "# 0003\n"},
    )
    lines = cdl.new_lines(root, scripted("0001", "0003", "k7m2"))
    assert lines[0] == "new: k7m2"
    assert any(line.startswith("note: ") for line in lines)

    def no_git(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(cdl.subprocess, "run", no_git)
    assert cdl.new_lines(root, scripted("k7m2"))[0] == "new: k7m2"


@needs_git
def test_new_with_unborn_head(git_env: Path) -> None:
    root = git_env / "repo"
    (root / cdl.LOG_DIR).mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    lines = cdl.new_lines(root)
    assert cdl.ENTRY_NAME.match(lines[0].removeprefix("new: ") + "-x.md")
    assert verdicts(lines) == []


@needs_git
def test_new_sees_branch_and_worktree(git_env: Path) -> None:
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "other")
    entry(root, "b222-b.md")
    commit(root, "b222-b")
    git(root, "checkout", "-q", "main")
    git(root, "worktree", "add", "-q", "-b", "wt", str(git_env / "wt"))
    entry(git_env / "wt", "c333-c.md")
    entry(root, "b222-a.md")
    lines = cdl.new_lines(root, scripted("0001", "b222", "c333", "d444"))
    assert lines[0] == "new: d444"
    assert verdicts(lines) == ["re-ID: b222-a.md; b222-b.md also uses b222 (on other)"]


@needs_git
def test_same_file_on_other_ref_is_not_a_collision(git_env: Path) -> None:
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "other")
    entry(root, "0002-b.md")
    commit(root, "0002-b on other")
    git(root, "checkout", "-q", "main")
    entry(root, "0002-b.md")
    commit(root, "0002-b on main")
    assert verdicts(cdl.new_lines(root)) == []


@needs_git
def test_new_ignores_own_uncommitted_rename(git_env: Path) -> None:
    root = repo(git_env / "repo")
    git(root, "remote", "add", "origin", str(git_env / "remote.git"))
    git(root, "checkout", "-q", "-b", "feat")
    entry(root, "0002-old.md")
    commit(root, "0002-old")
    git(root, "update-ref", "refs/remotes/origin/feat", "HEAD")
    git(root, "branch", "-q", "--set-upstream-to=origin/feat")
    # A rebase makes a new commit, so origin/feat is no longer merged into HEAD.
    git(root, "commit", "-q", "--amend", "-m", "0002-old, rebased")
    log = cdl.LOG_DIR.as_posix()
    git(root, "mv", f"{log}/entries/0002-old.md", f"{log}/entries/0002-new.md")
    assert verdicts(cdl.new_lines(root)) == []


@needs_git
def test_old_name_of_an_entry_is_not_a_collision(git_env: Path) -> None:
    """A stale branch has the old names of two entries that this tree gave new IDs."""
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "stale")
    entry(root, "0040-rules.md")
    entry(root, "0043-gate.md")
    commit(root, "old names")
    git(root, "checkout", "-q", "main")
    entry(root, "0043-rules.md")
    entry(root, "0046-gate.md")
    commit(root, "new names")
    assert verdicts(cdl.new_lines(root)) == []


@needs_git
def test_backup_branches_are_skipped(git_env: Path) -> None:
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "backup/before-re-id")
    entry(root, "0002-z.md")
    commit(root, "0002-z")
    git(root, "checkout", "-q", "main")
    entry(root, "0002-a.md")
    commit(root, "0002-a")
    assert verdicts(cdl.new_lines(root)) == []


@needs_git
def test_new_verdicts_agree_between_worktrees(git_env: Path) -> None:
    root = repo(git_env / "repo")
    other = git_env / "wt"
    git(root, "worktree", "add", "-q", "-b", "wt", str(other))
    entry(root, "0003-x.md")
    entry(other, "0003-y.md")
    here = verdicts(cdl.new_lines(root))
    there = verdicts(cdl.new_lines(other))
    assert len(here) == 1 and here[0].startswith("keep: 0003-x.md; 0003-y.md also uses 0003")
    assert len(there) == 1
    assert there[0].startswith("re-ID: 0003-y.md; 0003-x.md also uses 0003")


@needs_git
def test_first_commit_wins(git_env: Path) -> None:
    """The entry with the earlier first commit keeps its ID, also when its file name sorts later."""
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "early")
    entry(root, "k7m2-z.md")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "early", "--date=2026-01-01T00:00:00")
    git(root, "checkout", "-q", "main")
    entry(root, "k7m2-a.md")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "late", "--date=2026-02-01T00:00:00")
    assert verdicts(cdl.new_lines(root)) == [
        "re-ID: k7m2-a.md; k7m2-z.md also uses k7m2 (on early)"
    ]


@needs_git
def test_uncommitted_entry_loses_to_committed(git_env: Path) -> None:
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "other")
    entry(root, "k7m2-z.md")
    commit(root, "k7m2-z")
    git(root, "checkout", "-q", "main")
    entry(root, "k7m2-a.md")
    assert verdicts(cdl.new_lines(root)) == [
        "re-ID: k7m2-a.md; k7m2-z.md also uses k7m2 (on other)"
    ]


@needs_git
def test_new_target_wins(git_env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "t")
    entry(root, "0002-t.md")
    commit(root, "0002-t")
    git(root, "update-ref", f"refs/remotes/origin/{cdl.TARGET_BRANCH}", "HEAD")
    git(root, "checkout", "-q", "main")
    git(root, "branch", "-q", "-D", "t")
    entry(root, "0002-a.md")
    commit(root, "0002-a")
    assert verdicts(cdl.new_lines(root)) == [
        f"re-ID: 0002-a.md; 0002-t.md also uses 0002 (on origin/{cdl.TARGET_BRANCH})"
    ]
    assert cdl.main(["check_decision_log.py", "--new", str(root)]) == 1
    assert "re-ID: 0002-a.md" in capsys.readouterr().out
    assert cdl.main(["check_decision_log.py", "--collisions", str(root)]) == 1
    out = capsys.readouterr().out
    assert "re-ID: 0002-a.md" in out
    assert "new:" not in out


@needs_git
def test_target_rank_comes_first(git_env: Path) -> None:
    """The entry on TARGET_BRANCH wins, also against an entry on a remote with an earlier commit."""
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", cdl.TARGET_BRANCH)
    entry(root, "k7m2-t.md")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "late", "--date=2026-02-01T00:00:00")
    git(root, "checkout", "-q", "main")
    entry(root, "k7m2-a.md")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "early", "--date=2026-01-01T00:00:00")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert verdicts(cdl.new_lines(root)) == [
        f"re-ID: k7m2-a.md; k7m2-t.md also uses k7m2 (on {cdl.TARGET_BRANCH})"
    ]


@needs_git
def test_collisions_passes_without_a_collision(
    git_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "other")
    entry(root, "0002-b.md")
    commit(root, "0002-b")
    git(root, "checkout", "-q", "main")
    entry(root, "k7m2-a.md")
    assert cdl.main(["check_decision_log.py", "--collisions", str(root)]) == 0
    assert "new:" not in capsys.readouterr().out


@needs_git
@pytest.mark.usefixtures("two_logs")
def test_new_sees_module_log_ids(git_env: Path) -> None:
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "other")
    entry(root, "b222-b.md", MODULE)
    commit(root, "b222-b")
    git(root, "checkout", "-q", "main")
    git(root, "worktree", "add", "-q", "-b", "wt", str(git_env / "wt"))
    entry(git_env / "wt", "c333-c.md", MODULE)
    entry(root, "d444-d.md", MODULE)
    lines = cdl.new_lines(root, scripted("b222", "c333", "d444", "e555"))
    assert lines[0] == "new: e555"
    assert verdicts(lines) == []


@needs_git
@pytest.mark.usefixtures("two_logs")
def test_entry_moved_to_another_log_is_not_a_collision(git_env: Path) -> None:
    root = repo(git_env / "repo")
    entry(root, "k7m2-a.md", MODULE)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "k7m2-a", "--date=2026-01-01T00:00:00")
    added = cdl.first_commits(root, {"k7m2-a.md"})
    assert set(added) == {"k7m2-a.md"}
    # The stale branch is not merged into HEAD, and it has the entry in the old log.
    git(root, "checkout", "-q", "-b", "stale")
    entry(root, "0002-s.md")
    commit(root, "0002-s")
    git(root, "checkout", "-q", "main")
    git(root, "mv", f"{MODULE.as_posix()}/entries/k7m2-a.md", f"{cdl.LOG_DIR.as_posix()}/entries/k7m2-a.md")
    assert verdicts(cdl.new_lines(root)) == []
    git(root, "commit", "-q", "-m", "move", "--date=2026-02-01T00:00:00")
    lines = cdl.new_lines(root, scripted("K7M2", "B111"))
    assert lines[0] == "new: B111"
    assert verdicts(lines) == []
    assert cdl.first_commits(root, {"k7m2-a.md"}) == added


@needs_git
def test_new_reads_old_log_folders_on_branches(git_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "stale")
    entry(root, "b111-s.md")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "b111-s", "--date=2026-02-01T00:00:00")
    git(root, "checkout", "-q", "main")
    git(root, "mv", cdl.LOG_DIR.as_posix(), "moved")
    entry(root, "b111-o.md", Path("moved"))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "move", "--date=2026-01-01T00:00:00")
    monkeypatch.setattr(cdl, "LOG_DIRS", (Path("moved"),))
    assert verdicts(cdl.new_lines(root)) == []
    monkeypatch.setattr(cdl, "OLD_LOG_DIRS", (cdl.LOG_DIR,))
    assert verdicts(cdl.new_lines(root)) == ["keep: b111-o.md; b111-s.md also uses b111 (on stale)"]


def test_missing_tree_with_a_space_in_its_path_is_none() -> None:
    assert cdl.tree_entries(b"0123abcd:./my dir/decisions missing\n", 1) == [None]


def branches(root: Path, count: int) -> None:
    """Add `count` branches, each with one new entry in the next log of LOG_DIRS, in one `git fast-import` process."""
    stream = []
    for i in range(count):
        body = f"# {i + 2:04d}\n".encode()
        log = cdl.LOG_DIRS[i % len(cdl.LOG_DIRS)].as_posix()
        head = (
            f"commit refs/heads/b{i}\n"
            f"committer Tester <{EMAIL}> 1700000000 +0000\n"
            "data 1\nb\n"
            "from refs/heads/main^0\n"
            f"M 100644 inline {log}/{i + 2:04d}-b{i}.md\n"
            f"data {len(body)}\n"
        )
        stream.append(head.encode() + body + b"\n")
    git(root, "fast-import", "--quiet", stdin=b"".join(stream))


@needs_git
@pytest.mark.parametrize("log_count", [1, 2])
def test_new_process_count_is_fixed(
    git_env: Path, monkeypatch: pytest.MonkeyPatch, log_count: int
) -> None:
    monkeypatch.setattr(cdl, "LOG_DIRS", (cdl.LOG_DIR, MODULE)[:log_count])
    real_run = subprocess.run
    calls: list[object] = []

    def counting_run(*args: object, **kwargs: object) -> object:
        calls.append(args[0] if args else kwargs.get("args"))
        return real_run(*args, **kwargs)  # type: ignore[call-overload]

    counts = []
    for count in (2, 20):
        root = repo(git_env / f"repo{count}")
        branches(root, count)
        calls.clear()
        monkeypatch.setattr(cdl.subprocess, "run", counting_run)
        lines = cdl.new_lines(root)
        monkeypatch.setattr(cdl.subprocess, "run", real_run)
        assert verdicts(lines) == []
        counts.append(len(calls))
    assert counts[0] == counts[1] <= 5


def test_entry_file_outside_entries_is_reported(tmp_path: Path) -> None:
    root = make_log(tmp_path, active=row(1, "accepted"), entries={"0001-x.md": "# 0001\n"})
    (root / cdl.LOG_DIR / "0002-y.md").write_text("# 0002\n", encoding="utf-8")
    assert cdl.check(root) == [f"0002-y.md: an entry file must be in {cdl.ENTRIES}/"]


def test_entry_limit_does_not_count_edited_lines(tmp_path: Path) -> None:
    new = cdl.LAST_UNLIMITED_ENTRY + 1
    body = "x" * (cdl.ENTRY_LIMIT - 4) + "\n\n_Edited 2026-10-29 (#1): link repair._\n_Edited 2026-10-30 (#2): typo._\n"
    root = make_log(tmp_path, active=row(new, "accepted"), entries={f"{new:04d}-x.md": body})
    assert cdl.size(root / cdl.LOG_DIR / cdl.ENTRIES / f"{new:04d}-x.md") > cdl.ENTRY_LIMIT + 4
    assert not any(e.startswith(f"entries/{new:04d}-x.md: ") for e in cdl.check(root))


def test_old_form_row_link_names_the_entries_folder(tmp_path: Path) -> None:
    root = make_log(tmp_path, active="| [0001](0001-x.md) | Title | accepted |", entries={"0001-x.md": "# 0001\n"})
    assert "README.md:9: the link must be [0001](entries/0001-x.md)" in cdl.check(root)


def test_only_the_edit_line_form_is_exempt(tmp_path: Path) -> None:
    """A line that starts with _Edited but is not an edit line counts, so no body text hides in it."""
    new = cdl.LAST_UNLIMITED_ENTRY + 1
    body = "_Edited the whole body " + "x" * cdl.ENTRY_LIMIT + " is here._\n"
    root = make_log(tmp_path, active=row(new, "accepted"), entries={f"{new:04d}-x.md": body})
    assert any(e.startswith(f"entries/{new:04d}-x.md: ") for e in cdl.check(root))


@needs_git
def test_new_reads_the_flat_layout_on_branches(git_env: Path) -> None:
    """A branch from before the move to entries/ has its entry files in the log folder."""
    root = repo(git_env / "repo")
    git(root, "checkout", "-q", "-b", "stale")
    (root / cdl.LOG_DIR / "b111-s.md").write_text("# b111\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "b111-s", "--date=2026-02-01T00:00:00")
    git(root, "checkout", "-q", "main")
    entry(root, "b111-o.md")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "b111-o", "--date=2026-01-01T00:00:00")
    assert verdicts(cdl.new_lines(root)) == ["keep: b111-o.md; b111-s.md also uses b111 (on stale)"]


def test_new_id_never_reads_as_a_number() -> None:
    assert cdl.NUMBER_LIKE.fullmatch("1E23") and cdl.NUMBER_LIKE.fullmatch("12E3")
    assert not cdl.NUMBER_LIKE.fullmatch("1E2A") and not cdl.NUMBER_LIKE.fullmatch("E123")
    assert cdl.new_id(set(), scripted("1E23", "12E3", "3K7Q")) == "1E23"  # a scripted draw is not filtered
    for _ in range(5000):
        assert not cdl.NUMBER_LIKE.fullmatch(cdl.new_id(set()))
