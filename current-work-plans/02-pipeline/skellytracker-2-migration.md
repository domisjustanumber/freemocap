# freemocap → skellytracker 2.0.0 (`pipelines` and `detectors`)

Branch `sidecar-implementation`, made from `upstream/sfn26` at freemocap `ca0c17cc`. Its skellytracker
pair is `upstream/sfn26` at `2d356a6c`.

The contract:
- `../skellytracker/specs/pipeline/`;
- the headings 1.6, 1.10 and "freemocap migration" of
  `../skellytracker/specs/sidecar-implementation-plan.md` (branch `dom/sidecar-implementation`).

The first design, for `development-streaming`, is on the local branch
`sidecar-implementation-dev-streaming`.

Status: see §0, written for the handoff to new sessions on 2026-11-16. §1 and §2 are the Phase A
inventory and design: their line numbers are for `ca0c17cc`, and "ST" means skellytracker `sfn26`
`2d356a6c`. Paths are relative to `freemocap/`, except where they start with `./` (the repo root).

## 0. State at the handoff (2026-11-16)

Phase B has started. All work is in local commits on `sidecar-implementation`; nothing is pushed.
The skellytracker pair of Phase B is `dom/sidecar-implementation` at `abcfa9ce` (pipeline API
gate). The supervisor is the skellytracker session; the user decides the product questions.

### 0.1 Done (commit groups, oldest first)

| Group | Commits | What |
|---|---|---|
| Phase A docs | `5322e23f`, `f2302431`, `1804a2f0`, `dcd44a6e`, `eb09c7bc`, `0f8be36c` | inventory, design, baseline, removal list, mapping design |
| 1: removal of four detector choices | `765ac887` backend, `4f1cd681` tests, `088b3a91` UI/SDK, `49fa88e2` generated contract and SDK | `rtmw_mediapipe_hands`, `mediapipe_hands`, `rtmw_onnx_hands`, `dlc` (list: `skellytracker-2-removal-list.md`) |
| 2a: mapping package | `d97e797f` copy from ST sfn26 `2d356a6c41f831484251677050fafb2576193060`, `0bdb052b` callers | `freemocap/core/mapping/` with the OLD tracker names in its YAMLs |
| Phase B step 1: dependencies | `296ddebb` | Python `==3.13.18`, `skellytracker[mediapipe]`, `beartype==0.23.1`; no ORT variant extras, groups, NVIDIA index, overrides or Intel Mac. **No `uv.lock`** (§0.4 U1) |
| Phase B step 2, partial | `c8275d18` | `core/tracking/pipeline_runs.py`: detector → built-in key, RTMW size map, EP choice from `core.eps`, start of a run; not called yet |
| Phase B step 2: run model | `c5745e7f`, `a8d88985`, `da1457c4` | one `PipelineRun` per client; per-camera ms; the boundary `observations_from_results`; v2 EP keys; V2 stop |
| Phase B step 3: charuco | `750fc8f2` | `core/tracking/charuco_detection.py` through `create_detector`; calibration and the recording graph take a board |
| Phase B step 4: mapping 2b | `ec9b3b5d` | the three re-keyed YAMLs; names and edges from the run schema (`detector_point_names`, `detector_connections`) |
| Phase B step 5: old API removed | `c5be62ed`, `46e9a55d` | tracker factory, provider policy, per-camera inference, generated recipes, contract, spec, CI install |
| Phase B step 6: old-recording reader | this commit | a restart from saved `body.<point>` (skellytracker 1) observations raises `SkellytrackerOnePointNamesError`; old 3D results stay readable through their own snapshot |

State (2026-11-16, session after freemocap-5d). Committed: `1f532a77` F1 (MediaPipe settings Holistic
ignores: configs, UI incl. the dead `MediapipeConfigPanel`, contract delta, e2e; client `npm test`
131/131, realtime-processing 34/34, Playwright skeleton-detector-options pass), `fd7b629f` F2 (one
installer variant, no R2 in the installer workflow, docs page without variant picker; YAML parses,
docs `tsc` passes, no CI run), `d00da9d9` realtime replay test over `preset` rtmpose/mediapipe +
TESTING.md. Local only: `cbor-x` is missing in `freemocap-ui/node_modules` (install problem, not code).

Next, in order (supervisor, 2026-11-16; ST R1 to R6 = `55b6cd01`, `402c8838`, `a7e591ac`, `654c92b6`
on the local `../skellytracker` `dom/sidecar-implementation`):
- A. DONE `de80869e` (scratch ST clone detached at `68591617`). Holistic is a `3d` output (its z is
  kept); RTMW `2d` gets z 0; an absent row 0 is all NaN, score 0; `detector_connections` =
  `canonical_edges` for both (Holistic canonical_names == point_names). Fast suite on the Phase B env
  (`-m "not e2e and not slow"`, PYTHONPATH = checkout): 1508 passed, 8 failed (the 7 baseline +
  `test_observation_imports`, as at the handoff), 20 skipped, 43 deselected. Was: `InstanceKeypoints`/`CanonicalKeypoints` have `xy`
  `(I, P, 2)` float64 (missing = NaN), `z` `(I, P)` for 3D or `None` for 2D, read-only `geometry`
  ("2d"/"3d"); `xyz` and `by_track()` are gone; `instance()`/`single()` give keys `xy`, `z`; read
  person row 0 after checking `present[0]`. Camera result: `image_width`, `image_height` (ints).
  Output schema: `canonical_edges` (`[name, name]` pairs) replaces the `shortcut:` rename in
  `detector_connections`; expect 65 (yolox-rtmw-wholebody) and 213 (mediapipe-holistic-tasks). New
  rtmw-wholebody133 sidecar sha256 `7d69257a...`, `estimator_type: top_down`; ONNX unchanged.
  Possible renames (undecided; one import each, do not wait): `CallRefused`→`CallRefusedError`,
  `SetParamsRefused`→`SetParamsRefusedError`, `find_pipeline`→`get_pipeline`,
  `CanonicalKeypoints.names`→`point_names`.
