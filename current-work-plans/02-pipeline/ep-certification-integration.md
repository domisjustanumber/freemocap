# EP management, certification and report hand-in

**State (2026-11-19): APPROVED PLAN; the Electron shutdown fix (decision 31) the hardware cleanup (6 to 8), the version change (4), `BUILD_TREE_MODIFIED` (11) and the backend of the relay hand-in (10, 22 to 24, R1 to R5; see [Relay hand-in: built](#relay-hand-in-built)) and F15 step 1 (see [F15 step 1: built](#f15-step-1-built)) are built; the rest is not.** The user settled every decision below in a grilling
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
   PINNED 2026-11-19: `4dcf2a66e2b739e8b8b8165bf1ff4d937eba3501` (pushed fork commit; macOS CI waived by the
   user). `uv.lock` is regenerated (`75781fa0`). The source stays the local path `../skellytracker` until the
   sibling branches are pushed, so the pin is this record plus the checkout, not yet a git `rev`. Evidence, on
   that commit PLUS 16 uncommitted skellytracker files (another session's work in `core/eps`, certification):
   the app starts; fast suite 1588 passed, 7 failed (all the old baseline), 20 skipped, every file collects;
   gate A rtmpose and mediapipe complete on cpu; gate B rtmpose (trt-rtx) and mediapipe pass. Shutdown from
   `POST /shutdown` to exit on an idle backend: 1353, 1313, 1351 ms, no kill (decision 31; cameras unmeasured).
   Seen, not fixed: with stdout piped the backend prints `UnicodeEncodeError` logging errors (cp1252, from
   skellylogs' colored console handler); Electron pipes stdout too, the frozen app is unchecked.
   MOVED 2026-11-20 to `e17761b4ad7d57c560badc1257e12dd01f3fb18f` (head of `origin/dom/sidecar-implementation`,
   holds `669d9676`..`5020037f`, the 1.2.0 `summary` `0f233b5c` and the 0-to-1 install fraction). Still the
   path source plus this record: the sibling checkout already sat at it (with 12 uncommitted files of the
   skellytracker session in certification and `core/eps`), its `pyproject.toml` is unchanged since `4dcf2a66`,
   and `uv lock --check` passes, so `uv.lock` does not change. Fast suite on it: 1718 passed, 7 failed (the old
   baseline; the worker-exit and VMC ones then fixed in `7d97b4ce`, `809d7448`), 20 skipped; an earlier run under heavy load from other sessions also had 4 `test_quick_check`
   timeouts (child sent nothing in 60 s) that pass alone and in the rerun. UI: `tsc` clean, 230/10/46 pass.
   MOVED 2026-11-20 to `9a5f3912f3627e8d32b37c31109aab22d6d2a61c` (named by the skellytracker session: a LOCAL
   commit in its checkout `../skellytracker`, not pushed; holds `b9610a73`..`9a5f3912`: video and live rows,
   quick only on unreviewed pairs within 75 s, report 1.4.0, `eps.certify()` removed, `certify_frames`). Source:
   the clone `../skellytracker-pin`, fetched from the local path; its 22 ONNX hard links survive, the frames
   zip is tracked. `pyproject.toml` unchanged, `uv lock --check` passes, `uv.lock` unchanged. Fast suite:
   1750 passed, 0 failed, 20 skipped (340 s); UI: `tsc` clean, 230/10/46 pass. Isolated quick run (scratch EP
   store, CPU and DirectML on both GPUs): plan `total` 10 = progress `total` 10, estimate 42 s, no downloads;
   all 10 rows pass in 23.8 s.
2. After the migration, freemocap declares neither `onnx` nor `onnxruntime`; both arrive through
   skellytracker. `freemocap.spec:96-97` (collection), `:99-100` (stale `onnx` hidden import) and the
   onnxruntime excludes at `:151-156` move to a skellytracker PyInstaller hook. The dev pin `onnx==1.22.0`
   (`pyproject.toml:156`) goes with `legacy_tracker_run.py` at ST 2.4.
   DONE 2026-11-19 (`f053be14`, Windows only): the spec drops those lines and the seven mediapipe hidden
   imports that PyInstaller reported missing (migration plan "stale hidden imports"). PyInstaller loads
   `hook-onnxruntime.py` from `../skellytracker/skellytracker/_pyinstaller` through the `pyinstaller40`
   entry point, visible from the editable install. Payload before and after: the same 36 files, 78,610,666
   bytes under `onnxruntime`, `windowsml`, `onnx` and their metadata (the manual collection added nothing).
   `onnx` still arrives through skellytracker's imports. Without the excludes the archive gains
   `onnxruntime.transformers` and `.machine_info` (5.7 KB, reached only from ORT's CUDA debug print).
   Frozen run: `/health`, `/freemocap/onnx/system_information` (ORT 1.30.0, `onnxruntime-windowsml`,
   DML and CPU EPs) and `POST /shutdown` to exit 0 in 1.6 s. Seen, not fixed: a frozen build from this
   checkout lacks `skellycam` and `skellylogs` (setuptools finder editable installs are invisible to
   PyInstaller; the run needed `PYTHONPATH` with their sources), and the frozen app with piped stdout
   prints the cp1252 `UnicodeEncodeError` logging errors (58 at idle).
3. On Windows the ONNX Runtime distribution is `onnxruntime-windowsml` 1.30.0 (brings DirectML).
   `import skellytracker` sets `ORT_DISABLE_TELEMETRY=1` (a preset value stays); freemocap imports
   onnxruntime nowhere before skellytracker.
   VERIFIED 2026-11-19: no freemocap module imports `onnxruntime`; after `import freemocap.app.app` the
   variable is `1`, `onnxruntime` is not yet imported, and `onnxruntime-windowsml` is the only ORT
   distribution.
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
   A package may add keyword-only options with defaults after these three; `certify(level)` always works and
   `certify_plan` takes the same options (skellycertify `25b9631b`, report-format.md 2.2). An option that runs
   only part of a level makes the report `partial-run` (not evidence) unless the package's rules call that
   part complete for one item. skellytracker's planned options (names may change):
   `execution_providers=["cuda"]` and `pipeline=<the user's pipeline config or catalog key>`; that call is the
   quick check of decision 16. skellytracker's rule (wording confirmed with the built shape): that one-EP call
   is complete for item X, so its report is evidence when version, commit, unmodified tree and not-cancelled
   hold; it is not `partial-run`. A `quick` report never yields a reviewed row by itself. Until skellytracker
   has a SemVer version and a commit readable in a frozen app, reports carry `no-version` and possibly
   `no-commit` in `evidence.reasons`; the UI shows "not valid as evidence" as the expected state of development
   builds, not as a failed check.
   skellytracker check names (skellytracker-6c, 2026-11-19, local commit): each EP on each GPU gives `<ep>`,
   `<ep>:probe` and `<ep>:image` (since `9a5f3912`: `cpu:video`, `cpu:live` first, then per pair `<ep>:probe`,
   `<ep>:video`, `<ep>:live`, the JPEG rows and `<ep>`), with `<ep>` = `<key>@<device>` (device key without `gpu:`, `-` for `:`, e.g.
   `cuda@10de-2484-0`); `<key>` alone only when the EP has no GPU (`cpu`, a not-run row). Reader rule: a name
   with no `:` is the EP row; the EP key is the text before `@`; `details.eps.<ep>.device` is the real device
   key and `.gpu` the PCI id. Option `device=<device key or list>` (a named EP that cannot use a named GPU is
   not-run, `gpu-not-usable`), so decision 16 calls
   `certify("quick", ..., execution_providers=[key], device=<the run's device>, pipeline=P)`. With no EP named,
   `certify("quick")` checks every GPU EP with no reviewed row, `directml` and Windows ML catalog EPs included,
   on each GPU it can use (user ruling there; 11.9 s for directml on two GPUs on the RTX 3070 PC); this is
   what the start dialog's "Run quick check" runs for skellytracker. `certify_plan("quick")["details"]` has
   `checks` (the `<ep>` names), `execution_providers` (unique keys) and `not_run` (keyed by `<ep>`).
10. freemocap merges the module reports into one Markdown file (`certify-report-<yyyymmddThhmmssZ>.md`,
    `{schema, app {name, version, commit}, modules, note}`) and keeps it on the server host under
    `<base data folder>/certify/`. skellytracker's `certify()` also saves its own module report in the EP
    store; its pending hand-in entry carries that report's `created_utc` and `kind`, and freemocap finds its
    merged file by that pair. Passive records stay in the EP store; freemocap wraps them with the `app` block
    at hand-in.
    Built for hand-in (`208ae320`): the file is made at hand-in from `read_report()` of the chosen reports, not
    at run time, so no lookup by `created_utc`/`kind` exists. It is kept under `certify/` when it is accepted
    ("send" or "opened"). freemocap's own modules are in it since `8659b5d2` (see [freemocap's own module and reports:
    built](#freemocaps-own-module-and-reports-built)); skellycam's are not (its `certify()` is not built).
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
    run, about 10 s warm; measured warm on the RTX 3070 by skellytracker-6c: trt-rtx 9.2 s, cuda 10.7 s) and a "Cancel check" button, with a note that the EP is not usable until a check
    passes. Only a pass of the whole quick check (probe and comparison) makes an EP with no reviewed row
    usable, for every EP including cuda and trt-rtx (user ruling relayed by skellytracker-6c, confirmed here
    2026-11-19). A pass makes the EP usable on that PC at once, shown as "passed on this PC, not yet reviewed".
17. A field-test EP (`directml`, `amdgpu`, `migraphx`) becomes usable through a passed quick check, which is
    its opt-in (user ruling, skellytracker ADR-21BK item 2): the check gives a temporary opt-in that stays only
    on a pass. The start check's "Run quick check" includes it, so after a pass it is selectable, shown as
    "passed on this PC, not yet reviewed"; freemocap adds no extra click and follows the store (user,
    2026-11-19; replaces "only after an explicit opt-in"). `recommend()` never returns one, so Auto never
    uses it. The opt-in is one flag per EP key; usability per GPU comes only from the per-pair status flags
    (EP key, device key), never from the EP state alone. skellytracker stores one local result per `key |
    pack version | OS | GPU PCI id`, so two GPUs of the same model share a result, as a reviewed row does.
    The flags are built (skellytracker-6c, local on `dom/sidecar-implementation`, not pushed): each
    `status().eps` row has `checks`, a tuple of `DeviceCheck {device_key, name, certified, local_result
    ("passed" | "failed" | None), usable}`, one per GPU that passes the EP's floors, in `run_devices(key)`
    order, also for an EP not installed; `()` for cpu and for an EP no GPU here can use. `usable` = ready
    (installed, opted in when field-test) and no local failure and (certified or passed here); a local failure
    wins over a reviewed row. Labels: uncertified = not `certified`; passed on this PC = `local_result ==
    "passed"` and not certified; failed on this PC = `local_result == "failed"`; field-test =
    `PackStatus.catalog_status == "field-test"`. `recommend()` skips a pair that failed here (`skipped`,
    `failed_locally: true`). Limit: `PackStatus.usable`, `PackStatus.devices`, `check_start()` and a run do not
    read the quick checks, so freemocap offers a GPU only from `checks[n].usable`. User rulings 2026-11-19
    (relayed by skellytracker-6c, confirmed by the user here): check names stay `<key>@<device>` on every
    PC; two GPUs of one model share one local result; skellytracker itself will refuse a run on an EP and
    GPU with no reviewed row and no local pass (not built; the quick check keeps a way through). When that
    is built the limit above is gone and freemocap's menu filter only hides what would be refused.
    Built (`4a5d3da2`): the EP route carries `checks` (device key, certified, local result, usable); the menu and
    `usable_execution_providers()` offer an EP and GPU only from `checks[n].usable`, an EP with no checks from
    `usable`; the EP explanation says "passed on this PC, not yet reviewed" per GPU. skellytracker's local
    `669d9676` (after the pin) already makes `usable` and `devices` obey the rule (ADR-ER5X).
18. Evidence from normal use: asked once, right after a quick pass, off until yes, with a toggle in Settings.
    When Record waited on that quick check, the question waits until the recording and its processing end.
    After each recording, at idle, up to 30 frames from the saved videos run on the EP and on CPU and are
    compared; it stops when a recording starts. Counts and histograms only.
19. A hard failure (non-finite output, crash, hang, two unclean exits in a row) marks the EP failed on that
    PC and Auto skips it. A high disagreement rate only warns after the recording and offers a CPU re-run.
    The EP never changes during a recording.
    Built (`efcd4774`), the unclean-exit part only: the EP route's check row carries skellytracker's
    `DeviceCheck.local_cause` (`"unclean-exits"` or null) through the contract to the UI type. The UI says
    nothing of its own about a failed check (only "Not usable here." and skellytracker's `install_hint`), so the
    sentence "exited uncleanly twice" is not added yet; it belongs wherever a failed pair is first explained.
20. A certify run is refused while any pipeline holds the GPU (live, recording or posthoc); the app offers to
    stop it first.
21. "Do not ask again" for an EP lives in the EP store (`dismiss_certification`); after "later" the prompt
    comes back the next time that EP is selected (changed from "lasts for the UI session"; user ruling relayed by
    skellytracker-6c, confirmed here 2026-11-19).

### Hand-in

22. A passed quick check alone gets no hand-in prompt. A failure report is always offered, also for an EP
    with a reviewed row. One hand-in is one file and one issue with everything not yet covered on that
    backend host. Hand-in goes through the certify relay (decisions R1 to R5); the issue form stays as the
    fallback. "Open issue form" counts as handed in; "open again" and "not sent" stay available. For the
    issue form the backend returns the file as it is and the UI saves it on the UI machine. Nothing is sent
    automatically: a run sends nothing, and a file goes out only after the person read it and chose "send".
23. Timing: nothing at close or start; a "File report" button in a failure message; one non-modal notice at
    the first idle moment after a recording when the normal-use record reaches its minimum; at most one
    notice per UI session; never during a recording or post-processing. "Do not remind me" is one switch per
    person in localStorage (`freemocap:` prefix); the indicator stays.
24. skellytracker provides `pending_reports()` and `mark_reports()` (pending, opened, covered); the pending
    list reaches the UI as a full-state field of a server message. Planned shape (skellytracker-6c, not built;
    after its JPEG merge): `mark_reports(report_ids, state, *, reference=None)` with `state` one of
    `"pending"`, `"opened"`, `"covered"`. A relay 200 gives `"covered"` with `reference=<issue URL>`;
    "Save file and open issue form" gives `"opened"` (handed in, no link); "Not sent" gives `"pending"`, from
    opened or covered, and clears the reference. An unknown state or report id raises `ValueError` and changes
    nothing. `pending_reports()` gives the pending entries; the status gives each entry's state and reference,
    also after a restart. `reference` is opaque to skellytracker, which never contacts the relay or GitHub.
    Backend built (22 to 24, `31381fb1`; skellytracker `4dcf2a66` shape, read in its code): routes list every
    report with state and reference, return the exact file, send it and mark "opened". Not built: the pending
    list as a server-message field (24, decision 28 `certification`), "Not sent", and everything in the UI (23).

### Relay hand-in (skellycertify `1fc984d`, relay/README.md "Answers for the app developers", report-format.md 4.1)

The relay is a Cloudflare Worker that files a report as an issue in `domisjustanumber/skellycertify`, so
the person needs no GitHub account. Not deployed yet; the user does the Cloudflare steps. Test address:
`https://skellycertify-relay.<subdomain>.workers.dev`; issues from the test relay carry the label `relay-test`.
Routes: `POST /reports` with the file as body, `Content-Type: text/markdown; charset=utf-8`, at most 262,144
bytes; `GET /health` gives `{enabled, test_mode, schema_major}`. It allows any origin (CORS `*`).

R1. User rulings in the contract (2026-11-19): show the person the exact file and get a clear "send"
     before a send; keep the accepted file and retry only it, byte for byte, never with data added later (a
     resend is safe, the relay finds the earlier issue by SHA-256); on a failure with `retry: true`, keep
     the file and retry at the next app start; after 3 failed retries offer the issue form. 413 and 422 are
     permanent: never retry, offer the issue form at once; for 422 `privacy-rule` tell the person the rule
     number from `detail`. 400, 404 and 415 are app bugs.
R2. The app acts on the `retry` flag of the JSON error body `{error, retry, detail}`, never on the status
     number. 200 gives `{issue_url, issue_number, file_path, duplicate}`: show the link, mark the hand-in
     covered, delete the outbox copy.
R3. The backend sends and retries (user, 2026-11-19): the accepted file and its retry count live on the
     backend host beside the pending list and the shared state of decision 29; retry at the next backend
     start. A backend host without internet reaches the issue form after 3 retries.
R4. On "send" the exact accepted bytes go to `<base data folder>/certify/outbox/` with a retry count; only
     that file is ever sent. On 200 the outbox copy is deleted and the issue link recorded; the merged
     report stays as the local record (decision 10). The optional note is written before the person views
     the file, because it is part of the file.
R5. The relay address is one constant in freemocap with an environment-variable override, no UI (user,
     2026-11-19). It is empty until the user deploys; empty means relay off and hand-in offers only the
     issue form.

#### Relay hand-in: built

Backend only, 2026-11-19: `208ae320` (file builder), `4e152100` (sender, outbox, retry at start), `31381fb1`
(routes and client contract). The relay answered one `GET /health` with `{"enabled":true,"test_mode":false,
"schema_major":1}`; no POST was ever made to it (test mode is off), so a real 200 is unverified.
- File: `freemocap/system/certify/report_file.py`, a pure function of module reports, note and `app` block;
  reproduces `relay/samples/valid.md` byte for byte (minus its prose line) and passes the relay's own
  `report.js`/`privacy.js` (run with node when `../skellycertify` exists). The file name and time line use the
  earliest `created_utc`. It refuses a file that breaks privacy rules 1 to 11; the note is scrubbed first
  (paths to `<path>`, this host's user and host names to `<private>`) and appears only in the JSON block.
  The 13 real reports on the dev PC build into a 41,459-byte file the relay validator accepts.
- Exactness (R1, R4): "send" and "opened" carry the report ids, the note and the SHA-256 of the file the
  person viewed; the backend rebuilds it and answers 409 `file-changed` on a mismatch.
- Sender (R2, R3): `freemocap/system/certify/relay.py`, `requests`, 5 s connect / 30 s read. Before the POST the
  bytes and `{file_name, report_ids, failed_attempts, last_error}` go to `certify/outbox/<sha256>.md|.json`.
  200 with an issue URL of `domisjustanumber/skellycertify` and a matching number: `mark_reports(ids still
  listed, "covered", reference=url)`, then the outbox copy is deleted. Any other answer acts on `retry`;
  timeout, refused connection, a non-JSON body and an untrusted 200 count as `retry: true`. Retry runs once per
  backend start on a daemon thread; after 4 failed attempts (first send and 3 retries) or `retry: false` it
  stops and `offer_issue_form` is true. A file over 262,144 bytes is refused locally. A newer accepted file
  or "opened" removes the outbox entries that hold the same reports.
- Address (R5): `RELAY_URL` = the deployed address; `FREEMOCAP_CERTIFY_RELAY_URL` overrides it, empty = off.
- Routes (tag Certification): `GET /freemocap/certify/hand_in`, `POST .../hand_in/file`, `.../hand_in/send`,
  `.../hand_in/opened`. A stored reference reaches the UI only when it is such an issue URL; relay `detail` is
  plain text (max 200 characters) for the UI to show as text.
- Tests: `freemocap/tests/test_certify_report_file.py` (5), `test_certify_relay.py` (32, a fake relay on
  127.0.0.1; every non-local connection and every POST not to the fake raises).
- Open, for the user: a hand-in file holds several modules of one package, while report-format 4.1 says "one
  for each package" (the relay accepts it); whether "Not sent" should also drop a kept outbox file; whether a
  kept file can be cancelled before its retries end.

#### Relay follow-up: spec 1.1.0 and the switched-off relay

User-confirmed 2026-11-19, relayed from the skellycertify session (skellycertify-34):
- Several module reports of one package in one file are valid (spec 1.1.0, skellycertify main `56ad18e`).
  This closes the first open point above.
- skellytracker report ids become v4 UUIDs, with an optional `id` key per module.
- The relay is OFF now and stays off until the GitHub App is set up. (Superseded 2026-11-19: the relay is ON
  again; see "Decisions after step 1".)
- The `app` block gets no tree-modified flag.
- Report layout (spec section 4.2, skellycertify main `b7b6fd7`; owner confirmed 2026-11-19): the summary table has
  one row only for each section with the result `fail` (each failed check when a module has no sections), and a file
  with no such row has no table. `build_report_file` follows it; the JSON block still holds each check.

Built (`bf6e9e9f`): `send_report` reads `enabled` from `GET /health` after the file checks and before the
outbox copy. `enabled: false`, or a POST answer with error `relay-off` (503, `retry: true`), raises
`HandInError("relay-off")`, which `POST .../hand_in/send` answers as 409 `{"code": "relay-off", "detail":
"the relay is off; use the issue form"}`, the same answer as an empty address. No outbox copy is kept (a copy
made for this send is deleted) and no retry is counted. An unreachable health check or an unclear answer is
not "off": the send goes ahead and a failure counts as before. `retry_outbox` checks health once when an entry
waits and stops at `relay-off` with every entry and count unchanged. `GET .../hand_in` `relay_enabled` still
means only "an address is set"; it does not call the relay. The file declares `skellycertify.report/1.1.0`
once any module has an `id`, else 1.0.0; modules pass through unchanged. No code read a `quick-` prefix; the
relay tests now use UUID ids. Fixture `freemocap/tests/fixtures/certify/valid-quick.md` is the sample at
skellycertify `3609369`; the relay's own validator accepts the built file and refuses a non-UUID id
(`bad-value`).

### UI: one place (Fable design, accepted)

25. A "Certification" button at the top right of the main navigation strip
    (`freemocap-ui/src/layout/BasePanelLayout.tsx`, beside `MainNavTabs`), always visible, never disabled, with
    a fixed label. A suffix and colour come from the current server state: nothing pending, `· 2 to file`,
    `· quick check 12 s`, `· 1 failure to file`, dimmed when disconnected (state cleared), `@ <host>` for a
    remote backend.
26. Clicking opens one Certification dialog (the `SettingsModal` pattern) with three parts: reports to hand in
    (summary with failures first, optional note with the privacy warning, "View report" showing the exact
    file with "Send report" under it (R1), the fixed secondary "Save file and open issue form", made prominent
    after 3 failed retries or a 413/422 (user, 2026-11-19), a sent/opened line with the date and issue link,
    "Not sent", "Do not remind me"; labels never change with history);
    the running check (progress, "Cancel check"); and Items. Items is the EP page: each EP with state and
    reason, install with progress and cancel, remove, certify, and Windows ML catalog EPs with as much
    information as possible, plus "Run quick check", "Run full check" and, while a pipeline holds the GPU,
    "Stop pipelines" (no chained saved "then run"). Choosing the EP for a run stays in the detector settings.
27. The start box is the same dialog in a required mode. The normal-use question and the idle notice are one
    small pop-up attached to the button. The failure button "File report" opens the dialog. The full-run card
    is dropped. Record's waiting line stays at Record and reads the same `run` field.
28. Assumed server field (not built): `certification` in `app_state` (`AppStateSnapshot`,
    `freemocap/core/streaming/message_model.py`): `host {id, name, os}`, `run: null | {level, item_keys,
    seconds_left}`, `items[] {key, package, label, local_status, reviewed, hand_in, is_failure}` (for
    skellytracker, `key` is the `<ep>` check name, one item per EP per GPU),
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
    **Built in `efcd4774`** as `skellytracker.note_exit_requested()` (the code's name; `skellytracker.core.eps`
    does not export it): first in `POST /shutdown`, via `to_thread`, before `close_camera_groups()`; in
    `serve_application` when the reload stop is first seen and no fatal error set the kill flag; and in
    `__main__`'s SIGINT/SIGTERM handler. While uvicorn serves it captures those signals and re-raises them after
    its own shutdown, so on Ctrl+C the notice comes after the cameras close but before the process ends (which
    always ends with `os._exit`, so skellytracker's `atexit` clean exit never runs). Inference runs only on the
    `SharedInference` thread of the backend process, so no worker process needs the notice. Not verified with a
    real GPU session held at close.
    **Rule (skellytracker `e90245ce`, `core/eps/exits.py`, ADR-ER5X item 5).** Only the process that called
    `build_session()` on a GPU EP writes a marker (`<store>/sessions/<pid>-<ns>.marker`, locked for its life); a
    process that only starts it is unaffected. A clean interpreter exit (`atexit`) or `note_exit_requested()`
    removes it; any other end leaves it, and the next `collect()` counts one unclean exit per EP and GPU model in
    `<store>/unclean-exits.json`; two in a row write `failed`/`unclean-exits` to `quick-checks.json`. Call the
    notice only in a process that really is about to end on purpose; never on a crash or a hang. Certification
    writes no marker: every EP run of `certify()` is a `spawn` child inside `gate.certification_run()`, and
    `note_session()` returns early there, so killing the quick-check child (`system/certify/quick_check.py`) adds
    no count. CPU sessions write none (`gpu is None`).
    **Audit, 2026-11-19 (every hard end in freemocap's code, tests and tools).** Fixed: the dataset preparation
    worker, which runs `InferenceService` in its own process, was killed at once when `execute_worker` was
    interrupted; the parent now creates a stop file, the worker gives the notice and ends with 130, and the kill
    stays only for a timeout (a hang keeps its count) and after 10 s (`5803111e`, reworked in `60787afe` because a
    pending stdin read on Windows blocks every subprocess the worker starts). `tracker_matrix` and
    `machine_benchmarks` used `subprocess.run`, which kills the child 0.25 s after Ctrl+C on POSIX; they now
    wait and let the child (same console) end itself (`ea85e9e7`); on Windows `Popen.wait` is not interrupted by
    Ctrl+C, so that kill was reached only on POSIX. The start without `--port` killed whatever held port 53117 (an
    earlier backend after an Electron crash); it now sends `POST /shutdown` first, waits 5 s, then kills
    (`ce160407`, `freemocap/utilities/kill_process_on_port.py`, replacing skellycam's copy). Needs nothing: the
    backend's own `os._exit` (every requested path has the notice; `KeyboardInterrupt` there is reachable only
    before the signal handlers are installed, and a start that fails before serving has no session: sessions
    open only on a pipeline request); `ServerSession` and `sdk_live_validation` (already `POST /shutdown`, wait
    30 s, then terminate); Blender kills; node children; camera and annotation process workers (no ORT);
    `check_main_process_heartbeat`'s self-SIGTERM (a 300 s hang, which should count); tests (no fixture runs
    inference in a process it ends hard; `test_hardware_server_harness` ends its backend through `/shutdown`).
    Real hardware (RTX 3060, trt-rtx by Auto, store `%LOCALAPPDATA%\skellytracker\eps`, before: no marker, no
    count file): the worker held marker `19348-…` with `trt-rtx|0.5.0|Windows|10de:2484`, got the stop file,
    exited 130; the backend held `42560-…` mid-posthoc, answered `POST /shutdown` and exited 0 in 1.5 s. After
    each: no marker, no `unclean-exits.json`.

## The uncertified-EP flow, as settled 2026-11-19 (second grilling; user confirmed)

This section WINS over decisions 14, 16, 18, 21, 25 and 26 where they differ. Reason for most changes:
skellytracker now refuses, with no override, an EP on a GPU with no reviewed row and no local pass (ADR-ER5X),
so the quick check is the only way in.

- F1. An unchecked EP and GPU is SHOWN in the EP menu, marked; choosing it opens the quick-check prompt (the
  hiding built in `4a5d3da2` is reversed for it).
- F2. A pair that failed here stays visible with its reason; choosing it offers the check again.
- F3. On Auto the app runs what `recommend()` chose and, when a skipped candidate has `needs_check`, shows a
  non-blocking notice beside the EP setting ("A faster option needs a quick check on this machine" (G1)) with a
  "Run quick check" button. F11: that notice has no dismiss; it follows the server's observation.
- F4. A saved EP and GPU that skellytracker refuses makes the start fail visibly, with the reason and the
  quick-check offer. No automatic switch to CPU.
- F5. The prompt has two choices: "Run quick check" and "Not now". "Do not ask again" is dropped and
  freemocap does not call `dismiss_certification` (replaces that part of 16 and 21).
- F6. "Not now", cancel and failure revert the EP setting to what it was; a pass makes the new EP the
  selection. Choosing the EP again asks again.
- F7. Every pipeline start (realtime, recording, posthoc; CPU ones too) waits while any quick check runs, and
  a check is refused while any pipeline runs (extends 16 and 20). Widened to all work by H1.
- F8. Nothing is queued: after a pass the user presses Record or Start again.
- F9. One prompt checks one pair: `certify("quick", execution_providers=[key], device=<the GPU chosen in the
  Device row>, pipeline=P)`. The Device row marks each GPU with its own state and opens the same prompt.
- F10. Progress is checks done of total with a one-off "up to about N seconds"; no ticking countdown
  (skellytracker's `seconds_left` is a sum of uncalibrated ceilings). The button suffix of decision 25
  becomes `· quick check 1 of 3`.
- F12. Five states, worded with "machine", never "PC" or "device" for the computer (user: Mac users; G1):
  reviewed = no marker; "passed on this machine, not yet reviewed" (G1); "not checked on this machine" (G1);
  "check failed on this machine" (G1); "exited uncleanly twice". No marker for field-test. Text already built with "PC" changes too.
- F13. The full-check controls (the start box checkbox, "Run full check") are left out until skellytracker's
  full level exists.
- F14. Decision 18 (evidence from normal use) is deferred as a whole; nothing is asked after a quick pass.
- F15. Build order: (1) the `certification` state of decision 28 with the check job, its routes and the busy
  rule; (2) markers, prompt and background check in the UI; then in parallel (3) the Certification button and
  dialog with the hand-in UI, (4) the start check and freemocap's own checks, (5) the Windows ML controls.
- F16. Install and remove of a Windows ML EP are refused while a pipeline or a check runs; remove asks first.
- F17. The cp1252 logging errors are fixed on freemocap's side by forcing UTF-8 output, once a sub-agent has
  shown what works in a frozen app; skellylogs stays untouched; skellycam-18 is told. Built 2026-11-19
  (`fa3bd57c`): `freemocap/__main__.py` reconfigures stdout/stderr to UTF-8 before any import, since a frozen
  app ignores `PYTHONUTF8`/`PYTHONIOENCODING`; dev `python -m` workers still use cp1252 (they configure
  logging in skellycam's `managed_worker.py`).
- F18. One hand-in file may hold several reports of one package; the spec wording ("one for each package")
  is raised with the skellycertify session.
- F19 and F20. "Not sent" marks the reports pending again and deletes any kept outbox file for them; it is
  also offered on a file waiting to retry.
- Also: the test setup blanks the relay address for every test, so no test can post to the real relay.
- Built 2026-11-19. F19 and F20 (`9b5ea74d`): `POST /freemocap/certify/hand_in/not_sent` with `{report_ids}` returns the hand-in list;
  `relay.mark_not_sent` calls `mark_reports(ids, "pending")` (clears the reference; an unknown id raises and changes nothing, 422
  `unknown-report`), then deletes every outbox entry (`.md` and `.json`, waiting to retry or given up) holding one of them, under
  the send lock. A covered report may be un-covered (decision 24). The route addresses reports, not entries: for a kept file the UI
  passes its `report_ids`. The test guard (`2f178809`): `freemocap/tests/conftest.py` sets `FREEMOCAP_CERTIFY_RELAY_URL` to empty in
  `pytest_configure`; `relay_url()` reads it at each call. F12 wording (`e4082308`): "passed on this machine, not yet reviewed" (G1; built as "device", changed to "machine" after the third grilling).
  Also `92f22855`: `report_file_for` orders modules by `created_utc`, then report id, so the same reports give the same bytes.

### F15 step 1: built

Backend only, 2026-11-19, on skellytracker `b9660935` (local, after the pin). Commits: `b52ba94b` (job), `c0c71dc0`
(busy rule), `b820aaa5` (routes and client contract), `e89324f9` (F4). The message field, its golden fixture and
its tests landed inside `07f9ccf9` (another session committed while they were staged in the shared index; that
commit's message is the plan's). Tests: `freemocap/tests/test_quick_check.py` (21; the job runs in a real spawn
child with module-level stand-ins for `certify`).

- Job (`freemocap/system/certify/quick_check.py`): `QuickCheckJob` is a `BaseNode` worker made through the
  `WorkerRegistry`, like `SyncJob` (`freemocap/core/pipeline/posthoc/sync_job.py`), not daemonic because
  `certify()` starts spawn children of its own. The child runs `certify("quick", queue.put, cancel,
  execution_providers=[key], device=device_key, pipeline=load_detector_pipeline(detector_type, model))` and sends
  back only the EP row's `(result, reason)` (the check whose name has no `:`), or `("error", <class name>)`. A
  child watcher sets the cancel when the cross-process `multiprocessing.Event` is set, the job's stop flag or the
  global kill flag is set, or the backend process is gone; certify() gets a `threading.Event` mirror (see the
  interface differences). `QuickCheckManager` holds at most one job; `refresh()` runs in the backend's 0.5 s task
  collector (`freemocap/app/app.py`), keeps only the newest progress message, reaps the job (no result and a dead
  child = `crashed`, `exit-code-N`) and re-reads `eps.status()` and `pending_reports()` at once when a check ends
  and every 5 s otherwise. `shutdown()` is first in `shutdown_all_processing()`, so `/shutdown` and every backend
  exit cancel the check, wait up to 5 s, kill the child's process tree (psutil) and end the child; `/shutdown`
  and `__main__` are unchanged. The saved EP selection is never changed (F6 is the UI's).
- Busy rule (F7, decision 20): `FreemocapApplication.pipeline_holds()` = alive realtime pipelines, a realtime
  startup in progress, camera groups recording, alive posthoc pipelines (CPU ones too; sync and export jobs are
  not pipelines and do not count). A check start with any hold is refused 409 `pipelines-running` with
  `gpu_held_by`. `refuse_pipeline_start(kind)` is called first in `create_or_update_realtime_pipeline`,
  `start_recording_all`, `create_posthoc_calibration_pipeline` and `create_posthoc_mocap_pipeline` (every start
  route reaches one of these); while a check runs they answer 409 `quick-check-running` with
  `run {execution_provider, device_key, done, total}`, mapped in the realtime, mocap and calibration routes.
  Nothing is stored or queued; the refusal is the answer to that request.
- F4: before a realtime start or a posthoc tracking run, a chosen EP (not Auto) is checked with
  `eps.check_start(key, device=...)`; `EpUnavailableError` is refused 409 `execution-provider-unavailable` with
  `message` (skellytracker's text without the CLI hint), `execution_provider`, `device_key`, `reason_code` (the EP
  row's `PackStatus.reason_code`, null when the EP can run on another GPU) and `check {certified, local_result,
  local_cause, usable}` of that GPU. An unknown key is left to the run, as before. The late path (the inference
  thread's start failure, a string in the realtime startup task) is unchanged.
- Routes (`freemocap/api/http/certify/quick_check_router.py`, tag Certification):
  `GET /freemocap/certify/quick_check/plan?execution_provider&device_key` (skellytracker's `certify_plan`:
  `seconds_estimate`, `downloads`, `checks`, `not_run`); `POST /freemocap/certify/quick_check` with
  `{execution_provider, device_key, detector_type, rtmpose_model_name}` (the detector fields default to the camera
  node defaults) answers 202 with the run, or 400 `unknown-ep-or-device`, 409 `cannot-run` with skellytracker's
  `reason_code` from the plan's `not_run` (for example `ep-not-installed`), 409 `pipelines-running`, 409
  `quick-check-running`; `DELETE /freemocap/certify/quick_check` asks the check to stop and answers
  `{run: <the run> | null}`. Every refusal body is `{code, message, ...facts}`. Contract: only these paths and
  schemas were added to `contracts/openapi.json`, plus `operations.json`, `coverage.md` and the generated client.
- Message (`app_state.state.certification`, `CertificationSnapshot` in `message_model.py`): progress rides
  `app_state`, not the progress message. Reason: `app_state` is already sent once a second and only on change, so
  skellytracker's up to 10 progress messages a second are coalesced twice (the manager keeps the newest every
  0.5 s; the sender sends a changed state at most once a second), and the Certification button, the dialog and
  Record's waiting line read one field. The progress message would need a new task type in the client's strict
  task enum and is sent every 0.5 s regardless. Measured on the real check: 7 progress messages from
  skellytracker in about 11 s, 6 `app_state` messages with a run. The client's Zod schema does not list the field
  yet (it strips it; the transport accepts the golden), so step 2 adds the schema. Shape (a null value is left
  out of the CBOR map, as everywhere in `app_state`; the field itself is absent until the first status read):

  ```
  certification: {
    host: {name, os},                       // os = skellytracker's OS label, e.g. "Windows 11 Home 26H2"
    run: {level: "quick", items: [{execution_provider, device_key}],
          state,                            // skellytracker's: starting | running | cleaning-up | done
          done, total,                      // total absent until the first progress message
          seconds_estimate} | absent,       // certify_plan's one-off estimate
    last_result: {execution_provider, device_key,
                  result,                   // pass | fail | not-run (a cancel gives not-run, reason "cancelled") | crashed | error
                  reason} | absent,         // skellytracker's reason code, exit-code-N, or an exception class name
    items: [{execution_provider, label, device_key, device_name,
             certified, local_result, local_cause, usable,   // DeviceCheck facts: the UI words F12's five states
             reason_code, reason}],         // the EP row's PackStatus reason; one item per EP per GPU (PackStatus.checks)
    auto: {execution_provider, device_key, needs_check: [{execution_provider, device_key}]},
    gpu_held_by: [{kind: realtime | recording | posthoc, id}],
    pending_reports: [{report_id, has_failure}]  // skellytracker's pending hand-in list (decision 24)
  }
  ```

  Example (the golden `freemocap/tests/streaming_fixtures/message_app_state_golden.bin`, decoded):
  `{"host": {"name": "golden-host", "os": "Windows 11 Home 26H2"}, "run": {"level": "quick", "items":
  [{"execution_provider": "golden-ep", "device_key": "gpu:10de:2484:0"}], "state": "running", "done": 2,
  "total": 5, "seconds_estimate": 45}, "last_result": {"execution_provider": "other-ep", "device_key":
  "gpu:10de:2484:0", "result": "fail", "reason": "probe-l3-failed"}, "items": [{"execution_provider":
  "golden-ep", "label": "Golden EP", "device_key": "gpu:10de:2484:0", "device_name": "NVIDIA GeForce RTX 3070",
  "certified": false, "usable": false, "reason_code": "quick-check-needed", "reason": "no reviewed result and no
  quick check"}, ...], "auto": {"execution_provider": "cpu-ep", "needs_check": [...]}, "gpu_held_by": [{"kind":
  "posthoc", "id": "abc123"}], "pending_reports": [{"report_id": "quick-20261119T120000Z", "has_failure": true}]}`.

  Changes from decision 28 and why: items are keyed by the pair `(execution_provider, device_key)`, not the
  `<ep>` check name, which only skellytracker's private `_label()` builds; `run` carries `done`, `total`,
  `seconds_estimate` and `state` instead of `seconds_left` (F10) and `items` instead of `item_keys`; items carry
  skellytracker's facts instead of `local_status`, `reviewed`, `hand_in` and `is_failure`; `install_hint` is left
  out (a CLI command; the EP route still carries it); `last_result` is new, so the UI can say why a check ended
  without a change in the stored result (cancel, not-run with `models-missing`, crash); `host.id` is left out (no
  stable host id exists; requests are keyed on endpoint + serverPid); `start_required` is left out (adding it
  later is compatible, and a constant false would be a fake observation); `normal_use` is left out (F14); the
  hand-in state beyond the pending ids stays in the hand-in routes.
- Real check on this PC (RTX 3070, `cuda` on `gpu:10de:2484:0`, no pipeline, through the route): 202 in 0.26 s,
  a second start 409 `quick-check-running`, `pass` 15.0 s after the POST (the child's run about 13.8 s; plan
  estimate 50 s); `app_state` progress 0 (no total) -> 0/5 starting -> 0/5 running -> 1/5 -> 2/5 -> 5/5
  cleaning-up -> run absent with `last_result` pass. The stored result stayed `passed` (new `created_utc`), and
  the item's facts were identical before and after; skellytracker pruned repeated plain-pass reports, so this
  PC's pending list went from 13 to 6. An earlier attempt the same hour ended `not-run` with
  `BeartypeCallHintParamViolation` at the image step (the cancel type; fixed before `b52ba94b`); its probe ran
  and its report is in the store, outside the pending list (no pass or fail).
- Interface differences found in skellytracker (`b9660935` plus another session's uncommitted wording in
  `gate.py`): certify()'s docstring says `cancel` is "an object with `is_set()`", but `certification._wide_run`
  (and other inner functions) annotate `threading.Event`, and beartype refuses a `multiprocessing.Event` in a
  source run, so freemocap passes a mirror (ask skellytracker to annotate a protocol). The progress message also
  has `package`, `kind` and `step {name} | null`. `EpUnavailableError` carries only `message` and `hint`: no EP
  key, device key or reason code, and `DeviceCheck` has no per-pair reason code (ask for one). `recommend()`
  takes a form (`recommend("performance")`; `status().performance` is the same). `certify_plan` takes the same
  options but ignores `pipeline`.
- Open, for the user: whether sync and export jobs should also block a check (they are not pipelines today);
  what the UI says for each `last_result` (not decided; the facts are sent); whether a check start should be
  refused while the cameras only stream (today it is allowed). A small race is left: a pipeline admitted in the
  same instant a check starts can slip through (no shared lock across the async starts). Linux runs the check in
  the app's default start method (fork) until skellycam's `ManagedProcess` takes a context.

### F15 step 2: built

UI only, 2026-11-19. Commits: `48e61bf3` (transport), `4df61357` (menu, prompt, check). No backend or HTTP API change.

- Transport: `CertificationSchema` in `packages/freemocap-client/src/transport/message-contract.ts`, optional in
  `app_state.state`; null fields are optional keys; `kind`, `state`, `result` and the codes are open strings (the
  busy rule's new `kind` values pass). The connection slice keeps it as `certification` (null until known and while
  disconnected; replaced by every `app_state`). Test: the golden in `snapshot-reconciliation.test.ts`.
- Pure rules (`freemocap-ui/src/services/server/execution-providers.ts`): `pairState` and `PAIR_MARKERS` (F12's five
  states); `menuPairs` (usable pairs plus pairs that skellytracker refuses only by its check rule, reason codes
  `quick-check-needed`, `quick-check-failed`, `unclean-exits`, or none when the EP runs on another GPU; not-installed
  and field-test pairs stay hidden); `executionProviderOptions(selected, providers, items)` marks an EP with the state
  of the pair Auto's device would take; `menuDevices` (Device row, marked); `pairToCheck`; `quickCheckProgressText`
  (F10); `QUICK_CHECK_TEXT` and `quickCheckResultText` (the six lines, in one place); `checkIntentOutcome` (F6);
  `requestQuickCheck` and `requestQuickCheckCancel`. Before the first `certification` the menu works as before.
- The menu and the panel: `detector-setting-rows.tsx` routes an EP or Device choice that needs a check to the prompt
  and does not change the setting (so "Not now", a cancel and a failure leave it as it was, F6); a pass of a check this
  window started makes the choice the selection, through the rows' current change handler. `quick-check-panel.tsx`
  shows, from the server state: the running check with "Cancel check"; the prompt ("Run quick check" / "Not now"); for a
  selection that needs a check (F4, a saved choice) a line with "Run quick check"; on Auto, the notice "A faster option
  needs a quick check on this machine" with "Run quick check" and no dismiss (F3, F11); a refused start as "Quick check
  could not start: <server message>"; and how the last check ended. `useQuickCheck.ts` holds only what the person
  asked in this window (the prompt, the started check, the refusal, which result they moved on from), keyed on
  endpoint + pid + connected, and ignores a start answered after a newer choice or by another server.
- Cancel finding: a cancel shows in `last_result` as `result: "not-run", reason: "cancelled"` (skellytracker marks
  every unfinished check row so and adds `cancelled` to the evidence reasons); seen on the RTX 3070 (cuda, cancelled
  at 1 of 5: `last_result` not-run/cancelled about 1 s later). A cancel after the EP row already has its result keeps
  that result. `error` (certify() raised; the reason is the class name) is worded "could not start".
- Live run, this PC (backend from this checkout, relay URL empty, no UI window: no browser tool here): the real
  `certification` parsed through the client schema; the menu logic gave Auto, TensorRT RTX, CUDA, CPU with no
  markers (both GPU EPs reviewed; DirectML hidden as field-test); one quick check of cuda gave 202, a second start
  "A quick check of cuda on gpu:10de:2484:0 is already running.", progress "starting" then "0 of 5" and "1 of 5,
  up to about 50 seconds", then "Quick check cancelled". The backend was shut down through `/shutdown`.
- Tests: `execution-providers.test.ts` (17), `detector-setting-rows.test.tsx` (8 new; its runner 46), the golden
  test; the full UI unit suite passes (`node tools/test-sdk-integration.mjs`); `tsc --noEmit` clean.
- Not covered by tests: the hook's state changes (no DOM or React test renderer in the UI's dependencies), so the
  apply-on-pass, "Not now", the obsolete-answer rule and the server-change reset are checked only through their pure
  rules and markup; the manual checklist covers them. Not seen: the rendered page, a pipeline start refused while a
  check runs, a check refused while something runs, an unchecked or failed pair (none on this PC).
- Known limits: the started check lives in the settings window; if the person closes it before a pass, the
  selection does not change (choosing the EP again then needs no check). In the realtime settings a pass applies
  the change as every change there does (the realtime apply). CoreML's chip key is sent as `device_key` (the
  backend's concern; not seen on a Mac). The EP explanation popover still shows skellytracker's `install_hint` (a CLI
  command) for an EP that needs a check. A field-test EP with no opt-in stays hidden (decision 17's check-as-opt-in
  belongs to the start check, step 4). The Certification button's `· quick check 1 of 3` and Record's waiting line
  are step 3.

#### MANUAL CHECKLIST (G7)

You need an EP and GPU that this machine has not checked (on the dev PC every GPU EP is reviewed, so use a machine
with a GPU EP that has no reviewed result, or a fresh EP store). Start the app. The EP setting is in two places:
"Processing settings" (real-time) and the mocap processing window's skeleton detector section. Steps 1 to 10 work in
either.

1. Open "Processing settings". Open the "Execution provider" menu. You see your unchecked EP, with "(not checked on
   this machine)" after its name. A reviewed EP has nothing after its name.
2. Select Auto. If Auto skipped a faster EP that needs a check, you see "A faster option needs a quick check on this
   machine: <EP> on <GPU>." with a "Run quick check" button and no dismiss button. Leave it for now.
3. Select the unchecked EP. The menu still shows the EP you had before. A box says "<EP> on <GPU>: not checked on
   this machine." with two buttons: "Run quick check" and "Not now".
4. Click "Not now". The box closes. The menu still shows the EP you had before.
5. Select the unchecked EP again. The same box comes back. Click "Run quick check". A line says "Quick check of
   <EP> on <GPU>: starting, up to about N seconds." and then "1 of 5 checks done" and so on, with "Cancel check".
6. Click "Cancel check". Within a few seconds the line says "<EP> on <GPU>: Quick check cancelled". The menu still
   shows the EP you had before.
7. Select the unchecked EP again and click "Run quick check". Wait until it ends. If it passed, the menu now shows
   that EP, and a line says "Quick check passed". If it failed, the menu shows the EP you had before, and the line
   says "Quick check failed: <reason>"; the EP now shows "(check failed on this machine)".
8. Select another EP. The result line goes away.
9. If the machine has two GPUs for the EP: select the EP, open the "Device" menu. Each GPU shows its own state.
   Choosing an unchecked GPU opens the same two-button box for that GPU only.
10. Close and reopen the settings. The "Run quick check" and "Not now" buttons always have the same labels and are
    never greyed out, also after a refusal.
11. Busy rule, one way: start real-time processing (or a recording, or a posthoc run). Then try a quick check (step
    5). A red line says "Quick check could not start: <the server's reason>". Stop the processing; click "Run quick
    check" again; it starts.
12. Busy rule, with cameras: with cameras streaming and nothing else, try a quick check. It is refused with the
    server's reason (once the backend's wider busy rule is in).
13. Busy rule, other way: start a quick check, then press "Real-time processing" or Record. The start is refused:
    the error banner shows the server's reason ("The quick check of <EP> on <GPU> is running; ..."). Nothing starts by itself when
    the check ends; press it again.
14. Refused saved choice: on a machine where your saved EP is not checked (or failed), start real-time processing.
    It fails with the server's message in the error banner, and it does not switch to CPU. Under the EP setting you
    see "<EP> on <GPU>: not checked on this machine. A start with it is refused until a quick check passes." with
    "Run quick check".
15. Restart: start a quick check, then quit and restart the backend (or the app). The page recovers without a
    refresh; no old progress or prompt stays; the menu shows the server's states again.

### F15 step 3: built

UI only, 2026-11-19. Commits: `9ea49626` (rules, texts, requests, tests), `ed12f948` (button, dialog, wiring). No backend or
HTTP API change; the routes of "Relay hand-in: built" and F19/F20 were enough.

- Rules and texts (`freemocap-ui/src/services/server/certification-hand-in.ts`): `CERTIFICATION_TEXT` (every text of
  the button, the dialog, "File report" and Record's waiting line, in one place, G1 wording); `certificationButtonSuffix`
  (decision 25 and F10: `· quick check 1 of 3` while a check runs, else `· N failure(s) to file` when any pending report
  has a failure, else `· N to file`, plus `@ <host name>` when the backend address is not this machine); `pendingSummary`,
  `pendingRows` (failures first, with kind and time from the hand-in list); `handedIn` (covered reports grouped by
  issue link, issue-form reports together); `outboxLine` (F20: waiting to retry, or given up); `sendAnswerMessage`
  (accepted with the issue link, already filed, kept for the next start, given up, refused with the relay's code or
  privacy rule number, 409 `relay-off`, 409 `file-changed`, anything else); `viewIsCurrent` (the viewed file counts only
  for the same pending ids and note, R1); `issueFormProminent` (relay off or refused, no relay address, file too large,
  a kept file given up); `safeIssueUrl` (a link is made only from a skellycertify issue address); the five requests.
- `freemocap-ui/src/hooks/useHandIn.ts`: keyed on endpoint + pid + connected like `useQuickCheck`; reads
  `GET .../hand_in` while the dialog is open and again whenever the server's `pending_reports` change; keeps only the
  note, the viewed file and the answer to this window's last request, and ignores answers from a server that is no
  longer this one. "Save file and open issue form" saves the viewed file with a browser download (Electron shows its
  save dialog, as the log terminal's "save" already does), opens the issue form (`window.open`, which Electron hands to
  the system browser), then posts `opened`.
- `freemocap-ui/src/components/certification/CertificationDialog.tsx`: `CertificationButton` at the top right of the
  navigation strip (`BasePanelLayout.tsx`), fixed label, dimmed while disconnected; `CertificationDialog` in
  `AppContent.tsx` beside `SettingsModal`, opened by the window event `open-certification` (the button, and "File report"
  on a failed quick check's result line in `quick-check-panel.tsx`). Parts: the running check with "Cancel check"; the
  reports: summary, list, note with the privacy warning, "View report" showing the exact file, "Send report" (hidden
  only while the backend has no relay address, R5) and "Save file and open issue form" (highlighted per
  `issueFormProminent`), the answer line, each kept file with "Not sent", each hand-in made (issue link, or "Issue form
  opened" with a link to open the form again) with "Not sent". No health call on open (G3). Record's waiting line in
  `RecordingControlPanel.tsx` reads the same `run`.
- Tests: `certification-hand-in.test.ts` (8); UI unit suite (`node tools/test-sdk-integration.mjs`) 213 tests, 212
  pass, 1 skipped (as before), plus its 10 and 46; `tsc --noEmit` clean; client `npm test` 141 pass. Live, read-only,
  backend from this checkout with `FREEMOCAP_CERTIFY_RELAY_URL` empty: the real hand-in list (7 pending, 0 outbox, relay
  off) parsed and listed; the file built (23,990 bytes, fits the relay); "send" answered 409 `relay-off`, worded "The
  relay is off. Use the issue form." with the issue form highlighted. No `opened` or `not_sent` was posted (they would
  change this machine's store). Backend stopped through `/shutdown`.
- Not covered: the rendered dialog (no browser tool here; no DOM test renderer in the UI's dependencies), so the
  hook's state changes are checked only through their pure rules; the manual checklist covers them. Never seen: a
  relay 200, a kept or refused answer from a real relay, the `relay-off` answer to a send while an address is set.
- Choices made (open for the user): the suffix counts failures when there are any, else all pending; the issue form
  link is `issues/new?template=certify-report.yml` (straight to the form); a hand-in has no date in the backend's list,
  so the hand-in line shows the issue link and the report count but no date; "open again" for an issue-form hand-in
  opens the form, not the saved file; the saved file uses the browser download, not a new Electron IPC call (decision
  30), because the log terminal's download already works in Electron; no "Do not remind me" and no idle notice
  (decision 23's notice needs the normal-use record, deferred by F14); the dialog title carries the host name; the
  Items part (decision 26) is step 5.

#### MANUAL CHECKLIST (step 3)

Do NOT click "Send report" before step 13. Every other step files nothing. Closing a GitHub tab without submitting it
files nothing.

1. Start the app. In the strip, right after "Streaming" and "Playback", you see "Certification". On the dev
   machine (7 pending reports) it reads "Certification · 7 to file".
2. Stop the backend. The button text turns dim and the suffix goes away. Start the backend again. The suffix comes back
   without a page refresh.
3. Click "Certification". A dialog opens with the machine's name in its title, "Reports to hand in", "7 reports to hand
   in" and one line per report. The Escape key, the cross and "Close" each close it.
4. Type a short note. Click "View report". You see the file name, its size and the whole file. Your note is in it.
5. Change one letter of the note. The file disappears. Click "View report" again to see it.
6. Click "Save file and open issue form". The machine asks where to save `certify-report-....md` (or the browser
   downloads it). Your browser opens the GitHub "Certify report" form. Close that tab WITHOUT submitting it.
7. Back in the dialog: a line says "Attach the saved file to the issue form...". Below it: "Issue form opened (Open the
   issue form again) · 7 reports" with "Not sent". The button suffix is gone.
8. Click "Not sent". That line goes away, the 7 reports are listed again, and the button reads "· 7 to file" again.
9. Quit the app. Start the backend with the environment variable `FREEMOCAP_CERTIFY_RELAY_URL` set to an empty value
   (PowerShell: `$env:FREEMOCAP_CERTIFY_RELAY_URL=''` before the start), then the app. Open the dialog, click "View
   report". There is no "Send report"; a line says "Sending is not set up in this build; use the issue form." and
   "Save file and open issue form" is the highlighted button. Quit and start normally again.
10. Start a quick check (F15 step 2 checklist, step 5). The button reads "Certification · quick check 1 of 5" (and so on).
    The dialog shows "Running check" with "Cancel check". The Record panel shows "A recording can start once the quick
    check ends. ..." Click "Cancel check" in the dialog: the check stops and both lines go away.
11. Only on a machine with a failed quick check: the result line "Quick check failed: ..." has "File report". Clicking it
    opens the dialog. The button reads "· 1 failure to file".
12. With the dialog open, restart the backend. The dialog recovers by itself; old answer lines are gone; the list is
    read again. All buttons keep their labels and are never greyed out.
13. REAL SEND (files a real public issue in `domisjustanumber/skellycertify`; do it once, last, only if you want that):
    with the normal relay address, open the dialog, click "View report", read the file, click "Send report". You see
    "Handed in as issue #N: <link>" and a line "Handed in as issue #N · 7 reports" with "Not sent". The button suffix
    is gone. Clicking the link opens the issue. ("Not sent" afterwards only marks the reports pending here; the issue
    stays on GitHub.)
14. freemocap's own reports (after any start check that ended, pass or fail; step 4 checklist): open the dialog. Each
    line under "Reports to hand in" starts with the package, "freemocap · ..." or "skellytracker · ...".
15. Click "View report". The file holds a freemocap module and the skellytracker modules together; a table appears only
    when a section (or, for a module with no sections, a check) has the result `fail`, with rows starting
    "| freemocap |" for a failed freemocap check; a file with all passes has no table.
16. Click "Save file and open issue form", close the GitHub tab WITHOUT submitting, then "Not sent". The freemocap line is
    listed again with the skellytracker lines (each package's store got the mark).

### F15 step 4: built

Backend and UI, 2026-11-19, on skellytracker `19b70775` (read-only). Commits: `9a0f83a9` (backend, routes, client contract,
golden) and `829c5c3f` (UI). Before it, `c366e0bf` used skellytracker
`19b70775`'s new interface: the quick-check child passes its `multiprocessing.Event` straight to `certify()` (the
`threading.Event` mirror is gone; the watcher still polls, never `wait()`s); the F4 refusal takes the refused GPU and the
reason code from `EpUnavailableError.device_key` / `.reason_code` (so a refusal with no device chosen now names the GPU and
carries its check facts); `certification.items[].reason_code` is now the GPU's `DeviceCheck.reason_code` (same shape;
`reason` stays the EP row's text), and the menu filter shows a pair that is usable or has a check-rule code.

What step 4 is, from decisions 9, 12 to 15, 17, 27 and "freemocap's own checks", with F13/G12 (no full-check controls):
- freemocap's own checks (now `freemocap/certification.py`; it was `freemocap/system/certify/own_checks.py`): `certify(level, progress, cancel, *, ui_remote=None)`
  and `certify_plan(level)` per skellycertify report format 1.1.0. Quick: `build-identity` (pass with SemVer and a 40-hex
  commit, else record-only with the evidence reasons), `spawn-child` (a `spawn` child answers and exits within 120 s;
  else fail with `crashed`/`timed-out`/`hung-at-exit` and every later check `not-run` `spawn-failed`), `bundle-imports`
  (numpy, cv2, pyarrow, av, scipy, numba if shipped, skellyforge, skellytracker, then onnxruntime, in that child;
  `numbers.failed` as `<module>-<ExceptionClass>`, `from_bundle` when frozen), `data-folder` (create, read, delete a file
  under the base data folder; `free_bytes`), `install-facts` (record-only: install dir writable, per-user install when
  frozen, space or non-ASCII in the install, data or home path, `ui_remote`), `blender` (record-only: found, and the
  version from `blender --version`). Full: the four full checks are `not-run` `not-built`. Reason codes are listed in
  the module docstring (format 5.4). The report has `id` (UUID4), no path (tested against privacy rule 1), and the host
  block from skellytracker's `probe_host()`; no GPU facts.
- The start check (`freemocap/system/certify/start_check.py`): runs in the quick-check job's spawn child: freemocap's
  `certify("quick")`, then skellytracker's `certify("quick")` with no EP named (every GPU EP with no reviewed row, the
  field-test ones included; their pass is the opt-in, decision 17). A module that raises is `error` with the class name;
  after a cancel skellytracker is `not-run` `cancelled`. A freemocap pass is written to
  `<base data folder>/certify/start-check.json` with the version set (freemocap, skellycam, skellytracker) and the OS key.
  `start_check_needed()`: no reviewed row (`REVIEWED_OS_ROWS`, empty; key `os_name, os_release, os_arch, build_family,
  freemocap` major.minor, `kind: full`) and no recorded pass for the current version set. Build family: the Windows
  build, the macOS major, the Linux `ID-VERSION_ID`. The rows are a Python constant, not the proposed YAML, so a frozen
  build needs no data file.
- Job and busy rule (`quick_check.py`): `QuickCheckManager.start(pair=None, ...)` starts the start check through the same
  admission lock, refusals and claims as a pair check (H1, H2), in both directions; `DELETE /certify/quick_check` cancels
  it. A start check's run has no `items` and a new `run.package` (the package whose checks run now). Refusal texts now say
  "The quick check of X on Y ..." or "The start check is running; ...", and the run facts carry null EP and device for a
  start check.
- Message (`certification`): `start_required` (bool: needed and no start check ended other than by a cancel in this server
  session; decision 14) and `start_results` (`[{package, result, reason}]`: each package's part by the section rule, a
  cancelled run `not-run`/`cancelled`, nothing to check `not-run`/`no-check`, a fail's reason is the first failed check's
  name; a crash of the whole child has no package). `last_result` (the EP quick check's) is not touched by a start check.
- Routes (Certification tag): `GET /freemocap/certify/start_check/plan` (`{packages: [{package, seconds_estimate,
  downloads, system_changes, checks}]}`, freemocap then skellytracker) and `POST /freemocap/certify/start_check` (202 with
  the run; 409 `pipelines-running` or `quick-check-running`). `ui_remote` comes from the request's client address.
  Contract: these paths and `PackagePlan`, `StartCheckPlan` in `openapi.json`, `operations.json`, `coverage.md`, the
  generated client; `start_required`, `start_results` and `run.package` in the Zod schema (optional).
- UI: `freemocap-ui/src/services/server/start-check.ts` (`START_CHECK_TEXT`, `planLines`, `startResultLines`, the two
  requests), `components/certification/StartCheckSection.tsx` (in the Certification dialog: the plan per package, "Run
  quick check", the server's refusal of this window's start, how each package's part ended; progress and "Cancel check"
  are the dialog's running check, now worded "Quick check of this machine (freemocap): 2 of 6 checks done ..."). While
  `start_required`: `AppContent` opens the dialog in required mode (no overlay, no cross, no Close, no Escape); the main
  panel and the sidebar sections are `inert` and dimmed (`BasePanelLayout.tsx`, `SidePanelContent.tsx`); the server
  connection, the log terminal and the Electron menu stay usable. When the check ends the dialog stays open (now
  closable) so its results show. Everything comes from the current server state; a restart without a recorded pass
  brings the box back.
- Real run on this machine: `certification.certify("quick")` in 1.7 s (warm): spawn-child, bundle-imports, data-folder
  pass; build-identity record-only with evidence `modified-tree` (BUILD_TREE_MODIFIED is None outside CI); `blender`
  found 5.2.3; module result pass. skellytracker's quick plan with no EP
  named lists `directml` on both GPUs (RTX 3070 and the Intel iGPU), up to about 90 s. The whole start check was not run
  for real (it would run DirectML checks and write this machine's EP store).
- Tests: `freemocap/tests/test_start_check.py` (12: the real quick level, cancel, spawn failure, data folder failure,
  full level, local pass and version change, reviewed row, the job in a real spawn child for pass / fail / cancel, the
  busy rule both ways, the routes); `test_quick_check.py` 24 (F4 case with no device added); golden test passes (the
  golden was regenerated on the combined tree with step 5's fields); `start-check.test.ts` (4); UI suite 220 tests, 219
  pass, 1 skipped; `tsc --noEmit` clean; client `npm test` 146 pass.
- Not covered: the rendered required mode (no browser tool, no DOM renderer); "File report" for a start-check failure
  (see open questions); the collapsed sidebar's icon buttons are not greyed.
- Open questions, with the recommendation used or proposed:
  1. A failed start check releases the UI for this server session only (decision 14), and only a pass is recorded
     (decision 13), so the box returns at the next start until a pass. Recommended: keep (literal reading); the
     alternative is to record any finished check.
  2. (Resolved by J13/J18, `8659b5d2`.) freemocap's own module report is kept only inside `start-check.json` (on a pass) and is not in the hand-in list;
     the hand-in reads skellytracker's store only. So a freemocap failure shows as a failure line but has no report to
     file. Recommended: freemocap keeps its module reports under `certify/reports/` with its own pending state, and the
     hand-in routes merge them with skellytracker's (one file per hand-in, decision 22). Needs a decision because it
     changes the hand-in routes.
  3. (Resolved: skellycertify `f89c711` lists freemocap.) skellycertify's report format lists only skellytracker and skellycam as packages (section 9); freemocap's module
     needs a row there (reason codes: the docstring of `freemocap/certification.py`). Recommended: ask the skellycertify session.
  4. skellycam's `certify()` is not built, so only freemocap's item gates the box. Recommended: add skellycam's item when
     it exists; no placeholder now.
  5. "skellyforge native parts": skellyforge has no compiled modules here, so the check imports `skellyforge`.
     Recommended: keep until it ships native code.
  6. `blender` uses freemocap's best-guess Blender path, not the path chosen in the Blender settings (the backend does
     not hold that). Recommended: keep (record-only).

#### MANUAL CHECKLIST (step 4)

The start check writes to this machine's EP store (DirectML results) and to `<data folder>/certify/start-check.json`.
To see the box again later, delete that file.

1. Start the app (backend from this checkout). The Certification dialog opens by itself with "Quick check of this
   machine" and the text "This machine has no checked result for this version of freemocap...". It has no cross and no
   Close button, and Escape does nothing.
2. The rest of the app is dimmed and does not react to clicks. The server connection panel at the top left, the log
   terminal at the bottom and the window menu still work.
   With the sidebar collapsed, its expand button is dimmed and does not react either (J17); the compact connection
   status stays usable. (Not unit tested: no test renders the layout.)
3. The dialog lists "freemocap: 6 checks, up to about 30 seconds" and a skellytracker line (on the dev machine: 2
   checks, up to about 90 seconds).
4. Click "Run quick check". The "Running check" part says "Quick check of this machine (freemocap): 1 of 6 checks
   done ..." and later "(skellytracker)". The button is never greyed out.
5. Click "Cancel check". The check stops; the dialog shows "freemocap: Quick check cancelled" (or freemocap passed and
   "skellytracker: Quick check cancelled") and, if freemocap had not passed yet, the app stays dimmed.
6. Click "Run quick check" again and let it end. The app is no longer dimmed. The dialog stays open with one line per
   package ("Quick check passed", or "Quick check failed: <check>" in red) and now has its cross and Close.
7. Close the dialog. Quit and restart the app. The dialog does not open by itself (the pass is recorded).
8. With the dialog closed, open it with "Certification": the "Quick check of this machine" part is there and can run
   again.
9. Busy rule: with cameras connected, click "Run quick check". A red line says "Quick check could not start: A quick
   check cannot start while other work runs: cameras ...". While a start check runs, connecting cameras or pressing
   Record is refused with "The start check is running; ...".
10. Restart the backend while the dialog shows a running check. The page recovers without a refresh; no old progress or
    red line stays.
11. After a start check where a package failed, its red line "<package>: Quick check failed: <check>" has "File report".
    Clicking it scrolls the dialog to "Reports to hand in", where that package's report is listed. The label never
    changes and the button is never greyed out.
12. After a passed start check, `<data folder>/certify/reports/` holds one `<uuid>.json` (a second pass replaces it, the
    older pass is pruned) and the button's suffix counts it ("· N to file").
13. Quit and restart the app: the same freemocap report is still listed (the list is read from the data folder).

### F15 step 5: built

Windows ML install and remove (F16), 2026-11-19, against `../skellytracker` at `19b70775` (dirty in tools only). Commits:
`f1e23b91` (backend, tests, client) and `711ec645` (UI). Built and tested with stand-ins, never run for real (a real run needs Windows 11 with an AMD GPU). No real install, download or remove ran on any machine; skellytracker's `install()` and `remove()` were replaced by
stand-ins in every test.

- Which EPs: an EP whose `PackStatus.source` is `windows-ml` (today `amdgpu` and `migraphx`, both field-test, Windows
  only), whose state is not `unsupported` (no GPU here can run it) and not `field_test` (a field-test EP with no opt-in;
  skellytracker says never offer it). Install is offered only for `not_installed`; Remove always (see open points).
  On the dev PC (RTX 3070) both Windows ML EPs are `unsupported`, so nothing shows there.
- Job (`freemocap/system/certify/ep_packs.py`, `EpPackManager`, made by `FreemocapApplication`): one install or remove
  at a time, in a daemon thread of the backend (not a child process: `install()` takes a progress callback and a cancel
  with `is_set()`, and both calls run Windows' own installer; it reuses the step-1 manager pattern, not its child).
  Install runs `eps.install(eps.plan_install([key]), progress=..., cancel=threading.Event)`; remove runs
  `eps.remove(execution_provider=key)` (no cancel exists for it). `refresh()` runs in the 0.5 s task collector before the
  check's refresh; when the job has ended it keeps how, frees the busy rule and has `QuickCheckManager` read
  skellytracker's status again at once (`status_changed()`), so `certification.items` follow; the UI queries
  `/onnx/execution_providers` again when `last_pack_result` changes. `shutdown()` (in `shutdown_all_processing()`) sets
  the cancel and waits up to 5 s.
- Busy rule (F16, H1, H2): the start runs under `QuickCheckManager.admission_lock`: `refuse_pipeline_start("ep-pack")`
  (a check runs: 409 `quick-check-running`; another install or remove: 409 `ep-pack-running`), then `pipeline_holds()`
  (anything runs: 409 `pipelines-running` with `gpu_held_by`); then it adds a claim `PipelineHold("ep-pack", <EP key>)`
  to `claims` until the job is reaped. So `pipeline_holds()` and `certification.gpu_held_by` list it (new `kind`
  `ep-pack`), a quick check is refused with `pipelines-running`, and every other start (realtime, recording, cameras,
  posthoc, sync, export) is refused in `refuse_pipeline_start` with 409 `ep-pack-running` {`execution_provider`,
  `message`}. Nothing is queued.
- Routes (`freemocap/api/http/certify/ep_pack_router.py`, tag Certification):
  `POST /freemocap/certify/ep_pack/install` and `POST /freemocap/certify/ep_pack/remove` with `{execution_provider}`
  answer 202 with the run `{action, execution_provider, phase, fraction}`, or 400 `not-windows-ml`, 409 `cannot-install`
  (install only: the state is not `not_installed`, or `plan_install` refuses, e.g. a field-test EP with no opt-in; the
  message is skellytracker's), 409 `pipelines-running`, `quick-check-running`, `ep-pack-running`;
  `DELETE /freemocap/certify/ep_pack` asks a running install to stop and answers `{run: <the run> | null}`. The EP route
  `/onnx/execution_providers` now carries skellytracker's `source` and `state` per EP. Contract: only these paths, the
  three schemas and the two fields were added to `contracts/openapi.json`, plus `operations.json`, `coverage.md` and the
  generated client.
- Message: two fields in `app_state.state.certification` (null values left out, as everywhere):
  `pack_run: {action: install | remove, execution_provider, phase, fraction}` (skellytracker's latest `InstallProgress`;
  `fraction` is Windows ML's 0 to 1, absent before its first value and for a remove) and
  `last_pack_result: {action, execution_provider, result, reason, message}` with `result` `done`, `cancelled`, `failed`
  (`reason`: skellytracker's error code of the install, e.g. `failed`, or the remove's reason codes joined, e.g.
  `no-record`, `package-not-removed`; `message`: skellytracker's install text) or `error` (`reason`: the exception class).
  A remove of a package that was on the machine before the install is `done` with `reason` `was-present`. Golden
  fixtures regenerated on both sides; the client Zod schema lists both fields.
- Honest end states, as skellytracker reports them (read from its code, not seen on hardware): a cancel before Windows
  starts changes nothing; a cancel during the install asks Windows ML to stop; if it stops, skellytracker keeps its
  `pending` record (the EP stays `not_installed`) and Remove takes away each package that the install added; if Windows
  finishes first, the install is recorded and the result is `done`. A failed install leaves the `pending` record too.
- UI (`freemocap-ui/src/components/mocap-setup/ep-pack-panel.tsx`, rules, texts and requests in
  `freemocap-ui/src/services/server/ep-packs.ts`): beside the EP setting (both places, under the quick-check panel),
  one line per shown EP, "<EP> (Windows ML): <state>", with "Install" (when not installed) and "Remove"; Remove asks
  first ("Remove <EP>? Windows removes the package that this app installed for it; a package that was on this machine
  before stays." with "Remove" / "Keep"); the running job "Installing <EP>: 25%" with "Cancel install" (or "Removing
  <EP>…"); a refused start "Install could not start: <server's reason>"; and how the last job ended. The buttons never
  change label or disable; a start answered after a newer one or by another server is ignored.
- Tests: `freemocap/tests/test_ep_packs.py` (10: progress, cancel, error, both busy directions, shutdown, result
  mapping of skellytracker's records, skellytracker's real `install()` with only `windows_ml.install` replaced, the
  message fields, the routes), `freemocap-ui/src/services/server/ep-packs.test.tsx` (3), the golden test; results: test_ep_packs 10 passed; the five backend files 75 passed; UI SDK integration 46 passed, `tsc` clean, client package 146 passed.
- Not covered: a real install, cancel or remove (Windows ML on an AMD GPU; none here); the panel's rendering and its
  local state (no store or React renderer in the UI's unit tests; the pure rules are tested); the live routes (a backend
  from this checkout started and its EP route gave `source` and `state`; calling the install routes was not done).

#### Open points (smallest option taken; recommendations)

1. Placement: beside the EP setting, not in the Certification dialog's Items part (decision 26), which step 3's dialog
   does not have yet. Recommend moving `EpPackPanel` into Items when it exists (it is self-contained).
2. Field-test EPs: both Windows ML EPs are field-test, so with no opt-in they show no controls (skellytracker refuses
   the install and says never offer them). Passing `field_test=True` would install, but the EP's state stays
   `field_test`, so the UI could not tell installed from not, and a second Install would record the package as
   `was_present`, after which Remove keeps it. Today the controls appear after the CLI opt-in. Recommend asking
   skellytracker for the install state of a field-test EP in `PackStatus` and for `install()` to keep its own record,
   then offering Install with `field_test=True`, the quick check staying the opt-in (decision 17).
3. Repair: Install is not offered for `stale` or `not_ready` (the same `was_present` overwrite). Recommend the same
   skellytracker change; until then Remove, then Install.
4. Remove is always offered for a shown EP, so a cancelled install's `pending` record can be cleared; with nothing
   installed by this app it says "Nothing to remove: no install of <EP> by this app is recorded". Recommend keep.
5. Texts (all in `EP_PACK_TEXT`, `packStateText`, `packProgressText`, `packResultText`): "<EP> installed", "Install
   of <EP> cancelled. Remove takes away anything it added.", "Install of <EP> failed: <skellytracker's text>", "<EP>
   removed", "<EP> removed from this app; its package was on this machine before and stays", "Remove of <EP> failed:
   <codes>", "<Install|Remove> of <EP> could not run: <class>". Recommend the user confirms them.
6. Pack EPs (`cuda`, `trt-rtx`, wheels from pypi/azure) get no install or remove here: F16 names Windows ML only.
   Recommend a separate decision.
7. A remove while the inference service still holds a session of the EP could fail with `package-not-removed`
   (shown as it comes); not seen.

#### MANUAL CHECKLIST (step 5)

You need Windows 11 with an AMD GPU (the Windows ML EPs today: AMD GPU and MIGraphX). Steps marked REAL change the
machine: Windows downloads, installs or removes a package for your user.

1. REAL. Opt in and install once with skellytracker's tool: `skellytracker-eps install amdgpu --field-test` (answer
   yes). Without this the app shows no controls for a field-test EP (open point 2).
2. Start the app. Open "Processing settings". Under the EP setting you see "AMD GPU (Windows ML): installed" with a
   "Remove" button.
3. Start real-time processing. Click "Remove". A box asks "Remove AMD GPU? ..." with "Remove" and "Keep". Click
   "Remove". A red line says "Remove could not start: ..." (the processing runs). Stop the processing.
4. REAL. Click "Remove", then "Remove" in the box. A line says "Removing AMD GPU…", then "AMD GPU removed" (or "AMD GPU
   removed from this app; its package was on this machine before and stays" if it was there before step 1). The line
   above now says "not installed" and shows "Install".
5. REAL (downloads). Click "Install". A line says "Installing AMD GPU: starting", then a percentage, with "Cancel
   install". While it runs, press "Real-time processing": the error banner says an install or remove is running. When
   it ends: "AMD GPU installed", and the EP menu lists AMD GPU again (with its check marker).
6. REAL. Remove it again (step 4), then click "Install" and at once "Cancel install". You see "Install of AMD GPU
   cancelled. Remove takes away anything it added." (or "AMD GPU installed" if Windows finished first). Click "Remove"
   and confirm: it removes what the cancelled install added, or says "Nothing to remove: ...".
7. Start a quick check of another EP, then click "Install" or "Remove": "... could not start: A quick check of ... is
   running ...".
8. REAL. Start an install, then quit and restart the backend. The page recovers without a refresh; no old progress
   stays; the AMD GPU line shows the state skellytracker reports (an install stopped by the exit stays "not
   installed"; "Remove" clears what it added).
9. The "Install", "Remove", "Keep" and "Cancel install" labels never change and are never greyed out.

### freemocap's own module and reports: built

2026-11-19, decisions J13, J18, J19 (skellycertify main `f89c711` lists freemocap as a package). Commits: `f2909099`
(the module), `8659b5d2` (its reports and the merged hand-in).

- The module: `freemocap/certification.py` (moved with `git mv` from `freemocap/system/certify/own_checks.py`, check names
  unchanged) holds `certify`, `certify_plan` and the reason codes (its module docstring, "freemocap's reason codes", report
  format 5.4). `freemocap.certify` and `freemocap.certify_plan` are exported lazily by a module `__getattr__` in
  `freemocap/__init__.py`; `import freemocap` does not import `freemocap.certification` (tested in a fresh interpreter).
  `freemocap/system/certify/` keeps only the app role: the start check, the quick-check job, the file and the hand-in.
- Level `full` stays callable; its checks are `not-run` `not-built` and its report carries `partial-run` and is not valid
  (format 7.1 statement 4). `certify_plan(level, *, ui_remote=None, blender_exe_path=None)` takes `certify`'s options
  (format 2.2); neither changes the plan.
- The store, in the data folder: `certify()` keeps each report with a `pass` or `fail` check as
  `<base data folder>/certify/reports/<id>.json` and the hand-in states in `<base data folder>/certify/hand-in.json`, with
  skellytracker's function shapes and rules: `pending_reports(include_handed_in=False)`, `read_report(id)`,
  `mark_reports(ids, state, *, reference=None)` (states `pending`, `opened`, `covered`; "Not sent" = `pending`, which
  clears the reference; an unknown state or id, or a reference with `pending`, raises `ValueError` and changes nothing),
  and pruning of each older quick pass whose passed checks newer passes repeat (failures, handed-in reports and `full`
  reports stay). Ids are v4 UUIDs, matched only as safe file names, never parsed. A run with no pass or fail (cancelled,
  `full`) is not kept. A data folder that cannot be written logs a warning; `certify()` still returns the report.
- The merge (`freemocap/system/certify/relay.py`): `hand_in_reports()` joins freemocap's and skellytracker's
  `pending_reports()` rows, each with `package`, the oldest first; `report_file_for` reads each id from the store that holds
  it (freemocap's, then skellytracker's), so one file holds modules of both packages, each unchanged (top-level schema rule
  as before: 1.1.0 once any module has an `id`). Every mark (send's 200, the outbox retry's 200, "opened", "Not sent") groups
  the ids by store and calls that store's `mark_reports`; an id no store holds is `unknown-report` before anything changes.
- Message and API: `certification.pending_reports` now holds freemocap's reports too, with its existing fields (no message
  model, golden or Zod change: the UI takes the package from the hand-in list). `GET /freemocap/certify/hand_in` rows gain a
  required `package`; `openapi.json` and `schema.ts` refreshed; no operation added, so `operations.json`/`coverage.md`
  unchanged.
- UI: the dialog's report lines start with the package (`pendingRows`); a failed package line of the start-check result
  (freemocap's, and skellytracker's, whose report is in its store too) has "File report", which fires `open-certification`
  and scrolls to "Reports to hand in" (`REPORTS_SECTION_ID`).
- Until a freemocap build's commit is on a pushed branch of freemocap's public repository (format 9:
  `domisjustanumber/freemocap`), the reviewer treats its module as a record only (`commit-not-public`). Pushing is the
  user's decision; the note is also in `freemocap/certification.py`'s docstring.
- Tests: `test_start_check.py` (the store's states, not-sent, refused marks, pruning, one pass replacing the one before, an
  unwritable data folder, the lazy import, `partial-run`, `certify_plan` options), `test_certify_relay.py` (the merged list
  and file with two packages, the outbox retry's 200 and "Not sent"/"opened" reaching each store, the route's `package`;
  fake relay only), `test_certify_report_file.py` (freemocap's real `certify()` quick and full, with stand-ins for the
  spawn child and Blender, in one file with two skellytracker modules, through the Python privacy rules and the relay's
  own validator in node). Suite: 1707 passed, 7 failed (exactly the known baseline), 20 skipped, relay URL empty; skellytracker at 8b9caace.
- Not verified: a real start check (it writes this machine's EP store), the rendered dialog and the scroll (no DOM test
  renderer), a real relay send of a two-package file.
- Open points (smallest option taken):
  1. skellycertify's section 9 still names `freemocap.system.certify.own_checks.certify` and the docstring of
     `own_checks.py`; it should say `freemocap.certify` / `freemocap.certify_plan` and the docstring of
     `freemocap/certification.py`. It also lists only `ui_remote`; freemocap also takes `blender_exe_path` (J16).
     Recommended: ask the skellycertify session to update the row.
  2. The store lock is per process: the start check's child prunes while the server may mark. Only an older pass that a
     newer pass repeats can be pruned in that window. Recommended: keep (`shortcut:` comment in the code).
  3. "File report" also shows for a failed skellytracker part of the start check (its report is in its store). Recommended:
     keep.
  4. A freemocap pass is still also copied into `start-check.json` (the start check's record); the store keeps its own copy.
     Recommended: keep; they serve different rules (decision 13 against the hand-in).

### Playwright pass, 2026-11-19: defects fixed

A browser-only pass (Vite dev server, backend from this checkout, relay URL empty, telemetry off, no cameras) found four
defects in the certification UI; each is fixed and was seen rendered in the same setup afterwards.

1. The Certification button did not dim while disconnected: `.button.quaternary>p` sets the text colour, so its colour
   classes had no effect (and `text-gray` and `text-darkgray` are the same colour). Fix: the button is dimmed by opacity
   0.5 while disconnected, as the layout dims the required mode; the dead colour logic is gone. Other quaternary buttons are
   unchanged. `36404d81` (`CertificationDialog.tsx`).
2. The button (top right of the strip) was covered by the real-time toolbar ("Real-time processing", "Processing
   settings") and by Playback's grid button. Fix: it sits right after the Streaming and Playback tabs (one absolutely
   placed flex row holds both; `MainNavTabs` lost its own placement). Measured, banner gone, default sidebar: no overlap at
   1440, 1280, 1100 and 1024 px wide, on Streaming and Playback; at 1024 the button's right edge meets the toolbar's.
   `64ab6272` (`CertificationDialog.tsx`, `MainNavTabs.tsx`, `BasePanelLayout.tsx`). The step 3 checklist item 1 now says
   where it is.
3. A refusal named the EP and GPU by keys ("The quick check of directml on gpu:10de:2484:0 is already running."). Fix:
   `quick_check._what` takes the labels and device names of the cached `certification.items` (skellytracker's status),
   falling back to the keys; used by the busy refusal of every start, the refusal of a second check, and the router's
   `cannot-run` text; no longer `str.capitalize()`, which lowercased the labels. The refusal of a second check now reads like
   its siblings: "<The check> is running; the quick check start was refused. Start again when the check ends." So the step
   4 checklist item 9 ("The start check is running; ...") was already right and the text changed, not the checklist; the
   step 2 checklist item 13 now quotes the labelled form. `72feaa17` (`quick_check.py`, `quick_check_router.py`, test).
4. After a start check ended, the quick-check panel kept its refusal, and a result the person had moved on from came back
   (with a red border). Root cause: `useQuickCheck` cleared `dismissed` on any `certification.run`, also a start check's,
   which leaves `last_result` as it was; and the refusal outlived the run that caused it. Fix, once in the shared rule
   `settleQuickCheckLines` (`execution-providers.ts`): `dismissed` clears only when an EP quick check runs (`run.items`
   not empty); a refusal goes once the server has shown work running (`run` or `gpu_held_by`) and then none. A result line
   uses the bordered layout only when it fails (it then has "File report"), else a plain note. `92f9c4da`
   (`execution-providers.ts` with its test, `useQuickCheck.ts`, `quick-check-panel.tsx`).

Tests: UI unit suite (`node tools/test-sdk-integration.mjs`) 221 tests, 220 pass, 1 skipped, plus its 10 and 46;
`tsc --noEmit` clean; `test_quick_check.py`, `test_start_check.py`, `test_ep_packs.py` and
`test_no_execution_provider_knowledge.py` 54 pass; fast suite 1708 passed, 7 failed (exactly the known baseline), 20
skipped, relay URL empty; `check-ui-styles` 30 errors, none in the changed files.

Still unverified: Electron (only the browser build was seen); at 800 px (the window minimum) the real-time toolbar
already covers the tabs and now covers the Certification button too, so nothing fits in one row there; with the camera
error banner shown the real-time toolbar is under the banner (as before). Seen and not fixed: the button still showed its suffix
1.5 s after a disconnect (checklist step 3 item 2 says it goes away; not watched longer); the start-check refusal in
`StartCheckSection.tsx` also stays after the work ends; every other bordered quick-check note (running check, prompt,
offer) keeps the red border of `.settings-note-dismissable`; the EP pack refusals still name the EP by its key.

### Certify pop-up revision, 2026-11-20 (owner's notes)

The owner's notes, verbatim:

> Title: "Certify FreeMoCap on this system"
>
> Sub-title: "FreeMoCap has not run on this type of system before, so we need to run a check to confirm things work
> before launching."
>
> Content: "We'd love your help to know this is a good configuration for FreeMoCap to run on in the future, if you'd
> like to submit your anonymous certification report click the Submit Report button below. If you want to see what
> we'll get before it sends, click the View report button first."
>
> Notes: "Close button turns into a Continue button when complete. Buttons must look like buttons, not just text. The
> UI needs to not bounce around as much when tests are running, there needs to be a clear table of tests that need to
> run and status, and a moving icon to show things haven't frozen, are still happening."

A later ruling of the owner: show the "Full benchmark" paragraph with its button greyed out (text tidied: "If you have
the time (approx 5 to 10 mins), we'd really appreciate the results from a full benchmark run on your system. Click
the "Full benchmark" button to run that now.").

Built (UI only; no Python or message-contract change, the owner's backend kept running):

- Title "Certify FreeMoCap on this system", the host name as a small second line. Sub-title: the owner's sentence
  while `start_required`, else the describing sentence ("freemocap's own checks and every GPU execution provider that
  has no reviewed result on this system.").
- A table of the start check, one row per package (freemocap, skellytracker: from the plan route, the two names
  before it answers), columns package, what it checks (the plan line; the check names as the row's tooltip) and status:
  Waiting, Starting / "Running, N of M" with the turning `loader-icon` (stopped under `prefers-reduced-motion`),
  Done, Passed, "Failed: reason" with "File report", Cancelled, "Not run: reason", "Nothing to check", and "Not run in
  this session" when nothing is required. The rule is `startCheckRowStatus` in `start-check.ts`, tested.
  Per-package rows, because the snapshot carries only package-level progress (`run.package`, `done`, `total`) and
  per-package results (`start_results`). Per-check rows would need the server to send, per package, each check's
  name and state (waiting, running, passed, failed with reason) in the `certification` snapshot, e.g. a `checks` list
  in `run` and in each `start_results` row.
- No jumping: fixed 560 px width, the table's rows present from the start, one reserved line block (3 lines) for the
  progress and the refusal, "Run quick check" and "Cancel check" in a fixed row (Cancel hidden with its space kept
  while nothing runs; neither changes label). Measured in the browser build: dialog 560x720 and table 96 px high in
  every sample while waiting, running and done.
- Buttons: `ButtonSm` everywhere, filled `primary accent` for the main action, `secondary` (outlined) for the rest.
- Bottom button: none while required; "Continue" (filled) once a start check of this server session ended without a
  cancel (as the server releases the app), else "Close" (`bottomButtonLabel`, tested). It stays in sight (sticky) while
  the dialog scrolls.
- Reports: the owner's paragraph, the pending list and note, "Submit Report" and "View report", the privacy line.
  "Submit Report" sends the viewed file, or builds it first and sends it; with the relay off or a file too large it
  shows the file and the existing issue-form fallback. The old "Send report" is gone; there is one send action. All
  hand-in rules (marks, "Not sent", retries, refusal texts) unchanged.
- Full benchmark: the paragraph and a disabled "Full benchmark" button (tooltip "Not available yet"); no route.
- "system" for the computer in this dialog's texts only.

Awaiting the owner's confirmation: the host name kept as a second line under the title; the describing sentence as the
sub-title when nothing is required; "Submit Report" without a prior view; "system" only in this dialog for now (the
owner ruled "system everywhere" for the whole app, to be done after the demo); the "5 to 10 mins" figure (316 s
measured on the dev PC, plan estimate about 8 minutes); "Continue" also shown when the dialog is reopened later in the
same server session after a start check.

Not done: per-check rows (needs the server change above); the full benchmark itself; Electron not seen (browser build
only, scratch backend, relay URL empty, sends blocked); the restart-recovery of the new controls was not exercised in
one page (the plan and refusal keep their server-identity keys as before).

Commits: `73c87235`, `ded74c33`, `1087a6f7`, `826936fa`, `6500ff6a`. Tests: `tsc --noEmit` clean; UI unit suite 223
tests, 0 failures, plus its 10 and 46; `check-ui-styles` 30 errors (unchanged, none in the changed files).

#### Second round, 2026-11-20 (owner's notes after seeing the revision live)

The owner's words, verbatim:

> "Drop the hostname from the popup"
>
> "Quick check of this system must say 'Quick system checks to run:'"
>
> "Run quick check must say 'Start now' and the gap between the table and the button must be tightened up"
>
> "Reports to hand in sounds like school work, the tone must be more certifying hardware to help freemocap"
> (with the replacements below)
>
> "When clicking View report, the UI goes blurry (zoom/scale issue?). Instead it must open the report in another
> pop-up window."
>
> "The View report window must pop-up and show the summary view as described to skellycertify - the human-readable
> summary at the top, with the json below. This must be in a .md reader so it formats nicely for reading."
>
> "Drop 'Click the "Full benchmark" button to run that now'"

Built (UI only):

- The host name line is gone; the section heading is "Quick system checks to run:"; the start button says "Start now"
  in this dialog only (the EP setting's "Run quick check" elsewhere is unchanged). The reserved 3-line block for the
  progress and a refusal moved below the button row, so the buttons sit right under the table and nothing above them
  moves.
- "Submit Report" / "Submit Reports" follows the server's pending count (`submitLabel`, tested).
- "View report" opens a second pop-up over the dialog (same modal look, its own Close, Escape closes only it, focus
  returns to "View report"; checked in the browser build). It shows the file name and size as a small line and the
  exact file the server returned, read as Markdown: the summary on top, then "Data" with the JSON in a monospace block
  with its own scroll (35vh), pop-up up to 800 px wide. The first dialog no longer shows the file inline. Submit's
  fallback (sending off, too large) opens the same pop-up with "Save file and open issue form".
- The Markdown reader is in-house (`services/server/report-markdown.ts`, tested; `ReportMarkdown.tsx`): `#`/`##`
  headings, paragraphs (one line per line), `- ` lists, `> ` quotes, pipe tables with `\|`, one fenced block of any
  fence length, inline `**bold**` and backtick code; React elements only, no HTML interpreted. `marked` is in
  node_modules only as a transitive dependency, so it was not used. Checked with the current file and with
  skellycertify's `plans/sample-report-2-app-with-failures.md` (fed to the pop-up in the browser only).
- The Full benchmark paragraph ends after "...a full benchmark run on your system."
- The blur: not reproduced. The dialogs no longer centre with `translate(-50%, -50%)` (the settings-modal rule, which
  can put text on half pixels in a composited layer); a fixed flex layer centres them instead. At device scale 1.25
  the old centring gave whole device pixels at the measured height (720 px, 80vh of 900), so the cause is likely but
  not proven.

Text changes of this dialog (old -> new), the owner's ones first, then the coordinator's additions awaiting the
owner's confirmation:

| Old | New | By |
|---|---|---|
| Quick check of this system | Quick system checks to run: | owner |
| Run quick check (this dialog) | Start now | owner |
| Reports to hand in | Help FreeMoCap by sharing your (anonymous) results | owner |
| N reports to hand in[, F with a failure] | Share N reports with FreeMoCap[, F with a failure] (Share 1 report ...) | owner |
| Note (optional) | Anything you'd like to tell us? | owner |
| Submit Report | Submit Report / Submit Reports (count from the server) | owner |
| ...Click the "Full benchmark" button to run that now. | (dropped) | owner |
| No reports to hand in. | Nothing to share right now. | awaiting |
| Handed in as issue #N | Shared as issue #N | awaiting |
| Already handed in as issue #N | Already shared as issue #N | awaiting |
| Not handed in: ... Use the issue form. | Not shared: ... Use the issue form. | awaiting |
| Not handed in yet: ... | Not shared yet: ... | awaiting |
| Could not record the hand-in: | Could not record that the report was shared: | awaiting |

Unchanged: "File report", "Not sent", "Issue form opened", route names and code identifiers.

The 1.2.0 writer (hardware lines, EP table, camera line) is being built by a separate change on 2026-11-20; the
reader already shows that layout.

#### Third round, 2026-11-20 (owner's notes while watching)

The owner's words, verbatim:

> "At the bottom of the view report, the buttons must be submit (or save file and open issue form if the relay is
> down) and close. Close on the left, submit on the right, in blue"
>
> "reports must not populate in the main pop-up until the checks have completed."
>
> "Reduce the gap between the Start now button and the Help FreeMoCap heading."
>
> "Submit Reports should be Submit reports (no capital R for second word to match other buttons)."
>
> 'run a check must be "run some checks"'
>
> 'When clicking Submit reports, the button must change to "Submitting..." dim and the same circle animation must show
> to things are happening. When it's done, the button briefly changes to "Sent!" then the pop-up closes and the app
> opens.'

Built:

- The report pop-up has a sticky footer: "Close" at the left, and at the right "Submit report(s)" while the relay can
  take the file, else "Save file and open issue form" (relay off, too large, or a send answer that offers the issue
  form): `reportFooterAction`, tested. A reserved line above the footer shows the send answer or why the issue form
  is offered. The right button is filled with the existing primary fill, `--color-primary-fill` =
  `--color-info-strong` = `--blue-600` (the logo's teal, which `color.css` calls "Blue Shades"); the first dialog's
  Submit already used the same `primary accent` classes. The pop-up stays open after a send, showing the last viewed
  file and the answer line, until "Close" (coordinator's choice); with nothing pending the right button goes.
- The sharing section shows "Your results appear here when the checks are done." (coordinator's wording, awaiting the
  owner) while a check runs or the required start check has not ended; then the list, note and buttons
  (`reportsReady`, tested, from `start_required`, `run`, `start_results`).
- No reserved block between "Start now" and the sharing heading: a refusal (or an EP pair check's progress) is one
  truncated line beside the buttons with its full text as a tooltip; the start check's progress is in the table's
  status cells. The main dialog has a fixed height (80vh) so it does not move while the checks run; empty space is at
  its bottom.
- Labels "Submit report" / "Submit reports"; the owner's paragraph says "click the Submit report button below".
- Sub-title: "...so we need to run some checks to confirm things work before launching." ("run a check" appears in no
  other text of this dialog).
- "Submitting..." / "Sent!" (built and checked with the send route stubbed in Playwright): while this window's send is
  in flight the button (main pop-up and report footer alike) says "Submitting...", dimmed, disabled, `aria-busy`, with
  the turning `loader-icon` (still under reduced motion); on success "Sent!" for 1.5 s (coordinator's figure), then
  both pop-ups close. A refusal or failure returns the button at once with the answer line; the existing rules choose
  the issue-form fallback. The phase is held per server identity, so a reconnect clears it; the timer is cleared on
  unmount. `submitText`, tested.
- The owner's addition, verbatim: "and a web browser is launched with the issue page it just created". On a
  successful send the issue address from the server's answer opens with `window.open`, the mechanism the issue form
  already uses; only a skellycertify issue address on github.com passes `safeIssueUrl`. It is opened once per send
  answer of this window, never from a re-shown state. Not checked in Electron.

- The owner, verbatim: "include the line about helping FreeMoCap to the view report pop-up so it's clear what the
  submit button actually does". Above the footer of the report pop-up: the sharing heading, then one sentence for
  the right-hand button (coordinator's wording, awaiting the owner): "Submit report(s) sends this report to the
  FreeMoCap team as a public issue on GitHub." or "Save file and open issue form saves this report and opens the
  GitHub form to attach it to." (`footerActionText`, tested).
- The owner, verbatim: "why does the popup have a bunch of black space at the bottom?" The fixed 80vh height is gone:
  the main pop-up fits its content (max 80vh, scrolling inside) and is anchored 10vh from the top instead of centred,
  so the one height step when the checks end grows it downward. Measured at scale 1.25: top 90 px (900 px window) and
  108 px (1080 px), height 494 px while waiting and running, 720 / 774 px once complete and when opened later. Scale 1
  was not measured.

- The owner, verbatim: 'on the view report window the button must say "Send report and open FreeMoCap" the Close
  button must say "Do no send and open FreeMoCap". Then the send button changes to "Sending..." The spinning icon is
  on a black box that rotates, it needs to be transparent.' Built: the box was `.accent > .icon`'s fill
  (`--color-on-primary`) behind the loader, which is an image, not a mask; `.accent > .loader-icon` is now
  transparent. Footer: "Do not send and open FreeMoCap" (read as "not"; awaiting the owner) closes both pop-ups;
  "Send report(s) and open FreeMoCap" (plural by the Submit rule; awaiting the owner); the fallback keeps "Save file
  and open issue form". In flight both send buttons say "Sending..." (the main pop-up too; awaiting the owner). The
  helping sentence names the new label. `sendAndOpenLabel`, `submitText`, tested.

- The owner, verbatim (demo, Electron, fresh reset): "the certify popup is not blocking the initial screen - you can
  still click start cameras and they still start even with the pop-up showing". Built: while `required`, the
  dialog's full-window layer takes every pointer event and dims the app (rgba(0,0,0,0.5)), covering the connection
  panel and log terminal too (coordinator's reading, awaiting the owner; it replaces decision 14's exception for
  pointer input). Opened later, the dismiss layer now sits at z-index 999 above the app, so a click beside the dialog
  only closes it. The `inert` wrappers stay. Cause not reproduced: in the browser build with `start_required` true
  every camera, recording, real-time, tab and Certification control was inside an `inert` wrapper and no pointer hit
  reached any of them; Tab reaches only the connection panel and log terminal controls. Most likely the owner's
  window showed the dialog while the server's `start_required` was false (the dialog stays open after it turns false),
  which removes `inert` and, by design, this layer too; not verified in Electron. The server refuses a camera start
  only while a check runs (`refuse_pipeline_start`), not while `start_required` is true: to be fixed after the demo.

Commits: see `git log` for 2026-11-20 10:30 to 10:52.

#### Second round commits

Commits: `67b10d8d`, `87217f49`, and the fallback fix after it. Tests: `tsc --noEmit` clean; UI unit suite 226 tests, 0
failures, plus its 10 and 46; `check-ui-styles` 30 errors (unchanged).

## Environment on the dev PC

Found 2026-11-19 while measuring decision 31; nothing was changed. `freemocap/.venv` dates from August 2026
(non-editable skellycam `main@777b058`, skellytracker 2024.9.1019, no `platformdirs`), `../skellycam` is on
`dom/research` (`close_camera_groups` exists only on upstream `sfn26`), and `../freemocap_blender_addon` is not
cloned, so `uv lock --check` fails. benchmarks/README.md forbids changing shared environments or setting
PYTHONPATH, so the shutdown time stays unmeasured until the workspace is set up.

Changed 2026-11-19 on the user's order ("set up all 3 envs, run tests, fix what's needed"): the missing
siblings are cloned (`../freemocap_blender_addon` `sfn26`, `../utils/skellylogs`, `../utils/skellypings`),
`freemocap/.venv` is rebuilt on Python 3.13.18 from the regenerated lock, and `../skellyforge` (931 tests
pass, 1 skip) and `../skellysync` (59 pass) have their own environments. Decisions of that day's grilling:
- skellytracker pin: the user waived the macOS CI pass ("use the certify process to validate on a real mac");
  pin `4dcf2a66` (pushed fork commit with the hand-in list) after the fast suite reruns against it.
- skellycam: a stopgap worktree `../skellycam-sfn26-pins` (branch `dom/sfn26-pins` from `upstream/sfn26`
  `29eca818`, exact pins, no Rust: the user said to drop the Rust backend there after the crate would not
  link without the Windows SDK). That repo's rules: no AI attribution in commits, no push. freemocap moves
  to skellycam's frame-ring API after its phase 4 and rewrites its camera code once, then.
- Sibling sources stay local paths, and nothing is pushed (user, 2026-11-19, after the app started again):
  the skellycam stopgap stays local, so CI stays unbuildable until freemocap moves to the frame-ring API; the
  skellyforge and skellysync branches stay local too.
- Open design tension for decision 16 (found when the per-GPU menu filter was built): the menu now hides an
  uncertified, unchecked EP and GPU, but decision 16 shows it with an icon and offers the quick check when it
  is chosen. Settle with the user when decision 16 is built. Also found: the committed `openapi.json` is
  behind the app's routes in 7 schemas, and `../skellytracker` moved to local `669d9676` (after the pin),
  where `PackStatus.usable`, `.devices` and `check_start()` already obey the per-GPU check rule (ADR-ER5X).
- macOS 15 is the minimum supported macOS: the only macOS wheels of opencv-contrib-python 5.1.0.95 are
  `macosx_15_0` (arm64 and x86_64; read from PyPI).
- After the app imports: re-measure the ChArUco corner counts and the seeded numerical calibration on
  OpenCV 5.1.0.95 against the 5.0.0.93 figures of the migration plan (5.1 changed ArUco refinement and
  `warpAffine`/`remap` rounding); tell skellytracker-6c if they move.
  DONE 2026-11-19 (test_data, cpu fp32, numerical profile, 3 identical repetitions; result files in
  `%TEMP%mcal`): ChArUco corners 664 / 617 / 1089 bit-identical; seeded calibration error 0.314339 ->
  0.314726 px (not OpenCV: the solver's cv2 calls served from 5.0.0.93 give the same; numpy 2.4.6 -> 2.5.5
  suspected, untested); kept 2D points 97,425 -> 97,463 (RTMW part +38), caused by 5.1's `warpAffine` (only
  that function from 5.0.0.93 restores 97,425); alignment still foot_support; all numeric gates pass (error
  < 1.0 px, 666 observations, 0 rejected). The `reference-posthoc` check must use 97,463 / 0.314726 /
  foot_support, or a shipped tolerance that admits these shifts. skellytracker-6c is told.
- Done: CI installs Python from `.python-version` (`17c865d8`); `numpydantic` removed from freemocap's list
  (`2eb341f4`); skellyforge's beartype comment corrected (numpy >= 2.5 needs `beartype>=0.23`, no test
  notices otherwise); skellysync's librosa constraints recorded in its pyproject.
- Known, left alone: librosa stays 0.10.1 in skellysync (held up by `setuptools==75.8.0` and numpy <= 2.5;
  its one use is a WAV read that soundfile could do); skellysync's synced videos lose inherited Windows
  permissions (temp folder ACL since Python 3.12.4; the user fixes it later); freemocap lists `numba` but
  imports it nowhere; the ONNX Runtime import warning "Init provider bridge failed" is normal for the
  Windows ML build (skellytracker ADR-N6E8), and `get_available_providers()` never lists the plugin packs.
- Open: the wider dependency bumps, evaluated on branch `dom/dependency-bumps` (worktree
  `../freemocap-dep-bumps`); nothing of it is merged.

## Waiting on the user

- Done 2026-11-19 (user confirmed the address in this session): the relay is deployed at
  `https://skellycertify-relay.dom-dd0.workers.dev`, the value of the R5 constant. Per skellytracker-6c (from a
  skellycertify session; not checked here): test mode is OFF, so an accepted report files a real issue; test
  only with `GET /health` or a refused-format sample unless the user approves; the address may still change.
- Which skellycam freemocap builds against. `../skellycam-native-jpeg` (`dom/native-jpeg`, the new pins) lacks
  the `upstream/sfn26` camera-group API this branch imports (`close_camera_groups`, `camera_errors`,
  `rust_camera_group`, `camera_backend_manager`, `ipc.shared_memory`, `ImagePayloadFrame`); the branches split
  at `6b9ebe171`. With it the lock resolves (`5ad9efd6`, `baef6d20`) but `freemocap.app.app` fails to import and
  36 test files do not collect (fast suite 1359 passed, 13 failed: 7 baseline, 6 from the same imports; no
  failure from the new versions among what ran). `../skellycam` (`dom/research`) pins OpenCV 4.12.

## Waiting on skellytracker

State 2026-11-19 evening (skellytracker-6c's message; the commits are on disk in `../skellytracker`, local,
not pushed: `669d9676`, `544521ed`, `cada7f91`, `5020037f` on top of the pin `4dcf2a66`; not read here yet).
Nothing below is still missing except a package-wide `certify()` / `certify_plan()` confirmation and the push.

- Pin: done at `4dcf2a66` (decision 1); it moves forward when these four commits are pushed.
- Package-wide `certify()` and `certify_plan()` with the quick level: `certify()` exists (reports come from
  it); confirm the exact signature and `certify_plan` against the code before the certify integration.
- Check rule, enforced in the package (ADR-ER5X): `eps.check_start()` and `eps.build_session()` raise
  `EpUnavailableError` ("Run `skellytracker-eps certify KEY --quick`.") for an EP on a GPU with no reviewed
  row and no local pass, and after a local failure. No override. `certify()` always gets through.
  `PackStatus.usable` and `.devices` obey the rule; `reason_code` is `quick-check-needed` or
  `quick-check-failed`; `install_hint` holds the command. `eps.recommend()` names only an EP that can start
  now; a skipped candidate has `needs_check: true` or `failed_locally: true`; a fresh PC gets cpu.
- `skellytracker.note_exit_requested()`: built. Call it in the process that runs the pipelines when the user
  asks the app to close, before ending that process. Without it an end with no clean interpreter exit while
  a GPU EP session was held counts as one unclean exit; two in a row give `local_result "failed"` with
  `DeviceCheck.local_cause == "unclean-exits"` (say "exited uncleanly twice", not "the check failed"). A
  clean exit resets the count; a passed quick check clears the mark. `local_cause` is the new last field.
- CoreML: check name `coreml` (no `@device`), in the default quick selection; its one `DeviceCheck` has a
  chip id as `device_key` (for example `chip:apple-m2-pro`), which must not be passed as `device`. Fake Mac only.
- Reports: a new quick report deletes each older plain-pass report it repeats that was not handed in.
- Windows ML catalog: `eps.install(eps.plan_install([key]), progress=..., cancel=...)` with
  `InstallProgress.fraction` (0 to 1 or None, no bytes); `eps.remove(execution_provider=key)` gives
  `RemoveResult(removed, failed, was_present)`. Real download and cancel are not verified on hardware.
- PyInstaller: skellytracker ships `hook-onnxruntime.py` (the installed ORT's libraries, data and metadata,
  and windowsml on Windows; no GPU EP). Frozen on Windows only. beartype's checks are inactive when frozen.
- `pending_reports()` and `mark_reports()`: built 2026-11-19 (skellytracker-6c; one local commit on top of
  `e7ce3409`, not pushed, not read here). `skellytracker.pending_reports(include_handed_in=False)` gives rows
  `{report_id, kind, created_utc, has_failure, evidence_valid, state, reference}`, oldest first; with
  `include_handed_in=True` every state, so a "sent" line survives a restart. `read_report(report_id)` gives
  the module report as `certify()` returned it. `mark_reports` as in decision 24; `ValueError` with nothing
  changed also for a plain string in place of the list and for a reference with "pending". A report is
  listed only when a check ended pass or fail; `has_failure` is the "always offer a failure report" case;
  `report_id` is opaque; state is in `hand-in.json` in the EP store root; skellytracker never sends and never
  builds the Markdown file (freemocap builds it from `read_report()`); reports are never deleted.

## Handoff note, 2026-11-19 late evening (read this first after a compaction)

> 2026-11-20: the order of work and the newest rulings are in "Decisions of the fifth grilling, 2026-11-20"; read that section first.

The coordinating session works through sub-agents (opus/sonnet/haiku, never fable unless the user names it).
All work is local commits on `sidecar-implementation`; nothing is pushed; CI stays unbuildable until the
frame-ring move. Sub-agents stage by explicit path because several edit this checkout at once.

Running / built (update 2026-11-19 night): steps 1 to 5 of F15 are built: [F15 step 1: built](#f15-step-1-built),
[F15 step 2: built](#f15-step-2-built), [F15 step 3: built](#f15-step-3-built), [F15 step 4: built](#f15-step-4-built),
[F15 step 5: built](#f15-step-5-built). Open: the user's manual checklists (steps 2, 3, 4, 5), the questions of the
fourth grilling (in progress with the user), the full-check step (G12), and the pin move, which waits for the user's
version numbers (H4).
- F15 step 1: landed; see [F15 step 1: built](#f15-step-1-built) for the commits and the message shape.
- A hard-exit audit (rule from skellytracker-6c: a process that held a GPU EP session and ends by `os._exit`,
  terminate or kill must call `skellytracker.note_exit_requested()` first). Suspects: the tools
  `tools/hardware_validation/server_session.py` and `tools/sdk_live_validation.py`, which terminate a backend
  they started; `tools/datasets/preparation.py`; `utilities/kill_process_on_port.py`; tests that end a real
  backend. It also answers whether killing the quick-check child can leave a marker.

To do next, in order (items 1 to 3 below are older; see the update above for what is open now):
1. When step 1 lands: run the full fast suite (`uv run --frozen pytest freemocap/tests/ --timeout=120
   --timeout-method=thread -m "not e2e and not slow"`; last result 1634 passed, 7 failed = the old baseline,
   20 skipped) against `../skellytracker` at `e90245cefb7330ce33d9f1d395674b4ff3eaed7f`, then record the pin
   move in decision 1 (G11 supersedes the commit: move to `03e5b3bb`, falling back to this one) (pushed fork commit; all its CI is green on macOS, Windows and Ubuntu,
   fast tests included; it holds the check rule, `needs_check`, the exit notice, `local_cause` and the
   `unclean-exits` reason code, CoreML, pruning, the Windows ML controls and the PyInstaller hook).
2. Done (`bf6e9e9f`; see [Relay follow-up](#relay-follow-up-spec-110-and-the-switched-off-relay)).
   Relay follow-up (user confirmed 2026-11-19; one sub-agent; fake relay only in tests): before a send, read
   `enabled` from `GET /health`; when the relay is off, tell the user so and offer the issue form at once,
   with no outbox copy and no retry used. Declare `skellycertify.report/1.1.0` at the top of the file once
   any module carries an `id`; pass each module through unchanged. Tests: skellycertify's
   `relay/samples/valid-quick.md` (two quick modules with ids), the 503 `relay-off` answer (`retry: true`),
   the 422 `bad-value` for a module id that is not a v4 UUID, and that nothing assumes a `quick-` id prefix.
   Facts (skellycertify-34, confirmed by the user): several module reports of one package in one file are
   valid (spec 1.1.0 on skellycertify main `56ad18e`); skellytracker report ids become v4 UUIDs with an
   optional `id` key per module; the relay is OFF now (superseded: ON again, see "Decisions after step 1"); the
   `app` block gets no tree-modified flag. The approved single connection test was run before the switch-off:
   422 `wrong-schema`, classified refused, nothing made on GitHub. This PC's store has 13 pending reports
   with old ids; they pass through unchanged (G4).
3. Done (`48e61bf3`, `4df61357`; see [F15 step 2: built](#f15-step-2-built), with the user's manual checklist).
   F15 step 2: menu markers, the two-choice prompt and the background check in the UI, briefed from the
   message shape step 1 recorded. Then steps 3 to 5 in parallel.

Update 2026-11-19, after the fourth grilling (decisions J1 to J20, above):
(a) On this machine the app opens blocked until a start check has run, because
`C:\Users\Dom\freemocap_data\certify\start-check.json` does not exist and no reviewed OS row exists. Running it
also runs DirectML checks and writes this machine's EP store.
(b) Which repository holds freemocap's commits for `package.commit` is the user's open decision: the branch is local
with no upstream, and the remotes are the user's fork and the organisation's repository.
(c) To do next: the user's manual checklists for steps 2 to 5 (steps 3 and 4 gained freemocap-report steps); then the
full-check grilling; the pin move after the user's version numbers (H4). Done: freemocap's own module and reports (J13,
J18, J19; `f2909099`, `8659b5d2`); open: ask skellycertify to update section 9's freemocap row (the new import path).
(d) A freemocap module is a record only (`commit-not-public`) until this branch is pushed to freemocap's public
repository; pushing is the user's decision.

Settled by the third grilling (see below): freemocap says "machine" for the computer (G1); dependency bumps are
out of this plan (G8), so there is nothing to wait for from the user except the F15 step 2 checklist (G7).

Known gaps, not being worked on: development worker processes still print the cp1252 logging errors (the
fix point is in skellycam's worker setup; skellycam-18 is told); a frozen backend cannot start from this
workspace's editable installs (`skellylogs`, `skellycam` are invisible to PyInstaller); the committed
`openapi.json` lagged the app; that is fixed (G5, below).
Suite, 2026-11-19 late: 1672 passed, 7 failed (exactly the known baseline), 20 skipped, with the relay URL empty;
skellytracker was at `03e5b3bb`, dirty (certification.py, core/eps/installer.py, core/eps/store.py,
tools/certify_eps.py modified; .gitattributes modified; .editorconfig untracked).
Suite, 2026-11-19 night, after F15 step 5: 1697 passed, 7 failed (exactly the known baseline), 20 skipped, with the relay URL empty (the run showed 9 failures; 2 were the app-close test missing an `ep_packs` stand-in, fixed in `84ee32ac`); skellytracker was at `28ec03f04103de1936c6f3aaf22abe9a25b6cfeb`, dirty (tools/certify_eps.py and tools/tests/test_certify_eps.py modified).
G5 done in `e6ee3d78`: openapi.json and generated schema.ts regenerated from the app; no operation added or removed
(78 bindings verified), only CaptureMode, CameraDeviceInfo supported_modes/usb_version and route descriptions.


## Decisions of the third grilling, 2026-11-19

The user confirmed all of these.

- G1 Wording: "machine" for the computer in all of freemocap's user-facing text; "device" only for a GPU or a
  camera; never "PC". Applies to the certification texts now, to other screens only when they are touched
  anyway. Replaces "device" in F12 and in the other quoted texts (updated in place above).
- G2 Relay health check: only a clear `enabled: false` means "relay is off"; a failed or unclear health check
  goes on to the normal send. As built in `bf6e9e9f`.
- G3 The hand-in dialog makes no health call on open; the user learns the relay is off on Send.
- G4 Old pending reports with old-style ids pass through unchanged; freemocap never rewrites a report.
- G5 API contract: after the quick-check job (F15 step 1) lands, one catch-up commit regenerates the whole
  `packages/freemocap-client` contract and client, then the fast suite and the UI type check run.
- G6 The frozen backend not starting from local editable installs (skellylogs, skellycam invisible to
  PyInstaller) is deferred; it blocks release builds.
- G7 After F15 step 2 the user gets a manual checklist; steps 3 to 5 start without waiting for it.
- G8 Dependency bumps are out of this plan's scope: no more work, no rebase, no merge, no manual check asked.
  Branch `dom/dependency-bumps` and worktree `../freemocap-dep-bumps` stay on disk untouched.
- G9 `SHUTDOWN_GRACE_MS` stays 10 s until the user measures a shutdown with cameras attached. The idle
  measurement (`01be103b`: 1353, 1313, 1351 ms) was `POST /shutdown` to process exit, three runs; no script
  exists. To repeat it with cameras: (1) start the backend, connect and start the cameras (and a pipeline if
  wanted); (2) run in PowerShell `$t=Get-Date; Invoke-RestMethod -Method Post http://localhost:<port>/shutdown;
  while(Get-Process -Id <backend pid> -EA 0){Start-Sleep -Milliseconds 50}; ((Get-Date)-$t).TotalMilliseconds`
  (port and pid from the backend's startup log); (3) repeat three times and tell the session the numbers.
- G10 The stale-backend shutdown request at start (`ce160407`, up to about 10 s extra after a crash) and the
  preparation worker's stop file (`60787afe`; an orphaned worker runs to its end) stay as built.
- G11 skellytracker pin: move once, to fork commit `03e5b3bbeee1e42cc4b9eaef2913c1c96f3cd7e1`, if its CI is
  green and freemocap's fast suite passes against it; otherwise stay on
  `e90245cefb7330ce33d9f1d395674b4ff3eaed7f` and report why. Facts about `03e5b3bb`: report ids are v4 UUIDs,
  never parse an id; report schema 1.1.0 with top-level `id`; `certify("full")` and `certify_plan("full")` run
  for real (about 80 s on DirectML on an RTX 3070, estimates not calibrated); new check names
  `cpu:pipeline-1|3|6`, `cpu:jpeg`, `cpu:jpeg:<name>`, and per pair `<label>:pipeline-1|3|6`, `<label>:jpeg`,
  `<label>:jpeg:<name>`; a name with no `:` is still the EP row; about 70 JPEG rows per target, to be grouped
  by prefix in a view; the old stub check `full`/`not-built` is gone; `details.eps.<label>.pack_version` is new
  at both levels.
- G12 Full-check controls stay out of F15 steps 2 to 5; they come as their own step afterwards with its own
  short grilling.

## Decisions after step 1, 2026-11-19

- H1 (user: "nothing runs while the check is running"). The busy rule covers everything that does work, both
  ways. A quick check is refused (409 `pipelines-running`, holders in `gpu_held_by`) while any of these runs:
  a realtime pipeline or its startup (`realtime`), recording (`recording`), a connected camera group with no
  realtime pipeline (`cameras`), a posthoc mocap or calibration pipeline (`posthoc`), a sync job (`sync`), an
  export job of any kind, Blender included (`export`). While a check runs, each of those starts is refused with
  409 `quick-check-running` and the run facts. The names `pipelines-running`, `gpu_held_by` and `PipelineHold`
  are historical: they now cover all work, CPU work and cameras included, not only pipelines or the GPU.
  `kind` is an open string in the message model and the client Zod schema, so no fixture changed.
  Built (`bed3da15`): `FreemocapApplication.pipeline_holds()` is the one list of what runs, read by the check's
  admission and by `certification.gpu_held_by`. Admission points: the app's realtime, recording and both posthoc
  starts (`quick_checks.admit(kind)`); route dependency `admitted(kind)` (`quick_check_router.py`) on
  `POST /mocap/recording/synchronize`, `POST /recording-import/synchronize`, `POST /recordings/{id}/exports`,
  the deprecated `POST /exports/scientific`, `POST /exports/tall-csv` and `POST /blender/export`; and
  `camera_starts_admitted` on skellycam's router in `app.py` for `POST /skellycam/camera/group/apply`
  (`cameras`) and `POST /skellycam/camera/group/all/record/start` (`recording`). The last one was a gap: the
  UI starts recording through that skellycam route, which bypassed the app's recording admission. Always
  allowed: reads, cancelling a check, shutdown, closing and pausing cameras, camera detection, stopping
  recordings, cancelling pipelines, sync and export jobs. Not covered, as not work of the app's own: opening a
  .blend in Blender, installing the Blender add-on, video import's file copy, calibration transform saves,
  streaming outputs (they only relay a realtime pipeline). The new 409 on the sync, export and camera routes
  is not declared in OpenAPI, like the existing ones on the realtime, recording and posthoc routes; only the
  quick-check route's texts changed in the contract.
- H2 (user). One lock closes the race where a start and a check admitted in the same instant both get
  through. Built (`bed3da15`): `QuickCheckManager.admission_lock` (a `threading.Lock`: the check starts in a
  thread-pool route, other starts on the event loop or in threads). The check reads `holds` and sets its run
  under it, then spawns its child outside it; every other start checks for a run and registers a claim
  (`PipelineHold(kind, "starting")`, listed by `pipeline_holds()` until that start returns) under it. The lock
  is never held across a long start. Test: `test_a_start_and_a_check_admitted_at_once_cannot_both_get_through`
  (fails with both admitted when the lock is removed from `claim`).
- H3 (user confirmed). The six result texts stay as built: "Quick check passed", "Quick check failed:
  <reason>", "Quick check cancelled", "Quick check did not run: <reason>", "Quick check stopped unexpectedly",
  "Quick check could not start: <reason>". Each is shown by the EP in the menu until the next check or a
  selection change.
- H4 (user). skellytracker stays installed from the `../skellytracker` folder for now, with no separate pinned
  clone. The user is about to make proper version numbers, so the pin move of G11 waits for those.
- Fact, reported by the skellycertify session on 2026-11-19 (not a user ruling): the relay is switched ON
  again and files issues as the GitHub App (bot account `skellycertify-relay[bot]`). `GET /health` gives
  `enabled: true`, `test_mode: false`; a valid report sent to it files a real issue; request and answer are
  unchanged. This supersedes "the relay is OFF now". The rule stands and matters more now: tests and agents use
  a fake relay only, with `FREEMOCAP_CERTIFY_RELAY_URL` empty for anything run; the first real send is the
  user's, from the hand-in UI. No agent contacts the real relay.
- H5 (user, 2026-11-19). The report file is saved by a browser download instead of the Electron call of decision 30.
  The Electron call is built only if the save dialog does not appear in the user's manual check.
- H6 (user, 2026-11-19). The idle reminder notice and "Do not remind me" of decision 23 stay unbuilt until the
  normal-use record (deferred by F14) exists; the Certification button's suffix is the only reminder.
- Fact, from the skellytracker session, 2026-11-19: skellytracker `19b70775` has one red tool test on the fork (no
  package code wrong); it is not a pin target; freemocap already uses its cancel type and refusal fields.

## Decisions of the fourth grilling, 2026-11-19

All confirmed by the user.

- J1. The EP pack panel stays beside the EP setting; it moves into the Certification dialog when the dialog gets its EP
  list (with the full-check step).
- J2. Field-test EPs get no Install without an opt-in. skellytracker was asked to report the install state of a
  field-test EP's pack; the app stays as built until that exists.
- J3. No install or remove controls for the wheel packs (CUDA, TensorRT).
- J4. No Repair button; Remove, then Install.
- J5. Remove is always shown.
- J6. The EP pack panel's texts in `freemocap-ui/src/services/server/ep-packs.ts` are confirmed as written.
- J7. Step 3's seven choices are accepted as built ([F15 step 3: built](#f15-step-3-built)): the button suffix counts
  failures when there are any, else all pending; the issue form link is `issues/new?template=certify-report.yml`; a
  hand-in line shows the issue link and report count but no date; "open again" for an issue-form hand-in opens the form,
  not the saved file; the saved file uses the browser download, not a new Electron call; no "Do not remind me" and no
  idle notice; the dialog title carries the host name.
- J8 (`9e395508`). The busy rule covers two more starts: video import's file copy (`POST /recording-import` and
  `POST /mocap/recording/import`, kind `import`) and the Blender add-on install (`POST /blender/addon/install`, kind
  `blender-addon`) are refused while a quick check or start check runs, and while they run they refuse a check. Both are
  single synchronous requests with no in-progress state, so the route dependency `admitted(kind)` holds the claim for the
  request, as for sync and export. Opening a .blend in Blender and saving a calibration transform stay allowed.
- J9 (`84fad3dd`). `packages/freemocap-client/tools/refresh-openapi.py` writes `contracts/openapi.json` from the app's
  real OpenAPI, keeping key order and existing `example`/`examples` values and appending new keys; the README says to run
  it, then `npm run generate`. On the tree before J16 it gave no diff.
- J10. Step 5 is recorded as built and tested with stand-ins only. It has never run for real, until a Windows 11 machine
  with an AMD GPU is available.
- J11. A failed start check frees the app only until the backend restarts; only a pass is recorded.
- J12. After a cancel the app stays blocked if freemocap's own part had not passed.
- J13. freemocap will keep its own reports and pending state, and the hand-in routes will merge them with skellytracker's.
  J18: stored under `certify/` in the data folder, with the same states as skellytracker's (pending, handed in, "Not sent"
  returns to pending) and the same pruning of older duplicate passes. J19: it waited for skellycertify's spec to list
  freemocap as a package (done in skellycertify main `f89c711`). BUILT: J13, J18 and J19 in `f2909099` (module) and
  `8659b5d2` (reports and merged hand-in); see [freemocap's own module and reports:
  built](#freemocaps-own-module-and-reports-built). A failed package line of the start check now has "File report".
- J14. skellycertify was asked to add freemocap as a package. Facts from its reply: one file may hold modules of two
  packages (the normal case; report-format 4.1 and 4.3); the relay checks each module on its own; the issue title uses
  `app.name`/`app.version`, the OS label of `modules[0]` and the GPU names of all modules; the issue body limit is 65,536
  characters and one full-level skellytracker module (382 checks) needs about 51,000, so several large modules give a
  shortened table in the issue while the committed file holds everything.
- J15. skellycam's check is added when it exists; no placeholder.
- J16 (`4d0e5a03`). The start check's Blender check uses the path chosen in Blender settings, else the best guess. That
  path lives only in the UI's store, so `POST /certify/start_check` takes an optional body `{blenderExePath}` that the
  UI fills from `state.blender.blenderExePath` (not the detected path); it is passed through the child process to
  `certification.certify(..., blender_exe_path=)` and `runtime.executable(path)`. The contract and generated schema were
  refreshed.
- J17 (`245a885d`). While the start check is needed, the collapsed sidebar's expand button is dimmed and inert like the
  rest (`inert` and opacity 0.4); the compact connection status stays usable. Covered by the manual checklist of step 4
  (no test renders the layout).
- J20. The full-check step is designed after the user's manual pass over steps 2 to 5.

## Decisions of the fifth grilling, 2026-11-20 (after the demo; owner answered Q1 to Q52)

Read this section before the older "Next actions": it replaces their order. All points are the owner's
answers in the freemocap session unless marked "coordinator's choice".

### Order of work

1. The server refuses camera starts and pipeline starts while the start check is required: one sentence that
   the UI shows beside the control; the control keeps its label and stays clickable (stable-controls rule).
   Then one time-boxed trace, in the real Electron window, of the fault "cameras start behind the pop-up
   before any check ran". The blocking layer stays whatever the trace finds.
2. Move the skellytracker pin to `e17761b4` (named by the skellytracker session: branch head, four CI runs
   green, holds the 1.2.0 `summary`). Run the full fast Python suite and the UI suite (neither ran since the
   report writer and blocking changes). Bring `fixtures/certify/valid.md` to the 1.2.0 layout. Then push
   `sidecar-implementation`. skellytracker's and skellycam's commits are pushed by their own sessions.
3. "System" replaces "machine" in every text a user can read (UI labels, messages the server sends to the UI,
   the report file). Not in code identifiers, log lines, plan documents or test names.
4. Small report items: failed-checks table `Package | Module | Reason` (Module has the meaning of the results
   table; the failing check's name starts the Reason); a line naming the pairs the quick level skipped
   because they hold a reviewed pass (needs skellytracker to write them); comparison of freemocap's 6 quick
   checks with rule 3 of level quick, gaps brought to the owner before any check is added.
5. Full benchmark (below).
6. Smaller defects, with two findings of the skellytracker session: install progress scale (fixed there to
   0 to 1 in `e17761b4`; freemocap's install panel not yet checked) and pack removal failing in the process
   that installed the pack.

The installer for isolated systems (model files inside it) is out of this work: the owner starts a separate
session for it, it comes just before release and blocks nothing. The move to skellycam `dom/demo` is a
separate plan. The relay stays in test mode until the owner did one real send of a 1.2.0 report and saw
its issue. Each platform is validated independently; Linux and macOS do not wait for Windows.

### Rulings relayed by peer sessions and confirmed here by the owner

- "All system/platform/hardware/ep validation from now on will be done via the certify process in freemocap
  builds" (Linux and macOS certification runs need a freemocap build there).
- "passive record needs to be in pre-release"; freemocap's part (opt-in question, run at idle after a
  recording) waits until skellycertify defines the record and skellytracker has an interface.
- Level quick (skellycertify report-format.md section 2.7): the whole run takes no more than 2 minutes for
  all packages together; it downloads nothing; it is enough that a recording, a realtime session and a
  post-hoc session can each start and run, where the package has them.

### Start check (level quick)

- It stays limited to pairs with no reviewed pass in skellytracker's bundled evidence file. On the dev PC
  that is DirectML on both GPUs; CUDA and TensorRT RTX are skipped by design.
- Quick tests do not repeat work between packages.
- The test images are bundled (the owner handles this with skellytracker; ask that session for updates) and
  also sit in the shared test media folder.
- skellycam's quick part joins as soon as its session names a green commit with `skellycam.certify`, and
  runs first. No camera plugged in (detection finds none): its camera rows read "not checked", nothing
  fails, the app opens. A camera counts as checked per model (USB vendor and product id) on this system.
  An unchecked camera is checked when the user first asks the app to open it (pop-up and lock as for the
  start check, about 30 s, then the cameras start); plugging in alone triggers nothing.
- Provisional time split (coordinator's choice): 40 s for each of the three packages.

### Full benchmark (level full)

- The button keeps the name "Full benchmark". It runs every package's full tests; work is not duplicated.
- Division (the owner made this session the authority; the other sessions follow it): skellycam owns
  cameras, the recording of camera frames, disk speed and take load, its own processes' CPU use;
  skellytracker owns execution-provider correctness, the GPU JPEG suite and inference timing; freemocap owns
  the end-to-end post-hoc run on a known-good recording, Blender when installed, app and install facts, and
  only write access to its data folder. No package runs a whole-system CPU benchmark. freemocap makes no
  second recording.
- Run order: skellycam, skellytracker, freemocap. freemocap's benchmark uses the new skellytracker
  pipelines, not the legacy ones, and runs only on providers that passed skellytracker's checks.
- Recording: for now the freemocap sample recording, saved in a shared test media folder that other
  modules use too. The folder is per user, outside any one package's data; the app passes its location to
  each package; the rule is to be written in the skellycertify spec.
- The benchmark processes a fixed number of frames per provider (count set after measurement on the dev
  PC) and reports ms/frame with FPS per stage, reusing the measuring code of `machine_benchmarks.py`.
  Blender export runs once, timed as its own row, only when Blender is already installed (never install
  it); otherwise "Blender: not installed".
- Staging, in skellytracker's part and in the benchmark alike: unknown providers first (no reviewed pass
  for provider, GPU model and OS in the bundled evidence), then the known-fastest (TensorRT RTX), then CPU
  as baseline, then the rest.
- Offered only after the start check passed, also from the Certification button, never required.
- Consent step before the run: table of downloads (name, source host, size, total), time estimate per
  package, checkbox "remove benchmark data after a successful run" on by default, Start and Cancel; nothing
  downloads before Start. Clean-up removes what the run downloaded and its processing output; it keeps the
  report, bundled test images and files that were in the shared folder before. After a failed or cancelled
  run nothing is removed.
- The app is locked during the run as during the quick check; "Cancel check" stays and unlocks at once.
- Progress: one row per provider and GPU pair with state and turning icon, a count of finished checks, no
  percentage, no time remaining.
- Failure: a provider that fails probe or image is treated as after a quick-check failure; JPEG-suite
  failures and timing rows are reported only.
- Crash, both levels: the name of the running check is written to a small file and removed when the check
  ends; a file found at launch records that check as "crashed", it is not re-run automatically and it
  appears in the report; at level quick it counts as failed for its provider only.
- A cancelled or crashed run keeps its finished stages in a shareable report marked incomplete, with the
  rest "not run".
- The result is one more report in the same share list, never pruned. The Markdown head gains a table
  `| GPU | Module | Stage | ms/frame | FPS |` once the skellycertify session defined it; freemocap's own
  module then moves to 1.2.0.
- A full run of roughly 15 to 25 minutes is accepted (skellycam 6 to 11, skellytracker about 5, plus the
  benchmark); the text "approx 5 to 10 mins" is replaced by the measured total.

### Facts found this session

- `sidecar-implementation` sits on the tip of `upstream/sfn26` (`ca0c17cc`), 284 ahead, 0 behind (fetched
  2026-11-20). `upstream/main` has 5 commits that neither branch holds.
- `certify("full")` and `machine_benchmarks.py` share no code. Full is mostly correctness (probe, image
  against CPU, about 23 GPU JPEG checks) plus 3 record-only timing rows per provider, on one downloaded
  test image and generated pictures.
- skellytracker's plan `downloads` items hold only `name` and `bytes` (no source) and list only the test
  image; its full level downloads no model and has no clean-up option. Both are on that session's list.
- The installer bundles no EP pack and no model today (`freemocap.spec:81-83`); only CPU and, on Windows,
  DirectML come with the Python environment.
- Wording choices of the demo morning all stand (list in "Certify pop-up revision, 2026-11-20").

### After the grilling, 2026-11-20 (same day)

- Pin mechanism: freemocap takes skellytracker from a separate clone, `../skellytracker-pin`, detached at
  `e17761b4` (owner: "yes, pin to e17761b4"). Its 22 ONNX files are hard links to the files in
  `../skellytracker/skellytracker/core/model_zoo`. A git URL was tried first and failed: an installed
  skellytracker holds no ONNX file and the sidecars give no `url`. Move the clone only when the skellytracker
  session names a commit; its next commits rename `<label>:image` to `<label>:video` and `<label>:live`
  (fixtures `valid-quick.md` and `test_start_check.py` name the old rows).
- Pin moved to `9a5f3912` (local to the skellytracker session's checkout, not pushed; record in decision 1).
  freemocap now takes the plan's `total` (fallback removed), shows it as the "N checks" before the run so it
  matches the run's "N of M", shows plain sentences for `models-missing`, `test-media-missing`, `over-budget`,
  `video-not-passed`, `cpu-reference-missing`; `test_start_check.py` uses the new rows. `valid-quick.md` keeps
  `:image`: it is a byte copy of skellycertify's sample at `9e6d575`, which still names them, and tests only the
  writer's layout. Fast suite 1750 passed, 0 failed, 20 skipped; UI 230/10/46.
- Fast suite on the clone: 1724 passed, 1 failed, 20 skipped. The failure,
  `test_the_relay_validator_accepts_the_built_file`, comes from the hardened relay code in `../skellycertify`
  (rule 18, clean note) and stays until the note cleaning is built here.
- Owner, Q53 to Q56: freemocap adds two quick checks, realtime session and post-hoc session, through its own
  processes on skellytracker's 30 bundled frames (a function returning the JPEG bytes is promised by that
  session); with no model files they are `not-run` with `models-missing` and do not fail the start check;
  quick budget skellytracker 75 s, skellycam 30 s, freemocap 15 s.
- Done: steps 1 to 3 of the order of work (server refusal `796dede6`, `254ff4dd`; branch pushed once at
  `68381103`; "system" wording `0518a227`); test isolation from the real stores `f2a36e64`. Cause of the
  demo fault: the Welcome window's "Connect Cameras" card stayed clickable under the pop-up.
- Waiting on the owner's confirmation here: skellycertify format 1.4.0 (table "Checks that did not pass:"
  `Package | Module | Test | Result | Reason`; no pop-up when each plan's `total` is 0; `risks`, `notices`),
  the sender rules 17 to 20 with the clean note (skellycertify `9e6d575`), and skellycam's "pause is a
  display freeze only". The relay is switched off.

### Not built from skellycam's overlap list (freemocap's duties, coordinator accepted them)

The app closes its camera groups before any certify run; the app asks for the macOS camera permission
before the run; the app shows "Camera <name>: wedged, please replug" from a `cleanup` row
`release:<camera>` (reason `camera-wedged` or `camera-not-restored`), name found through the summary item
with the same `device`.

## State after the pin move, 2026-11-20 evening (read after "After the grilling")

Steps 1 to 4 of the order of work are done. Step 5 has started. Nothing is running.

### Built since "After the grilling"

- Pin: `pyproject.toml` names `../skellytracker-pin`, this session's own clone, detached at `9a5f3912`
  (a local, unpushed commit of the skellytracker session), commit `9bd1a4bc`; moved to `346b77eb` on 2026-11-21
  (see "Owner's answers of 2026-11-21 and the pin at 346b77eb"), then to `0342ecb8` the same day (see "Pin at
  0342ecb8, 2026-11-21"). A git-URL pin fails because an
  installed skellytracker holds no ONNX file; the clone has them hard-linked from `../skellytracker`.
  Move it with `git -C ../skellytracker-pin fetch ../skellytracker <hash>` and `git checkout --detach`.
- Report format 1.4.0 (owner confirmed): head layout, benchmark table, five-column failed-checks table,
  `incomplete` word, file schema `skellycertify.report/1.4.0` (`freemocap/system/certify/report_file.py`).
- Note cleaning (owner: "yes to both"): `clean_note()` in `report_file.py`, mirrored as `cleanNote` in
  `freemocap-ui/src/services/server/certification-hand-in.ts`, shared cases in `clean-note-cases.json`.
  The dialog shows the cleaned text as the person types; the field stops at 2000 characters.
  IPv4-looking values and link markup are printed harmlessly in the Markdown part only; the JSON keeps
  each value.
- Reason sentences in `freemocap-ui/src/services/server/execution-providers.ts` (`REASON_TEXT`) for
  `models-missing`, `test-media-missing`, `over-budget`, `video-not-passed`, `cpu-reference-missing`.
  The owner has not reviewed the wording.
- Post-hoc session quick check `posthoc-session` in `freemocap/certification.py`, commit `8be2785e`:
  3 bundled frames as a small video, the app's `MocapPipeline` to `stop_stage="observations"`, the run
  record read back, scratch folder under `<data>/certify/` removed. `not-run` with `models-missing` or
  `over-budget`, never a failure for those. Whole freemocap quick module: 10.4, 9.5, 9.5 s on CPU here
  (17 s inside pytest).
- Test isolation: `freemocap/tests/conftest.py` points the EP store, EP cache and base folder at temp
  folders for the whole run.

Suites at `8be2785e`: Python 1758 passed, 0 failed, 20 skipped; UI 230 of 231 with 1 skipped;
`npx tsc --noEmit` clean. Never run pytest with `-p no:logging`.

### Open with the owner

- Q57: the realtime session quick check cannot run in the certify child process, because
  `PubSubTopicManager.create` (`freemocap/pubsub/pubsub_manager.py:45`) refuses any process but the main
  one. Proposed: run it in a fresh copy of the app started for the check; the guard stays. Not built.
  A camera-less realtime session in a main process took about 7.4 s; frame 0 is untracked because the
  models load slower than the aggregator's 2 s wait.
- Q58: freemocap's quick share 15 s to 25 s, skellytracker's cap 75 s to 65 s. If yes, the skellytracker
  session gets it for the owner to confirm there.
- Push: one push was approved and done at `68381103`. Everything later is local. Ask before pushing.
- Wording of the five reason sentences.

### From peer sessions (facts, no ruling)

- skellytracker's local head (unpushed, after `9a5f3912`) adds `mediapipe:smoke` (`module: "MediaPipe"`,
  last check, about 3 s, no summary item) to the default quick selection. It is `not-run` with
  `models-missing` when MediaPipe or `holistic_landmarker.task` in `~/.freemocap/skellytracker-models` is
  absent, and it counts in the plan `total` when MediaPipe is installed. It matters for Q58 and for the
  installer. The pin does not hold it yet.
- The skellycertify relay is switched off until its hardening is deployed.

### Next action

The crash record for both levels (fifth grilling, "Crash, both levels"), then the consent step and the
lock of the Full benchmark. The realtime check waits for Q57.

### Crash record, 2026-11-21 (commit `f22419ba`)

`freemocap/system/certify/crash_record.py`, wired into `quick_check.py`. File
`<data>/certify/running-check.json` (level, pair, newest progress message), rewritten on each new progress
message, removed on every ordinary end. Found at launch: running check `fail`/`crashed`, unfinished checks
`not-run`/`interrupted` (spec 2.5), report marked incomplete in the share list, the pair stored as a failed
quick check, nothing re-run. A child-process crash ends in the same record. Suites: Python 1763 passed,
0 failed, 20 skipped; UI 230 of 231.

Open with the owner: a lasting skip after a crash in freemocap's own part (today the start check is asked
again at the launch after next); the code `reason-lost` (progress messages carry no reasons); the failed
pair is written through skellytracker's private `_record` and `_label` (ask that session for a public
call). Limits: 0.5 s refresh gap; no pair failure for `coreml` (check name without `@`); no real crash
tested.

### Full benchmark run, 2026-11-21 (commits `13c11cd0` server, `a30ffdc2` UI)

The run itself at level full; not built: freemocap's recording benchmark, Blender, the shared test media download,
skellycam's part. `QuickCheckManager.start(level="full", remove_data=...)` reuses the job, the refusals, the crash
record and `DELETE /certify/quick_check`; the child runs `start_check.run_full_check` (skellytracker, then freemocap
when its full plan has a check; today it has none). Routes `GET /certify/full_benchmark/plan` (each package's
`certify_plan("full")` in run order) and `POST /certify/full_benchmark` `{remove_data}`; refused with
`start-check-not-passed` unless `start_check_needed()` read false (the start check's pass is recorded). New message
fields: `run.rows` (one per EP and GPU, the CPU, or a package; state and result) and `full_results`; a cancel sets
`run.state` to `cancelling`, which ends the UI lock at once. At level full a crashed check fails its pair only for
`:probe` and `:video`. UI: `FullBenchmarkSection` (invitation with the plans' total, the never-disabled button, the
consent step, rows with turning icon, "N checks finished", "Cancel check", result lines); the lock is AppContent's
`inert` layer, now `start_required` or a running full benchmark. `QuickCheckJob.end()` no longer sets the cancel of a
dead child (it blocked forever when the child died holding the Event's lock).

On the dev PC skellytracker's full plan: 38 checks, 333 s, no downloads, pairs DirectML on both GPUs, TensorRT RTX
and CUDA on the RTX. The clean-up choice reaches the child and removes nothing: no full level downloads or keeps
output yet, and skellytracker's has no clean-up interface. Suites: Python 1772 passed, 0 failed, 20 skipped; UI 238
of 239 with 1 skipped; `npx tsc --noEmit` clean. No real full run yet.

### Defects of the first real run, 2026-11-21

Fixed (tests only; no real window since):

1. Count past the plan total (`41737ccc`): the count and total of a full run take only names with at most one `:`
   (skellytracker's `<label>:jpeg:<name>` and `:exit` rows are parts of a check) and skip the pairs the plan lists in
   `details.not_run`, which the route passes as `not_counted`. Total is now the sum over packages so far.
2. Menu and Shift+Space past the lock (`749b4950`): one gate `appLocked` (start check required or a running full
   benchmark) for the inert layer, `useKeyboardShortcuts` and `useMenuActions`; Shift+Space reaches the renderer as
   the Camera menu's accelerator, so the menu gate covers it.
3. Two reports per crash (`0985dd39`): a child whose backend died kills its own children and `os._exit`s, without
   the cancel that made certify() write a `cancelled` report; the watch now also runs after a cancel.
4. Wrong package in the share list (`f33b4625`): freemocap's `pending_reports` rows carry the report's own package.
5. "Quick check" during a full run (`87cae0a0`): "A recording can start once the full benchmark ends. " and "Full
   benchmark of …" in the progress text; quick wording unchanged.
6. Rows (`aea44601`): new row state `partly-done`, shown "Partly done" (grey, no icon); new message field
   `certification.full_rows`, the rows as the run ended (unfinished checks `not-run`, the running one `fail` after a
   crash), cleared when the next full run starts. Golden fixtures regenerated.

Not changed, per skellycertify `report-format.md`: the GPU table has one row per `ep` item of each module report (4.2
part 4), so repeated rows across reports are required; `modified-tree` is the reason whenever `tree_modified` is not
`false`, null included (7.1 item 3, reason table), so the freemocap report and its JSON agree.

Open: the orphan's `os._exit` skips what certify() undoes on a cancel (a field-test EP's opt-in during its check); a
cancel that writes no report would need skellytracker. The lingering ≥3 s was not reproduced with the stand-in. No
final rows after a restart (the crash record gives the result line only). A crashed timing check's row reads "Not
run" (the EP check's result). Not tried in the real window: the menu gate, the record line, the kept rows.
Suites: Python 1774 passed, 0 failed, 20 skipped; UI 240 of 241 with 1 skipped; `npx tsc --noEmit` clean; client
package 148 of 148.

### Recording benchmark, 2026-11-21

freemocap's level full is built (`freemocap/certification.py`; docstring has the rules). Checks: `data-folder` (write
access only), `recording`, one `posthoc:<label>` per pair, `blender`; all names have at most one `:`, so the count
matches the plan's `total`. No UI change.

Decisions and facts:

- Recording: the freemocap sample recording, `freemocap_sample_data.zip`, 166 958 457 bytes, sha256
  `c23d6a24…acf4f`, from the URL the dataset tools already use (`tools/datasets/catalog.py` `SAMPLE_DATA`,
  github.com release). `utilities/download_sample_data.py` is dead code (its imports no longer exist). The download
  and zip-safety code of `acquire_recording` became `catalog.download` (streams, hashes, polls a cancel) and
  `catalog.extract_recording`. Spec 2.8 holds the recording as written: the archive is one file,
  `<sha256>.zip` in the shared folder. The extracted, cut copy lives in freemocap's work folder
  `<data>/certify/benchmark` (spec 2.5 "its own work folder"). The cut writes the first 300 frames of each of the 3 videos
  in the sample's own codec (MPEG-4 Part 2, `mp4v`, no B-frames).
- Shared test media folder: `default_paths.get_test_media_dir()`, `%LOCALAPPDATA%\skellycertify\test-media` (else
  `~/.cache/...`), override `FREEMOCAP_TEST_MEDIA_DIR`. The plan route and `run_full_check` pass it to both packages at
  level full. skellytracker reads its frames only from `<dir>/<sha>.zip` when it gets the option and does not copy them
  there, so `start_check.seed_test_media` copies its bundled file there first (`frames_record`/`frames_file`). That
  file is bundled, so the clean-up keeps it. The level quick does not get the folder yet.
- Pairs and order: the labels that skellytracker's `certify_plan("full")` runs (`details.checks` minus `not_run`),
  matched to `eps.status()` rows. Reviewed state is `DeviceCheck.certified`. The known-fastest is the first reviewed
  pair in the `status().eps` order, which skellytracker documents as its order of preference. The CPU is the status row
  with `uses_gpu` false. A pair runs when its `DeviceCheck.usable` (the CPU row: `usable`) is true after
  skellytracker's own run (its `_record` writes the local pass or fail), else `not-run`/`ep-not-passed`. A reviewed
  pair that failed in this run therefore does not run. Labels use skellytracker's private `_label`, as `crash_record`
  does.
- Measuring: the session's own `PerformanceReport` line "Processing performance:" is captured in the spawn child and
  read with `tools/datasets/reporting.parse_performance` and `normalized_stages`, the code `machine_benchmarks.py` uses.
  Summary items are written for 7 stages: inference, tracking, triangulation, filtering, reconstruction, saving and
  exports (channel exports only, so Blender is not mixed in). Every stage is kept in `numbers.stages`; the one-off
  `inference.session_setup` is in `numbers.startup_seconds`. Blender is the app's `export_to_blender` on the first
  finished pair's recording, in its own child. It gets the item `Blender`/`export` and the check is `record-only`.
  When Blender is not found the check is `not-run`/`not-installed`.
- Frame count 300: in the 150-frame trial on this PC the CPU session took 19.5 s. With 300 frames the CPU pair takes
  40.1 and 38.7 s from start to end (2 runs). Estimates: download 20 s, prepare 10 s, 45 s per pair, Blender 20 s. The
  plan gave 165 s; the freemocap part measured 147.7 and 144.5 s.
- Clean-up: `certify(..., remove_data=True)` removes the work folder, and the archive only when this run downloaded
  it. It does this only after a run with no failed check and no cancel. `run_full_check` passes `remove_data` only when
  every earlier package passed. Failures go in `cleanup`. A partial or wrong download is always deleted. The start of
  a run replaces an earlier run's work folder.
- `host.gpus` is now in freemocap's report (the benchmark GPU cells need it). A file with freemocap's module alone
  therefore lists the GPUs as "not checked".

Measured (scratch store, RTX 3070 + UHD 770, DirectML a field-test EP that skellytracker's full pass opted in; CUDA and
TensorRT RTX not installed in the scratch store, so not measured). Cancel during a pair ended the run 0.31 s later. The
work folder stayed, the rest of the checks were `not-run`/`cancelled`, and no child process was left.

Tests run: `test_recording_benchmark.py` (new: plan, success and clean-up, fail/cancel/no choice, archive kept or wrong
hash, timing read-out, `run_full_check` options) and the updated `test_start_check`, `test_full_benchmark`,
`test_certify_report_file`. A cancelled full run now also lists freemocap as `not-run`/`cancelled`. Full fast suite:
1782 passed, 0 failed, 20 skipped (baseline 1774); no download, real folders untouched.

Open (owner's decisions or gaps):

- The Markdown head has no place for "Blender: not installed". The JSON has it (check `blender`, `not-installed`). A
  line needs the skellycertify spec.
- The UI shows freemocap's failed check names raw (`posthoc:cpu`, `recording`, `blender`), and the progress has one
  freemocap row, not one row per pair.
- The folder name `skellycertify/test-media` and the env variable are this session's choice.
- The plan route and the full run do not pass the Blender path chosen in settings (the best guess is used).
- No real download was timed through the app. A pair's timeout is 600 s; Blender's is 600 s.
- macOS `coreml` (no device key) is not in the pair list. A test stand-in is needed so that no test runs the real full
  level: one did, and downloaded the archive twice before it was stubbed.

### Recording benchmark in the UI, 2026-11-21

Closed the UI gaps above; tests only, no real window. Commits:

- `a5e6eb63` guard: in the fast suite the real `catalog.download` raises unless the test stubs it or `requests.get`
  (in-process only; the full benchmark job tests now give the child `own_stand_in` for freemocap's `certify`), and
  conftest points `FREEMOCAP_TEST_MEDIA_DIR` at scratch.
- `b77d8267` rows: freemocap's progress has one row per check (`_full_rows`): `posthoc:<label>` rows carry the pair's EP
  and device key, so they read as the pair; `data-folder`, `recording`, `blender` are rows of their own. The UI puts
  each package's rows under a heading with its name ("skellytracker", "freemocap"); proposed to the owner, not chosen
  by them. Counting is unchanged (`_counted`), so the row count of freemocap equals its plan total.
- `40b4d6b3` words: `REASON_TEXT` gains `bad-hash`, `recording-missing`, `ep-not-passed`, `not-installed`,
  `cancelled`, `interrupted`, `reason-lost`; `checkText` names freemocap's full checks ("data folder write access",
  "sample recording download and preparation", "Blender export", "post-hoc processing on <pair>", the pair from the
  run's rows, else the label) in the rows and the result lines. Report files keep the names; quick wording unchanged.
- `b374cfe9` Blender path: `GET /certify/full_benchmark/plan?blenderExePath=` and `POST /certify/full_benchmark`
  `{blenderExePath}` reach `certify_plan`/`certify` through `run_full_check`; contract refreshed.
- `4810aee2` test media at quick: `run_start_check` passes `test_media_dir` to freemocap (unused at quick) and to
  skellytracker only when its frames file is already there: given a folder, skellytracker reads its frames only from it
  (no fallback to the bundled file), and the quick level must write nothing. A fresh system's start check therefore
  runs as before; after a full benchmark seeded the folder it reads the same bytes from there.
- `b8b68718` download through the consent step (read and tested with stand-ins for `requests.get`): a broken download
  fails `recording` with the exception class, the pairs are `not-run`/`recording-missing`; a cancel stops between 1 MB
  chunks; neither keeps a `.part` file or the final name, and nothing is removed. Limit: a stalled connection is only
  noticed at the next chunk or the 300 s read timeout.
- `8a2167a2` (separable; revert if the owner declines): a row with a crashed check reads "Failed" (`_ended` marks it).

Suites: Python 1785 passed, 0 failed, 20 skipped (no test reached the download guard; `%LOCALAPPDATA%\skellycertify` was absent before and after); UI 243 of 244 with 1 skipped; `npx tsc --noEmit` clean; client package 148 of 148.

Open: the owner's choice of the package headings and of the crashed-row wording; all of it in the real window.

### Defects of the second real run, 2026-11-21

Tests only, no real window since. Commits:

1. Stale consent (`4aad3443`): the plan is read again at each opening of the consent step, after each refused Start
   and at each start and end of a full run (`planReadKey`: opening count and whether a full run is running). The
   consent step shows only the plan read for the current key (`consentPlan`), else "Reading what the full benchmark
   runs…". Server side: `POST /certify/full_benchmark` takes `downloads` (the names the consent listed; default empty)
   and refuses with `downloads-changed` when the current plan needs another one: "The full benchmark now needs a
   download you did not agree to (<names>); check the downloads and start again." The UI then reads the plan again and
   shows the refreshed consent with that sentence. A consent that listed more than is needed now is not refused.
2. Count (`baefdf66`): the child put its result on its own queue while the last progress message (every check ended)
   was still in the progress queue's feeder thread. The backend reads the result first, so that message was lost and
   the last check's kept row read "Not run". The child now closes and joins the progress queue before putting the
   result. At level full each package's newest message is also kept during the drain. The end of a run shows no count
   (the existing layout); "27 of 28" is the last running message, and the done message comes with the result.
   Reproduced before the fix with a progress message that is slow to send.
3. Share list (`d09501af`): `HandInReport.incomplete` (the hand-in route only, read per report through
   `relay.report_incomplete`, by `report_file.incomplete`, the header's rule). The list line reads
   "freemocap · <time> · full · incomplete · no failure". Spec 4.2 sets only the file. It says nothing against this.
4. Cancelled rows (`29088d83`): a cancel stores, per package, the checks that had not ended. In the kept rows those
   that ended `not-run` get `reason: "cancelled"` (new optional `CertificationRunRow.reason`), shown "Cancelled". After
   a crash nothing changes. Golden fixtures unchanged; OpenAPI and client schema refreshed.
5. Combined report time: not changed. Spec 4.2 says the name and the header carry "the UTC start time of the run". A
   build time would also change the bytes between "View report" and "Send", which `file-changed` refuses, and defeat
   the relay's SHA-256 duplicate check. The earliest `created_utc` stays. For several runs that is the owner's call
   or a spec question.
6. Start under the Close bar (`42b0de49`): `scrollPaddingBottom: '4em'` on the dialog. Keyboard focus and
   scrollIntoView now keep Start clear of the bar. A mouse scroll still slides content under a sticky bar, by design.
7. Cancel latency (`62fbf72d`): the 31 s was the UI script's `getByText(...).innerText()`, which waits 30 s for text that is
   gone; the server ended the run 0.27 s after the DELETE. Direct runs: 0.05 to 0.27 s at every point of a pair. The real
   defect: the kill left skellytracker's unclean-exit markers, and two cancels marked DirectML on the RTX `unclean-exits`
   (`ep-not-passed` next run). A pair child now ends its session itself (`STOP_GRACE_SECONDS` 1.5, then the kill): 0.8 to
   1.7 s, no marker, the next run ran every pair.

Suites: Python 1787 passed, 0 failed, 20 skipped (`%LOCALAPPDATA%\skellycertify` absent before and after); UI main run
244 of 245 with 1 skipped; `npx tsc --noEmit` clean; client package 148 of 148.

Open: all six in the real window, mostly the consent after a kept or deleted archive, the kept rows after a cancel, and
Tab to Start at 1000×700. Item 5 is the owner's.

### Smaller defects, 2026-11-21

Step 6 of the order of work. Tests only, no real window. Fixed:

1. Stale refused-camera banner (`e5e096cf`): the camera slice keeps the refusal's `code`
   (`cameras.errorCode`). An app_state whose `certification.start_required` is not `true` clears a
   `start-check-required` refusal. A new request also clears it. Other camera errors are unchanged. The other
   slices (calibration, mocap, realtime) were not changed: no stale banner of theirs was reported.
2. Welcome window behind the pop-up (`445e752b`): the Welcome modal shows only while the Certification dialog is
   closed and the app is not locked. On a first launch it appears after "Continue". If the start check is not
   required, it can show for a moment before the first app_state arrives.
4. Red borders (`67ec93db`): `.settings-note-dismissable` had the danger border for every bordered note. It now
   has the neutral hairline, and the danger border stays for `.settings-note-error`. A failed quick-check result
   line now carries `settings-note-error`, so its text is red too. The legacy-EP notice and the old-threshold prompt
   also become neutral.
5. EP pack keys (`0fc20866`): `packResultText` reads reason codes through `reasonText`. A remove's comma-joined
   codes are worded one by one. New sentences, not yet reviewed by the owner: `package-not-removed`,
   `package-name-mismatch`, `package-unknown`, `record-refused`, `thread-not-started`. Left: the server's
   refusal sentences still name the EP by its key and the kind `ep-pack` ("the ep-pack start was refused").
   Those sentences are shared with the quick check's refusals, so changing them is the owner's call.
6. EP menu keys (`69ecb4b7`): a saved choice takes its name from the EP list or from `certification.items`,
   whichever arrives first. Before either, it shows "…". After the EP list is read, a key that the server does
   not list still shows as saved.
7. Narrow strip (`d503d75a`): below 1100 px the toolbar's gaps shrink to 4 px. Its two buttons get a 100 px
   maximum width, so "Real-time processing" and "Processing settings" wrap onto two lines. Every label is kept
   whole. Not measured in a window.
9. Snapshot (`f744efa4`): the button is the pipeline metrics window's "Save snapshot"
   (`electron/main/services/pipeline-metrics-window.ts`). It offers `pipeline-metrics-<YYYYMMDD-HHMMSS>.png`
   in Downloads and writes the captured PNG where the person picks. The name is now in local time, as recording
   names are; it was UTC. The new test `pipeline-metrics-window.test.cjs` covers this with stand-ins for Electron
   and fs. Left in UTC: the log terminal's export name (`LogTerminal.tsx`), calibration export names and certify
   report names (UTC by the spec).

Not found:

3. Camera actions during the lock: every Electron menu item only sends a renderer action, and the renderer ignores
   these while `appLocked`. The only other items open docs links. The main process makes no server call besides
   `/shutdown`. The in-window camera controls sit in AppContent's `inert` layer. `CameraSettingsModal` is portaled
   out of that layer, but it closes on any click outside it, and the server refuses the start anyway.
8. Install progress scale: skellytracker gives `fraction` from 0 to 1 (`windows_ml._ensure_ready` divides by 100).
   `EpPackManager` passes it on unchanged, and `packProgressText` multiplies by 100. Already tested:
   `test_ep_packs.py` (stub progress 0.25 and 0.5 reach `run.fraction` and the message) and `ep-packs.test.tsx`
   (0.256 shows 26%).

Suites: Python 1788 passed, 0 failed, 20 skipped (`%LOCALAPPDATA%\skellycertify` absent afterwards); UI main run 244
of 245 with 1 skipped, plus 10 and 46; `npx tsc --noEmit` clean; `node --test` of the new snapshot test 1 of 1;
`check-ui-styles` 30 errors as before, none of them new. No contract change, so the client package suite was not run.

Real window: the banner clearing after the start check passes, Welcome after "Continue" on a fresh profile, note
borders in the dialog and the EP panel, the EP menu right after connect, the strip at 1000 px and 1100 px on
Streaming, and Save snapshot.

### Owner's answers of 2026-11-21 and the pin at 346b77eb

The owner's answers, as relayed by the coordinator. Tests only, no real window.

| Q | Owner's answer | Built |
|---|---|---|
| Q58 | yes: freemocap's quick share 15 s to 25 s; skellytracker's cap 75 s to 65 s in its own repository | `907484b9`: `QUICK_BUDGET_SECONDS = 25`. It sets the quick plan's `seconds_estimate` and the `over-budget` guard of `posthoc-session`; the UI's "up to about N seconds" comes from the plan. freemocap neither passes nor assumes skellytracker's cap (its tests use stand-in estimates 75 and 90). |
| Q59 | yes: a start check that crashed in freemocap's own part is skipped for good until a package version changes | `95ac9536`: `crash_record.recover` writes `{"versions", "os", "crashed": <check>}` to `start-check.json` (`start_check.record_crash`) when the crash record is a start check (level quick, no pair) whose progress names freemocap (or no package). `start_check_needed()` then reads false for that version set. The report stays in the hand-in list; the Certification button still runs the check; a later pass overwrites the record. A crash in skellytracker's part writes nothing. |
| Q61 | yes | `da90e7ef`: `REASON_TEXT.crashed` "it stopped unexpectedly while it ran and is not run again by itself" → "it stopped unexpectedly and will not run again automatically". |
| Q68 | "use freemocap instead of skellycertify" | `f09687cc`: default `%LOCALAPPDATA%\freemocap\test-media` (else `~/.cache/freemocap/test-media`, the Blender storage pattern); `FREEMOCAP_TEST_MEDIA_DIR` still overrides. Checked: no code removes `%LOCALAPPDATA%\freemocap` or `storage_root()` (Blender only creates `packages`, `built`, `profiles` under `freemocap\blender`); the NSIS uninstaller has `deleteAppDataOnUninstall: false` and a per-user install lives in `%LOCALAPPDATA%\Programs\…`. The real folder also holds `TensorRT-RTX-EP-ABI-v0.1.0` (not written by these tests). |
| Q69 | "skipped is ok for this" | `ca0146e6`: the row reads "Skipped". freemocap's progress now carries each check's `reason` (a field the spec's progress table does not list), so `run.rows`/`full_rows` give the `blender` row `reason: "not-installed"`; `CertificationRunRow.reason` description refreshed in OpenAPI and the client schema. The report keeps `not-run`/`not-installed`: spec 3.7 allows `skipped` only for a summary item and only with `busy` or `reviewed`, and part 8 prints no row for a `not-run` check without a partial or failed item, so the Markdown cannot say "skipped" without a spec change. |
| Q74 | yes | `a60801b9`, sentences below. |
| Q75 | yes | `d8b94cfb`: `freemocap-logs-<YYYYMMDD-HHMMSS>.txt` in local time (was `toISOString()` with `-` for `:` and `.`); calibration export names unchanged. |

Q74 sentences (key `amdgpu`, display name "AMD GPU" from skellytracker's label in the cached status, else the key):

- "<check> is running; the ep-pack start was refused. Start again when the check ends." → "…; the provider pack
  install start was refused. …" ("provider pack remove" for a remove).
- "An install or remove of the amdgpu EP is running; the <kind> start was refused. Start again when it ends." → "An
  install or remove of the AMD GPU EP is running; the <kind> start was refused. …"
- "The quick check cannot start while other work runs: ep-pack amdgpu. Stop it first." → "…: the provider pack install
  or remove of AMD GPU. Stop it first." (the same list in every `pipelines-running` sentence; the running pack's action
  is not in its claim, so it says "install or remove").
- "The install of amdgpu cannot start while other work runs: cameras g1. Stop it first." → "The provider pack install
  of AMD GPU cannot start while other work runs: cameras g1. Stop it first."

Codes, `gpu_held_by` kinds (`ep-pack`) and the other quick-check and full-benchmark sentences are unchanged.

Confirmed with no change (owner's yes): Q63 (the button stays clickable after a failed start check; the server refuses
with its sentence), Q64 (consent inline; rows grouped under package headings), Q66 ("Partly done"), Q67 (a crashed row
reads "Failed", `8a2167a2` stays), Q72 (the download guard compares names only). Still open, not built: Q57, Q60, Q62,
Q70, Q71.

Owner's call, found while building Q59: the full benchmark's gate is `start_check_needed()` false, so after a crash
marker the full benchmark is admitted although the start check never passed. Not covered by Q59: a freemocap check that
ends `fail`/`crashed` inside an ordinary run (a crashed spawn child) records nothing, so the start check is asked again.

Pin: skellytracker `dom/sidecar-implementation` at `346b77eb`. CI on that commit, all green: Fast tests (ubuntu), EP
pack (windows, ubuntu, macos), Lint, Secret scan; the full test suite runs only on a pull request or by hand and did
not run. `../skellytracker-pin` fetched and detached there; its model files are the same set as `../skellytracker`'s
(no new ONNX or model file; the MediaPipe smoke check reads `holistic_landmarker.task` from
`~/.freemocap/skellytracker-models` and downloads nothing). Commit `45e4ec09` updates the `pyproject.toml` comment; no
`uv sync`/`uv lock` (an editable path; skellytracker's `pyproject.toml` did not change). Nothing in freemocap needed
adapting to `mediapipe:smoke`: the start check uses package-level rows and skellytracker's done/total, crash_record
ignores a label without `@`, and freemocap does not read `details.skipped`.

Isolated quick run after the pin (scratch EP store, cache, base folder, logs, test media; RTX 3070 and UHD 770,
DirectML):

| Package | Checks | Results | Plan estimate | Seconds |
|---|---|---|---|---|
| freemocap | 7 | 4 pass (`posthoc-session` 8.7 s), 3 record-only (`build-identity` `modified-tree`, `install-facts`, `blender`) | 25 s | 10.2 |
| skellytracker | 11 | 11 pass: CPU video/live, DirectML on both GPUs (probe, video, live, roll-up), `mediapipe:smoke` 2.9 s; evidence valid | 48 s | 24.4 |

Suites: after the rulings Python 1791 passed, 0 failed, 20 skipped; UI main run 244 of 245 with 1 skipped, plus 10 and
46; `npx tsc --noEmit` clean; client package 148 of 148. After the pin: Python 1791 passed, 0 failed, 20 skipped; UI
the same; `npx tsc --noEmit` clean. `%LOCALAPPDATA%\freemocap` held only `blender` and `TensorRT-RTX-EP-ABI-v0.1.0`
before and after; no `%LOCALAPPDATA%\skellycertify`.

Real window: the "Skipped" Blender row, the crash marker after a real crash, the new refusal sentences, the log export
name.

### Format 1.5.0 and reported-only failures, 2026-11-21

Owner's answers of 2026-11-21, relayed by the coordinator: Q77 agree (move to skellycertify format 1.5.0, `0966552`,
ADR-VV80), Q62 agree (a full benchmark's failed JPEG checks and timings are reported only), Q79 and Q80 agree (below).
Commit messages from here on carry no attribution line. Tests only, no real window.

- `20896503` format 1.5.0. freemocap's module and the file declare `skellycertify.report/1.5.0`. Each check of freemocap's
  own module has `module` (`certification.COMPONENTS`: Build identity, Child process, Bundle imports, Data folder,
  Post-hoc session, Install facts, Sample recording, Blender; `posthoc:<label>` keeps the EP's name). Each such check
  that ended `pass`, `fail` or `record-only` gets a `component` item (`device` null) with its result. A `not-run` check
  gets none, and neither does Blender when it is not installed (`not-found` at quick, `not-run`/`not-installed` at full;
  a "skipped: not installed" row is not in the spec). The writer prints `| Module | Result |` directly after the
  benchmark table (4.2 part 6). Each module keeps its own schema id. skellytracker at the pin still writes 1.4.0, and
  the relay checks each module against `1.x` on its own. Spec 8 says "the module reports and the report file of one run
  use the same schema id"; the writer does not rewrite a package's report. Rule 20 was already a loop until stable
  (`_no_ipv4`, tested with `1.2.3.4.5.6.7`), so no change there. ms/frame was already one frame set and is unchanged: a
  stage's total time over the run divided by `PerformanceReport.frames`. That counter is the synchronized frames, 300,
  not the 900 images. FPS is frame sets per second; Blender's is its export time over 300. The samples in
  `relay/samples` are unchanged at 1.4.0; the byte-for-byte tests swap only the file's schema line. New fixture
  `valid-component.md`, built by the writer: a freemocap 1.5.0 module beside skellytracker's 1.4.0 one. The local relay
  validator (`0966552`) accepts it. `ReportMarkdown` renders any table, so it gets a parser test only.
- `7139815a` Q62. Reported only, by name shape (spec 3.6; no field of skellytracker's marks them; `module` is the EP
  name for both an EP's and its JPEG checks): `<label>:jpeg`, `<label>:jpeg:<name>`, `<label>:pipeline-<n>`
  (`start_check.REPORTED_ONLY`). `full_result()`: when every failed check of a package matches, the result is that of
  its other checks. `StartCheckResult.reported_only` (new message field; client contract updated by hand, as before;
  no OpenAPI or golden change) names them. So freemocap's clean-up still runs. A failed probe, video or live check, or
  a failed freemocap pair, still gives "finished with failed checks" and lists nothing apart. A row with no roll-up
  check (the CPU) takes no result from those checks; pair rows keep their roll-up. UI line under the package's
  "finished": "Reported only: JPEG checks on <pair>, timings on CPU: they did not pass, and they do not change the
  result."
- `d82a5d6c` Q79. `start_check_needed(crash_skips=False)` treats a crash marker as no pass. The manager's
  `_full_needed` gates `POST /certify/full_benchmark` with the existing `start-check-not-passed` sentence. A reviewed
  row or "nothing to check" still admits it. `start_required` is unchanged, so the app and the button stay usable.
- `1449b6eb` Q80. A start check whose freemocap module ends `fail` (a crashed check is `fail`/`crashed`) writes the
  crash marker with its first failed check. skellytracker's failures write no freemocap marker. A later pass
  overwrites it. Not covered: freemocap's `certify()` raising (`error`) writes no marker.

The closed owner's call under "Owner's answers of 2026-11-21": Q79 and Q80 answer both points. The full benchmark rejects
a run started after a crash marker, and a failed freemocap check now writes the marker.

Live relay: switched off (503 `relay-off`, retryable; the app keeps the file). Its deployed code predates 1.4.0. Once it
is on, a pre-1.5.0 relay would refuse each freemocap file with 422 `bad-value` at the summary `group` (every freemocap
module now has `component` items), and the app offers the issue form at once. Not verified against the deployed code.

Suites: after format 1.5.0, Python 1793 passed, 0 failed, 20 skipped; UI main run 245 of 246 with 1 skipped, plus 10 and
46; `npx tsc --noEmit` clean. After Q62: Python 1792 passed, 1 failed (`test_pipeline_timing.py::
test_maybe_flush_publishes_and_clears`, a `Queue.empty()` race; it passed 3 reruns alone); UI 246 of 247 with 1
skipped; client package 148 of 148. After Q79 and Q80: Python 1795 passed, 0 failed, 20 skipped (the race test passed);
UI main run 246 of 247 with 1 skipped, plus 10 and 46; `npx tsc --noEmit` clean.

Reading list: `../skellycertify/report-format.md` 3.6, 3.7, 4.2, 8 (what 1.5.0 requires);
`freemocap/certification.py` docstring (component items, ms/frame); `system/certify/start_check.py` `full_result`,
`start_check_needed` (Q62, Q79, Q80).

### Format 1.6.0, 2026-11-21

Owner's answers of 2026-11-21, relayed by the coordinator: Q71 agree, Q78 agree: move to skellycertify format 1.6.0
(`ba9a071`, ADR-9FHP). The spec text is the authority. Tests only, no real window. No commit has an attribution line.

- `5e9e800c` schema ids. freemocap's module, the crash record's report (it takes `certification.SCHEMA`) and the file
  declare `skellycertify.report/1.6.0`. skellytracker at the pin still writes 1.4.0; the writer keeps each module's id.
- `85f13ad6` Blender not installed (3.7, 4.2). Both levels now give the check `not-run` with `not-installed` (quick was
  `record-only`/`not-found`; the code `not-found` is gone) and the `component` item `skipped` with `not-installed`. The
  writer prints it as "skipped (not installed)". The UI's full-benchmark row keeps "Skipped" (Q69); the start check shows
  package rows only.
- `f3718bea` `test_media` (3.9, 2.8). freemocap's module lists `quick_frames.zip` (`bundled`) when `posthoc-session`
  ended `pass` or `fail` (the session ran on the frames; none for `models-missing`, `over-budget`,
  `test-media-missing` or a cancel), and `freemocap_sample_data.zip` (`shared`) once `recording` checked the archive's
  SHA-256 (none after `bad-hash`). The frames item comes from skellytracker's `frames_record()`
  (`skellytracker.core.eps.certification`, a module freemocap already imports; `certify_frames()` gives only JPEG
  bytes): `certify_frames()` returns frames only from a file whose SHA-256 is that record's. The archive item takes the
  SHA-256 computed from the bytes (the download's digest or `_sha256` of the present file) and the file's size. Proof:
  `test_the_frames_file_the_session_ran_on_is_listed_with_the_hash_of_the_bytes_of_its_frames` hashes the bundled file
  itself and checks that the frames given to the session child are its first members; the full-level tests compare the
  item with `hashlib.sha256` of the archive bytes used. The crash record of a freemocap run lists the same files by the
  same rules from its progress (`interrupted_media`); skellytracker's crash record lists none.
- `3a817e34` `abandon` (2.4). `certify(..., abandon=None)`: a set abandon is read as a cancel by every check and child
  (the stop event and `STOP_GRACE_SECONDS` of `62fbf72d`), wins over `cancel`, and no report goes to the hand-in list.
  In the job's child (`quick_check._run`), freemocap's own `certify` is wrapped by `_abandonable`: when the backend dies
  while it runs, the watch sets `abandon`; the run stops and the child ends (`_end_orphan`) at its return, or after
  `CANCEL_GRACE_SECONDS`. While skellytracker runs, or between packages, the child ends at once as before (`0985dd39`).
  Next pin move: uncomment the one line under the `own_certify` wrap in `_run`:
  `certify = _abandonable(certify, abandon, running)`. It covers the start check, the full benchmark and the pair quick
  check, which all take `certify` from there.
- `e9576021` Q80, the coordinator's reading for the owner to confirm: freemocap's `certify()` raising in the start check
  (`error`) writes the crash marker like a `fail`, with the exception's class name as `crashed`.
- `7d0067e6` `shared_memory_bytes` (3.3). freemocap builds `host.gpus` itself (`certification._host`, from
  skellytracker's `probe_host()`). skellytracker's `GpuInfo` has no such field at the pin, so the value is null;
  `getattr` picks up the field that skellytracker's local `records.py` already adds once the pin moves.
- `8bb6bd69` 4.2: a test pins the oldest `created_utc` in the name and header for two reports of one package; the writer
  already took `min()`.
- `671cfeec` `valid-component.md` regenerated by the writer (a scratch script, as before): `test_media`, the Blender row
  "skipped (not installed)", `shared_memory_bytes: null`. The relay validator of the skellycertify working tree accepts
  it and refuses a `name` with `/`; the committed `ba9a071` relay sources (copied to a scratch folder) accept it and both
  `relay/samples` copies. `valid.md`, `valid-quick.md` and `refused-privacy.md` are still the samples byte for byte.

Found: the skellycertify working tree has uncommitted changes of a peer (`relay/src/privacy.js`, `report-format.md`,
new ADR-Q02Y "test media name exempt from rule 7"). freemocap's Python copy of rule 7 still applies to every string, as
`ba9a071` says; freemocap's names end in `.zip`, so neither reading changes a file.

Live relay: on, in test mode; the deployed code predates 1.6.0 (ADR-9FHP: "It must be deployed"), so it may refuse a
`skipped`/`not-installed` item or `test_media`. Not verified; no test contacts it.

Suites: Python 1802 passed, 0 failed, 20 skipped (at `671cfeec`; the race test passed; 7 new tests); after `d3b27492`
the job-level files (`test_quick_check`, `test_full_benchmark`, `test_start_check`, `test_crash_record`) 72 passed. UI
main run 246 of 247 with 1 skipped, plus 10 and 46; `npx tsc --noEmit` clean. No UI, OpenAPI or client contract change,
so the client package did not run.

Next action: the owner confirms the coordinator's reading of Q80 (`error` writes the marker); at the next pin move,
uncomment the `abandon` line of `_run` and drop the `getattr` default once skellytracker's `GpuInfo` has the field.

Reading list: `../skellycertify/report-format.md` 2.4, 2.8, 3.3, 3.7, 3.9, 4.2 (what 1.6.0 requires);
`freemocap/certification.py` `_frames_media`, `_posthoc`, `_recording`, `certify` (test media, abandon);
`system/certify/quick_check.py` `_abandonable`, `_run` (the orphan and the next pin's line).

### Pin at 0342ecb8, 2026-11-21

Owner's authorizations for the unattended session of 2026-11-21: pin moves to pushed skellytracker commits with green
CI; pushes of `sidecar-implementation` and `agents-and-adr-kit` to the fork after green suites; the merge of the kit
branch and the migration of decisions; rulings relayed by peer sessions acted on only when they follow from the owner's
earlier answers (held: skellycertify format 1.7.0, which exempts a `test_media` name from privacy rule 7; freemocap stays
on 1.6.0); private source paths fixed where the change is behaviour-neutral; skellycam's certify part left alone.

Pin: skellytracker `dom/sidecar-implementation` at `0342ecb830816f60d428a12009b97711d21cf508` (`346b77eb..0342ecb8`:
`b981e586` ADR-889R, decision only; `d5dae2e5` format 1.5.0 with a MediaPipe `component` item; `ba690194` quick limit
65 s, `abandon`, `check_label`, `record_failed_pair`, ADR-Q9R6; `87c68e8a` docs-site skill; `0342ecb8` format 1.6.0 and
`package-in-use`, ADR-P47E). CI on that commit, all green: Fast tests, EP pack, Lint, Secret scan. `../skellytracker-pin`
fetched and detached there; no new model or ONNX file, skellytracker's `pyproject.toml` unchanged, so no `uv sync`/`uv
lock`. Commit `7257a2c8` updates the `pyproject.toml` comment. Tests only, no real window.

- `76962fcd` public calls. `crash_record.record_provider_failure(check)` (the unused `created` argument dropped: skellytracker
  stamps the time) maps the label to the device key by `check_label` over `gpu_device_keys` and calls `record_failed_pair`;
  a `ValueError` (an EP or GPU this system no longer has) is logged, not raised. `certification._pairs`, `_usable_labels`
  and `quick_check._full_rows` use `check_label`. No `_label` or `_record` is imported from skellytracker any more. Still
  imported from skellytracker's internals (no underscore, not its top-level interface): `core.eps.certification`
  (`frames_record`, `FramesUnavailableError`, `reports_dir`), `core.eps.evidence.gpu_id`, `core.system.host`
  (`probe_host`, `gpu_device_keys`), `core.eps` (`install`, `remove`); the tests also import `core.eps._download`.
- `753894b4` `abandon`. `_run` now wraps skellytracker's `certify` with `_abandonable` too, so the start check, the full
  benchmark and the pair quick check all pass it. After the backend dies, a running certify() of either package gets
  `abandon`, stops as for a cancel with its clean-up, and the child ends at its return or after `CANCEL_GRACE_SECONDS`;
  between packages it ends at once. Tests: the real-process orphan test now covers skellytracker's run with a stand-in
  that stops on `abandon`, and a certify() that ignores it is ended after the grace with no report. `abandoned` gets no
  sentence: skellytracker's report after an abandon has no file and goes nowhere, and the orphaned child publishes
  nothing, so the code never reaches the UI.
- Quick limit: skellytracker's cap is 65 s (`QUICK_BUDGET_SECONDS`), freemocap's share stays 25 s; freemocap neither
  passes nor assumes the cap, and the UI's "up to about N seconds" is the sum of the plans (at most 90 s). No text changed.
- `759981cd` test media. The start check passes the shared folder to skellytracker always (skellytracker falls back to
  its own file when the folder does not hold it). `seed_test_media` and `_frames_target` are removed: with the fallback
  the full run reads the package's file, and its report says `bundled`, which is the truth; nothing is copied into the
  shared folder any more. freemocap's `posthoc-session` now reads `certify_frames(test_media_dir)` and lists the item from
  `frames_record(test_media_dir)`: `shared` when the folder holds the file (`dir` set), else `bundled`, the same file as
  skellytracker's run. skellytracker has no public record of name, SHA-256, bytes and source beyond its report's
  `test_media`, so `frames_record` stays (a `shortcut:` comment). The gap: the frames are listed once the session child
  got them and did not answer `not-run` (`models-missing`), so a cancel while the session ran lists them, as a crash
  does. A crash record still lists none for a cancelled `posthoc-session`: its progress cannot tell whether the session
  had started. The pair quick check still passes no folder (skellytracker reads its own file).
- `f0ee7f4d` `package-in-use` (owner to review the wording): `REASON_TEXT['package-in-use']` "this app is still using its
  package; close FreeMoCap, start it again and run the removal before you use this EP". freemocap's install runs
  `eps.install` in a thread of the backend, so the backend process holds the package until FreeMoCap closes; a session
  or check on that EP registers it again in its process. Shown as "Remove of AMD GPU failed: this app is …".
- `81f0c18a` `shared_memory_bytes` reads `GpuInfo.shared_memory_bytes` directly (the `getattr` default dropped).
  `9970ddb5` docstring wording.

Isolated quick run on `9970ddb5` (the same code as `374638f4`; only a test changed) (scratch EP store, cache, base folder, logs, test media; RTX 3070 and UHD 770,
DirectML; the shared folder empty):

| Package | Checks | Results | Plan estimate | Seconds |
|---|---|---|---|---|
| freemocap | 7 | 4 pass (`posthoc-session` 9.0 s), 3 record-only (`build-identity` `modified-tree`, `install-facts`, `blender`) | 25 s | 10.0 |
| skellytracker | 11 | 11 pass: CPU video/live, DirectML on both GPUs, `mediapipe:smoke` 3.1 s; evidence valid | 48 s | 24.6 |

Both modules declare 1.6.0 and list `[{"name": "quick_frames.zip", "sha256": "a973456f…94c1f4", "bytes": 6215661,
"source": "bundled"}]`. skellytracker's summary ends with `{"group": "component", "name": "MediaPipe", "result":
"pass"}`; both `host.gpus` carry `shared_memory_bytes` 51208134656. The built file prints the GPU table, then `| Module |
Result |` with freemocap's seven rows and MediaPipe; the relay validator of the skellycertify working tree (with a peer's
uncommitted changes) gives rule 0. `%LOCALAPPDATA%\freemocap` and `%LOCALAPPDATA%\skellytracker` unchanged; no
`%LOCALAPPDATA%\skellycertify`.

`374638f4`: the crashed-pair test names `fake-ep` (the EP-knowledge guard refused `cuda` in a test).

Suites on `374638f4`: Python fast suite 1805 passed, 0 failed, 20 skipped (the race test passed; the first run on
`9970ddb5` had 1 failure, the guard above); UI `npx tsc --noEmit` clean, main run 246 of 247 with 1 skipped, plus 10 and
46. No OpenAPI or client contract change, so the client package did not run.

Next action: the owner reviews the `package-in-use` sentence and confirms the coordinator's reading of Q80.

Reading list: `../skellytracker-pin/skellytracker/certification.py` `certify`, `check_label`, `record_failed_pair`,
`certify_frames`; `core/eps/certification.py` `frames_record` (the fallback); `system/certify/quick_check.py` `_run`;
`freemocap/certification.py` `_frames_media`, `_posthoc`.

### Realtime session quick check, 2026-11-21

Owner's answer to Q57, relayed by the coordinator: the realtime quick check runs "in a fresh copy of the app started just
for the check, fed the bundled frames through a stand-in camera group"; the guard of `PubSubTopicManager.create` stays.
Tests and direct runs only, no real window, no frozen build.

- `ecc46563` `realtime-session`, the sixth of freemocap's eight quick checks (`module` and `component` item "Realtime
  session"), right after `posthoc-session`; the two run one after the other. The plan's `total` is 8; its
  `seconds_estimate` stays `QUICK_BUDGET_SECONDS` (25 s). The check starts only when `REALTIME_SECONDS` (10) fits what is
  left of the budget, else `not-run`/`over-budget`. `not-run` also for `models-missing` and `test-media-missing`;
  `fail` with `crashed`, `timed-out`, `hung-at-exit`, `session-failed`, `untracked` (new code: no frame after frame 0
  tracked) or an exception class name. `test_media` lists `quick_frames.zip` once when either session check used it
  (`interrupted_media` too).
- Fresh copy (start mode): `--certify-realtime [<test media folder>]`, an argument of `run_main` in
  `freemocap/__main__.py`, parsed before anything starts a server; it calls `certification.realtime_session_main` and
  returns. Dev: `python -m freemocap --certify-realtime` (`certification._app_command`: `sys.executable -m freemocap`).
  Built app: `freemocap_server --certify-realtime` (`sys.frozen`: `sys.executable` is the PyInstaller onedir executable,
  whose entry is `freemocap/__main__.py`; `freeze_support()` runs first, so the copy's own spawn workers re-enter as the
  backend's do). Started with `subprocess.Popen`, so `multiprocessing.parent_process()` is None in the copy. It starts no
  HTTP server, opens no port or camera, starts no Electron, reads no app settings and calls no `configure_logging`; its
  worker processes write their log files as any worker does (two files per run, seen in the scratch log folder). The
  copy prints one JSON line (the parent takes the line that parses as a result; `__main__` still prints `Done!` after
  it). Not tested in a frozen build.
- Stop: the parent closes the copy's stdin; the copy polls `_stdin_closed()` every 50 ms while it drives frames and ends
  its session itself, then `REALTIME_STOP_GRACE_SECONDS` (3 s) before a kill of its tree. A peek (`PeekNamedPipe` on
  Windows, `select` elsewhere), not a read: a thread blocked reading stdin stalled the copy's DLL loading (numpy's, at
  import; seen with `faulthandler`). The parent's death closes the pipe too. The copy calls
  `skellytracker.note_exit_requested()` after its session ended, since `__main__` ends with `os._exit(0)`, which skips
  the atexit removal of skellytracker's session marker.
- Stand-in camera group (`freemocap/system/certify/stand_in_cameras.py`): a subclass of skellycam's `CameraGroup` with
  its own `__init__`, one camera config (`CameraConfig`, `ImageResolution`) of the frames' size (720x1280), and the group
  shared memory from `CameraGroupSharedMemory.create(camera_configs, timebase_mapping=TimebaseMapping(), read_only=False)`
  (the call and layout of `CameraGroup._start`, 388 slots, about 1 GiB, 1.5 ms to create). Frames are written with
  `CameraSharedMemoryRingBuffer.put_frame` in a `create_frame_dtype` record, frame N at ring index N, as the test
  `MockCameraGroup` does. What skellycam lacks: a public constructor of a `CameraGroup` without its `CameraManager` (whose
  `create` makes camera workers), so the subclass sets `ipc.group_id`, `configs`, `shm`, `started` and `transport_error`
  itself. Not exercised compared with real cameras: capture, camera workers and their processes, the orchestrator,
  `frame_slot`/`commit_frame` writes, camera settings updates, frame pacing (frames go in lockstep), multi-camera
  grouping, recording.
- Session: `RealtimePipelineManager.create_pipeline` with `RealtimePipelineConfig()` (worker processes, RTMPose, Charuco
  on, Auto EP), `InferenceService` and `WorkerRegistry` as the backend makes them, `CaptureGroup` around the stand-in.
  Each frame is written once `get_latest_aggregator_output` gave the one before it. It passes once a frame after frame 0
  is tracked and stops at `REALTIME_TRACKED` (3) tracked frames; providers from `InferenceService.provider_status()`.
  The aggregator reads the latest calibration file when one exists, as the backend's session does (none in the scratch
  folder). Shutdown: `manager.shutdown()`, `service.close()`, `registry.shutdown_all()`, `group.close()` (unlink).

Measured (this PC: i7-14700K, RTX 3070, UHD 770; scratch EP store, so Auto chose CPU; other sessions' test runs were on
the PC at the same time):

| Run | spawn-child | posthoc-session | realtime-session (copy start, session) | Blender | freemocap total |
|---|---|---|---|---|---|
| 1 | 0.81 s | 10.03 s | 8.71 s (3.35, 5.35) | 0.59 s | 20.16 s |
| 2 | 0.82 s | 9.17 s | 8.48 s (3.01, 5.47) | 0.28 s | 18.77 s |
| 3 | 0.96 s | 9.84 s | 8.62 s (3.27, 5.35) | 0.25 s | 19.71 s |

Each run: realtime 4 frames, 3 tracked (frame 0 untracked), post-hoc 3 frames; `person` and `wholebody` on CPU in both
checks. 18.8 to 20.2 s against the 25 s share. Cancel (parent-side, from the cancel to `_realtime`'s return): 0.3 to
2.7 s with a clean end once the session runs; before the session (imports, worker start) the copy is killed after the
3 s grace, before any model loads. Session shutdown after a stop: 0.2 to 2.0 s. After each direct run no process of
this checkout's venv and no `--certify-realtime` process remained; the real test checks no new child process of the
test process. Shared memory: after a real session in a main process, none of the 9 shared memory names of the stand-in group could be opened, and no spawn worker was left with a dead parent.

Suites on `ecc46563`: Python fast suite 1824 passed, 0 failed, 20 skipped (19 new fast tests; the race test passed). UI `npx tsc --noEmit` clean; main run 246 of 247 with 1 skipped, plus 10 and 46.
The real check is the `slow` test `test_the_realtime_check_runs_the_apps_realtime_session_in_a_fresh_copy_and_leaves_no_process`
(8.5 s; passed); the real whole-module test stubs the realtime check to keep its time.

New text a user can read: `REASON_TEXT['realtime-session']` "a real-time processing session did not start and run on
this system" (owner to review); the component row "Realtime session" in the report file.

Not verified: the frozen build (the start mode, `sys.executable`, stdin pipe and PeekNamedPipe there), a real window, a
GPU EP run of the check (the marker path), Linux and macOS (the `select` branch).

Owner's calls: the reason sentence; whether the realtime check should also run when the post-hoc one used most of the
budget on a slow PC (today `over-budget`); whether `REALTIME_TRACKED` 3 is enough "run"; the aggregator reading the
person's latest calibration in the check.

Reading list: `freemocap/certification.py` `_realtime_session`, `realtime_session_main`, `_stdin_closed`, `_fresh_app`,
`_realtime` (the check); `freemocap/system/certify/stand_in_cameras.py` (what the stand-in sets and why);
`freemocap/__main__.py` `run_main` (the start mode); `freemocap.spec` (the frozen entry); `../skellycam-sfn26-pins/
skellycam/core/camera_group/camera_group.py` `_start` (the shared memory call it mirrors).

Next action: the owner reviews the sentence and the calls above; a frozen build runs the start check once.

## Next actions

All as local commits on `sidecar-implementation`, in this order:

1. Done: Electron's close (decision 31, `2a4c130d`). Still open: measure `POST /shutdown` to exit once an
   environment runs current freemocap, then set `SHUTDOWN_GRACE_MS`. The skellytracker call (32) is built
   (`efcd4774`).
2. Done: the hardware cleanup (decisions 6 to 8, `3cdf672f`). The ping keeps its payload keys; the benchmark
   snapshot keeps `available_memory_bytes` and `system_cpu_percent` (percent) and replaces the `load_average`
   list with `load_average_1m`; `psutil>=7.0.0` as skellycam declares it. `uv.lock` is not regenerated (it
   cannot be on the dev PC); that happens with the pin. Checked: the new expressions run in skellytracker's
   venv and match the old psutil/platform values; `test_machine_benchmarks.py` gives 9 passed, 4 failed both
   before and after the change, all four from the stale freemocap venv.
0. Dependency lockstep (user, 2026-11-19: before everything else, bump only what keeps freemocap in
   lockstep with skellycam and skellytracker; a wider bump to latest was made and undone the same day).
   Done in `69f2d2a5`, `pyproject.toml` only, not locked or run: exact pins polars 2.1.0, pydantic 2.14.3,
   numpydantic 2.0.0, psutil 7.2.2 (both), PyYAML 6.0.3, requests 2.34.2, pyinstaller 6.22.3 (skellytracker),
   msgspec 0.22.0, httpx 0.28.1 (skellycam), scipy-stubs ~=1.18.1. Sources: skellytracker `77e38399` (local),
   skellycam `dom/native-jpeg` `b761d31e2` (pushed fork). Open with the user: the two siblings disagree on
   opencv-contrib-python (skellytracker 5.0.0.93, skellycam 5.1.0.95) and numpy (2.4.6 against 2.5.5), so
   OpenCV stays unpinned here and `uv.lock` cannot resolve; and which skellycam branch freemocap builds
   against. The pin target of action 3 is a pushed skellytracker commit at or after `77e38399`, not `55fabf4a`.
   Siblings done the same day, each on a new local branch `dom/sidecar-implementation` of a new fork
   (`origin` = the user's fork, nothing pushed): `../skellyforge` `5dd7ab5` from `sfn26` (Python ==3.13.18,
   pyyaml, beartype; its `uv lock` fails, `../utils/skellylogs` is not cloned) and `../skellysync` `b4e129c`
   from `philip/rewrite` (Python ==3.13.18, pydantic, scipy, extras; resolves with both numpy/OpenCV
   candidates; librosa 0.10.1 kept, not run under numpy 2). Open: freemocap still sources skelly_synchronize
   from upstream `philip/rewrite` (Python <3.13), so its lock cannot resolve until the source points at the
   new branch (needs a push or a path source). The Blender addon, skellylogs and skellypings need no change.
   Later the same day: skellytracker moved to skellycam's numpy 2.5.5, opencv-contrib-python 5.1.0.95 and
   platformdirs 4.14.7 (its local `e7ce3409`, ADR-F9QR, read on disk), so that conflict is closed; freemocap
   pins OpenCV 5.1.0.95 (`a4e27293`), skellyforge numpy (`18c77d8`), skellysync both with its lock (`4f17591`).
   freemocap sources skelly_synchronize from `../skellysync` for now (`558a765c`, user); CI has no such path.
   Platform fact (skellytracker-6c, not checked here): the macOS wheel of OpenCV 5.1.0.95 is
   `macosx_15_0_arm64`, so macOS 13 and 14 get no wheel.
3. When skellytracker's CI on `55fabf4a` is green, macOS included: pin it and regenerate `uv.lock` (decision 1).
   Right after the pin: the preprocess benchmark ([migration state](skellytracker-2-migration.md) item 9),
   and the EP menu switches from `PackStatus.usable` to the per-GPU `checks[n].usable` (decision 17):
   done in `4a5d3da2`, built on the pin `4dcf2a66` shape.
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
| skellycertify `relay/README.md`, "Answers for the app developers" | Relay routes, the error table with `retry`, limits and the send rules |
| `freemocap/system/certify/relay.py`, `freemocap/api/http/certify/certify_router.py` | How a hand-in is built, kept, sent, retried and marked today |
| `freemocap/core/tracking/execution_providers.py`, `freemocap/api/http/onnx/onnx_router.py` | Today's EP calls and routes |
| `freemocap-ui/src/hooks/useExecutionProviderOptions.ts`, `src/services/server/execution-providers.ts` | How the EP menu filters rows today (on `usable` only) |
| `freemocap-ui/electron/main/services/python-server.ts`, `electron/main/index.ts` | The shutdown defect |
| `freemocap/system/telemetry/telemetry.py`, `freemocap/tools/machine_benchmarks.py` | The hardware cleanup targets |
| `freemocap/build_info.py`, `.github/workflows/build-installers-pyinstaller.yml:185-211` | Where the version, commit and tree state come from in a frozen build |
| [skellytracker-2-migration.md](skellytracker-2-migration.md) section 0.2 | The migration this work sits on |
