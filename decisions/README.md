# Decision log

This log records the technical decisions of FreeMoCap Core (this repository), with their reasons and evidence. Read this
file and [open-work.md](open-work.md) before you change code, a normative document, a workflow or the agent instructions. The
[Rules](#rules) tell you which entries to read
([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).

Each entry gives the decision, its reason, the evidence (when there is evidence), the alternatives
rejected and a "Not repeated" section for pitfalls already found. When a decision changes, add a new
entry that supersedes the old entry in full. The body of a decided entry changes only by the edits
that the [Rules](#rules) allow. To write an entry, use [template.md](template.md).

## Index

### Active

These entries are `accepted`.

| # | Decision | Status |
|---|----------|--------|
| [0001](entries/0001-decision-log-agents-md-and-private-data.md) | Decision log and its rules; `AGENTS.md` files hold the instructions; `plans/` is local; no private data | accepted |
| [4TK3](entries/4TK3-certification-work-division-run-order-and-platforms.md) | Certification: what each package checks, the run order, validation in freemocap builds on each platform | accepted |
| [H3ZJ](entries/H3ZJ-onnx-runtime-hardware-facts-and-build-identity.md) | ONNX Runtime and hardware facts through skellytracker; SemVer version; build commit; UTF-8 output | accepted |
| [FS1H](entries/FS1H-exit-notice-and-shutdown.md) | Electron close sends `POST /shutdown` first; exit notice; a child ends its GPU session before a kill | accepted |
| [FG8V](entries/FG8V-busy-rule-and-admission-lock.md) | Busy rule: no work during a check, no check during work; refusals answer one request; one lock | accepted |
| [WKE6](entries/WKE6-unchecked-pairs-in-the-ep-setting.md) | Unchecked EP and GPU pairs: shown and marked, two-choice prompt, one-pair quick check, states, texts | accepted |
| [YZC3](entries/YZC3-start-check-required-run-and-lock.md) | Start check: reviewed OS rows, when it is required, what it runs, lock, release, crash marker | accepted |
| [WKC0](entries/WKC0-quick-level-budget-and-session-checks.md) | Level quick: 2 minutes in all, 25 s for freemocap, session checks, realtime check in a fresh copy | accepted |
| [5ZRX](entries/5ZRX-full-benchmark-offer-consent-lock-and-clean-up.md) | Full benchmark: offer, consent step, downloads guard, lock, cancel, clean-up | accepted |
| [HT08](entries/HT08-full-benchmark-stages-order-measures-and-rows.md) | Full benchmark: pair order, sample recording, 300 frames, measures, Blender, reported-only failures, rows | accepted |
| [FS03](entries/FS03-crash-record-and-incomplete-reports.md) | Crash record at both levels; no automatic re-run; incomplete reports; `abandon` | accepted |
| [GZ9H](entries/GZ9H-report-file-and-format-1-6-0.md) | Report file: format 1.6.0, built at hand-in, components, test media, note cleaning, privacy | accepted |
| [5XXN](entries/5XXN-hand-in-relay-and-test-mode.md) | Hand-in: report stores, send after view, outbox and retry, relay off, issue form, test mode | accepted |
| [X2KK](entries/X2KK-skellytracker-pin-in-a-separate-clone.md) | skellytracker pin: the clone `../skellytracker-pin`; when and how to move it | accepted |
| [WP3Z](entries/WP3Z-shared-test-media-folder.md) | Shared test media folder for each user; the app passes it to each package | accepted |
| [NG3E](entries/NG3E-user-facing-wording-of-certification.md) | User text says "system"; the confirmed sentences; plain reason sentences | accepted |
| [BMA1](entries/BMA1-windows-ml-ep-pack-install-and-remove.md) | Windows ML EP pack controls: which EPs, Remove always, no Repair, busy rule, texts | accepted |

### Evidence

These entries are `evidence`: measurements. They are not in the read path. Scan these rows before
you make a measurement ([Rules](#rules)).

| # | Decision | Status |
|---|----------|--------|

### Proposed

These entries wait for a decision of the user. Section is the section or area of the change, or
`none`.

| # | Decision | Section | Status |
|---|----------|---------|--------|
| [ENY6](entries/ENY6-test-isolation-for-certification.md) | Test isolation of the certification work: scratch stores, no relay, no download, no hardware | none | proposed |

The entries that are `rejected`, `superseded by XXXX`, `absorbed into <path>#<anchor>`,
`evidence; used by XXXX` or `done` are in [historical.md](historical.md).

## Open work

The open work is in [open-work.md](open-work.md).

## Rules

- Read the Active entries that apply to your task. Then you do not repeat a settled question. Before
  you make a measurement, scan the rows of the Evidence table of each log, and read the entries that
  apply. Then you do not repeat a completed measurement. The Evidence entries are not in the read
  path. Read a Proposed entry only for work in its section, or when a skill
  tells you to. Read an entry of [historical.md](historical.md) only to find the reason for a
  decision.
- The body of an entry that is not `proposed` changes only by four edits: a link or anchor repair, a
  typo that does not change the meaning, the redaction of private data, and a change of ID with the
  repair of its citations. Each edit adds `_Edited YYYY-MM-DD (#PR): <kind>._` at the end of the
  entry, for example `re-ID from XXXX`. For a
  change of ID, the renamed entry gets `re-ID from XXXX`, and each repaired entry gets
  `citation repair`. Add these two lines only to an entry that is on `sfn26`. A plain-text
  old path in a decided entry or a script stays, and means the same file at
  its new path.
- An entry in a commit that is not pushed to a remote can change in that commit, in each part. Make
  the correction and report it to the user. Do not write a new entry for it, and do not ask. The
  four edits apply from the first push.
- A decision that a document or code refers to must be in an entry. "This log" in an older entry or
  in the Rules means all logs.
- An absorb document is one of these: the root or a nested `AGENTS.md`, the skills, [`RECORDING_CONTRACT.md`](../RECORDING_CONTRACT.md),
  [`TRACKER_COMPOSITION_INTEGRATION.md`](../TRACKER_COMPOSITION_INTEGRATION.md),
  [`CITATIONS.md`](../CITATIONS.md), and in `current-work-plans/` the
  [ontology](../current-work-plans/01-data-model/ontology.md), the
  [conventions](../current-work-plans/00-foundation/conventions.md), the
  [tensor contract](../current-work-plans/01-data-model/tensor-contract.md) and the
  [message protocol](../current-work-plans/03-transport/message-protocol.md), the Rules of this file with [template.md](template.md), and the docstring of a
  tool in `tools/` for the rules that it checks. A test in `tools/tests/` or in the
  tests of the package is a tool here: its docstring states the rules that it checks.
  `pyproject.toml` is an absorb document for a rule that a test checks. Its `absorbed into` link
  stands beside the link of that test. An accepted entry is absorbed when the absorb
  documents together state all of its rules. Open work of the entry does not stop the absorb when
  `open-work.md` states that work in full. A link to the entry is not
  enough.
- Absorb at landing. The commit group that writes or lands an entry, or that writes the rules of an
  entry into the absorb documents, absorbs the entry in its last commit when the absorb documents
  state all of its rules. This applies in each log, in each skill and without a skill. If an absorb
  document does not state a rule, the entry stays `accepted`. Do not ask the user.
- The status `absorbed into` has one link for each heading that states a rule of the entry. Link a
  heading one time, also when it states two or more rules. Link a file with no anchor only when the
  rule is not under a heading, for example in a tool docstring or a YAML file. When the status
  paragraph is longer than `STATUS_EXEMPTION_LIMIT`, replace the headings of one file with the title
  heading of that file. Start with the file that has the most links. If the paragraph is still too
  long, replace the files of one document with the title heading of its
  main file. A commit that renames a heading repairs each status link to that heading. A change from
  a file link to heading links is a link repair.
- The entry that supersedes an old entry restates each rule of the old entry that stays. A link can
  restate a rule. The link must go to a heading of an absorb document, and that heading must state
  the rule. Link the heading of each kept rule that a heading states. Write text only for a changed
  rule and for a kept rule that no heading states. The commit that changes the text under such a heading cites its own entry next to the
  changed rule. That change does not supersede the entry that links the heading.
- Only these status changes are allowed: `proposed` to `accepted` or `rejected`; `accepted` to
  `superseded by XXXX`, `absorbed into <path>#<anchor>` or `done`; `absorbed into <path>#<anchor>`
  to `superseded by XXXX`; and `evidence` to
  `evidence; used by XXXX`, when an accepted entry cites the `evidence` entry for its decision.
  `done` is for an accepted entry that records a one-off action, with no rule that stays, when the
  action is complete. Each status change adds its date and the PR that made it. In the same PR,
  change the status in the index and move the row to the table for the new status.
- `tools/check_decision_log.py` checks the tables, the status forms, the Section cell, the ID
  alphabet and the size limits. Its docstring states them. `tools/check_links.py` checks the links
  and the full-SHA permalinks. A tool is the source of a rule that it checks.
- A consolidation entry states the rules that stay from a group of entries, and it supersedes each
  entry of the group. It changes no decision.
- When the read path is at 90% of its limit or more, first absorb each accepted entry whose rules
  the absorb documents state. Then
  write each rule that no absorb document states in the absorb document where it belongs, and
  absorb its entry.
- A commit that only makes a workflow, skill, template or tool copy agree with a landed entry
  cites that entry. It needs no entry of its own. A new rule is not a copy.
- Delete an open-work item when the work is done. Put a dated fact in `open-work.md` or in an
  entry, not in `AGENTS.md`.
- Put long evidence in a tracked file in `evidence/` of the log folder, and link to it. A PR that raises a limit
  of `tools/check_decision_log.py` must add an entry.
- An ID changes only on a `re-ID:` line of `tools/check_decision_log.py`, to the ID of a new `--new`
  run.
- Until a commit is on `sfn26`, cite its PR number and the file path, not its SHA.
  The `ADR-` prefix is for citations only: a file name, a
  heading, an index row and a status line hold the bare ID. Cite a provisional entry of another repo
  by the repo name, the PR number and the slug. Do not edit a decided entry only to add or move the
  prefix or the link.
