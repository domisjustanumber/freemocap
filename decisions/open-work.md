# Open work

This file holds the open work of the [decision log](README.md). Read the items that apply to your
task. Delete an item when its work is done. The PR that closes an item records the result.

- **Private data in tracked files.** On 2026-11-21, `tools/check_private_data.py` reported 18
  findings on `sidecar-implementation` after the kit merge. The merge follow-up replaced the
  user-folder paths in two plan documents and in three test literals with `<you>`. It also gave the
  OpenAPI request examples of `freemocap/system/default_paths.py` (`FREEMOCAP_TEST_DATA_EXAMPLE`) a
  fixed `~/freemocap_data/...` string, and regenerated the client contract. 7 findings stay. Thus
  `test_repository_has_no_private_data`, the `private-data` hook and the doc-checks workflow fail.
  The user decides each redaction. Git history keeps the old text
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
  - `freemocap-ui/src/hooks/floatingOnboarding.tsx:1` and `useDraggableTooltips.tsx:1`: the
    personal email address of a contributor in the author comment. Remove the address and keep the
    name, or use the GitHub noreply address of the contributor.
  - `packages/freemocap-client/contracts/openapi.json:3711`: a user-folder path in the example of
    `StartRecordingRequest`. Its source is in `../skellycam/skellycam/api/http/cameras/camera_router.py`.
    Give that example a fixed `~/skellycam_data/...` string in skellycam. Then delete this example
    from `openapi.json`, run `uv run python packages/freemocap-client/tools/refresh-openapi.py` and
    run `npm run generate` in `packages/freemocap-client`. The refresh keeps each existing example,
    so it does not replace the old value by itself.
  - `packages/freemocap-client/tests/socket.test.mjs:57` and
    `freemocap-ui/src/services/server/certification-hand-in.test.ts:34`: a private IP address in a
    test fake. Each test needs only a host that is not local. Use a documentation address of RFC
    5737, for example `192.0.2.20`.
  - `freemocap/tests/test_certify_report_file.py:287,325`: an invented user name in a user-folder
    path. The scrubber test and the relay rule 1 test need a path of that form, so `<you>` changes
    what they test. The tool has no allow mechanism for a test fixture. Ask the kit maintainers for
    one (they sync the tool from skellytracker), or accept these two findings.
  - `freemocap/api/http/blender/blender_router.py:68`: `ExportToBlenderRequest` uses
    `FREEMOCAP_TEST_DATA_PATH` as a real field default. The check does not report it, and the
    contract does not hold this request now. A later contract refresh can write a user-folder path
    from it. The user decides the default.
- **The kit copy of `tools/check_private_data.py` differs.** This copy also skips
  `package-lock.json`, `npm-shrinkwrap.json` and `pnpm-lock.yaml`, because these files hold the
  email addresses of third-party package authors. Send the change to the kit maintainers, who sync
  the tool from skellytracker
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
- **The hooks are not installed.** `pyproject.toml` lists `pre-commit==4.7.0` in the `dev` group,
  and `uv run pre-commit install` works. On 2026-11-21, nobody ran it, because the private-data
  findings above stay and the `private-data` hook then stops each commit. Run it when
  `tools/check_private_data.py` passes. It writes the hooks to the hooks folder that all worktrees
  of a clone share
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
- **The older `pre-commit-hooks`.** On 2026-11-21, the user decided to remove the `black` hook, and
  the kit PR removed it.
  `.pre-commit-config.yaml` keeps `check-yaml` and `trailing-whitespace` from `pre-commit-hooks`
  v2.3.0. This version is old. On 2026-11-21, 41 tracked text files on `sidecar-implementation`
  had trailing whitespace, so `pre-commit run --all-files` changes them. The hook changes only the
  files of a commit. The user decides to update the hooks and to clean the files
  ([ADR-0001](entries/0001-decision-log-agents-md-and-private-data.md)).