- B. Inventory reported to the supervisor (130 CODE + 44 DOC entries: backend 43, UI 25, electron 10
  (both files dead: `dependency-manager.ts`, `system-scanner.ts` are imported nowhere), contract 19,
  tests 33). Gaps for skellytracker: no usable flag per `PackStatus` (`USABLE_STATES` not exported),
  no install hint per EP (`install_hint` private), no applied EP per model of a run
  (`PipelineRun.models` has no used_ep; freemocap makes it up in `inference_service.py:161`), no GPU
  flag per EP, no documented order of `EpStatus.eps`, no devices in `status()`. Also: Auto drops
  `EpRecommendation.options` and `device_key` (`pipeline_runs.py:62`).
  ANSWERS (supervisor, 2026-11-16): skellytracker fills gaps 1 (usable flag), 2 (install hint),
  4 (GPU flag), 5 (stated order of `EpStatus.eps`) and 3 (per model node: applied EP, device,
  precision); names come in a later message, code against them only then. Gaps 6 (devices) and 7
  (description) are NOT dropped (§0.3): skellytracker fills them too, in part 2.
  Until then: no new import of `USABLE_STATES` from `eps.records`, no call of private `install_hint()`.
  `/onnx/session_providers` stays untouched until gap 3; the made-up `applied_providers` at
  `inference_service.py:161` **waits for gap 3**.
  - Part 1 progress: (i) DONE `c4c158fe`; (ii) DONE `f915bc50` (`run_ep_choice` returns key, options,
    device; `run_execution_provider` is a wrapper for `application_pipeline`; 53 passed in
    test_pipeline_runs, test_inference_service, test_execution_providers, test_dataflow_tracker_adapter).
    `freemocap-ui/tsconfig.node.json` has a pre-existing TS deprecation error (`moduleResolution=node10`),
    not from this work.
    PART 1 DONE (2026-11-16, §0.6 items 1, 12-14): (iii) `ab15c4e7` host probes (log fields
    `HOST_FIELDS`/`GPU_FIELDS` in `app/app.py`, printed only when the record has them; workflow prints
    `skellytracker-eps status`); (iv) `de6be21a` `graph_execution_provider` gone; (v) `c9a58321` EP key
    is `str | None` everywhere, `run_ep_choice` passes any key but None/"auto" to skellytracker, which
    raises `EpRequestError` (message reaches the UI through `_record_startup(..., str(error))`); (vi)
    `57be4131` `pipeline_runs.detector_takes_execution_provider` (cached `check_pipeline`), a pipeline
    with no EP ignores the saved choice (no refusal; reversible if the supervisor wants one); (vii)
    `c0f66701` `/onnx/execution_providers` → `{available: [{key, label}]}` from
    `usable_execution_provider_rows()` (status order; still the existing `USABLE_STATES` import), UI
    `ExecutionProviderName = string`, no table; help texts kept. Device list plan for part 2: the same
    route gains `devices: [{key, name, vram_total_bytes}]` per EP from the part 2 names, and the EP row
    gets a device select under it when an EP has more than one device; (viii) `74e91d12`
    `test_no_execution_provider_knowledge.py`, allowlist = 9 part-3 tool lines (named in the test).
    Fast suite after part 1 (Phase B env, `-m "not e2e and not slow"`): 1507 passed, 8 failed (the same
    8 test ids as at `de80869e`), 20 skipped, 43 deselected. Then `59f55e9a` (§0.3 E1): its files pass.
    Tests: per step the touched files pass; UI tsc only the 4 `cbor-x` errors (rebuild the client
    `dist/` with `npm run build:client` after a contract change, it was stale); UI EP options 4/4,
    realtime-processing 34/34. Next: part 2 waits for the supervisor's message with the final
    skellytracker commit and names; part 3 (tools, docs) after it or when told.
  - Part 1, its own commit groups with tests:
    (i) delete the dead `freemocap-ui/electron/main/services/dependency-manager.ts` and `system-scanner.ts`
    (own commit);
    (ii) FIRST, with a test, Auto = `status().performance.chosen` and pass `options` and `device_key`
    to `start_pipeline(ep_options=..., device=...)`;
    (iii) OWN COMMIT GROUP, host probes dropped (§0.3):
      - `freemocap/app/app.py`: delete `_query_nvidia_smi`, `_query_wmic_gpus`, `_query_lspci_gpus`,
        `_query_macos_gpus`, `_detect_gpus`, the `onnxruntime.get_available_providers()` read and the
        "GPU acceleration" string-match verdict. One startup log call: hardware lines from
        `skellytracker.core.system.probe_host()` (`HostInfo`: OS, arch, `memory_total_bytes`, `cpu_name`,
        core counts, `gpus` with `name`, `vendor`, `vram_total_bytes`, `driver_version`), EP lines from
        `skellytracker.core.eps.status()` (each `eps[i].key`, `.state`, the `performance`
        recommendation). Print what the records give; no vendor or EP formatting rule.
      - `freemocap/tools/machine_benchmarks.py` `machine_info()`: drop nvidia-smi, PowerShell
        `Get-CimInstance`, `system_profiler`, `get_available_providers()`; write
        `dataclasses.asdict(probe_host())` + EP keys and states of `status()`. `render` reads the CPU
        name and memory from `cpu_name`/`memory_total_bytes`; old benchmark JSON must still render.
      - `.github/workflows/build-installers-pyinstaller.yml:210`: replace the
        `ort.get_available_providers()` print by the skellytracker EP CLI status command (check its form
        in the scratch clone), or delete the step if it only prints.
      - Docs `gpu-setup.mdx` and `architecture/backend-overview.mdx:85` go with part 3.
    (iv) delete the dead `graph_execution_provider` Literal (backend, contract, UI);
    (v) contract EP types become plain strings; delete the Literal key list, `EXECUTION_PROVIDERS`,
    `REMOVED_PROVIDERS` and the validator; an unknown key gives skellytracker's `EpRequestError`, show its
    message;
    (vi) the mediapipe rule uses `check_pipeline(...).needs_execution_provider`;
    (vii) the UI gets keys and labels from the backend route at run time: no union type, label table or
    order table; KEEP the GPU/CPU help-text places as they are until part 2 gives the description
    field, and plan a device list in the EP setting;
    (viii) a test that fails when a source file under `freemocap/` or `freemocap-ui/src/` holds an EP
    key literal (`cuda`, `trt-rtx`, `coreml`, `directml`, `trt`), an ORT provider name
    (`*ExecutionProvider`), or names `nvidia-smi`, `wmic`, `lspci` or `system_profiler`; allowlist empty
    or justified line by line.
    Report to the supervisor after part 1.
  - Part 2, after the supervisor's message: usable flag, install hint, GPU flag, order, description,
    devices (UI device list: key, name, VRAM), the applied EP of `/onnx/session_providers`, and the
    `app/app.py` probe per the verdict.
    Also (supervisor, 2026-11-16): the server sends "takes an EP" per detector (from
    `pipeline_runs.detector_takes_execution_provider`) and the UI shows the EP row from that flag; remove
    the two detector-name checks (`detector-setting-rows.tsx:111`,
    `realtimepipeline-mediapipedetector-settings.tsx:73`); reword the comments
    `realtime_skeleton_inference_node_config.py:8` and `pipeline_runs.py:73`; saved retired keys per §0.3
    E2 (the user's choice for a key that cannot be honoured, Auto with a notice or fail at start, comes
    with the part 2 message). Confirmed: 57be4131 (ignore the EP choice for a pipeline with no EP).
    Done early (part 3 docs, allowed): `gpu-setup.mdx` "How GPU Detection Works" and
    `backend-overview.mdx:85` no longer name nvidia-smi; the rest of those pages stays for part 3.
  - PART 2 MESSAGE (supervisor, 2026-11-16): ST local `c4b51dde` (one more commit follows: RTMW sidecar
    with face edges, `source.version` 0.3.0, new hash, RTMW `canonical_edges` 130: read counts from the
    schema, never pin 65). Names: renames without alias `CallRefused`->`CallRefusedError`,
    `SetParamsRefused`->`SetParamsRefusedError`, `find_pipeline`->`get_pipeline`,
    `CanonicalKeypoints.names`->`.point_names`. `PackStatus` (`eps/records.py:197`): `usable`,
    `install_hint` (sentence or None), `uses_gpu`, `description` (one sentence), `devices`
    (`RunDevice`: device key, name, `vram_total_bytes`; most VRAM first). `EpStatus.eps` order = catalog
    preference order, show as given (Auto = `status().performance`). `PipelineRun.models[node]` = key,
    version, sidecar_sha256, size, precision, execution_provider (applied), device (key, list or None).
    OOM in a call: `VRAMExhaustionError`, run closed, later calls `RunClosedError`; show message, new run.
    `HostInfo.cpu_max_frequency_hz`; Linux GPU names and macOS VRAM now in `GpuInfo` (§0.6 item 12
    losses gone). Work order: part 2 (drop `USABLE_STATES`; route gives key, label, description, usable,
    install_hint, uses_gpu, devices; UI help from `description`, delete `EXECUTION_PROVIDER_INFO` and the
    "GPU batched"/"CPU-only" texts, show `install_hint` when not usable; device select when >1 device;
    `/onnx/session_providers` from `PipelineRun.models`; "takes an EP" flag per detector; two comments),
    then R1 block (accepted + `stage_settings` fix + test of a recording without the block; no re-run UI),
    then R2 (accepted; `settingsVersion: 1`; run button waits for the suggestion). Legacy call contract
    (not built; fake it in tests): saved key -> key or None; legacy trt/cuda -> trt-rtx if usable else
    cuda if usable else None; other usable key -> same; unusable or no successor -> None = Auto + notice.
    Report after each.
  - PART 2 DONE (2026-11-16): `47d684cd` rename `CanonicalKeypoints.point_names` + edge count read
    from the schema; `d97932ff` `PackStatus.usable` (no `USABLE_STATES`), route
    `{providers: [{key, label, description, usable, install_hint, uses_gpu, devices}],
    detector_takes_execution_provider}`, UI help from `description` (`execution-provider-info.tsx`),
    `/onnx/session_providers` = `PipelineRun.models`, `cpu_max_frequency_hz`, the two comments, the
    third detector-name check in `RealtimePipelineConfigTree.tsx`; `f844f90c` device choice. Tests:
    touched Python files pass; UI tsc only `cbor-x`; UI 37/37 realtime-processing, 4/4 EP options. The
    two e2e specs whose fixtures changed cannot run here (local node_modules lacks
    `@fontsource-variable/*` and `@axe-core/playwright`; same failure without the change).
    Found: posthoc Auto is resolved to a bare key in `resolve_tracking_provider` before the run, so
    the posthoc run drops the recommendation's options and device; fix in the R1 group.
  - R1 DONE (2026-11-16) `604b7de2`: `start_detector_run` returns `(run, record)`; record =
    `{pipeline: export_pipeline(config, resolved=True), running_mode, execution: {selected,
    selected_device, requested, options, device}}`, the inference client adds `models` (=
    `PipelineRun.models` at start) as `InferenceClient.run_record`; the adapter hands it to
    `recording_pipeline`, which writes `definition["skellytracker"]` (fresh tracking only) and
    `execution.requested_provider` from it. `stage_settings` OBSERVATIONS = detector_type,
    rtmpose_model_name, rtmpose_confidence_threshold, execution_provider, execution_device,
    skellytracker, charuco fields; the "requested providers" limitation is gone (RECORDING_CONTRACT.md
    updated). Posthoc Auto now reaches the run as None (`resolve_tracking_provider`), so the run takes
    the recommendation with options and device; `run_execution_provider` deleted;
    `build_recording_pipeline(execution_provider: str | None = None)` (beartype refused None).
    Tests: `test_recording_pipeline.py` block written + recording without the block restarts; real run
    record test in `test_pipeline_runs.py`. Fast suite: 1514 passed, the same 8 failed, 20 skipped.
    Scratch ST clone then moved to `b8bfa7d2`: 130 RTMW edges (65 face); one test_data frame
    (Cam1, frame 100) annotated: face lines drawn, yellow like the face points, 1 px, mostly under the
    point dots at that face size (11 px differ from the same annotation without face edges).
  - R2 DONE (2026-11-16) `288deb48`, scratch ST clone at `de7e18f3`: `MOCAP_SETTINGS_VERSION = 1`
    written into `freemocap:mocap.config` on every save (`persistence-listener.ts`); at load
    `takeLegacyExecutionProvider` holds back the EP key of a config without it
    (`mocap.executionProviderMigration` pending, config Auto meanwhile); while pending nothing is saved
    and `selectCanProcessMocapRecording` is false; `legacy-execution-provider-listener.ts` asks
    `GET /onnx/execution_providers/suggestion?saved=` on connect/reconnect, which calls
    `skellytracker.core.eps.suggest_execution_provider`; `legacyExecutionProviderResolved` applies the
    key or Auto, the notice in `mocap-detector-settings.tsx` names both (and the install hint of a
    suggested EP that is not usable, ready for the open "usable = pack installed" question); a choice
    by the user while pending ends it. Realtime settings are not persisted: nothing legacy there.
    Next: V3 (smaller face points).
  - Part 3: the tools (an EP key as a free string, skellytracker refuses a bad one; a matrix takes its
    keys from `status()`), then the docs (41 files: remove EP lists, link to the skellytracker EP docs
    or the in-app list). `bench_*.py` and `experiments/` stay untouched (F3).
  - Then the gate runs, once.
  EP rule (§0.3): inventory every EP key / ORT provider name (path:line) with a sub-agent; report
  the count and each UI need that `skellytracker.core.eps` does not give (do not work around); then
  implement. This replaces the fixed keys of step 1 and the `trt-rtx` fix of (a): delete those
  literals. (b) the Playwright "Apply sends selected settings" `camera.skeleton_tracker_config`
  check still has to go.
- C. DONE `b5a5570c` (channel-file fix), `1dd00942` (rename; docs `fileLabel(os, version)` keeps the old
  labels up to alpha.26). No copies (F2b). Facts: the updater is the
  GitHub provider (`freemocap-ui/electron-builder.json:105-109`), no channel, no feed URL, the same
  for every variant. Installs read `latest.yml`/`latest-linux.yml`/`latest-mac.yml` of the newest
  alpha tag and download the `url` named inside (only sha512 and size are checked). Old `-cuda`
  installs read the same GitHub files (the R2 `latest-linux-cuda.yml` was never read), so no R2 upload.
  BUG: the rewrite seds (`build-installers-pyinstaller.yml:555,572,581`) match lowercase `freemocap_`
  but the files start with `FreeMoCap_`, and `.deb` is never rewritten, so alpha.15/21/26 channel
  files name assets that 404. The mac name must keep `arm64` (MacUpdater filter). Versioned old links
  cannot be pointed at a new file. Plan: labels at `:28,:36,:44` + `update-metadata-*-cpu` dirs
  `:551,552,578,579`; case-insensitive seds + `.deb` + a guard that every `url:`/`path:` is an asset;
  docs `downloads.ts` `fileLabel` picks the old label for releases that have `_windows-x64-cpu.`.
  Was: Installer names lose `-cpu` (`windows-x64`, ...); old `-cpu` and `-cuda` installs must update to
  the new file and old links must lead to it. First report the auto-update mechanism and the plan as
  path:line facts; do not publish or upload anything.
- Then the gate runs, once.

Gate plan (accepted by the supervisor): `test_data` only, `numerical` profile, prepared root in this
session's scratchpad, no model download (the ONNX are hard links in the scratch clone's
`core/model_zoo/`). A: `python -m freemocap.tools.datasets process test_data --from observations
--tracker-preset <rtmpose|mediapipe> --calibration existing --output-profile numerical
--prepared-root <scratch>/prep-<det>`; B: `pytest
freemocap/tests/reference_recordings/test_realtime_pipeline.py -k "human-<det> and test-data"` with
`FREEMOCAP_PROVENANCE_PREPARED_ROOT=<scratch>/prep-<det>`. Both with `phasebenv313` and
`PYTHONPATH` = this checkout.

Handoff state of freemocap-5d (2026-11-16): the suite on the Phase B environment, with `PYTHONPATH` set to
this checkout, is 1503 passed, 8 failed, 21 skipped (39 deselected). 7 of the failures are the
baseline ones. `test_observation_imports` fails only because its child runs `python -I`, which imports
the freemocap of `phaseb\venv313` (the scratch clone at `0bdb052b`); it passes when that clone is at
this branch's HEAD. The beartype 0.23.1 check (step 6 of the list) is covered by that run: no
decoration error. Next: the R1 to R3 and R4 to R6 boundary commit when skellytracker sends its commit;
the user's answers on the MediaPipe settings, the installer variants and `bench_*.py`/`experiments/`;
then the real end-to-end runs of the gate.

Test counts:

- **Baseline:** freemocap `ca0c17cc` with ST `2d356a6c`, Python 3.12.13 = 1572 passed, 15 failed,
  31 skipped (`skellytracker-2-baseline-sfn26.tsv`; §4a).
- **After groups 1 and 2a**, in the same environment: 1602 passed, 15 failed (the same 15),
  23 skipped.
  - The 8 `test_sidecar_factory_contract` failures pin the old session contract and go with it.
- **On the Phase B environment** (Python 3.13.18, ST `abcfa9ce`), the current code cannot import:
  it still uses the old API (`keypoint_detectors.charuco`, `sessions.shared_sessions`). Only
  `test_pipeline_runs.py` runs there (4 passed). The full suite is the gate of Phase B.

### 0.2 Next: Phase B steps 2 to 6 (the supervisor's order)

