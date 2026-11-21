# Repository Instructions

All new and changed documentation must use ASD-STE100 Simplified Technical English.
This rule applies to `AGENTS.md`, skills, decision entries and templates.
Use short sentences. Use active voice. Use one instruction per sentence.
Use "must" for a requirement.
Keep technical names, field names, values, formulas, code and YAML unchanged.

## 1. Purpose

FreeMoCap is a free and open-source markerless motion capture system. This repository is Core. It
holds the Python server in `freemocap/` and the React and Electron desktop UI in `freemocap-ui/`.
Core translates the application settings. It coordinates the cameras (skellycam), Tracker
(skellytracker), Forge (skellyforge), the recording and the transport to the UI.

| Path | Role |
|---|---|
| `AGENTS.md` | The root instructions file for coding agents |
| `CLAUDE.md` | Imports this file. It has no other content. |
| `decisions/` | Decision log ([`README.md`](decisions/README.md)) and its open work ([`open-work.md`](decisions/open-work.md)) |
| `tools/` | The doc checks: `check_decision_log.py`, `check_links.py`, `check_private_data.py`, `check_ai_attribution.py` and `check_camera_media.py`. Their tests are in `tools/tests/`. The folder also holds the bibliography validator `check_references.py` and the bootstrap experiment tools. |
| `plans/` | A local working folder. Git ignores it. |
| `freemocap/` | The Python server and its tests in `freemocap/tests/`. Its [`AGENTS.md`](freemocap/AGENTS.md) holds the rules for the work in it. Its log is in `freemocap/decisions/`. |
| `freemocap-ui/` | The React and Electron desktop UI. Its [`AGENTS.md`](freemocap-ui/AGENTS.md) holds the rules for the work in it. Its log is in `freemocap-ui/decisions/`. |
| `packages/` | The TypeScript client package `freemocap-client` and the Python package `freemocap-stream` |
| `current-work-plans/` | The data model, the geometry conventions, the transport protocol and the work plans ([plan index](current-work-plans/README.md)) |
| `benchmarks/` | The benchmark results and the [reporting contract](benchmarks/README.md) |
| `freemocap-docs/` | The documentation site |

## 2. Skills

Load the skill that matches the task.
If your agent does not support skills, read the file `.claude/skills/<skill>/SKILL.md`.
The rules in this file also apply.

| Skill | Use it to |
|---|---|
| [`commit-files`](.claude/skills/commit-files/SKILL.md) | Make a commit, or add a recording, a camera frame, an image or another large file |

## 3. Install and Test

