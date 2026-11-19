# EP management, certification and report hand-in

**State (2026-11-19): APPROVED PLAN; the Electron shutdown fix (decision 31) the hardware cleanup (6 to 8), the version change (4) and `BUILD_TREE_MODIFIED` (11) are built; the rest is not.** The user settled every decision below in a grilling
round in this session and in the skellytracker session (`skellytracker-6c`, the session that owns
ONNX Runtime, EP packs and EP certification). The skellytracker interfaces this plan needs do not exist yet;
do not code against their names until that session sends the built shapes. The work that needs no new
skellytracker interface is listed in [Next actions](#next-actions).

Checkout when written: freemocap `sidecar-implementation` at `c4ec71e6` (local commits, nothing pushed).
skellytracker `dom/sidecar-implementation` pushed to the user's fork at `55fabf4a` (CI running at the time).
No tests were run for this plan.

## Objective

The app shows each execution provider (EP) with its state, installs and removes EP packs, certifies EPs and
the OS on this PC, and lets the person hand in certify reports. It does this through skellytracker's public
`eps` interface, skellycam's checks and freemocap's own checks. freemocap holds no EP knowledge of its own
(`freemocap/tests/test_no_execution_provider_knowledge.py`).

## Ownership

- **skellytracker** owns EP state, EP packs, Windows ML catalog installs, EP certification checks, the EP
  store (local passes, failures, `dismiss_certification`, the hand-in list, its own saved module reports and
  passive records), the unclean-exit count, the ONNX Runtime PyInstaller hook, and hardware facts and live
  metrics (`core.system`, `core.metrics`).
- **skellycam** owns camera checks (camera controls per OS) and camera evidence.
- **freemocap** owns its own checks (below), running every module's `certify()`, merging the module reports
  into one report file, the local record of a start-check pass, the anonymous ping, and the whole UI.
- **skellycertify** (https://github.com/domisjustanumber/skellycertify) holds the report format
  (`report-format.md`, the contract) and the reviewer procedure (`review.md`), and receives reports as
  GitHub issues. It has no shared code package.
- freemocap never edits skellytracker; every change it needs is a request to the skellytracker session.

## Decisions

### Dependencies and packaging

1. Pin skellytracker to one exact commit of the fork branch `dom/sidecar-implementation` until semver exists
   (the user owns that scheme), and regenerate the stale `uv.lock` in the same change. Candidate: `55fabf4a`,
   once its CI is green.
2. After the migration, freemocap declares neither `onnx` nor `onnxruntime`; both arrive through
   skellytracker. `freemocap.spec:96-97` (collection), `:99-100` (stale `onnx` hidden import) and the
   onnxruntime excludes at `:151-156` move to a skellytracker PyInstaller hook. The dev pin `onnx==1.22.0`
   (`pyproject.toml:156`) goes with `legacy_tracker_run.py` at ST 2.4.
3. On Windows the ONNX Runtime distribution is `onnxruntime-windowsml` 1.30.0 (brings DirectML).
   `import skellytracker` sets `ORT_DISABLE_TELEMETRY=1` (a preset value stays); freemocap imports
   onnxruntime nowhere before skellytracker.
4. `freemocap.__version__` drops its leading `v` (`v2.0.0-alpha.25` becomes `2.0.0-alpha.25`), and every
   reader of it changes in the same commit. Reason: the report format requires SemVer with no prefix.
5. Windows first.

### Hardware facts and live metrics

6. skellytracker is the only home. The anonymous `app_opened` ping stays only in freemocap
   (`freemocap/system/telemetry/telemetry.py:35-47`) and takes its eight facts from `probe_host()`
   (os_name, os_version, os_release, arch, cpu_physical_cores, cpu_logical_cores, memory_total_bytes) and
   `probe_environment().python.version`.
7. `tools/machine_benchmarks.py: load_snapshot()` uses `LiveSampler`; the load average becomes
   `LiveSample.load_average_1m` (1 minute only; empty on Windows and in a checkout without the field).
8. Declare `psutil` in `pyproject.toml` (five files import it; it arrived only through skellycam).
   Delete the unused Electron `memoryInfo` call (`freemocap-ui/electron/main/api.ts:136`).

### Certify contract (skellycertify report format 1.0.0)

9. Each package exposes `certify(level, progress=None, cancel=None) -> dict` and `certify_plan(level) -> dict`,
   level `quick` (seconds) or `full` (minutes, opt-in). freemocap calls each module in a multiprocessing
   `spawn` child (no `sys.executable` with a script path; `freeze_support()` is already in `__main__`),
   passes `progress` through a queue and `cancel` as a `multiprocessing.Event`, and keeps the latest
   full-state progress message as the job state for the UI.
10. freemocap merges the module reports into one Markdown file (`certify-report-<yyyymmddThhmmssZ>.md`,
    `{schema, app {name, version, commit}, modules, note}`) and keeps it on the server host under
    `<base data folder>/certify/`. skellytracker's `certify()` also saves its own module report in the EP
    store; its pending hand-in entry carries that report's `created_utc` and `kind`, and freemocap finds its
    merged file by that pair. Passive records stay in the EP store; freemocap wraps them with the `app` block
    at hand-in.
11. freemocap's `package.commit` comes from `freemocap/build_info.py` (`BUILD_GIT_SHA`, written by the
    installer workflow); in a source tree it tries git, else `no-commit`. The workflow must compute a new
    `BUILD_TREE_MODIFIED` before it writes `build_info.py`, because writing that file dirties the tree.

### freemocap's own checks

Rule: freemocap checks only what it owns (its bundle, process model, data folder and its own posthoc chain on
CPU). Anything that loads an EP, a built-in pipeline's model or a detector is skellytracker's; cameras are
skellycam's. So freemocap's checks never use a GPU, and an OS row is independent of the GPU.

| Level | Check | Pass rule |
|---|---|---|
| quick | `build-identity` | SemVer version and 40-hex commit; else `record-only` with evidence reasons |
| quick | `spawn-child` | a spawn child starts, answers and exits; if it fails, the rest is `not-run` (`spawn-failed`) |
| quick | `bundle-imports` | numpy, cv2, pyarrow, av, scipy, numba (if shipped), skellyforge native parts and onnxruntime import in that child; `from_bundle` when frozen |
| quick | `data-folder` | a file can be created, read and deleted under the base data folder; records `free_bytes` |
| quick | `install-facts` | record-only: install dir writable, per-user install, spaces or non-ASCII in paths, `ui_remote` |
| quick | `blender` | record-only: Blender found and its version |
| full | `reference-posthoc` | test_data, 3 cameras, cpu numerical profile, against 97,425 kept, 0.314339 px and foot_support within a shipped tolerance |
| full | `concurrent-runs` | a realtime run on recorded frames and a posthoc run together on CPU; both finish, the backend answers HTTP |
| full | `exports` | the CSV, npy and npz of `reference-posthoc` read back with the right shapes |
| full | `live-numbers` | record-only: 3-camera realtime ms/frame and FPS on CPU |

Installer uninstall and reinstall, signing and SmartScreen go on a release checklist, not in `certify()`.
skellytracker took these into its own checks: ONNX Runtime loaded from the bundle and not from PATH, the EP
store writable as non-admin, the telemetry switch, two sessions on one GPU, multi-GPU device selection,
Windows ML catalog installs as non-admin, and MediaPipe loading.

### OS rows and the start check

12. "This OS is certified for freemocap" is a reviewed row shipped in freemocap (proposed
    `freemocap/system/certify/os_evidence.yaml`): `os.name`, `os.release`, `os.arch`, the OS build family
    (Windows feature-update build, macOS major, Linux distro and version), the freemocap major.minor,
    `kind: full`, the issue number and the review date. A new freemocap minor invalidates a row; the build
    family is part of the key.
13. The start box appears only when an OS-level item (skellycam's or freemocap's) has no reviewed row and no
    local quick pass for the current version set. A quick pass on this PC stops the box until the freemocap,
    skellycam or skellytracker version changes. freemocap records that pass, with the version set, under
    `<base data folder>/certify/` on the server host.
14. While the start check is needed, the UI is greyed out, except the server connection panel, the log
    terminal and the Electron menu, and the Certification dialog stays open with no dismiss. It shows each
    package's plan; one click on "Run quick check" starts it, with an "Also run the full check" checkbox.
    Cancel returns the dialog to that state with the UI still grey. Any finished quick check, pass or fail,
    releases the UI; failures show as failures with "File report". The greyed state comes from the current
    server observation, not client history.
15. If only GPU EPs are uncertified, there is no box at start.

### EPs in use

16. An uncertified EP shows an icon in the EP list. Selecting it asks first ("certify now / later / do not
    ask again"; these choices exist only here), then runs the quick check in the background: a tiny probe,
    then one image through the person's selected pipeline on the EP and on CPU, in a child process, with no
    model download. Record waits for a running check, shows the seconds left (an estimate: 30-60 s on a first
    run, about 10 s warm) and a "Cancel check" button, with a note that the EP is not usable until a check
    passes. Only a pass of the whole quick check (probe and comparison) makes an EP with no reviewed row
    usable, for every EP including cuda and trt-rtx (user ruling relayed by skellytracker-6c, confirmed here
    2026-11-19). A pass makes the EP usable on that PC at once, shown as "passed on this PC, not yet reviewed".
17. A field-test EP (`directml`, `amdgpu`, `migraphx`) is usable only after an explicit opt-in recorded in
    the EP store; `recommend()` never returns one and the app does not offer it as a normal choice.
18. Evidence from normal use: asked once, right after a quick pass, off until yes, with a toggle in Settings.
    When Record waited on that quick check, the question waits until the recording and its processing end.
    After each recording, at idle, up to 30 frames from the saved videos run on the EP and on CPU and are
    compared; it stops when a recording starts. Counts and histograms only.
19. A hard failure (non-finite output, crash, hang, two unclean exits in a row) marks the EP failed on that
    PC and Auto skips it. A high disagreement rate only warns after the recording and offers a CPU re-run.
    The EP never changes during a recording.
20. A certify run is refused while any pipeline holds the GPU (live, recording or posthoc); the app offers to
    stop it first.
21. "Do not ask again" for an EP lives in the EP store (`dismiss_certification`); after "later" the prompt
    comes back the next time that EP is selected (changed from "lasts for the UI session"; user ruling relayed by
    skellytracker-6c, confirmed here 2026-11-19).

### Hand-in

22. A passed quick check alone gets no hand-in prompt. A failure report is always offered, also for an EP
    with a reviewed row. One hand-in is one file and one issue with everything not yet covered on that
    backend host. "Open issue form" counts as handed in; "open again" and "not sent" stay available. The
    backend returns the file as it is; the UI saves it on the UI machine and opens the issue form. Nothing is
    sent automatically.
23. Timing: nothing at close or start; a "File report" button in a failure message; one non-modal notice at
    the first idle moment after a recording when the normal-use record reaches its minimum; at most one
    notice per UI session; never during a recording or post-processing. "Do not remind me" is one switch per
    person in localStorage (`freemocap:` prefix); the indicator stays.
24. skellytracker provides `pending_reports()` and `mark_reports()` (pending, opened, covered); the pending
    list reaches the UI as a full-state field of a server message.

### UI: one place (Fable design, accepted)

25. A "Certification" button at the top right of the main navigation strip
    (`freemocap-ui/src/layout/BasePanelLayout.tsx`, beside `MainNavTabs`), always visible, never disabled, with
    a fixed label. A suffix and colour come from the current server state: nothing pending, `· 2 to file`,
    `· quick check 12 s`, `· 1 failure to file`, dimmed when disconnected (state cleared), `@ <host>` for a
    remote backend.
26. Clicking opens one Certification dialog (the `SettingsModal` pattern) with three parts: reports to hand in
    (summary with failures first, "View report", optional note with the privacy warning, "Save report and
    open issue form" with an unchanged label plus an "opened <date>" line, "Not sent", "Do not remind me");
    the running check (progress, "Cancel check"); and Items. Items is the EP page: each EP with state and
    reason, install with progress and cancel, remove, certify, and Windows ML catalog EPs with as much
    information as possible, plus "Run quick check", "Run full check" and, while a pipeline holds the GPU,
    "Stop pipelines" (no chained saved "then run"). Choosing the EP for a run stays in the detector settings.
27. The start box is the same dialog in a required mode. The normal-use question and the idle notice are one
    small pop-up attached to the button. The failure button "File report" opens the dialog. The full-run card
    is dropped. Record's waiting line stays at Record and reads the same `run` field.
28. Assumed server field (not built): `certification` in `app_state` (`AppStateSnapshot`,
    `freemocap/core/streaming/message_model.py`): `host {id, name, os}`, `run: null | {level, item_keys,
    seconds_left}`, `items[] {key, package, label, local_status, reviewed, hand_in, is_failure}`,
    `start_required`, `gpu_held_by[]`, `normal_use {consent, notice_due}`. Requests are keyed on endpoint +
    serverPid. Whether `seconds_left` rides `app_state` or the existing progress message is freemocap's
    choice (one message per second otherwise).
29. "Opened" and the normal-use consent live on the backend and are shared by everyone who uses that host;
    only "Do not remind me" is per person. Each report file stands alone. Add "Copy report text" if dragging
    the file into the issue form proves awkward (not yet checked).
30. New pieces: `CertificationButton`, `CertificationDialog`, a `certification` store slice fed by
    `app_state`, and one Electron IPC call to save a text file (none exists; browser fallback is a blob
    download).

### Exit signal and shutdown

31. Defect today: Electron tree-kills the backend on every close, and the shutdown runs twice
    (`electron/main/index.ts:59-62` and `:71-76`, `electron/main/services/python-server.ts:150-175`).
    The fix: close sends `POST /shutdown` (it exists: `freemocap/api/http/app/shutdown.py`), waits N seconds,
    tree-kills only as the fallback, once per close. **Built in `2a4c130d`** with N = 10 s as
    `SHUTDOWN_GRACE_MS`, marked unmeasured: the user chose "fix now, measure later" because no environment on
    the dev PC runs current freemocap (see [Environment on the dev PC](#environment-on-the-dev-pc)). Covered by
    `freemocap-ui/electron/main/services/python-server.test.cjs` (graceful exit with two concurrent calls; kill
    fallback). The installed September build is no reference: its `GET /shutdown` kills its own process
    (exit code 15, about 0.14 s, connection reset, 5 runs).
32. The backend's first act on a requested exit is `skellytracker.core.eps.note_exit_requested()` (working
    name; synchronous, under the store lock, no onnxruntime import, a no-op without an opened EP session),
    called via `to_thread` in `/shutdown` before cameras close, on SIGINT/SIGTERM (Ctrl+C) and on the dev
    reload stop (`serve_application.py:22`), not on the fatal-error path (`app.py:95-96`). skellytracker counts
    an exit as unclean only when an EP session was open and no notice arrived; "requested, then killed" is its
    own fact.

## Environment on the dev PC

Found 2026-11-19 while measuring decision 31; nothing was changed. `freemocap/.venv` dates from August 2026
(non-editable skellycam `main@777b058`, skellytracker 2024.9.1019, no `platformdirs`), `../skellycam` is on
`dom/research` (`close_camera_groups` exists only on upstream `sfn26`), and `../freemocap_blender_addon` is not
cloned, so `uv lock --check` fails. benchmarks/README.md forbids changing shared environments or setting
PYTHONPATH, so the shutdown time stays unmeasured until the workspace is set up.

## Waiting on skellytracker

- CI result of `55fabf4a`, then the pin. Windows and Linux are green; the macOS job never got a runner. The
  user ruled: wait for the macOS re-run before pinning.
- Package-wide `certify()` and `certify_plan()` with the quick level.
- Status-row flags for uncertified, failed on this PC and field-test.
- Windows ML catalog install progress and cancel, and a remove call.
- `note_exit_requested()`.
- `pending_reports()` and `mark_reports()`.
- The ONNX Runtime PyInstaller hook.

## Next actions

All as local commits on `sidecar-implementation`, in this order:

1. Done: Electron's close (decision 31, `2a4c130d`). Still open: measure `POST /shutdown` to exit once an
   environment runs current freemocap, then set `SHUTDOWN_GRACE_MS`. The skellytracker call (32) follows when
   it exists.
2. Done: the hardware cleanup (decisions 6 to 8, `3cdf672f`). The ping keeps its payload keys; the benchmark
   snapshot keeps `available_memory_bytes` and `system_cpu_percent` (percent) and replaces the `load_average`
   list with `load_average_1m`; `psutil>=7.0.0` as skellycam declares it. `uv.lock` is not regenerated (it
   cannot be on the dev PC); that happens with the pin. Checked: the new expressions run in skellytracker's
   venv and match the old psutil/platform values; `test_machine_benchmarks.py` gives 9 passed, 4 failed both
   before and after the change, all four from the stale freemocap venv.
3. When skellytracker's CI on `55fabf4a` is green, macOS included: pin it and regenerate `uv.lock` (decision 1).
4. Done (`61f68980`): `__version__` is `2.0.0-alpha.25`; bumpver writes it with the `package.json` pattern
   (dry run checked; `current_version` and git tags keep the `v`); the client contract and building.mdx
   follow. The telemetry `app_version` now arrives without the `v`, so dashboards see two spellings across
   this change. `BUILD_TREE_MODIFIED` (`bool | None`, `None` outside CI) is computed from tracked files with
   `git status --porcelain --untracked-files=no` before `build_info.py` is written; not yet run in CI.
5. Everything else waits for the skellytracker shapes.

## Reading list

| Source | Question it answers |
|---|---|
| `AGENTS.md`, section on self-describing transport | Which control rules every UI piece here must obey |
| `current-work-plans/03-transport/message-protocol.md`, "Client recovery and stable controls" | How the indicator, dialog and greyed state reconcile after failure, reconnect and restart |
| https://github.com/domisjustanumber/skellycertify `report-format.md` | The certify function, progress, cancel, runtime, report file, privacy and evidence rules |
| `freemocap/core/tracking/execution_providers.py`, `freemocap/api/http/onnx/onnx_router.py` | Today's EP calls and routes |
| `freemocap-ui/src/hooks/useExecutionProviderOptions.ts`, `src/services/server/execution-providers.ts` | How the EP menu filters rows today (on `usable` only) |
| `freemocap-ui/electron/main/services/python-server.ts`, `electron/main/index.ts` | The shutdown defect |
| `freemocap/system/telemetry/telemetry.py`, `freemocap/tools/machine_benchmarks.py` | The hardware cleanup targets |
| `freemocap/build_info.py`, `.github/workflows/build-installers-pyinstaller.yml:185-211` | Where the version, commit and tree state come from in a frozen build |
| [skellytracker-2-migration.md](skellytracker-2-migration.md) section 0.2 | The migration this work sits on |