2. **The run model.**
   - One `PipelineRun` for each realtime camera group (`live`, one float `timestamp_ms` for each
     camera from that camera's `(pre + post grab) / 2`, the source frame number as
     `frame_index`) and for each posthoc recording (`video`, the recording timestamps).
   - `rtmpose` → the RTMW built-in with the size map; `mediapipe` → the Holistic built-in.
   - freemocap's own result type at ONE boundary function. **It waits for S2.**
   - The 0.4 gate on RTMW points: test x and y only, because z is NaN for a 2D output.
   - `person_roi` clipped to whole pixels (clip, then `int()`).
   - `DETECTOR_RAN`, the colour and `object_detector_runs` from `node_ran["person"]`.
   - The UI EP keys become `cpu`, `coreml`, `cuda`, `trt-rtx`.
   - `InstanceKeypoints.image_size` is `(width, height)`; the old one was `(height, width)`.
   - Map points by NAME only: the RTMW column order differs from sfn26 (§0.5).
3. **Charuco.** Use `create_detector("charuco@skellytracker", board=...)` and the helpers of
   `skellytracker.core.detectors.calibration`. `with_charuco_tracker` leaves the recording graph.
4. **Mapping step 2b.** The re-keyed YAMLs replace the old-name files: `rtmw_body_to_standard_human.yaml`
   keyed on the canonical names, `mediapipe_holistic_body_to_standard_human.yaml` keyed on the
   Holistic `body/<name>` names, and one `hand_to_standard_human.yaml` (§6.2).
5. **Delete what is left of the old API.**
   - the presets, `tracker_profiles`, the sessions and `InferenceService`;
   - `max_consecutive_misses`, and the 30 fps constants where timestamps or the run parameter
     `fps` replace them;
   - the field `pipeline_implementation`;
   - `use_centralized_inference=False` and its `camera_node.py` branches;
   - the stale hidden imports and the NVIDIA `collect_all` of `freemocap.spec`;
   - the CI install steps that name the removed `cpu`/`cuda` groups.
6. **The reader for old recordings**, with the clear errors (§6.3; `saved_observations.py`
   already names a removed detector).

The gate of Phase B is the freemocap suite on the Phase B environment, reported per file against
1602/15/23, plus real end-to-end runs: one posthoc recording and the realtime path on recorded
frames, each with `rtmpose` and with `mediapipe`.

### 0.3 Decisions of the user (all 2026-11-16, through the supervisor)

- Base on `upstream/sfn26` at its tip `ca0c17cc`.
- Only `rtmpose` and `mediapipe` are migrated. The four other choices are removed; they come back
  later from `sfn26`.
- `rtmpose` → `yolox-rtmw-wholebody`. skellytracker made the built-in match the sfn26 box
  behaviour:
  - a redetect every 150 frames, and after a lost person;
  - the One Euro box;
  - the output `person_roi`.
- `mediapipe` → `mediapipe-holistic-tasks`: another model, a 478-point face, no hand crops and no
  reset.
- freemocap owns the tracker → standard-human mappings. They are applied to 3D. One package for new
  and old recordings.
- Old recordings stay readable through a read-only reader.
- Drop Intel Mac. Python 3.13.18 with the exact skellytracker pins; `beartype==0.23.1`.
- Keep the detector-ran colour, column and metric, from `node_ran`.
- Charuco through the public surface only: `create_detector` and `detectors.calibration`. The board
  selector, the tag constants and `CHARUCO_BOARD_MAPPING` were ported into skellytracker.
- No merge of development-streaming into skellytracker.
- V2 (2026-11-16): keep the stop. A camera video that fails while it is read stops posthoc tracking
  with freemocap's own error (`CameraSourceEndedError`, with the camera and the frame), because a
  `video` run takes a frame from each camera on each call (ST `V-pipeline.running-2`).
- Result API revisions R1 to R3 (2026-11-16), changed in skellytracker; freemocap follows in
  `pipeline_runs.observations_from_results` only, when the skellytracker commit lands:
  - R1: a keypoints value has `xy` `(I, P, 2)` always and `z` `(I, P)` only for a `3d` output, and
    carries `geometry`. A missing point is "xy is NaN". The `xyz` array with NaN z goes.
  - R2: `by_track()` is deleted (freemocap does not call it).
  - R3: the camera result gives `image_width` and `image_height`; the tuple `image_size` goes.
- Result API revisions R4 to R6 (2026-11-16), changed in skellytracker after R1 to R3:
  - R4: the sidecar value `keypoint.estimator_type` becomes `top_down` or `bottom_up`. No code
    change in freemocap; the rtmw-wholebody133 sidecar hash and the built-in pipeline pins change.
  - R5: the point names do not change. Take a point by name or by `groups`, never by a fixed column.
    An old-to-new name table for the old-recording reader is freemocap's own data.
  - R6: a keypoints output schema gets `canonical_edges` (the `edges` in canonical names; an edge
    with a point that has no canonical name is left out). When it lands,
    `pipeline_runs.detector_connections` becomes one dict read and its `shortcut:` goes.
- EP rule (2026-11-16): "FreeMoCap must not keep any knowledge of Execution Providers. It uses the
  new API surface of skellytracker to populate the available options, and it sets the recommended
  and auto options from the suggestions of skellytracker." No EP key list, display names, ordering,
  GPU or platform test, or precision rule in freemocap code, UI or contract enums; the source is
  `skellytracker.core.eps` (`status()`, `recommend(form)`, `run_devices`, `check_start`); Auto = the
  `performance` recommendation; the contract type is a string. Replaces the fixed keys of step 1.
- EP devices and descriptions (2026-11-16): gaps 6 and 7 are NOT dropped. The UI shows the devices as
  skellytracker reports them (key, name, VRAM in the EP setting; no device knowledge in freemocap),
  and skellytracker adds a short description per EP that the UI shows. Both fields come with the
  supervisor's part 2 message.
- Host probes (2026-11-16): "the user wants nvidia-smi dropped, and WMIC, lspci and system_profiler
  dropped when they only find information that skellytracker gives". Verdict (supervisor, same day):
  drop all of them; each only finds values skellytracker gives, and none feeds a decision, a route,
  the UI, telemetry or a test.
- F2b (2026-11-16): no copies. New releases ship without installer copies under the old `-cpu` and
  `-cuda` names; existing installs update through the channel files.
- F2 revised (2026-11-16): the installer names drop `-cpu` (`windows-x64`, ...); old `-cpu` and
  `-cuda` installs and links must lead to the new file.
- F1 (2026-11-16): the MediaPipe settings that do nothing for Holistic leave the settings and the UI:
  model complexity, the detection, presence and tracking confidences, and `num_faces`
  (`mediapipe_num_hands`, fixed at 2, stays). A saved settings file that still has them loads, and
  they are not written again. This removes the import of the old `mediapipe_model_manager` (§0.7).
- F2 (2026-11-16): the installer builds one variant; the `cuda` variant goes (matrix, names, docs). GPU
  EPs come from the skellytracker EP packs at runtime. `cuda` stays as an EP key.
- F3 (2026-11-16): leave `bench_final.py`, `bench_inference.py`, `bench_redetect.py`, `bench_tracker.py`
  and `experiments/executable_graph_lab/` untouched: not ported, not deleted. They **do not run on
  skellytracker 2.0** (they import the old API).
- F4 (2026-11-16): freemocap accepts RTMW with no face lines for now, and draws none itself. The exporter
  gets a request for face edges in a fresh export; when that sidecar lands, the lines come back through
  `canonical_edges` with no freemocap change (§0.6 item 6). DONE with skellytracker `b8bfa7d2`
  (`rtmw-wholebody133` 0.3.0, new sidecar hash, same ONNX).
- U1 (2026-11-16): the user moves the skellycam OpenCV pin and the skellyforge Python cap themself,
  separately. The freemocap `uv.lock` stays uncommitted until then; tests run with the two pins relaxed
  in scratch.
- E1 (2026-11-16, correction): a saved `graphExecutionProvider` keeps its meaning. On `sfn26` the run
  used `execution_provider or graph_execution_provider`, so a file with only
  `graphExecutionProvider: cuda` ran on CUDA; `de6be21a` made it Auto, a regression. Fixed in
  `59f55e9a`: at load, when no `executionProvider` is saved and the saved `graphExecutionProvider` is not
  `auto`, its value goes to `execution_provider`; when both are saved, `executionProvider` wins (no
  "disagree" error); the old key is not written again. It copies a string, no EP knowledge.
- E2 (2026-11-16, correction): a saved `trt` maps to `trt-rtx` when `trt-rtx` is usable on this host.
  freemocap does NOT hold that mapping: skellytracker gives it through the EP API (a retired key gives
  its successor key with its usable state; names come with the part 2 message). Until then the run start
  fails with skellytracker's message, as now. REPLACED by R2 and G1-G3 below.
- R1 (2026-11-16, user, NOT implemented yet; report first): "FMC must save the pipeline config in a
  saved processing config of a recording, as well as the selected EP." Supervisor's reading: the saved
  processing config of a recording holds (a) the pipeline that ran: key, version and the full config as
  skellytracker exports it (`skellytracker.core.pipelines.export_pipeline`: JSON types, `schema_version`,
  `pipeline_id`, `source`, nodes with params and each `onnx_model` node's `sidecar_sha256`), with the run
  parameters freemocap set (size, thresholds, fps, running mode); (b) the EP the user selected (also
  Auto) AND what ran: per model the applied EP, device, precision and size, with key, version and
  sidecar_sha256 from `PipelineRun.models` (applied fields come with part 2). Goal: a recording says
  exactly how it was processed and can be processed again the same way. Stored as skellytracker gives
  it, as data; no EP or pipeline knowledge copied into freemocap.
- R2 (2026-11-16, user): "If loading a legacy settings file, trt or cuda must suggest trt-rtx if
  supported on the current hardware, else suggest cuda." The rule lives in skellytracker: one EP API call
  takes the saved key and returns the suggested key or None (name with the part 2 message); freemocap
  calls it only for a legacy file and holds no key list.
  - G1: "suggest" = apply with a notice. The setting loads as the suggested EP; the UI shows which saved
    key was replaced and by which.
  - G2: a choice made in the new freemocap stays as chosen (a new `cuda` stays `cuda`, also where
    `trt-rtx` works). Only a file with no new-format marker is legacy, so new saves carry a marker.
  - G3: no usable suggestion, or a legacy key with no successor (`directml`): the setting becomes Auto,
    with a notice.
  - Built in `288deb48` against `suggest_execution_provider` (ST `de7e18f3`). OPEN with the user: "usable"
    = pack installed, so on an RTX machine without the pack a saved `trt`/`cuda` becomes Auto; the notice
    can already carry the install hint of a suggested EP.
- S2 (2026-11-16, user): a "process again with the saved pipeline" button or route is NOT part of this
  work; save the data only. LATER WORK: re-run a recording from its saved `skellytracker` block.
- R1/R2 facts and plan (reported 2026-11-16, not implemented):
  - Recording: no separate settings file. The run's settings are the tracker source `definition`
    (`PosthocMocapPipelineConfig.model_dump(mode="json")` + `execution.requested_provider`,
    `recording_pipeline.py:214-223`) inside `RecordingMetadata`, embedded in `<rec>_data.parquet`
    (`parquet_writer.py:57-58`); `Source.definition` is free-form `dict[str, JsonValue]`
    (`recording_descriptor.py:38`). Restart from triangulation copies only detector fields back
    (`saved_observation_source.py:21-24`); later starts read no settings. `stage_settings`
    (`provenance.py:75-77`) still names the removed `tracker_config` and omits the RTMW model,
    threshold and EP.
  - R1 plan: one `skellytracker` block in that `definition`: `pipeline` = `export_pipeline(<the config
    that ran>)`, `running_mode`, `execution` = {selected (raw, None = Auto), requested key, options,
    device}, `models` = `PipelineRun.models` (+ applied EP/device/precision in part 2); old recordings
    load unchanged (free-form dict; the reader's config ignores extra keys); absent = unknown.
  - R2 facts: the only persisted EP choice is the UI localStorage `freemocap:mocap.config`
    (`persistence-listener.ts:80-89`, load `mocap-slice.ts:140-156`), no version; the realtime config is
    not persisted. Marker plan: `settingsVersion: 1` in `mocap.config`, as camera settings do
    (`camera-settings-storage.ts:14`); absent = legacy.

### 0.4 Open questions

- **S2 / V1, the result type.** Who: the user. The options:
  - copy the four old data types (`Observation`, `StageObservation`, `Keypoints`, `BoundingBox`)
    into freemocap and turn a pipeline result into them at one function (recommended by this
    session and the supervisor);
  - a new small type, which means a rewrite of 24 backend and 34 test files, with a risk to the
    recording format.
  `skellytracker.core.data_primitives` may go at ST stage 2.4. Step 2 waits for this answer.
- **U1, the sibling pins.** Answered (§0.3 U1). Who moves skellycam (sfn26 pins `opencv-contrib-python==4.12.*`) to
  `5.0.0.93`, and skellyforge (sfn26 says `requires-python <3.13`) to 3.13.18, and on which
  branches? The freemocap `uv.lock` waits for it.
  - Facts: skellycam's suite gives the same result on OpenCV 5.0.0.93 and on 4.12 (456 passed;
    the one failure is the missing Rust extension). skellyforge's suite passes on 3.13.18 (931
    passed, 1 skipped).
