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

## Certification

The decisions of the certification work are the rows from
[ADR-4TK3](entries/4TK3-certification-work-division-run-order-and-platforms.md) to
[ADR-BMA1](entries/BMA1-windows-ml-ep-pack-install-and-remove.md) of the Active table, and freemocap-ui
[ADR-JDH9](../freemocap-ui/decisions/entries/JDH9-certification-dialog-layout-and-owner-texts.md). The
[checkpoint](../current-work-plans/02-pipeline/ep-certification-integration.md) holds their history and the build
records.

### Questions for the owner

- **Reason sentences.** The owner has not reviewed the wording of these `REASON_TEXT` sentences in
  `freemocap-ui/src/services/server/execution-providers.ts`: `models-missing`, `test-media-missing`, `over-budget`,
  `video-not-passed`, `cpu-reference-missing`, `bad-hash`, `recording-missing`, `ep-not-passed`, `not-installed`,
  `cancelled`, `interrupted`, `reason-lost`, `realtime-session`, `package-not-removed`, `package-name-mismatch`,
  `package-unknown`, `record-refused`, `thread-not-started` and `package-in-use`
  ([ADR-NG3E](entries/NG3E-user-facing-wording-of-certification.md)).
- **Q80, `error`.** The coordinator read Q80 so that a start check whose freemocap `certify()` raises (`error`)
  writes the crash marker like a `fail`, with the exception class as `crashed`. It is built (`e9576021`). The owner
  must confirm it ([ADR-YZC3](entries/YZC3-start-check-required-run-and-lock.md) item 4).
- **The realtime check.** Four questions ([ADR-WKC0](entries/WKC0-quick-level-budget-and-session-checks.md)): must
  it also run when the post-hoc check used most of the budget on a slow system (today `over-budget`)? Is
  `REALTIME_TRACKED` 3 enough "run"? Can the aggregator read the latest calibration file of the person in the
  check? Is the wording of its reason sentence right?
- **Format 1.7.0.** It exempts a `test_media` name from privacy rule 7. It is held. freemocap stays on 1.6.0 until
  the owner decides ([ADR-GZ9H](entries/GZ9H-report-file-and-format-1-6-0.md)).
- **Test media in a crash record.** A crash record lists no frames for a cancelled `posthoc-session`, because its
  progress cannot tell if the session had started. A cancel while the session ran lists them.
- **Blender at level quick.** Since format 1.6.0 a missing Blender is `not-run` with `not-installed` at level quick.
  Before, it was `record-only` with `not-found`. The owner must confirm it.
- **The pair quick check** passes no shared test media folder. skellytracker then reads its own file.
- **The time of a combined file.** The file takes the earliest `created_utc`. For reports of several runs this is
  the call of the owner or a question for the skellycertify spec.
- **The lock of the start check.** Decision 14 of the owner keeps the server connection panel, the log terminal
  and the Electron menu usable during the lock. Two later changes of the coordinator are not confirmed: the
  full-window layer of the required dialog takes each pointer event, also over the connection panel and the log
  terminal; and the renderer ignores the Electron menu actions while `appLocked`. The owner must choose
  ([ADR-YZC3](entries/YZC3-start-check-required-run-and-lock.md) item 5).
- **Q60 and Q70** are open. The checkpoint does not record their text.
- **Duties from the overlap list of skellycam**, accepted by the coordinator only: close the camera groups before
  each certify run; ask for the macOS camera permission before the run; show "Camera <name>: wedged, please
  replug" from a `cleanup` row `release:<camera>`. None is built.
- **Pause.** skellycam ADR-V8RS makes pause a freeze of the UI display only. freemocap waits for the confirmation of
  the owner.
- **Test isolation.** The owner decides items 2 to 6 of
  [ADR-ENY6](entries/ENY6-test-isolation-for-certification.md).
- **Smaller choices of the sessions.** The name `FREEMOCAP_TEST_MEDIA_DIR`; the value 300 of `BENCHMARK_FRAMES`,
  which the session set after its measurement as the owner directed; the full-level rule that only a crashed
  `:probe` or `:video` check fails its pair.
- **Public commit.** Which repository holds the commits of freemocap for `package.commit`, and when to push. Until a
  push, the module of freemocap is a record only (`commit-not-public`).

### Not built

- **skellycam's part**: its quick and full checks, the camera check for each model and the check at the first open
  of an unchecked camera ([ADR-WKC0](entries/WKC0-quick-level-budget-and-session-checks.md) item 8). It waits for a
  green skellycam commit with `skellycam.certify`.
- **Passive record** (evidence from normal use). The owner wants it in the pre-release. freemocap's part (the opt-in
  question, the run at idle after a recording, the idle notice) waits until skellycertify defines the record and
  skellytracker has an interface. The disagreement warning with the CPU re-run waits for it too.
- **The skipped pairs line.** A line of the report that names the pairs that the quick level skipped because they
  hold a reviewed pass. It needs skellytracker to write them.
- **Installer for isolated systems** (model files inside it). The owner runs a separate session for it, before the
  release.
- **Frozen build.** The start mode `--certify-realtime`, `sys.executable`, the stdin pipe and `PeekNamedPipe` are not
  tested in a frozen build. A frozen build from editable sibling installs does not start (skellycam and skellylogs
  are not visible to PyInstaller); this blocks release builds
  ([ADR-H3ZJ](entries/H3ZJ-onnx-runtime-hardware-facts-and-build-identity.md)).
- **Linux and macOS.** No run. The `select` branch of the realtime stop, `coreml` in the full benchmark pairs and a
  `coreml` pair failure after a crash are not covered. Linux runs the check with the `fork` start method until the
  `ManagedProcess` of skellycam takes a context.
- **Real runs.** The first real send by the owner (then the end of the test mode). A whole full benchmark in the real
  window with a real download. A Windows ML install, cancel and remove on Windows 11 with an AMD GPU. A real crash.
  The manual checklists of the checkpoint. A shutdown measurement with cameras, to set `SHUTDOWN_GRACE_MS`
  ([ADR-FS1H](entries/FS1H-exit-notice-and-shutdown.md)).
- **Requests to other sessions.** skellycertify: the section 9 row of freemocap must name `freemocap.certify` and the
  option `blender_exe_path`. skellytracker: the install state of a field-test pack; a public record of the test media
  (freemocap uses `frames_record`); public calls for the internals that freemocap imports
  (`core.eps.certification`, `core.eps.evidence.gpu_id`, `core.system.host`, `core.eps.install` and `remove`).
