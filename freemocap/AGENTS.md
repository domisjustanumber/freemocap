# Instructions for `freemocap/`

The root `AGENTS.md` also applies: [root `AGENTS.md`](../AGENTS.md).
This file holds only the rules for the work in this module.

## Decision log

This module has its own decision log: [`decisions/README.md`](decisions/README.md).
The Rules of the root log apply to it: [root Rules](../decisions/README.md#rules).
To write an entry, use the root template [`template.md`](../decisions/template.md).

- Put an entry in this log only when each file that its Decision section names or changes is in
  this module. Its file goes in `decisions/entries/`.
- Put all other entries in the root log [`decisions/`](../decisions/README.md). An entry for two or more modules goes
  there.
- Before you change a file in this module, read the root [`decisions/README.md`](../decisions/README.md) and the root
  [`decisions/open-work.md`](../decisions/open-work.md).
- Then read [`decisions/README.md`](decisions/README.md) and
  [`decisions/open-work.md`](decisions/open-work.md) of this module.
- Then read the Active entries of both logs that apply to your task.

Tools are in the root `tools/`. Scripts are in `scripts/` of the log that holds their entry.

## Module rules

Run the fast backend tests with `uv run pytest freemocap/tests -m "not e2e and not slow"`.
The `e2e` and `slow` tests need the test recording at `FREEMOCAP_TEST_DATA_PATH`.
Run the linter with `uv run ruff check freemocap/`.