- **The beartype 0.23.1 check.** The old cap came from `d057537d` ("chkkpt"), which names no
  failing case. Run the full suite after the migration code lands and look for beartype decoration
  errors. A failure goes to the user.
- **The names of the pipeline API that are not confirmed:** `CallRefused`, `RunClosedError`,
  `Frame`, `PipelineRun.models`, `check_pipeline`, `needs_execution_provider`, `annotate` and
  `find_pipeline`. Keep each behind one import or one small function.

### 0.5 Corrections found

- The RTMW column order of the built-in differs from sfn26. The name set is the same, but only
  body and feet (23 of 133) keep their position:
  - old: body+feet, right_hand, left_hand, face;
  - new: body, feet, face, left_hand, right_hand.
  Map by name only, through `to_canonical`.
- The committed `contracts/openapi.json` was already out of date with the backend at `ca0c17cc`.
  Group 1 applied only the delta of the removal (a 3-way merge).

### 0.6 User-visible changes of Phase B

1. The EP menu offers Auto and the EPs that skellytracker lists as usable on this host, with its labels
   and in its order (`c0f66701`). A saved key that the server does not list stays visible under its key.
   **Changes in part 2 (§0.3 E2).** Now: a saved `trt` or `directml` no longer reads as Auto: the run
   start fails with skellytracker's message ("The EP key 'trt' is reserved: classic TensorRT is a
   separate EP; it is not in v2.") (`c9a58321`; was Auto since `a8d88985`). Part 2: a saved `trt` runs
   on its skellytracker successor `trt-rtx` when that is usable; the other cases wait for the user.
2. `/onnx/session_providers` gives, per run, the user's `requested_provider` and per model node what
   skellytracker's `PipelineRun.models` reports: `node`, `key`, `version`, `sidecar_sha256`, `size`,
   `precision`, the applied `execution_provider` and `device` (`d97932ff`). `applied_providers` and
   `model_name` are gone; nothing is made up.
3. A camera video that fails while it is read stops posthoc tracking with `CameraSourceEndedError`,
   which names the camera and the frame. On `sfn26` the other cameras went on, but the save refused
   the incomplete coverage, so nothing was saved in either case. The user decided this (V2, §0.3).
4. New 2D point names are `body.<group>/<point>` (for example `body.body/nose`,
   `body.left_hand/wrist`); the 3D names are `<group>/<point>`. The mapping YAMLs follow in step 3.
5. The posthoc MediaPipe GPU switch (`mediapipe_disable_gpu`) is gone: the Holistic built-in has no
   GPU param.
6. (removed 2026-11-16: with skellytracker `b8bfa7d2` the RTMW schema has 130 edges, 65 face edges,
   and the annotation draws them; checked on one test_data frame, no freemocap change.)
7. MediaPipe sends no hand boxes: Holistic makes no hand crops (`detector_box_stages`).
8. The realtime setting `use_centralized_inference` is gone: skeleton inference always runs in the
   group's inference node. A saved `skeleton_tracker_config`, `charuco_tracker_config`,
   `tracker_config`, `pipelineImplementation` or `videoFps` loads and is not written again.
9. A `charuco_observations_realtime.pkl` written on `sfn26` no longer loads (it pickles the old module
   path of `CharucoBoardDefinition`); calibration detects every frame again.
10. MediaPipe has no pose model size, detection, presence or tracking confidence, or face count any
    more (F1). A saved setting with them loads and is not written again.
11. One installer variant (F2): Windows x64, macOS Apple Silicon and Linux x64. The CUDA installers and
    the Cloudflare R2 hosting of the installer workflow are gone; the docs download page has no variant
    choice and no GPU detection.
    - From the next release the files are `freemocap_<version>_windows-x64`, `_macos-arm64` and
      `_linux-x64` (F2 revised). The docs page keeps the old names (`-cpu`,
      `macos-arm64-apple-silicon`) for `2.0.0-alpha.26` and earlier (`downloads.ts` `fileLabel`).
    - Auto-update: every installed app, old `-cpu` AND old `-cuda`, reads the same GitHub
      `latest.yml` / `latest-linux.yml` / `latest-mac.yml` of the newest tag (GitHub provider, no
      channel; the R2 `latest-linux-cuda.yml` was never read), so both kinds move to the new file
      with no extra step.
    - Fixed bug: the channel files of alpha.15, alpha.21 and alpha.26 named files that do not exist
      ("Update available", then the download fails). The release job now rewrites every `url:`/`path:`
      by extension (`.github/scripts/update_metadata.sh`) and fails when one names a missing asset.
      Checked offline on the published alpha.26 files: they fail the check as published and pass it
      after the rewrite.
    - Old links keep giving their own old file (every link has the version in it). New releases ship
      no copies under the old names (F2b).
    - **Not verifiable without a release:** which tag the updater picks, the download, install and
      restart on each OS, the update of a `.deb` install, and the AppImage saved under its new name.
    - `freemocap-ui/package.json` says `2.0.0-alpha.25` here while `2.0.0-alpha.26` is published. The
      channel `version` comes from package.json and the asset names from the tag; the release process
      sets the version.
    - `.github/workflows/test-bucket.yml` (manual R2 test) stays: R2 still hosts the CUDA builds of
      old releases. The `upx_exclude` CUDA names in `freemocap.spec` are dead but harmless.
12. Host probes (`ab15c4e7`): the startup log and `machine_benchmarks` take the hardware from
    `probe_host()` and the EP states from `status()`; nvidia-smi, WMIC, lspci, system_profiler and the
    ORT provider list are gone, and the log has no "GPU acceleration" verdict. A machine record now
    has the `HostInfo` fields (`cpu_name`, `memory_total_bytes`, `gpus`, ...) and `execution_providers`
    (key → state) instead of `cpu`, `memory_bytes`, `gpu`, `available_onnx_providers`; old records
    still render. The build step prints `skellytracker-eps status`. The three losses accepted at first
    are gone with skellytracker `c4b51dde`: the log prints `cpu_max_frequency_hz` (`d97932ff`), and the
    Linux GPU names (`pci.ids`) and the macOS VRAM come through `GpuInfo`.
13. `graphExecutionProvider` is gone from the settings (`de6be21a`). A saved one keeps its meaning
    (`59f55e9a`, §0.3 E1): with no saved `executionProvider` its value is the EP choice, and
    `executionProvider` wins when both are saved; it is not written again.
14. A detector whose pipeline takes no EP (MediaPipe) ignores the saved EP choice (`57be4131`). The
    preview no longer refuses MediaPipe with an explicit `cuda`: the UI hides the EP row for MediaPipe
    but keeps the RTMW choice, so a refusal would block a setting the user cannot see.
15. The EP menu (part 2, `d97932ff`, `f844f90c`): the help text is skellytracker's `description` of
    each EP, with its `install_hint` for an EP that is not usable here; the "GPU batched" and
    "CPU-only" texts are gone; the EP row shows when the server says the detector takes an EP. A
    "Device" row (Auto + each GPU with its name and VRAM, most VRAM first) shows when the chosen EP has
    more than one device; a new EP clears the device. Posthoc `executionDevice` and realtime
    `execution_device` reach `start_pipeline(device=...)`; Auto ignores them.
16. Saved mocap settings carry `settingsVersion: 1` (`288deb48`). A config saved before it is legacy: its
    EP key is replaced by skellytracker's suggestion for this computer (legacy `trt`/`cuda` -> `trt-rtx`
    if usable, else `cuda` if usable; another usable key stays; else Auto) and a notice says which key
    was replaced by which. Processing waits until the server has answered.

### 0.7 Imports of old skellytracker modules that stage 2.4 can remove

At `0f00f5a4`. Every other skellytracker import is the 2.0 surface (`core.pipelines`,
`core.detectors.create_detector`, `core.detectors.calibration`, `core.eps`). `CharucoAnnotator` comes
through `core.detectors.calibration` but is old annotation code too (`annotation_style.py`). The
`data_primitives` imports are the result type, which waits for V1.

- `skellytracker.core.annotation.keypoint_annotator`:
  - `freemocap/core/pipeline/posthoc/annotation_style.py:16`
  - `freemocap/core/pipeline/posthoc/annotation_style.py:7`
- `skellytracker.core.detectors.keypoint_detectors.mediapipe.mediapipe_model_manager`: none since F1.
- `skellytracker.core.eps.records`:
  - `freemocap/core/tracking/execution_providers.py:19`
