# 0001 — Decision log, `AGENTS.md`, `plans/` and private data

**Status:** accepted, 2026-11-21 (user).

## Decision

1. **Decision log.** This repo keeps its decisions in a root log in `decisions/`. The
   [index](../README.md) has the Active and Proposed tables and the rules.
   [`historical.md`](../historical.md) has the Historical table. The entry files are in `entries/`.
   [`template.md`](../template.md) has the
   entry template. [`open-work.md`](../open-work.md) has the open work. A module can also have a log in
   `<module>/decisions/`. Each log is in `LOG_DIRS` of `tools/check_decision_log.py`. All logs have
   one ID space. A decision that code or a document refers to must be in an entry.
2. **Instruction files.** The root [`AGENTS.md`](../../AGENTS.md) and the `AGENTS.md` of each module
   are the only instruction files for coding agents. Each `CLAUDE.md` only imports the `AGENTS.md`
   in its folder: its full content is `@AGENTS.md`. Do not put instructions in a `CLAUDE.md`. Agent
   procedures are skills in `.claude/skills/`. Git tracks that folder and ignores the rest of
   `.claude/`. The `AGENTS.md` of a module with a log links to that log.
3. **`plans/`.** `plans/` is a local working folder. Git ignores it. Do not commit it. A tracked file
   does not link to `plans/` and does not cite its sections, item numbers or local PR labels.
4. **Log rules.** The [Rules](../README.md#rules) of the index give the allowed edits, absorption,
   complete supersession, the status changes, `done` and consolidation. The intro of the index gives
   the read path. `tools/check_decision_log.py` checks the tables, the status forms and the size
   limits. `tools/check_links.py` checks the links and the full-SHA permalinks.
5. **Private data.** [`AGENTS.md`](../../AGENTS.md#8-private-data) gives the rule.
   `tools/check_private_data.py` checks the tracked files. The pre-commit hook and the workflow
   `.github/workflows/secrets.yml` run `gitleaks`. `.private-terms` is a local, untracked list of
   terms to block. A camera recording or a camera frame is not committed, except a golden reference
   file. `tools/check_camera_media.py` checks the files of each commit.
6. **Links.** `tools/check_links.py` checks the relative links and their anchors. A GitHub link in
   `AGENTS.md`, `notes/`, `decisions/` or `.claude/skills/` must pin a full SHA.

## Reason

- Plans are working notes for a session. They go out of date, and a clone does not have them. A
  decision that code refers to must be in a tracked file.
- Two instruction files can disagree. The import gives all agents the same text.
- Agents read the log before each task. Without limits and status tables, the part that they read
  grows with each entry, also when the number of rules does not grow.
- A partial supersession makes a reader join two or three entries to find the current rule.
- The repo is public, or it can become public. Git history is permanent. A pasted command output can
  hold paths, user names and tokens. A camera recording or a camera frame is large, and it can show
  people and rooms.
- A test makes each rule a check that CI runs. A written rule alone does not stop a mistake.

## Consequences

- Each decision costs one entry and one index row.
- The first `pre-commit` run on a clone downloads Go to build `gitleaks`.

## Not repeated

- Do not link to `plans/` from a tracked file. Link to a decision entry.
- Do not add rules to `CLAUDE.md`. Add them to `AGENTS.md`.
- Do not commit `.private-terms`. A tracked list publishes the terms.
