# Open work

This file holds the open work of the [decision log](README.md). Read the items that apply to your
task. Delete an item when its work is done. The PR that closes an item records the result.

- **Private data in tracked files.** On 2026-11-21, `tools/check_private_data.py` reported 32
  findings on `sfn26`. The kit PR removed the user-folder paths from the bench scripts,
  `current-work-plans/` and `experiments/`, and the check now skips the npm lock files. 8 findings
  stay. Thus `test_repository_has_no_private_data`, the `private-data` hook and the doc-checks
  workflow fail. The user decides each redaction. Git history keeps the old text
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
  - `freemocap-ui/src/hooks/floatingOnboarding.tsx:1` and `useDraggableTooltips.tsx:1`: the
    personal email address of a contributor in the author comment. Remove the address and keep the
    name, or use the GitHub noreply address of the contributor.
  - `packages/freemocap-client/contracts/openapi.json:3303,4059,7119` and
    `packages/freemocap-client/src/generated/schema.ts:1527,3045`: user-folder paths in the request
    examples. The server writes these examples from the home folder when it starts.
    The sources are `FREEMOCAP_TEST_DATA_PATH` in `freemocap/system/default_paths.py:49` (used in
    `freemocap/api/http/blender/blender_router.py:99` and
    `freemocap/api/http/calibration/calibration_router.py:159`) and `StartRecordingRequest` in
    `../skellycam/skellycam/api/http/cameras/camera_router.py:37-44,138`. Give these examples a
    fixed `~/freemocap_data/...` string. Then get `/openapi.json` again from a running server and
    run `npm run generate` in `packages/freemocap-client`. Do not edit the generated files.
  - `packages/freemocap-client/tests/socket.test.mjs:57`: a private IP address in the URL of a test
    fake. The tool has no allow mechanism for a test fixture. Use the documentation address
    `192.0.2.20` (RFC 5737). The test needs only a host that is not `localhost`.
- **The kit copy of `tools/check_private_data.py` differs.** This copy also skips
  `package-lock.json`, `npm-shrinkwrap.json` and `pnpm-lock.yaml`, because these files hold the
  email addresses of third-party package authors. Send the change to the kit maintainers, who sync
  the tool from skellytracker
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
- **`pre-commit` in the `dev` group.** `pyproject.toml` does not list `pre-commit` yet. On
  2026-11-21, `uv lock` could not resolve the project: the sibling checkouts were not on `sfn26`,
  and `../skellyforge` required Python `==3.13.18`. Add `pre-commit==4.7.0` (released 2026-10-12)
  to the `dev` group and run `uv lock` in a checkout whose siblings match `sfn26`. Until then,
  `uv run pre-commit install` fails. `pre-commit install` writes the hooks to the hooks folder that
  all worktrees of a clone share
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
- **The older `pre-commit-hooks`.** On 2026-11-21, the user decided to remove the `black` hook, and
  the kit PR removed it.
  `.pre-commit-config.yaml` keeps `check-yaml` and `trailing-whitespace` from `pre-commit-hooks`
  v2.3.0. This version is old. On 2026-11-21, 42 tracked text files had trailing whitespace, so
  `pre-commit run --all-files` changes them. The user decides to update the hooks and to clean the
  files ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
