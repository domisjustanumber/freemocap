# Open work

This file holds the open work of the [decision log](README.md). Read the items that apply to your
task. Delete an item when its work is done. The PR that closes an item records the result.

- **Private data in tracked files.** On 2026-11-21, `tools/check_private_data.py` reported 32
  findings on `sfn26`. Thus `test_repository_has_no_private_data`, the `private-data` hook and the
  doc-checks workflow fail. The findings are user-folder paths in `bench_final.py`,
  `bench_redetect.py`, `bench_tracker.py`, 11 files in `current-work-plans/`, 2 files in
  `experiments/executable_graph_lab/`, `freemocap/core/pipeline/posthoc/video_group_helper.py`,
  `freemocap/core/viz/blender/blender_trajectory_loader.py`,
  `packages/freemocap-client/contracts/openapi.json` and
  `packages/freemocap-client/src/generated/schema.ts`; personal email addresses in
  `freemocap-ui/src/hooks/floatingOnboarding.tsx` and `useDraggableTooltips.tsx`; the email address
  of a package author in `freemocap-ui/package-lock.json`; and a private IP address in
  `packages/freemocap-client/tests/socket.test.mjs`. The user decides each redaction. Git history
  keeps the old text
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
- **`pre-commit` in the `dev` group.** `pyproject.toml` does not list `pre-commit` yet. On
  2026-11-21, `uv lock` could not resolve the project: the sibling checkouts were not on `sfn26`,
  and `../skellyforge` required Python `==3.13.18`. Add `pre-commit==4.7.0` (released 2026-10-12)
  to the `dev` group and run `uv lock` in a checkout whose siblings match `sfn26`. Until then,
  `uv run pre-commit install` fails. `pre-commit install` writes the hooks to the hooks folder that
  all worktrees of a clone share
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
- **The older pre-commit hooks.** `.pre-commit-config.yaml` keeps `trailing-whitespace` from
  `pre-commit-hooks` v2.3.0 and `black` 22.6.0. On 2026-11-21,
  `pre-commit run --all-files` changed 42 files with `trailing-whitespace`, and `black` reformatted
  630 of 760 Python files. `black` also reformats the doc-check tools in `tools/`, which are kit
  copies. CI uses `ruff`, not `black`. The user decides to keep, update or remove these hooks
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