- `skellytracker.core.data_primitives`:
  - `freemocap/core/pipeline/dataflow/annotation_workers.py:15`
  - `freemocap/core/pipeline/dataflow/recording_processing.py:16`
  - `freemocap/core/pipeline/dataflow/tracker_adapter.py:15`
  - `freemocap/core/pipeline/inference_service.py:21`
  - `freemocap/core/pipeline/posthoc/annotation_output.py:15`
  - `freemocap/core/pipeline/posthoc/annotation_style.py:17`
  - `freemocap/core/pipeline/posthoc/video_node.py:31`
  - `freemocap/core/pipeline/realtime/camera_node.py:41`
  - `freemocap/core/pipeline/realtime/charuco_recorder_node.py:15`
  - `freemocap/core/pipeline/realtime/realtime_aggregator_node.py:80`
  - `freemocap/core/pipeline/realtime/realtime_skeleton_inference_node.py:30`
  - `freemocap/core/recording/result_processing/observation_inputs.py:27`
  - `freemocap/core/recording/sample_encoding/observation_samples.py:19`
  - `freemocap/core/tasks/calibration/anipose_calibration/run_anipose_calibration.py:12`
  - `freemocap/core/tasks/calibration/camera_matching/live_matching.py:7`
  - `freemocap/core/tasks/calibration/camera_matching/observation_sampling.py:10`
  - `freemocap/core/tasks/calibration/camera_matching/posthoc_matching.py:8`
  - `freemocap/core/tasks/calibration/charuco_board/charuco_observation_aggregator.py:9`
  - `freemocap/core/tasks/calibration/posthoc_calibration_task.py:20`
  - `freemocap/core/tasks/calibration/shared/calibration_state.py:23`
  - `freemocap/core/tracking/charuco_detection.py:8`
  - `freemocap/core/tracking/observation_arrays.py:11`
  - `freemocap/core/tracking/observation_arrays.py:12`
  - `freemocap/core/tracking/observation_buffer.py:10`
  - `freemocap/core/tracking/observation_series.py:277`
  - `freemocap/core/tracking/observation_series.py:278`
  - `freemocap/core/tracking/observation_series.py:279`
  - `freemocap/core/tracking/observation_series.py:88`
  - `freemocap/core/tracking/observation_series.py:89`
  - `freemocap/core/tracking/pipeline_runs.py:124`
  - `freemocap/pubsub/pubsub_topics.py:22`
  - tests (61 imports): `calibration/test_calibration_state_latch.py:20`; `calibration/test_observation_sampling.py:5,6`; `calibration/test_posthoc_matching.py:8,9`; `calibration/test_streaming_reference_frame.py:15`; `pipelines/test_calibration_cache_alignment.py:26`; `pipelines/test_charuco_recorder.py:14,15`; `pipelines/test_realtime_calibration_resume.py:12`; `reference_recordings/test_columnar_observation_publication.py:10,11`; `reference_recordings/test_fresh_observation_retention.py:9`; `test_annotation_video_encoding.py:12`; `test_annotation_workers.py:13,14`; `test_board_cache_scope.py:8,9`; `test_box_channel.py:28,29`; `test_box_samples.py:13,14`; `test_columnar_observation_publication.py:8,9,10`; `test_columnar_serialization.py:8,9`; `test_core_tensor_consumers.py:4,8`; `test_dataflow_recording_processing.py:11,12`; `test_dataflow_tracker_adapter.py:8,92`; `test_detector_streaming.py:15,16,17`; `test_fresh_observation_tensors.py:9,10,11`; `test_inference_service.py:10`; `test_observation_alignment.py:4,5`; `test_observation_arrays.py:6,7`; `test_observation_samples.py:9,10`; `test_pipeline_diagnostics.py:8,9`; `test_posthoc_annotation_composition.py:4,5`; `test_posthoc_observation_recording.py:26,27,28`; `test_realtime_inference_adapter.py:17`; `test_reconstruction_checkpoints.py:10,11`; `test_saved_observation_tensors.py:9`; `test_startup_stream_integration.py:19`; `test_temporal_pipeline.py:6,7`; `test_tensor_pipeline_integration.py:14`

## 1. Inventory

### 1.1 Run and session code

- `core/pipeline/inference_service.py`:
  - `:19-22` imports `TrackerConfig`, `Observation`, `SessionRequest`, `SharedSessionPool`,
    `TrackerLease` and `TrackerState`.
  - `:40-46` `InferenceRequest(frame_number, images, timestamp_ms: int | None)`: one timestamp for
    each request.
  - `:79-98` one "SharedInference" thread.
  - `:210-221` scheduling: round-robin, with 1 posthoc request after 3 realtime ones.
  - `:224,315` one `SharedSessionPool` on that thread.
  - `:263-271` one lease for each client, made on its first request.
  - `:63,277-280` a `TrackerState` for each client and camera;
    `lease.tracker.process_batch(images, frame_number, states, timestamp_ms=)`.
  - `:153-168` an ONNX provider `None` or `"trt"` becomes `application_provider()`.
  - `:190-193,281-284` the frame rules: they increase, and posthoc frames are consecutive from 0;
    the cameras and the `frame_number` of the result must match the request.
  - `:200-208,228-240,287,326-334` cancel, retire, failure (this stops the whole realtime pipeline)
    and close (it joins for 10 s).
- `app/freemocap_application.py:90-101`: one app-wide service. `PosthocPipelineManager` keeps it and
  never uses it (`posthoc_pipeline_manager.py:47`).
- `core/pipeline/dataflow/recording_pipeline.py:161-187`: each posthoc recording run has its own
  service and pool. Thus realtime and posthoc share no session.
- `core/pipeline/realtime/realtime_skeleton_inference_node.py`:
  - `:147-156` one REALTIME client for each camera group;
  - `:188-201` it keeps only the newest frame;
  - `:244-247,289-302` submit, then a poll every 50 ms;
  - `:285` close.
- `core/pipeline/dataflow/tracker_adapter.py`: `:74-84` one POSTHOC client for each recording;
  `:116-131` one batch at a time; `:152` close.
- `core/tracking/tracker_factory.py`:
  - `:16-32` imports `Tracker`, the sessions, `SessionRequest`, `tracker_session_requests` and
    `ExecutionProviderName`;
  - `:41-61` `build_configured_tracker`;
  - `:64-85` `tracker_session_requests` (DLC: cpu/cuda, no fp16);
  - `:88-100` `build_charuco_tracker`;
  - `:103-191` builders that only tests use.
- `core/tracking/execution_providers.py:27,46-101`: `provider_loads`, `application_provider` (the
  first of cuda, coreml, directml, cpu that loads), `inspect_onnx_session` and
  `SessionCreationError`.
- `core/pipeline/dataflow/application_pipeline.py:53-66`: `resolve_tracking_provider`; ST
  `auto_detect_provider` and `provider_loads`.
- `ExecutionProviderName` is `trt | cuda | coreml | directml | cpu`.
- The per-camera path, `use_centralized_inference=False`:
  - `realtime_pipeline_config.py:20` (default True);
  - read at `realtime_pipeline.py:246,253,393,411`, `realtime_aggregator_node.py:710` and
    `api/websocket/websocket_server.py:129,141,380`;
  - its branches in `camera_node.py:84-91,108,159,164-177,189,226-242,295-297`;
  - tests: `pipelines/test_calibration_cache_e2e.py:39`,
    `reference_recordings/test_realtime_pipeline.py:59,172`, `test_tensor_replay.py:79`,
    `test_realtime_lifecycle.py:13`, `test_realtime_startup_lifecycle.py:55` and
    `test_rust_group_realtime_replay.py:106`.
- The legacy posthoc path is **already gone**. `pipeline_implementation` is
  `Literal["typed_dataflow"]` (`tasks/mocap/mocap_task_config.py:42`), and 72235c4d deleted
  `mocap_detection.py` and `mocap_video_node.py`. The field is still read at:
  - `tests/test_application_graph.py:22-29`;
  - `tests/test_combined_tracker_integration.py:19-20`;
  - `tools/datasets/preparation.py:221`;
  - `./freemocap-ui/src/components/mocap-setup/mocap-setup-modal.tsx:40`;
  - `./freemocap-ui/src/services/recording/posthoc-processing.ts:19`;
  - `./packages/freemocap-client/src/generated/schema.ts:3362`.
- Calibration still runs the old `Tracker` through `CalibrationPipeline` → `PosthocPipeline` →
  `VideoNode`: `core/pipeline/posthoc/video_node.py:153-154,521`
  (`process_image(image, frame_number, state)`, with no timestamp).

### 1.2 Tracker configs and detector types

- `core/tracking/tracker_factory.py:200-221` has
  `tracker_config_for_settings(settings, *, video_fps=30.0)`:
  - `dlc` → ST `dlc_tracker_config`;
  - each other type → ST `human_tracker_config(preset=detector_type, hand_count, model_name, ...)`.
- Callers: `camera_node_config.py:95`, `realtime_skeleton_inference_node.py:149`,
  `camera_node.py:89` and `tasks/mocap/mocap_task_config.py:206`.
- ST `core/tracker/tracker_presets.py` builds the presets:

| `detector_type` | Where offered | ST preset | What it is |
|---|---|---|---|
| `rtmpose` | realtime + posthoc (default) | `skeleton_tracker_config` `:173-214` | stage `body`: YOLOX-m (score 0.7, 1 person) + RTMW `model_name` (conf 0.4); redetect every `round(5 s × video_fps)` = 150 frames; no early redetect (`fitness_checks=[]`); floors 0.995 / 0.5 / 80 px; box expansion 0.05; One Euro on the box corners (3.0, 0.02, 1.0, reset 0.5 s) |
| `rtmw_mediapipe_hands` | realtime + posthoc | `combined_tracker_config` `:144-171` | the `rtmpose` config + child stages `right_hand`/`left_hand` (`mediapipe_hand_stage`, `:217-268`): a crop from the RTMW wrist/forefinger/pinky points, ×3.0, min 30 px, `HandLandmarker(num_hands=1, assumed_handedness)`, One Euro crop; assembled into `body` |
| `rtmw_onnx_hands` | realtime only | `mediapipe_onnx/experimental_recipe.py:12-28` | as `rtmw_mediapipe_hands`, with each hand child an experimental two-model ONNX palm + landmark detector; models from the env var `SKELLYTRACKER_HAND_CANDIDATE_DIR`; cpu/cuda only |
| `mediapipe` | realtime (LITE) + posthoc (HEAVY) | `build_mediapipe_tracker_config` `:271-356` | Pose + HandLandmarker on crops from the pose points + FaceLandmarker on the full frame; assembled `body`, `right_hand_*`, `left_hand_*`, `face_*`; `max_consecutive_misses=10` (`:353`) |
| `mediapipe_hands` | realtime only | `human_tracker_config` `:105-116` | stage `hands`: HandLandmarker on the full frame, no body; `num_hands` 1, 2, or "unknown" (doubled when full); per-camera hand tracks (§1.5) |
| `dlc` | realtime + posthoc | `dlc_tracker_config` `:58-73` | stage `dlc_keypoints`, one DLC sidecar model |
| `charuco` | — | `charuco_tracker_config`, `with_charuco_tracker` `:82-94` | §1.4 |

- Definitions:
  - realtime: `core/pipeline/realtime/camera_node_config.py:31` (all six types; default
    `rtmpose` `:17`);
  - posthoc: `tasks/mocap/mocap_task_config.py:69` (no `mediapipe_hands`, no `rtmw_onnx_hands`).
- RTMW `model_name` values are `rtmw-x-l_256x192` (the default), `rtmw-x-l_384x288` and
  `rtmw-l-m_256x192`. They are set at:
  - `camera_node_config.py:36`, `mocap_task_config.py:78`;
  - in the UI: `mocap-slice.ts:59-70`, `RealtimeProcessingSettings.tsx:28`,
    `mocap-detector-settings.tsx:38`, `RealtimePipelineConfigTree.tsx:231` and
    `realtime-types.ts:64`.
  - YOLOX `yolox-m` is hard-coded in the source label at `recording_pipeline.py:240`.
- Branches on `detector_type`:
  - `core/streaming/channel_helpers.py:54-69`;
  - `core/streaming/message_composer.py:74,111-140`;
  - `core/streaming/producers/{box,overlay}_producer.py`, `producer_contexts.py:31`;
  - `core/pipeline/realtime/realtime_aggregator_node.py:410,542-548,866,886,950,1003`;
  - `core/pipeline/realtime/realtime_pipeline.py:396-437`;
  - `core/skeletons/tracked_skeleton_set.py:40-53`;
  - `core/pipeline/dataflow/application_pipeline.py:49,55,146`;
  - `core/pipeline/dataflow/recording_pipeline.py:75,96-116,167,206,242`;
  - `api/websocket/websocket_server.py:153,208,288,336-346`;
  - `api/http/realtime/realtime_router.py:153`, `api/http/mocap/mocap_router.py:410-412`;
  - the UI option lists in `components/mocap-setup/detector-options.ts:5-17`, and about 12 more UI
    files.
- DLC:
  - `api/http/dlc/dlc_router.py:10-15` (`DlcConversionRequest`, `prepare_dlc_model`,
    `dlc_conversion_readiness`, `DEFAULT_CACHE_DIR`, `SidecarError`, `dlc_tracker_metadata`);
  - `core/skeletons/dlc_object_skeleton.py:8-32`;
  - `core/pipeline/realtime/realtime_pipeline.py:17`;
  - `core/streaming/producers/{overlay_producer,producer_contexts}.py`.