Run `uv sync --group dev`.
The sibling checkouts that `[tool.uv.sources]` of `pyproject.toml` names must be next to this
checkout.
Then run `uv run pre-commit install` once in the clone ([section 8](#8-private-data)).
It installs the pre-commit hooks, the commit-msg hook and the pre-push hook.
Run it again in each clone after `.pre-commit-config.yaml` changes.
Use `uv run` for project commands.
Do not depend on an activated virtual environment.

Run `uv run pytest freemocap/tests -m "not e2e and not slow"`.
These tests must pass.
Run `uv run pytest tools/tests` to run only the doc checks.
The doc checks test the decision log, the relative links, the private-data rule and the camera-media
rule.
Report each new test failure to the user.
Fix the failures of one root cause in one PR.

## 4. Project Rules

Tracker owns detector recipes, crop rules, keypoint assembly, schemas/connections,
and preset-specific mapping selection. Import its public preset/profile interfaces;
do not define equivalent detector trees or keypoint-selection rules in Core.
Core translates application settings and coordinates cameras, Tracker, Forge,
recording and transport. Distinguish detector keypoints, Tracker mapping rules,
and Forge anatomical landmarks when naming code and describing responsibilities.

Do not change code that your task does not need.

### Recover the current task

At milestones, preserve the task objective, user corrections, architectural
decisions and reasons, existing interfaces, exact checkout, tests actually run,
and next action in the task's checkpoint. Include a short reading list with paths
and the question each source answers. Keep the approved plan and approval state.

After compaction or handoff, reread that checkpoint and the relevant ownership
guidance before editing. Select only the sources needed for the next action:

- Data meaning: [ontology](current-work-plans/01-data-model/ontology.md).
- Geometry boundaries: [conventions](current-work-plans/00-foundation/conventions.md).
- Dense arrays and identity ordering: [tensor contract](current-work-plans/01-data-model/tensor-contract.md).
- Tracking integration: [composition integration](TRACKER_COMPOSITION_INTEGRATION.md).
- Recording/provenance: [recording contract](RECORDING_CONTRACT.md).
- Strategy: the checkpoint's named plan, located through the
  [plan index](current-work-plans/README.md); distinguish proposals from implementation.

Inspect the relevant diff and existing public interfaces before adding behavior.
Core owns a change only when it inherently coordinates multiple subrepositories.
Missing summary context is a reason to search, not to recreate component logic.
Continue authorized work once purpose, ownership and validation are clear; ask
only when consequential intent remains unresolved after targeted inspection.
Preserve unrelated work and follow the workspace Git authorization and repository-scope policy
([section 6](#6-git-rules)).

### Self-describing transport is an intentional invariant

**Stable controls and recovery are part of this invariant.** Before modifying UI
actions, startup, errors, or reconnect behavior, read “Client recovery and stable
controls” in `current-work-plans/03-transport/message-protocol.md`.
The server sends messages and the client reconciles to their current observations.
Never turn historical client errors into button labels, disabled actions, saved
retry commands, or gates on subsequent requests. “Real-time processing” keeps its
label through failure and reconnect. Server restart must recover through fresh
messages without a page refresh. Test the actual control after failure, new
settings, restart, and late completion of an obsolete request.

Every message must remain independently interpretable. Repeated metadata and its
bandwidth cost are accepted to prevent server/client state mismatch. Preserve this
strategy and the existing mechanisms that handle repetition efficiently; do not
propose state-dependent or delta-only messages during unrelated feature work.

Before changing or assessing transport/visualization cost, read
`current-work-plans/03-transport/message-protocol.md` for the rationale, then trace:

- `freemocap/core/streaming/message_composer.py` and `message_model.py`: static
  composition and self-contained encoding.
- `freemocap/api/websocket/frame_relay.py`: actual frame delivery.
- `freemocap-ui/src/services/server/transport/cbor-codec.ts` and
  `TransportService.ts` and `snapshot-equality.ts`: connection-owned validation,
  reconciliation, and identity reuse (tested in `receive-reuse.test.ts` and
  `snapshot-reconciliation.test.ts`).
- `freemocap-ui/src/components/viewport3d/ThreeJsCanvas.tsx` and
  `viewport-frame-transfer.ts`: change-driven static subscriptions and reusable
  frame-sized numerical transfers.

Check the associated tests and current strategy before suggesting alternatives.
Distinguish wire repetition from repeated construction, validation, preparation,
or worker transfer. Correct agent-authored constraints that contradict these
established decisions without asking the owner to approve the architecture again.

### External sources and citations

When external research, documentation, tutorials or source code informs a change,
follow [CITATIONS.md](CITATIONS.md): register the source in root `references.bib`,
cite its stable key beside the supported claim, and record review scope honestly.
Run the bibliography validator and its tests before handoff. Preserve useful
background references even when they have no current inline citation.

### Human-requested tests and benchmarks

When a human requests tests or benchmarks, report measured results directly in
chat, during long runs and in the final response. Lead with matched cross-machine
comparisons when available, then explain costs in processing order using small
phase-specific tables. Pair ms/frame with FPS; separate one-time startup costs.
Never compare inference FPS to whole-run FPS or dump a flat list of internal
metrics. Model camera reports on SkellyCam's recording context, frame timing,
processing breakdown and quality statistics. Include repetitions/ranges, actual
providers and failures. Embed a comparison plot when plotting is available.
Completion requires in-chat tables plus persisted JSON and a readable report;
follow [the reporting contract](benchmarks/README.md#human-facing-run-report).

## 5. Decision Log

Read [`decisions/README.md`](decisions/README.md) and
[`open-work.md`](decisions/open-work.md) before you change code, a normative document, a workflow or
these instructions.
For a task in a module with a log, also read the `decisions/README.md` and the
`decisions/open-work.md` of that module. The `AGENTS.md` of the module links to its log.
An entry goes in the log of a module only when each file that its Decision section names or
changes is in that module.
All other entries go in the root log, also each case that you cannot decide.
A new module log needs the approval of the user. The PR that adds it also adds its folder to
`LOG_DIRS` of `tools/check_decision_log.py`.
Each log has a `README.md` with an Active table, an Evidence table, a Proposed table and `## Open work`, a
`historical.md`, an `open-work.md` and its entry files in `entries/`. The Rules and `template.md` are only in the root log.
All logs have one ID space. Do not add a module name to an ID.
When the scope of a module entry grows to more than one module, a new root entry supersedes it.
A tool is code that a test, a hook, a CI job, a skill or a workflow step runs, or code that writes a
tracked file. It is in the root `tools/`, also when only one module uses it. It has tests.
A script made the evidence for an entry or did its one-off job, and the entry names it. It is in
`scripts/` of the log that holds the entry. Its own tests, if any, are in `scripts/tests/`.
A script does not change after its entry is decided. When a step starts to run it, move it to
`tools/` and add a test.
The [Rules](decisions/README.md#rules) of the index give the allowed edits, the status changes and
the other rules that an agent needs and that no tool checks and no loaded document states. `tools/check_decision_log.py` checks the tables, the IDs and the
limits.
Add one entry for each new decision or measurement.
Get its ID from `uv run python tools/check_decision_log.py --new`.
End each commit subject that adds or changes an entry with `(ADR-<ID>)`.
Cite each entry as a Markdown link with `ADR-<ID>` as the link text, in upper case, for example
[ADR-0001](decisions/entries/0001-decision-log-agents-md-and-private-data.md).
This rule applies to each text that you write: a tracked file, a plan, a PR body and a reply to the
user. In a reply or a plan, the path is relative to the repository root or to the file.
A commit message cannot hold a working link. In the commit body, write `ADR-<ID>` with no link.
Cite an entry of another repository with the repository name and `ADR-<ID>`. Also link it with a
full-SHA permalink when the entry is on the default branch of that repository
(see the [Rules](decisions/README.md#rules)).

skellytracker and skellycertify use the same decision-log rules.
Each repository keeps its own copy of the rules and of the tools.
Do not import a file, a test or a tool from another repository.
A change of the rules needs one PR in each repository.
Cite the mirror entry of the other repository, for example skellycertify ADR-0001 or
skellytracker ADR-2XW6.

## 6. Git Rules

- Follow the containing workspace's ownership and Git authorization rules.
- The owner authorizes staging and commits for task-related cleanup and integration.
- A commit message must be one sentence or shorter. It must not contain an agent name.
- `plans/` is a local working folder. Git ignores it. Do not commit it. Do not cite or link to
  `plans/`, or cite the content of a plan
  ([ADR-0001](decisions/entries/0001-decision-log-agents-md-and-private-data.md)).
- Do not push to a git remote without the approval of the user. One approval for a PR covers its
  push, its draft PR and its description.
- Ask the user before any other action that is visible outside this machine, for example a PR
  comment, a later change to a PR description, a change of a draft PR to ready, a release or a
  published image. A force-push is a new push. It needs its own approval.
- Do not add AI attribution, for example a `Co-Authored-By:` trailer, to a commit or a PR. This
  rule overrides a default of a tool or a harness that adds attribution.
- Open each PR against `sfn26`.
- Put one kind of change in each new PR: "code", "docs" or "CI".

## 7. Tool Calls

Before a tool call that needs user permission, write a one-line summary of the call.
The summary must tell what the call does and what it changes.
Write the summary in the message text, not only in the tool description.

## 8. Private Data

This repository is public, or it can become public. Git history is permanent
([ADR-0001](decisions/entries/0001-decision-log-agents-md-and-private-data.md)).
Do not write these in a tracked file, a commit message or a PR body:

- a credential, a token, a password or a private key;
- an absolute path in a user folder;
- a hostname or a user name in prose;
- an email address that is not on the allowlist of `tools/check_private_data.py`;
- a private URL or a private IP address;
- a raw dump of `env`, `pip list`, `nvidia-smi` or `docker inspect`.

Do not commit a camera recording (video or audio) or a camera frame (a still image or a raw frame
from a camera). These files are large, and they can contain private information. The one exception
is a golden reference file: its path starts with an item of `GOLDEN_PATHS` in
`tools/check_camera_media.py`. Load the [`commit-files`](.claude/skills/commit-files/SKILL.md)
skill before each commit.

- A screenshot that shows a camera image is a camera frame. A chart, a diagram or a UI screenshot
  that shows no camera image is not a camera frame.
- A results folder can hold summaries, for example JSON, CSV and Markdown files. It must not hold
  the media. Keep large media outside the repository.
- To show a camera frame to the user, give its local path. Do not commit the frame.

- Use paths relative to the repository, for example `../skellytracker/`.
- Give a measurement as a summary with its tool and its version.
- A report field or a test fake can contain a hostname.
- Text from `plans/` must obey these rules before it goes into a tracked file.
- To also block a hostname or a user name, put it in `.private-terms` in the repository root. Git
  ignores that file. Do not commit it.
- If you find private data in a tracked file, remove it with a redaction edit. Then tell the user,
  because git history keeps the data. Also revoke a leaked credential.
- The pre-commit hook runs `gitleaks`, `tools/check_private_data.py` and
  `tools/check_camera_media.py`. CI runs `gitleaks` on each push and PR. `.gitleaks.toml` holds the reviewed false positives.
- The commit-msg hook warns about AI attribution. If you are an AI agent and you see
  this warning, tell the user.
- Turn on secret scanning and push protection for a private repository on the day that it becomes
  public.