### 1.3 `Observation`, names and mappings

`Observation`, `StageObservation`, `Keypoints`, `BoundingBox` and `TrackedHand` are freemocap's data
types in memory, in pubsub messages (`pubsub/pubsub_topics.py:22`), in pickles and in recordings.

- Names:
  - ST `core/io/tracker_profiles.py:66-93`, `tracker_profile(preset)`, gives flat names,
    connections, mapping paths and crop paths for each preset. freemocap uses it in
    `core/tracking/tracker_definitions.py:3,10-18`, `tasks/mocap/tracker_mappings.py:3-17`,
    `core/skeletons/standard_human_skeleton.py:18,43-90` and `core/streaming/channel_helpers.py:11,69`.
  - The child stages are assembled into `body` in ST (`KeypointAssemblyConfig`).
- The `<stage>.<point>` names:
  - made at `core/tracking/observation_arrays.py:21-31,125-135`;
  - read back at `core/tracking/observation_series.py:34-41,96-100,200-201,252-253,292`;
  - stripped at the first `.`: `tasks/calibration/shared/calibration_state.py:59-66,548`
    (imported at `reconstruction/posthoc_reconstruction.py:23-24,140`),
    `tasks/triangulation/helpers/project_single_camera.py:35` and
    `core/tracking/observation_buffer.py:118`.
  - Hard-coded: `recording/exports/notebook.py:97` (`'body.nose'`),
    `recording/exports/wide_csv.py:72` and `guides.py:132-134` (`body.nose.x`), and the `"body"`
    key at `pipeline/posthoc/annotation_style.py:174`.
- Mappings:
  - ST `TrackerMapping`, `CompositeTrackerMapping`, `PreparedTrackerMapping`,
    `TrackerMappingSnapshot`, `MappedLandmarkEvidence` and `mapping_paths`;
  - used at `core/skeletons/{charuco_board_skeleton.py:39-40,106, dlc_object_skeleton.py:8,27,
    reconstruction_state.py:23,151-158, tracked_skeleton_bundle.py:27,41-68}`,
    `core/reconstruction/{posthoc_reconstruction.py:163-222, alignment_evidence.py:77-79}` and
    `core/recording/data_descriptors/recording_model.py:9-10,97-123`;
  - in tools: `tools/generate_tracker_mapping_ratios.py`.
- Annotation:
  - `pipeline/posthoc/annotation_style.py:7-179` uses `KeypointAnnotator`, `StageKeypointAnnotator`,
    `ConnectionGroupSchema`, `StageAnnotationSchema` and `CharucoAnnotator`;
  - the names come from `tracker_profile`;
  - the callers are `pipeline/posthoc/annotation_output.py:84`, `video_node.py:202` and
    `dataflow/annotation_workers.py:42`.

### 1.4 Charuco

The full list went to `skellytracker-ef` on 2026-11-16 (the message "calibration list"). In short:

- Detector:
  - `CharucoDetectorConfig(board=)` runs through `Tracker.create(config, {"cpu": CpuSession})`;
  - in realtime, `camera_node.py:305` runs one charuco tracker in each camera process;
  - in calibration, `video_node.py`;
  - in the typed graph, ST `with_charuco_tracker` at `recording_pipeline.py:104-107`. **This is the
    link between charuco and the tracker.**
- Helpers:
  - `CharucoBoardDefinition`: a mutable pydantic model and a config field (alias `charucoBoard`);
  - `CharucoBoardSelector` (`observe_image`, `search_frame`) and `CharucoBoardSelectionError`;
  - `anipose_export.to_anipose_camera_row`;
  - `CharucoAnnotator`/`CharucoAnnotatorConfig`;
  - the tag constants and `CHARUCO_BOARD_MAPPING` (+ `TrackerMapping`).
- The result is read by name (`CharucoCorner-{i}`) and by position (the first `n_corners` points).
- 25 test files use charuco.

### 1.5 Hand tracking (`mediapipe_hands`, added in 313c9c22 and ca0c17cc)

Each item says what freemocap does with it, and which part of the new API could carry it.

- **`mediapipe_hands`** (realtime only):
  - ST `human_tracker_config:105-116` → `HandTrackingStage` (`hand_tracking_stage.py:18-99`):
    - one HandLandmarker on the full frame for each camera;
    - "unknown" hand count doubles `num_hands`;
    - a track for each camera: a Hungarian match on IoU + points, `max_age` 10;
    - a constant-velocity prediction from `timestamp_ms` within 500 ms;
    - handedness by a 5-sample vote.
  - The output is `StageObservation("hands", hands=tuple[TrackedHand])`, with no keypoints and no
    boxes.
  - freemocap uses it at:
    - `core/pipeline/realtime/temporal_pipeline.py:63-77`: a filter for each (camera, track);
    - `realtime_aggregator_node.py:866-874,949-968,995`: association, and one fitter for each hand,
      `hand-<id>`;
    - `message_composer.py:74-77,111-114`: one tracker message for each hand, with handedness.
  - Nothing is saved to disk.
  - **New API:** no built-in. The node type `mediapipe_tasks` `variant: hand` exists. **Gaps:**
    - track ids across frames (`track_ids` is -1 until an `associate` node; v2 tracks one person);
    - handedness in the result;
    - the "unknown" hand count;
    - `I` > 1 with a temporal node (refused by `V-pipeline.graph-11`).
- **`TrackedHand`** (ST `data_primitives/tracked_hand.py:12-21`: `track_id`, `handedness`, 21
  unprefixed points):
  - used at `core/pipeline/realtime/hand_observations.py:8,22-113`, `temporal_pipeline.py:75` and
    `core/streaming/producers/overlay_producer.py:65-70`.
  - **New API:** nothing. **Gap:** no type for a hand instance with an id and handedness.
- **`core.io.tracker_profiles`** for hands:
  - `mediapipe_hand_names(side)`, `hand_connections()`, `tracker_profile("mediapipe_hands")` and
    `.hand_mapping(side)`;
  - the hand wrist becomes the carpal origin (ST `:26-50`);
  - used at `standard_human_skeleton.py:72-90` and `message_composer.py:17,47-49`.
  - **New API:** `to_canonical` gives `left_hand/*` and `right_hand/*` for RTMW. MediaPipe groups
    pass through until 2.2. **Gaps:**
    - the name of a hand of unknown side;
    - a hand-only mapping with the hand wrist as palm origin;
    - connections for each hand instance.
- **`ort_session_utils.provider_loads`** (and `auto_detect_provider`):
  - this is ONNX provider probing, used at `core/tracking/execution_providers.py:27,46-56` and
    `application_pipeline.py:59-65`;
  - the experimental ONNX hands take only cpu/cuda;
  - the `./freemocap-ui` provider choices are `trt|cuda|coreml|directml|cpu`.
  - **New API:** `core.eps.status`, `recommend` and `check_start` could carry it. **Gap:** v2 has
    no DirectML and no classic TensorRT (ADR-M2C6), and CoreML is not in the plan. Both are
    choices in freemocap now.
- **Hand crops from body points** (`mediapipe_hand_stage`, used by `mediapipe`,
  `rtmw_mediapipe_hands` and `rtmw_onnx_hands`):
  - **New API:** `mediapipe_tasks` has no ROI input in v2 (plan "Later"), so
    `rtmw_mediapipe_hands` has no pipeline.
  - `rtmw_onnx_hands` would need hand sidecars and a pipeline file. `rtmpose-hand-detector` is
    only a structure example.
  - `mediapipe` ≠ `mediapipe-holistic-tasks`: Holistic is another model, with another face point
    set and no reset. **Gap** for each of the three.
- **Hand identity across cameras** (`hand_observations.py:42-121`: DLT reprojection match,
  10-frame id history, handedness vote): this is freemocap-side code.
  - **Gap:** it needs per-camera hand track ids, which no pipeline output gives.
- **DLC:** one ONNX sidecar.
  - **New API:** `create_detector`, if a DLC sidecar is a catalog entry (not checked).
  - **Gap:** the DLC conversion tools (`dlc_router.py`) have no named 2.0 home.

### 1.6 `frame_number`, fps, resets and timestamps

- Tracker `frame_number`:
  - into the tracker: `inference_service.py:43,278`, `realtime_skeleton_inference_node.py:210,244`
    (gaps from dropped frames), `tracker_adapter.py:95,117`, `camera_node.py:295-306` and
    `video_node.py:227-233,521`;
  - out of the tracker: `inference_service.py:283`, `dataflow/recording_processing.py:108`,
    `annotation_workers.py:56-57`, `realtime_aggregator_node.py:839-843`,
    `hand_observations.py:111-113`, `observation_series.py:98,168,304`,
    `observation_buffer.py:96,114`, `annotation_output.py:75`,
    `charuco_observation_aggregator.py:60`, `observation_sampling.py:62`,
    `observation_inputs.py:112`, `observation_publication.py:107` and
    `observation_samples.py:105-120,242-245`.
  - freemocap's own `frame_number` stays: about 300 lines.
- 30 fps:
  - `tracker_factory.py:151,200` (default 30.0; no realtime caller passes it);
  - `mocap_task_config.py:145-146,206` (default 30.0; nothing in the app or UI sets it);
  - ST `tracker_presets.py:99,146,177`.
  - It sets only the redetect interval (150 frames).
  - In live mode, ST counts source frame numbers, with the dropped frames (`bbox_policy.py:153-159`).
- `max_consecutive_misses=10`: ST `tracker_presets.py:353` (the `mediapipe` body). freemocap never
  sets it.
- Timestamps:
  - Live: `core/tracking/capture_timing.py:6-23` gives one integer ms for each batch, the mean over
    the cameras of `(pre_frame_grab_ns + post_frame_grab_ns) / 2`, from skellycam
    `perf_counter_ns`. It is used at `realtime_skeleton_inference_node.py:245-246` and
    `camera_node.py:297`. Charuco gets none.
  - Posthoc: `tracker_adapter.py:37-49` gives integer ms from the group start, strictly increasing,
    one for each batch.
- The box: ST `bounding_box.py:114-117` `clipped_pixels` makes the crop whole pixels
  (`detection_stage.py:147,551`). ST sets `detector_ran` (`detection_stage.py:119-176,436-740`).
  - freemocap sends `[x1,y1,x2,y2,confidence,detector_ran]` (`channel_helpers.py:142,169`;
    `box_producer.py:44-63`).
  - It counts `object_detector_runs` (`tracker_adapter.py:144`).
  - It saves it (`observation_series.py:221,297`; `recording/data_descriptors/sample_conventions.py:23`).
  - The UI draws it by column name: `./freemocap-ui/src/services/server/server-helpers/image-overlay/skeleton-overlay-renderer.ts:164,231-244`
    and `./packages/freemocap-client/src/transport/frame-resolution.ts:34-67,276-280`.

### 1.7 What a recording keeps (for the read-only old-recording reader)

- 2D channels:
  - source `keypoint_model:<model>` (`recording_pipeline.py:108-116`);
  - `<stage>.<point>` names (`observation_series.py:41` requires the `.`);
  - boxes `object_detector:yolox-m` with `detector_ran`.
- The source definition is the whole `config.model_dump` (`recording_pipeline.py:229-232`).
  `saved_observations.py:44-50` validates it again as `PosthocMocapPipelineConfig`, so an old
  `detector_type` or `pipeline_implementation` value fails.
- `RecordedModel` (`recording_model.py:19-31,104-123`) holds `detector_type`,
  `tracker_keypoint_names`, the `TrackerMappingSnapshot` list and `tracker_stage_path`, and makes a
  `CompositeTrackerMapping` again.
- Provenance (`provenance.py:38,76-79`) holds the skellytracker version and commit, `tracker_config`
  and `video_fps`.
- The pickle `output_data/charuco_observations_realtime.pkl` holds the ST `Observation` and
  `CharucoBoardDefinition` classes. Its writer is never created.

### 1.8 Packaging and CI

- `./pyproject.toml`:
  - `:6` `requires-python >=3.11`; `./.python-version` 3.12. ST `sfn26` says `>=3.11,<3.13`.
  - `:54` in `[tool.uv.sources]`: `skellytracker = { path = "../skellytracker", editable = true }`.
    **This is what uv installs** (`./uv.lock:2593-2594`).
  - `:65` `[tool.freemocap.workspace.sources]` holds git `sfn26`. It is metadata for the workspace
    tools, and uv does not read it.
  - `:46-49,164-172,95` extras and groups `cuda|trt|cpu` → `skellytracker[all-*]`, and
    `default-groups = ["tracker-default"]`;
  - `:81-85` uv environments with Intel Mac; `:100` numpy override; **`:101` the
    `mediapipe==0.10.33` override**; `:108-110` NVIDIA index;
  - `:94,142-144` stale rtmlib comments.
- **`../skellytracker` is on `dom/sidecar-implementation`, not `sfn26`.** It lacks
  `core/sessions/shared_sessions.py`, `core/tracker/tracker_presets.py`,
  `core/io/tracker_profiles.py`, `core/data_primitives/tracked_hand.py`,
  `core/io/mapping_paths.py` and `core/detectors/keypoint_detectors/charuco/`. So freemocap
  `ca0c17cc` cannot import here, and no freemocap test runs now.
- `./uv.lock`:
  - onnxruntime 1.31.0 has no macOS x86_64 wheel. So Intel Mac cannot install now.
  - Other pins: mediapipe 0.10.33, onnxruntime-gpu 1.26.0, the nvidia cu12 wheels and
    tensorrt-cu12 10.16.
- `./freemocap.spec`:
  - `:46-79` MediaPipe datas, hidden imports (the old `solutions.*`) and binaries;
  - `:90` skellytracker `**/*.yaml`;
  - `:91-108,220-225` hidden imports and excludes of modules that do not exist;
  - `:131-149` NVIDIA `collect_all` (variant `cuda`);
  - `:152-156` onnxruntime;
  - no TensorRT.
- `./.github/workflows/`:
  - `build-installers-pyinstaller.yml:29-78,209-226,261-267`: variants cpu/cuda, no trt, no Intel
    Mac; the `variant` input is never read.
  - `test.yml`, `e2e-tests.yml`, `lint.yml`: `uv sync --group dev` (all-cuda on Linux and Windows).
  - No workflow checks out the sibling repos, so `[tool.uv.sources]` with paths cannot resolve in
    CI. This was inferred, not run.
- `./noxfile.py:5,11-62`: Python 3.11/3.12, `pip install -e .[dev]`, and no skellytracker.

### 1.9 Tests, tools, UI

- The run and session contract tests:
  - `test_inference_service.py` (private `_lease._entries[0].session`);
  - `test_dataflow_tracker_adapter.py:76` (`round(frame*1000/30)`);
  - `test_tracker_factory.py`, `test_sidecar_factory_contract.py`,
    `test_inference_provider_defaults.py` and `test_execution_providers.py` (the patch targets
    `skellytracker.core.sessions.ort_session_utils.{sys.platform,provider_loads}`);
  - `test_combined_tracker_integration.py`, `test_rtmw_schema_contract.py`,
    `test_tracking_configuration_contracts.py`, `test_experimental_onnx_hands.py`,
    `test_onnx_hand_benchmark.py`, `test_detector_streaming.py`, `test_dlc_streaming.py`,
    `test_hand_reconstruction_contract.py` and `test_independent_hand_views.py`;
  - `conftest.py:36-50` patches `ort_session_utils.provider_loads`.
- About 21 more test files build `Observation`/`StageObservation`/`Keypoints`/`BoundingBox` as fake
  tracker output. Several patch `Observation.__init__` or `BoundingBox.__init__`.
- Tools and experiments:
  - `tools/datasets/{tracker_comparison, hand_tracker_comparison, workflow, preparation,
    tracker_matrix, __main__}.py`;
  - `tools/machine_benchmarks.py:344`;
  - `tools/generate_tracker_mapping_ratios.py`;
  - `./experiments/executable_graph_lab/graph/tracking.py`;
  - `./bench_{tracker,inference,redetect,final}.py` (private tracker state).
- UI and the SDK:
  - the `detector_type` lists: `mocap-slice.ts:58`, `realtime-types.ts:13`,
    `detector-options.ts:5-17`;
  - the hand payload: `packages/freemocap-client/src/transport/message-contract.ts:205-207` and
    `frame-resolution.ts:120-129,265-280`;
  - name heuristics: `skeleton-overlay-renderer.ts:39-54`;
  - e2e: `realtime-startup.spec.ts:31-113`, which injects a `skeleton_tracker_config`.

## 2. Design (changes from the `development-streaming` design)

The run model, the names and the time rules of the first design stay:

- a `PipelineRun` for each realtime camera group (`live`) and for each posthoc recording (`video`);
- `InferenceService` stays the one calling thread until the thread rules are fixed;
- a small result type of freemocap's own;
- `to_canonical`;
- `frame_index` only at the boundary.

The changes for `sfn26`:

1. **Presets.**
   - `tracker_config_for_settings` and each use of ST `tracker_presets`, `tracker_profiles` and
     the sessions go.
   - `rtmpose` → the built-in `yolox-rtmw-wholebody`. The user decided this, and skellytracker
     changes the built-in to the `sfn26` box behaviour: redetect every 150 frames, a redetect after
     a lost person, One Euro, and the output `person_roi`.
   - The other five types wait for the gap answers of §4.
2. **Live time.** `capture_timing.py` changes from a mean over the batch to one value for each
   camera: `(pre + post) / 2` ns of that camera, as float ms. It keeps its clock and its checks.
3. **Box.**
   - freemocap clips `person_roi` to whole pixels, as ST `clipped_pixels` does now (clip, then
     `int()`).
   - `detector_ran` comes from `result["node_ran"][<person node id>]`.
4. **Legacy.** The `"current"` path is already gone. Delete the `pipeline_implementation` field and
   its readers (§1.1), and `use_centralized_inference=False` with its `camera_node.py` branches and
   tests.
5. **Charuco.**
   - `create_detector("charuco@skellytracker", board=...)` and the helpers from the public surface
     (in progress in skellytracker).
   - `with_charuco_tracker` leaves `recording_pipeline.py:104-107`.
   - freemocap imports nothing from `calibration_detectors` or `keypoint_detectors.charuco`.
6. **Dependencies.**
   - The path source `../skellytracker` already exists. Remove the `all-*` extras and groups,
     `tracker-default`, the NVIDIA index, the `mediapipe` override and the Intel Mac environments.
   - `requires-python ==3.13.18`.
   - The EP choice comes from `core.eps`.
   - `freemocap.spec` uses the skellytracker PyInstaller hook.
7. **Old recordings.** A small read-only reader keeps `<stage>.<point>` names and
   `TrackerMappingSnapshot` data readable.
   - It must also read an old `detector_type` and source definition that the new config Literals
     refuse (§1.7).
   - The charuco pickle cache has no live writer. Its reader can go.

## 3. Decisions

Recorded on 2026-11-16, by the user through `skellytracker-ef`.

- Base branch: `upstream/sfn26`, at its tip `ca0c17cc`.
- Q7: freemocap takes the built-in `yolox-rtmw-wholebody` and ships no pipeline file. skellytracker
  makes the built-in match `sfn26` plus the early redetect of `03b9c1dc`. freemocap must do three
  things itself:
  - clip `person_roi`;
  - set the points with score < 0.4 to missing;
  - give real timestamps.
- Q10: a small read-only reader keeps old recordings readable. New recordings use the new names.
- Q11: drop Intel Mac; Python 3.13.18 with the skellytracker pins; `mediapipe==1.2.2`.
- Q12: delete the legacy paths. On `sfn26` only `use_centralized_inference=False` is left.
- Q14: keep the detector-ran colour, column and metric, from `node_ran`.
- Charuco: freemocap uses only the public surface (`create_detector` and the helpers). It calls no
  calibration class directly.
- Detector choices: only `rtmpose` and `mediapipe` are migrated.
  - `rtmpose` → `yolox-rtmw-wholebody`.
  - `mediapipe` → `mediapipe-holistic-tasks` (another model, a 478-point face, no hand crops, no
    reset).
  - The other four choices go, with the code that only they use, in the backend, the UI and the
    SDK. The removal list is `skellytracker-2-removal-list.md`.
- Mapping, the second decision (2026-11-16, after the 3D fact): "in that case - freemocap owns the
  mappings." There is no mapping node and no mapping API in skellytracker 2.0.0. The design is in
  §6. The first decision, "Skellytracker must own these mappings", is withdrawn.
  - The fact that changed the decision: on `sfn26`, freemocap applies the mapping only to
    triangulated 3D points. The call sites are:
    - `posthoc_reconstruction.py:170,179,222,231`;
    - `reconstruction_state.py:151-158` (from `reconstruct_skeleton.py:17,24` and the realtime
      aggregator `:970`);
    - `alignment_evidence.py:77-80` (`apply_with_quality`, with a quality from reprojection: the
      second-best camera score, `mocap_alignment.py:66-82`).
    - No call site maps the 2D points of a camera.
- Gate, 2026-11-16: the calibration surface is pushed on skellytracker `ae2d75b5`
  (`skellytracker.core.detectors.create_detector` and `skellytracker.core.detectors.calibration`).
  The pipeline API stage has started.

### Features this migration removes

These four features stay on `sfn26`. They come back when skellytracker has pipelines for them,
which is later work.

1. **RTMW body + MediaPipe hands** (`rtmw_mediapipe_hands`): RTMW whole-body, with MediaPipe hand
   landmarks on hand crops from the RTMW wrist points.
2. **Hands only** (`mediapipe_hands`): MediaPipe hands on the full frame with no body, with per-camera
   hand tracks, handedness, a hand count of one, two or unknown, hand identity across cameras, and
   one reconstructed hand for each track in realtime.
3. **RTMW body + experimental ONNX hands** (`rtmw_onnx_hands`): the experimental ONNX palm and
   landmark hands on crops from the RTMW points (models from `SKELLYTRACKER_HAND_CANDIDATE_DIR`).
4. **DeepLabCut** (`dlc`): DLC models for objects and animals, with the DLC import and conversion
   (`/dlc` routes), the DLC rigid-object skeleton and the DLC overlays.

## 4. Open questions and gaps

Sent to `skellytracker-ef` on 2026-11-16. The detector-choice and hand gaps of §1.2 and §1.5 are with
the user as one scope question.

The answers:

- N1: build a baseline in a separate environment, with a clone of skellytracker at `2d356a6c`. Record:
  - the counts for each test file;
  - the commit pair;
  - the Python version;
  - each failure that exists before the migration.
  Change no tracked file.
- N2: `redetect_interval` in `live` counts `frame_index` steps, and a skip counts
  (`specs/pipeline/nodes/redetect_trigger.md`, Behaviour step 3). Give the source frame number as
  `frame_index`.
- N3: `mediapipe` → `mediapipe-holistic-tasks`. The plan decides this. The known consequences:
  another model, a 478-point face, no hand crops and no reset. Do not design for the decomposed
  MediaPipe.
- N4:
  - RTMW of the built-in: a point with score < 0.4 becomes missing. Do this in the one function that
    turns the pipeline result into freemocap's result type.
  - MediaPipe: no gate. The node gives score 1.0 to each found hand or face point, and the
    visibility to each body point (ADR-Y7C3). Keep freemocap's use of visibility.
- N5: the skellytracker plan does not name DLC. The DLC detector, `dlc_conversion.py` and
  `dlc_import.py` exist only on skellytracker `sfn26`. DLC is in the scope question.
- EP keys in v2: `cpu`, `coreml`, `cuda`, `trt-rtx`. DirectML and the classic TensorRT go
  (ADR-M2C6). `core.eps.status()`, `recommend()` and `check_start()` replace `provider_loads` and
  `auto_detect_provider`.
- RTMW sizes:

  | Old name | New size |
  |---|---|
  | `rtmw-l-m_256x192` | `m` |
  | `rtmw-x-l_256x192` | `l-256` |
  | `rtmw-x-l_384x288` | `l-384` |
  | (new) | `x-256` |
  | (new) | `x-384` |

- The batch conversion at the session start takes 0.01 to 1.02 s. No cache will be built.

## 4a. Baseline before the migration (2026-11-16)

- **Commit pair:** freemocap `ca0c17cc`, skellytracker `2d356a6c`.
- **The other siblings:** skellycam `sfn26` `f486d3882`, skellyforge `sfn26` `5f0fd2d`,
  freemocap_blender_addon `sfn26` `aefde7d`, skellylogs `eeea4fa` and skellypings `dbaa4b2`.
- **Where:** fresh clones in a scratchpad workspace. `../skellytracker` and freemocap's `.venv` did
  not change.
- **Install:** `uv sync --frozen --group dev`, as CI (tracker-default = `all-cuda`), with
  `--no-install-package skellycam-rust`.
  - The Rust build of `skellycam-rust` needs a Windows SDK (`kernel32.lib`), and this machine has
    none.
  - No collected test failed for want of it. It is not checked whether any of the 31 skips do.
- **Runtime:** Python **3.12.13** (the old Python; the target is 3.13.18), onnxruntime-gpu 1.26.0
  (TensorRT, CUDA and CPU providers), mediapipe 0.10.33 and OpenCV 4.12.0.
- **Command:** as `.github/workflows/test.yml`:
  `pytest freemocap/tests/ --timeout=120 --timeout-method=thread -m "not e2e and not slow"`.
- **Result:** 221 test files: **1572 passed, 15 failed, 31 skipped**, 57 deselected, 117 subtests
  passed. The counts for each file are in `skellytracker-2-baseline-sfn26.tsv`.
- **Failures:** all 15 fail again in a second run.

| Tests | Count | Failure |
|---|---|---|
| `test_csv_export_ui_api.py::test_completion_exports_only_when_enabled_and_preserves_processing_success[True-False]`, `[False-False]` | 2 | exports incomplete: "Unknown recording run: 0" and `'types.SimpleNamespace' object has no attribute 'files'` |
| `test_recording_export_jobs.py::test_automatic_export_binds_produced_run_and_separates_failure[False-observations]`, `[False-filtering]`, `[False-reconstruction]` | 3 | the same `SimpleNamespace` error |
| `test_mocap_pipeline_integration.py::test_worker_exit_without_terminal_report_fails_pipeline` | 1 | beartype refuses a `Mock` as `plan` of `AggregatorNodeProgressMessage` |
| `test_sidecar_factory_contract.py::test_core_requests_preserve_declared_models_and_settings[*-rtmw]`, `[*-combined]` | 8 | the `SessionRequest` of `OnnxSession` (RTMW model spec) differs from the expected one. This is the old session contract, which the migration deletes. |
| `test_streaming_vmc.py::test_real_udp_measurement_time_and_clean_close` | 1 | `assert 51 == 21`: the VMC message count |

- **Not run:** the e2e and slow tests (57), the UI tests and the tests in `packages/`. The
  `packages/freemocap-stream` tests do not collect in this environment, but CI does not run them.

## 6. Mapping package (freemocap owns the mappings)

One package, `freemocap/core/mapping/`, serves the new recordings and the reader of old
recordings. The mapping stays applied to the triangulated 3D points, at the call sites of §3. The
code is copied from skellytracker `sfn26` `2d356a6c`. The commit that adds it names that commit.

### 6.1 Files copied

The ST paths are under `skellytracker/core/io/` and `skellytracker/tests/`.

| freemocap file | Source (ST) | Change |
|---|---|---|
| `core/mapping/tracker_mapping.py` | `core/io/tracker_mapping.py` (781 lines: `TrackerMapping` with the offsets and the quality propagation, `TrackerMappingSnapshot`, `MappedLandmarkEvidence`, passthrough) | imports only |
| `core/mapping/canonical_mapping_expansion.py` | `core/io/canonical_mapping_expansion.py` (53 lines; `tracker_mapping.py` imports it) | none |
| `core/mapping/composite_tracker_mapping.py` | `core/io/composite_tracker_mapping.py` (57 lines) | imports only |
| `core/mapping/prepared_tracker_mapping.py` | `core/io/prepared_tracker_mapping.py` (357 lines) | imports only |
| `core/mapping/tracker_mapping_batch.py` (+ `.md`) | `core/io/tracker_mapping_batch.py` (23 lines; `prepared_tracker_mapping.py` imports it) | none |
| `core/mapping/mapping_paths.py` | `core/io/mapping_paths.py` | new paths: only the three YAMLs of §6.2 |
| `tests/mapping/` | `tests/test_hand_cmc_mapping.py`, `test_mapping_quality.py`, `test_passthrough_mapping.py`, `test_shoulder_mapping.py`, `test_tracker_mapping_batch.py`, `test_mapping_paths.py`, `shoulder_mapping_notes.md` | imports and paths; the YAML tests get the new keys |

- The code has no assumption about the name separator. Its only name check is the optional
  `prefix` (`tracker_mapping.py:245`), so `<group>/<point>` names need no change.
- Not copied:
  - `tracker_profiles.py`. It holds the profile selection and the `mediapipe_hands` rewrite;
    freemocap's `tasks/mocap/tracker_mappings.py` picks the YAMLs itself.
  - the `*_to_canonical_mapping.yaml` files and `rtmpose_body17_to_canonical_mapping.yaml`;
  - each mapping of the four removed choices.
- The ratio tool `tools/generate_tracker_mapping_ratios.py` is already in freemocap. Only its
  import changes (`:35`).

### 6.2 YAML files rewritten for the new point names

The ST paths are under `skellytracker/core/detectors/keypoint_detectors/`. The values (the tracker
side) change. The keys (the standard-human landmarks) and the offsets and ratios do not change.

| freemocap file | Source (ST) | Source names | Example |
|---|---|---|---|
| `core/mapping/yaml/rtmw_body_to_standard_human.yaml` | `rtmpose/body/rtmpose_body_to_standard_human_mapping.yaml` | the canonical names of `to_canonical` (ST `core/model_zoo/landmark_schemas/COCO_WholeBody.yaml`, `canonical_mapping`, region `body`) | `left_acromion: left_shoulder` → `left_acromion: body/left_shoulder`; `head_center: [left_ear, right_ear]` → `[body/left_ear, body/right_ear]` |
| `core/mapping/yaml/mediapipe_holistic_body_to_standard_human.yaml` | `mediapipe/body/mediapipe_body_to_standard_human_mapping.yaml` | `mediapipe-holistic-tasks` group `body`: `body/<name of mediapipe_body.yaml>` | `left_eye_inner: left_eye_inner` → `left_eye_inner: body/left_eye_inner` |
| `core/mapping/yaml/hand_to_standard_human.yaml` | `rtmpose/hand/rtmpose_hand_to_standard_human_mapping.yaml` and `mediapipe/hands/mediapipe_hand_to_standard_human_mapping.yaml` | `left_hand/<name>`, `right_hand/<name>` | RTMW `left_thumb_cmc: "left_hand_thumb1"` and MediaPipe `left_thumb_cmc: "left_hand_thumb_cmc"` → both `left_thumb_cmc: left_hand/thumb_cmc` |

- One hand file serves both choices:
  - The two source files differ only in their comments and their source names. Checked: the
    `diff` is empty after the source names are normalised.
  - The canonical hand names of RTMW (`left_hand/wrist`, `thumb_cmc`, `index_finger_mcp`, ...,
    `pinky_tip`) are the MediaPipe hand names.
  - So both become the same text. The `anatomical_offset` CMC entries keep their numbers, for
    example `left_index_cmc` with origin `[left_wrist]` → `[body/left_wrist]` and `to:
    left_hand_forefinger1` → `left_hand/index_finger_mcp`.
- MediaPipe:
  - The body file keeps the MediaPipe pose names (for example `left_foot_index`, the eye inner and
    outer points).
  - No mapping uses the face points (0 references to `face_` in the body file), so the
    478-point face of Holistic needs no mapping.
  - These keys stay `<group>/<point>` names of the node until a later skellytracker stage
    registers the MediaPipe schemas.
- The bundle's `tracker_keypoint_names` become the point names that freemocap triangulates: the
  `canonical_names` (RTMW) or the output `point_names` (Holistic).
- Charuco needs no YAML. freemocap builds the passthrough mapping in
  `core/skeletons/charuco_board_skeleton.py:106-107` as
  `TrackerMapping(entries={}, known_tracker_keypoints=set(board.all_point_names),
  passthrough_keypoints_as_landmarks=True)`, from its own copy. The charuco names stay
  `CharucoCorner-{i}` and `ArucoMarkerCorner-{id}-{j}`.

### 6.3 Old and new snapshots in the reader

- `RecordedModel.mappings` (`core/recording/data_descriptors/recording_model.py:19-31`) holds
  `TrackerMappingSnapshot` values as plain pydantic data: `entries`, `prefix`,
  `known_tracker_keypoints` and `passthrough`. It holds no module path. `to_bundle` (`:104-123`)
  makes `CompositeTrackerMapping(item.restore() for item in self.mappings)` again.
- Each recording carries its own mapping:
  - An old snapshot has old source names (`left_shoulder`, `left_hand_thumb1`). Its restored
    mapping applies to the old 3D channels of that recording, which also have the old flat names
    (the stage prefix was stripped).
  - A new snapshot has the new names (`body/left_shoulder`, `left_hand/thumb_cmc`), and applies to
    the new channels.
  - So old and new snapshots coexist with no version field and no name translation. The only rule
    is that a snapshot and the channels it maps come from the same recording.
- Because of that, the copy must keep the four snapshot fields, their types and their order. The
  `RecordedModel` serializer keeps historical fingerprints (`recording_model.py:33-...`). A change
  of the snapshot form changes the fingerprints of old recordings.
- The reader needs no old YAML. The 2D observation channels of an old recording keep their
  `<stage>.<point>` names (`observation_series.py:41`), and only the reader parses them.

### 6.4 Callers that move to `freemocap.core.mapping`

- `core/skeletons/charuco_board_skeleton.py:39-40,106-107`;
- `core/skeletons/reconstruction_state.py:23`;
- `core/reconstruction/posthoc_reconstruction.py:163,215`;
- `core/skeletons/tracked_skeleton_bundle.py:27`;
- `core/recording/data_descriptors/recording_model.py:9-10`;
- `core/tasks/mocap/tracker_mappings.py:3-17` (the YAMLs come from `freemocap.core.mapping.mapping_paths`);
- `core/skeletons/standard_human_skeleton.py:18,43,58-59`;
- `tools/generate_tracker_mapping_ratios.py:35`;
- the tests `test_tracker_mapping_authoring.py:12,18-19` (it reads the ST YAML paths),
  `test_alignment_evidence.py:9`, `test_model_presentation.py:41` and
  `test_model_scale_in_the_loop.py:19`.

## 5. Sharing, lifetime and threads (input to the 1.10 investigation)

The conclusions of the first design stay:

- no session is shared between realtime and posthoc, because posthoc has its own pool for each
  recording;
- no lease for each stream: one run for each camera group and one for each recording;
- the thread rules and the start time are requirements.

`sfn26` adds two points:

- A realtime processing failure stops the whole realtime pipeline.
- `InferenceService.close` joins for 10 s and raises if native code still runs.
