# Pipeline metrics port: plan (stage PM)

Status: PLAN ONLY, 2026-11-17. No code has changed for it. The user ruled on Q1, Q2, Q7, L1 and on what
"RTMPose" means. Those rulings are in §10, which replaces any part of §2-§8 it contradicts. Q3, Q4, Q5, Q6 and
Q8 are open with the user; Q9 is the supervisor's.

The user, in their words: "Before the stage where legacy pipelines are removed, I want to add a stage that ports
over the work from dom/pipeline-metrics-rebased and: 1. Clean the code up and get it to work smoothly for both the
legacy and new-format pipeline. 2. Add all of the system information provided by skellytracker to a suitably
organised top-panel of the pop-up. Then I want to manually run some tests to check performance of the pipelines."

How it was checked:
- Revisions: freemocap `sidecar-implementation` at `6fe45a8c`, the branch `dom/pipeline-metrics-rebased` at
  `dadfe94c`, the merge base `83c6bc7e`, and skellytracker at `12c477da` (the scratch clone, read only).
- B: means `git show dadfe94c:<path>`; S: means `sidecar-implementation`.
- Three read-only sub-agents read the code. The key claims were checked again by hand: `start_pipeline` has
  `timing_sink`, the executor gate, `timing_spans` is empty by default, freemocap passes no sink, the branch
  imports `skellytracker.core.tracker`, and ST 2.4 is "NOT STARTED".

## 1. Where the stage goes

- The stage that removes the legacy pipelines is skellytracker stage 2.4 (ST `specs/sidecar-implementation-plan.md:1531`
  "### 2.4 Delete the old run code (was Dc)", `:1533` "**Status: NOT STARTED.**"). It deletes `core/tracker/`
  (`Tracker`, `DetectionStage`, ...). The branch's skellytracker work lives in that directory (`core/tracker/task_events.py`).
- freemocap's own legacy step is already done: migration doc §0.1, "Phase B step 5: old API removed"
  (`c5be62ed`, `46e9a55d`). No `pipeline_implementation` and no `use_centralized_inference` are left in `freemocap/`.
- So stage PM goes after Phase B and before ST 2.4. It needs nothing from ST 2.4 and does not block it, because it
  does not use `core/tracker/` (§3).

## 2. (a) The pipeline paths that run on S, and where their timing comes from

All skeleton detection, realtime and posthoc, goes through skellytracker 2.0 `PipelineRun` via `InferenceService`
(`inference_service.py:260` `client._run.process_batch({`; the run starts at `pipeline_runs.py:82`
`run = start_pipeline(config, ...)`). freemocap runs no old skellytracker run code.

| Path | Entry | Timing today |
|---|---|---|
| Realtime | `realtime_router.py:139` `/apply` -> `realtime_pipeline_manager.py:54,81` -> `realtime_pipeline.py:234` `CameraNode`, `:247` `RealtimeSkeletonInferenceNode`, `:278` `RealtimeAggregatorNode` | `PipelineStageTimer`: `camera_node.py:148`, `:225` `"charuco_detection"`; `realtime_skeleton_inference_node.py:251` `"predict_batch"`, `:252` `"predict_per_camera"`; aggregator `:772-969`. `PipelineTimingReporter` (`realtime_aggregator_node.py:454`) only writes them to the log, every 30 s (`pipeline_timing_reporter.py:228`). Nothing reaches the websocket. |
| Posthoc mocap (dataflow graph) | `processing_router.py:40` / `mocap_router.py:390` -> `posthoc_pipeline_manager.py:151` `MocapPipeline` -> `application_pipeline.py:205` `run_recording_pipeline` | `PerformanceReport` (`mocap_pipeline.py:30`, logged at `:66`). It is fed by `inference_service.py:249` `"inference.queue_wait"`, `:252` `"inference.session_setup"`, `:259` `"inference.process_batch.images=N"`; `tracker_adapter.py:120`; `application_pipeline.py:210` `graph.<node>`; the graph's own times are at `recording_executor.py:60-71`. Log only. |
| Posthoc calibration (the older `PosthocPipeline`/`VideoNode` coordinator, ChArUco through the 2.0 detector) | `calibration_router.py:315` (deprecated) -> `posthoc_pipeline_manager.py:139` -> `calibration_pipeline.py:94` | `video_node.py:203-216` per-frame times, logged as "Processing statistics" (`:265-275`). |

skellytracker 2.0 timing is not used.
- `start_pipeline(..., timing_sink: Any = None, timing: str = "on", ...)` (ST `core/pipelines/run.py:198-199`).
- The executor writes it only `if timing == "on" and timing_sink is not None:` (ST `core/pipelines/_runtime/executor.py:186`).
- freemocap passes no `timing_sink`; `grep -rn timing_sink freemocap` finds nothing.

### "Legacy" and "new-format": the meaning is unclear

The words have no current meaning in freemocap: no old-format pipeline runs any more. They can be read in three
ways, listed in Q1 (§8). This plan assumes Q1 = B until the user answers.

Stale plan text to fix: migration doc `:965-967` ("Calibration still runs the old `Tracker` through ... `VideoNode`").
That is no longer true: `video_node.py:131` has `create_charuco_detector(board)`.

## 3. (b) What the branch needs from the old skellytracker run code

- freemocap B imports, from old skellytracker:
  - `realtime_skeleton_inference_node.py:56` `from skellytracker.core.tracker.tracker import Tracker`
  - `:57` `from skellytracker.core.tracker.tracker_state import TrackerState`
  - `:58` `from skellytracker.core.tracker.task_events import TrackerTaskEventCollector`
- These names are used:
  - `TrackerTaskEventCollector()` at `:168`;
  - `tracker.process_batch(..., event_collector=event_collector)` at `:253`;
  - the fields `task_id, parent_task_ids, stage, node_kind, camera_id, frame_number, start_time_ns, end_time_ns,
    duration_ms, batch_index, batch_size` at `:297-313`.
- Nothing else is used. `StageTimer` is not used in B freemocap.
- skellytracker B (`94d5fcae` against `8d5b5203`):
  - `core/tracker/task_events.py` +228: `TrackerTaskEvent`, `TrackerTaskEventSink`, `TrackerTaskEventCollector`,
    `make_batch_task_id`, `make_camera_task_id`, `normalize_parent_task_ids`, `TrackerTaskEventContext`, `StageTimer`.
  - `detection_stage.py` +94, `tracker.py` ±12 (the `event_collector` kwarg), `detection_context.py` ±6.
- None of this is in ST `12c477da`.
- The rest of B's helpers (`tracker_events_to_pipeline_events`, `collect_tracker_batch_events`,
  `synthesize_rtmpose_batch_events`) have test callers only and read old session attributes. Drop them.

The recommendation is to port nothing into skellytracker. There are two timing sources that need no
skellytracker change:
1. freemocap's coarse timers around the call: realtime `predict_batch` / `predict_per_camera`, and posthoc
   `inference.queue_wait` / `session_setup` / `process_batch`.
2. skellytracker 2.0's own spans. freemocap only has to pass a callable `timing_sink` and set
   `config.instrumentation.timing_spans`; `start_pipeline` has no argument for the spans (ST `config.py:687-688`,
   empty by default).

Both sources use the same clock (`perf_counter_ns`).

## 4. (c) skellytracker 2.0 timing events against the branch's `PipelineTimingEvent`

skellytracker's side:
- The rules are in ST `specs/pipeline/timing.md`, which is still a draft (`:11`). ADR-Q59W is superseded by 0WTV and
  then W5QD, with no rule change.
- An event is a dict (ST `core/pipelines/timing.py:30`): `images[{frame_index, camera_id}], node_id, span,
  batch_size, start_ns, end_ns`. The clock is `perf_counter_ns`.
- The spans: `onnx_model` nodes have preprocess / inference / postprocess; other nodes and the pipeline have `run`.
  There is one event per node per device call, covering that device's cameras.
- Each run sends one header, with `run_id`, `clock`, `anchor{perf_counter_ns, unix_ns}` and `nodes[]`
  (`inputs`, `execution{requested_ep, used_ep, device, ...}`).
- A callable sink gets each dict synchronously, on the caller's thread, after the call (`executor.py:395-399`).
- `timing` is not in `core.pipelines.__all__`; it is imported as `skellytracker.core.pipelines.timing`.

The branch's event (B `pubsub_topics.py:189-201`) and where each field would come from:

| B field | From ST 2.0 | Status |
|---|---|---|
| `task_id` | `timing.task_ids(event)` = `{frame}:{cam}:{node_id}:{span}` | same shape; a multi-camera event needs the batch form or one event per image |
| `parent_task_ids` | none (`timing.md:86`: "An event has no field for its parents") | derive from header `nodes[].inputs`, plus `pipeline.run` as the wrapper |
| `stage` | `span` | use `{node_id}.{span}`; the UI labels (B `pipelineTaskTopology.ts:60-88`) are written for the 1.x stages |
| `node_kind` | none | set by freemocap (`skeleton_inference`); the node type is in the header |
| `camera_id`, `frame_number` | `images[i]` | exact for one image; frame numbers can differ between cameras in one live call |
| `start_time_ns`, `end_time_ns`, `duration_ms` | `start_ns`, `end_ns`, `timing.duration_ms` | direct, same clock |
| `batch_index` | none | missing |
| `batch_size` | `batch_size` | counts cameras, not person crops |

Missing from skellytracker's public API, to request:
1. A start argument that turns the spans on.
2. Parent links, or a public `parent_task_ids(event, header)` helper.
3. A crop/row count per event for top-down models.
4. A device key per event.
5. A chunk index inside `inference`.
6. Session build and warm-up times. `SessionReport.build_ns` / `warmup_ns` are measured but private
   (ST `eps/records.py:192-193`).
7. The full execution facts in `PipelineRun.models` (`artifact_sha256`, `ep_options`, `gpu_uuid`, `cpu_nodes`,
   `cpu_op_types`, `requested_ep`). Today they are only in the timing header.
8. MediaPipe nodes in `models`.
9. A public read of the run header on `PipelineRun`.
10. A fix or a note in the docs for two behaviours: `pipeline.run` includes the sink's own time on the node
    events (`executor.py:395-399`), and no new header is written on a session change, although `timing.md:69`
    says one is.

None of these blocks a first port: 1 has a config work-around, 2 can be derived, and 3-9 are for later.

## 5. (d) System information from skellytracker, and the top panel

| Group | Values | Source | Update |
|---|---|---|---|
| Host: OS, CPU, memory | OS name, release, build; arch; CPU name; physical/logical cores; nominal max frequency; total memory; VM/WSL/container | `core.system.probe_host()` (cached; about 100 ms the first time on Windows) | once per process |
| GPU devices | device key, name, vendor, driver, total VRAM, NVIDIA compute capability and brand | `probe_host().gpus`, `gpu_device_keys()` | once per process |
| Runtime and libraries | Python build, skellytracker version and commit, ORT version and packages, MediaPipe version, driver-supported CUDA; loaded CUDA/cuDNN/TensorRT libraries | `probe_runtime()`, `probe_environment()`, `probe_loaded_libraries()` | static, but loaded libraries change after the first session; probe in the inference process after the first frame |
| Execution providers | each EP: usable, install hint, devices; recommendation chosen/skipped/offers; `core_matches_pin`; warnings | `core.eps.status()` (loads no library; about 18 ms, then about 1 ms), `recommend()` | on open, and after an EP install |
| Models of this run | key, version, size, precision, EP, device (joined to the GPU name) | `PipelineRun.models` (static for a run); the timing header `execution` when timing is on | per run |
| Live load | CPU share, RAM used and available, inference process CPU/RSS/VRAM, per-GPU utilisation and VRAM | `core.metrics.LiveSampler().sample(pids)` (about 2-3 ms after its first call; not per frame), `free_vram(device)` | 1-2 Hz from one backend thread |

Notes:
- `GpuSample.key` is the PCI bus id, while `models[].device` and `free_vram` use device keys. Join them through
  `gpu_device_keys()`.
- `vram_used_bytes` is `None` under Windows WDDM.
- Live GPU values exist only for NVIDIA.
- S already uses `probe_host` and `eps.status` in `freemocap/app/app.py:69-71` (`HOST_FIELDS` `:38`, `GPU_FIELDS` `:40`)
  and `/onnx/execution_providers` (`onnx_router.py:43`). The branch's `/realtime/gpu-info` and `_detect_gpus` are
  replaced by these; do not port them.
- Observed but not explained: `probe_runtime().skellytracker_version` reads `v2024.09.1019` in the scratch venv. It
  is probably stale editable-install metadata; unverified.

## 6. (e) What must not come over

- The fork pin: B `pyproject.toml:44` `skellytracker = { git = "https://github.com/domisjustanumber/skellytracker", branch = "dom/pipeline-metrics-rebased"}` (commit `87d676bc`).
- Dependencies and tooling:
  - `tabulate`: S already has it.
  - The `exclude-dependencies` reflow.
  - All of `uv.lock` (commits `8ce85bef`, `50ba3a02`, `bfe51f18`).
  - `poe_tasks.toml` (`test-all`, `test-e2e-ui`).
- Commits that should not come over:
  - Reverts and merges: `4d02fe99`, `ed79d0ab`, `01fbadcb`, `5ae3fb84`, `d5cfeb51`.
  - The node churn of `f988221a` and `7f24a3a1`.
  - The clock rename of `d7654f1a`, which `cf227ccb` undid.
- Root PNGs.
- Unrelated UI behaviour: `useZoomTransform.ts` (Ctrl/Cmd zoom), the `useServerPanel.ts` line split, and the
  `freemocap/__init__.py` version bump.
- Websocket regressions hidden in B's diff:
  - three removed `self._global_kill_flag.value = True`;
  - unvalidated `displayImageSizes` (B `websocket_server.py:643`);
  - dropped `display_image_sizes=` (B `:503`);
  - the dead skellycam `get_and_clear_frontend_preview_*` fallback (B `:33-41`).
- B's change to `pipeline_timing_reporter.py`: S rewrote that file (`:29`, `:164`: "do not sum rows or infer
  end-to-end latency").
- B's GPU endpoint and the GPU text of the flyout.
- B's headline `Average frame processing time ... (~fps)` (B `PipelineMetricsWindowPage.tsx:111-118,183`). It adds
  `predict_batch` to the largest `total_camera_node`, two windows that were sampled independently. S's reporter
  and AGENTS.md rule this out (Q3).
- B's transport bugs:
  - every websocket client drains the same `pipeline_timing_subscription` (B `realtime_pipeline.py:252`,
    `websocket_server.py:208,212`), so two windows split the events;
  - client-side accumulation of `droppedTimingEvents` (B `pipeline-timing-store.ts:292`);
  - `maxReconnectAttempts: 10` (B `MetricsServerContextProvider.tsx:32`), which may conflict with the
    restart-recovery invariant (not checked).

## 7. (f) Port method and commit order

Do not cherry-pick. Commits 1-34 sit on `088dace2` (alpha.18), not on the base, and carry churn that later commits
revert. Re-apply the final diff by area, and rewrite where S replaced the target code:

| Area | Carry over | Rewrite |
|---|---|---|
| Backend model | `PipelineTimingEvent` and the new `PipelineTimingMessage` fields (`pubsub_topics.py`; `PipelineTimingMessage` is unchanged on S at `:202`), `pipeline_timing_task_ids.py`, B's `pipeline_stage_timer.py` (S's copy equals the base; B also fixes S's mixed clocks, `:29` `time.monotonic` against `:46` `time.perf_counter()`), from `pipeline_timing_events.py` only `PipelineTimingEventStore`, `cap_events_by_frame_window`, `compute_timing_lag_info` | — |
| Producers | the charuco event (S `camera_node.py:225`) | skeleton inference: events from the skellytracker 2.0 sink and a `predict_batch` span around `_await_inference_result`; start time and flush interval in S's `RealtimePipeline.create` |
| Transport | — | `websocket_server.py` (35 commits on S), and the deleted `websocket_message_types.py` / `websocket-message-types.ts`: a new message kind in `core/streaming/message_model.py` (`MessageKind` `:58`, `encode_message` `:759`) and the UI `services/server/transport/`, following `current-work-plans/03-transport/message-protocol.md` (self-contained messages, client recovery); a fan-out, not a shared drain |
| UI store | `pipeline-timing-store.ts`, `pipeline-timing-types.ts`, `sample-window-stats.ts` | the metrics provider on S's `TransportService`/CBOR, not B's JSON `WebSocketConnection` |
| UI components | metrics page, timeline, topology, tooltips, `useTimelineChartZoom`, i18n, `App.tsx` route, electron window and IPC | the entry button in S's `SettingsOverlay.tsx` (rewritten on S, +11/−155); the toolbar headline (Q3); the new top panel (§5) |
| Tests | unit classes of `test_pipeline_timing.py` (TaskIds, DroppedEventAccounting, Cap, Store, LagInfo); vitest topology, timeline model, tooltips | transport tests against S's codec; Playwright later |

Commit order, each one tested on its own:
1. The backend model and its unit tests.
2. Realtime producers: charuco and predict_batch spans, with timer tests.
3. The skellytracker 2.0 timing sink in `pipeline_runs.py` / `InferenceService`, turned on only while the
   metrics are open, with a test using a fake run.
4. The transport message and fan-out, with codec and reconnect tests.
5. The UI store on S's transport.
6. The UI window, route and entry, with vitest.
7. The system-information endpoint and the top panel (§5).
8. Posthoc coverage, if Q1/Q7 want it.
9. The state doc and a run report.

## 8. Decisions for the user (open; each with options and a recommendation)

- **Q1. What "legacy" and "new-format" pipeline mean.**
  - A: old skellytracker run code against 2.0. freemocap no longer runs the old code, so supporting it would
    mean putting a removed path back.
  - B: the realtime pipeline and the posthoc pipelines (mocap and calibration).
  - C: the older posthoc coordinator (calibration, `PosthocPipeline`/`VideoNode`) against the dataflow graph
    (mocap).
  - Recommendation: B. The branch covers realtime only, and A has nothing left to measure.
- **Q2. The source of skeleton-inference timing.**
  - A: skellytracker 2.0 spans through a `timing_sink` (per node, preprocess/inference/postprocess), plus
    freemocap's coarse timers.
  - B: freemocap's coarse timers only.
  - C: port `TrackerTaskEventCollector` into skellytracker 2.0.
  - Recommendation: A. It needs no skellytracker change. C would rebuild what 2.0 already has.
- **Q3. The headline number.** B's "Average frame processing time (~fps)" adds windows that were sampled
  separately.
  - A: replace it with the end-to-end time of each complete frame from the events of that frame, and ms/frame
    with FPS for each stage.
  - B: drop the headline.
  - C: keep it as it is.
  - Recommendation: A (AGENTS.md: pair ms/frame with FPS; never compare inference FPS with whole-run FPS).
- **Q4. Transport.**
  - A: a new message kind on the main CBOR transport, with the metrics window as one more client of it.
  - B: B's separate `?client_role=metrics` JSON websocket.
  - Recommendation: A. It is the self-describing-transport invariant of AGENTS.md, and it removes the shared-drain
    bug.
- **Q5. Where the system information comes from.**
  - A: one HTTP endpoint for the static groups and the run's models, with live load samples in the metrics
    message at 1-2 Hz.
  - B: everything in the metrics message.
  - Recommendation: A. The static values do not need to be repeated per frame, and they reuse what `app.py` already
    calls.
- **Q6. Which process runs the probes and `LiveSampler`.**
  - A: the inference process. It loads the libraries and owns the VRAM.
  - B: the main backend process, passing the inference pid.
  - Recommendation: A for `probe_loaded_libraries` and `PipelineRun.models`; one `LiveSampler` in the main process
    with the inference pid.
- **Q7. Posthoc in the pop-up.**
  - A: a live timeline for posthoc too.
  - B: a per-stage summary table after each posthoc run, from `PerformanceReport`.
  - C: realtime only.
  - Recommendation: B first; A later if the manual tests need it.
- **Q8. Timing cost when the window is closed.**
  - A: send events only while a metrics client is connected, and switch the skellytracker spans on only then.
  - B: always on.
  - Recommendation: A. The sink runs on the caller's thread and is counted inside `pipeline.run`.
- **Q9. The skellytracker API requests of §4.** Recommendation: ask for 1 (spans argument), 2 (parent links) and
  6 (build and warm-up times) now, the rest later. This is for the supervisor and the user; this session never
  changes skellytracker.

## 9. (g) What the manual performance tests need

How the user opens the pop-up:
- On B: the gear button "Realtime Pipeline Info" in the realtime settings overlay (B `SettingsOverlay.tsx:240-251`),
  then "Open Pipeline Metrics Window" (B `realtimepipeline-actions-flyout.tsx:94-99`).
- That opens an Electron window on `#/pipeline-metrics` (B `window-manager.ts:109,174`), or a browser pop-up
  (B `open-pipeline-metrics-window.ts:12`).
- On S the entry has to be placed again (S's `SettingsOverlay.tsx` changed).
- There is no shortcut.

What it shows on B:
- A toolbar: connection state, GPU, pause, the headline (Q3), incomplete frames, per-node lag and stalled nodes.
- A timeline of the last 5 frames (`pipeline-timing-types.ts:2`): one row per task event, coloured by category,
  with durations and a detail pane.
- Realtime only. There is no per-pipeline table.
- After the port there would also be the §5 top panel and, with Q7 = B, a posthoc summary.

Whether the numbers are comparable:
- **Within one run:** yes. All events use `perf_counter_ns`, and the UI aligns them through
  `relay_perf_counter_ns` (B `pipeline-timing-store.ts:46-57`). Across processes this is verified only on Windows.
- **Realtime against posthoc:** only stage by stage, not as whole runs.
  - Realtime spans cover a single live call per frame.
  - Posthoc `inference.process_batch.images=N` covers a batch of N images, and includes queue time and IPC.
  - Per image, compare skellytracker's `inference` span, which has the same meaning in both modes.
  - Do not compare inference FPS with whole-run FPS (AGENTS.md).
- **Against B's numbers (old run code):** no. The old 1.x stages (`predict_batch` inside the tracker) are not the 2.0
  spans, and the machine, models and EP can differ. A fair comparison needs the same recording, EP, model size
  and precision, and should report ms/frame with FPS and ranges over repeats (the `benchmarks/README.md` report
  contract).

## 10. The rulings of 2026-11-17 and the updated plan

### 10.1 Rulings

These came through the supervisor.

- **Q1, the user's words:** "it must run for both the legacy, dynamic batch YOLOX + RTMW and RTMPose pipelines, as
  well as the new fixed-batch YOLOX+RTMW pipeline / any future sidecar + pipeline config based pipelines."
- **"RTMPose":** the legacy side is only the old YOLOX + RTMW wholebody, the pipeline freemocap had under `rtmpose`.
  There is no old RTMPose-body path, and no optional step for it.
- **L1 = C:** the user wrote "No post-hoc for legacy pipelines."
  - A legacy run path comes back, realtime only, and drives the old skellytracker `Tracker`.
  - Its per-model timing comes from the old `core/tracker/task_events.py`. The supervisor ports it onto skellytracker
    `dom/sidecar-implementation`; this session never changes skellytracker.
  - The legacy path is deleted at ST 2.4 together with the matching freemocap step.
- **Q2:** 2.0 pipelines use the skellytracker 2.0 timing sink plus freemocap's coarse timers. The legacy path uses the
  task events plus the same coarse timers.
- **Q7 and posthoc:** the user's rule is "If it's the same work, do both." Both are done for the 2.0 pipelines, with a
  live posthoc timeline. Posthoc calibration is out: it has no `PipelineRun` (no inference service in
  `calibration_pipeline.py`).

### 10.2 The posthoc review, checked in the code

- **Shared THREAD worker:** true for realtime only.
  - `freemocap_application.py:90` `inference_service = InferenceService(worker_registry=worker_registry)`.
  - `inference_service.py:106` `worker_mode=WorkerMode.THREAD`.
- **"Posthoc shares that service": wrong.** Each posthoc recording builds and closes its own service and thread.
  - `recording_pipeline.py:148-150` `registry = WorkerRegistry(... WorkerMode.THREAD)` /
    `service = InferenceService(worker_registry=registry)` / `service.start()`.
  - `PosthocPipelineManager.inference_service` (`posthoc_pipeline_manager.py:47`) is stored but never used.
  - So the timing sink belongs on the registration of whichever service a client uses. Realtime and posthoc
    still share the same code: `InferenceRegistration` and `_start_run`.
- **"Once per frame": true, but imprecise.** There is one `client._run.process_batch({` (`inference_service.py:260`)
  per frame index, covering all cameras.
  - Posthoc submits one request per frame, with every camera (`tracker_adapter.py:117`, `:136`
    `require_every_camera`, `:139`).
  - Realtime runs only the newest frame and drops older ones (`realtime_skeleton_inference_node.py:189-196`), and
    unreadable cameras are skipped (`:316-326`). So realtime `batch_size` varies.
- **"Selector by the posthoc pipeline_id": imprecise.** The posthoc registration id is the fixed string
  `"recording-graph"` (`recording_pipeline.py:147,156` -> `tracker_adapter.py:99` `pipeline_id=execution_id`).
  The task's real id (`mocap_pipeline.py:24` `pipeline_id`) has to be passed down.
- **The realtime id** is `str(uuid.uuid4())[:6]` (`realtime_pipeline.py:210`, used at
  `realtime_skeleton_inference_node.py:148`). The branch keys its timing by camera group, so every payload carries
  `mode`, `pipeline_id` and `camera_group_id`.
- **Extra fact:** realtime requests carry no `performance` (`realtime_skeleton_inference_node.py:243-244`), so
  `inference.queue_wait` exists only for posthoc.

### 10.3 The per-client 2.0 timing sink

1. `InferenceRegistration` (`inference_service.py:32-43`) gets a field
   `timing_sink: Callable[[dict], None] | None = None`. `_start_run` (`:157-163`) passes it to `start_detector_run`.
2. `start_detector_run` (`pipeline_runs.py:69`; the only `start_pipeline` call is at `:82`) takes `timing_sink`.
   When a sink is given:
   - It builds the span list from the public node types:
     `[f"{n.id}.{s}" for n in config.nodes for s in types[n.type].timing_spans] + ["pipeline.run"]`
     (`list_node_types()`; ST rule V-pipeline.timing-1, `config.py:814-819`).
   - It starts the run on a `model_copy` whose `instrumentation.timing_spans` holds that list.
   - The recorded provenance (`:84` `export_pipeline(config, resolved=True)`) stays on the un-instrumented config.
     Whether `model_copy` marks `instrumentation` as set in the export is unverified; a test checks it.
3. The sink runs on the inference thread, synchronously after each call, under the run lock (ST
   `core/pipelines/run.py:132`, `_runtime/executor.py:395-399`).
   - The header comes through the same callable (`"schema"` in the record). It is kept for the node items,
     `stage_providers` and `execution`.
   - The sink only does `deque.append`, because the time it takes is counted inside `pipeline.run`.
4. Each event becomes one `PipelineTimingEvent`:
   - `stage = f"{node_id}.{span}"`;
   - `node_kind = "skeleton_inference"`;
   - `frame_number = images[0].frame_index`. All images of one call share it: `inference_service.py:261` takes
     `frame_index=request.frame_number`.
   - `batch_size` is taken from the event, and `camera_id = None`;
   - the task id is prefixed with the pipeline id;
   - parents are derived: the `pipeline.run` event, plus the header `nodes[].inputs`.
5. **Realtime:** the node owns the deque. Events of frame N are appended before the future resolves
   (`inference_service.py:287`). The node drains them into the branch's `timer.extend_task_events`, and the existing
   `timer.maybe_flush(publication_queue=timing_pub, ...)` (`realtime_skeleton_inference_node.py:268-271`) publishes
   them on `PipelineTimingTopic`.
6. **Posthoc:** there is no pubsub.
   - A bounded deque goes on `MocapWorkerRequest` (`mocap_pipeline.py:23-30`). It is passed through
     `run_recording_pipeline` (`application_pipeline.py:205`) -> `build_recording_pipeline` (`recording_pipeline.py:57`)
     -> `SkellyTrackerAdapter`, together with the real `pipeline_id` instead of `"recording-graph"`.
   - The metrics relay reads it through `posthoc_pipeline_manager.pipelines[id]`.
   - A `graph.camera_batch_wait` event per frame (`perf_counter_ns` around `tracker_adapter.py:120-132`) goes into the
     same deque, from the graph thread. `deque.append` is thread-safe.
7. **Posthoc in the UI:**
   - a run selector (the realtime group or a posthoc pipeline id);
   - the opener takes `?pipeline=<id>`, which needs the Electron IPC change;
   - an "Open metrics" entry after "Load in playback" in `PipelineGroupCard.tsx:178-220`, for mocap only;
   - lag and stall hidden for posthoc. Their rule `max(0.5 s, 15/fps)` (B `pipeline_timing_events.py:354-356`) marks a
     slow CPU run stale, and the relay then drops its events. Posthoc skips `compute_timing_lag_info` and the stale
     filter.

### 10.4 The legacy realtime path (L1 = C)

**(a) Old-API names at skellytracker 12c477da**

The legacy path follows `dadfe94c:freemocap/core/tracking/tracker_factory.py:67-143`, which builds the configs
directly. It does not use the presets or the shared sessions.

Present at 12c477da:
- `Tracker`, `TrackerConfig`, `DetectionStageConfig` (ST `core/__init__.py:3-9,29-36`; `core/config/__init__.py:1-7`).
- `TrackerState` (`core/tracker/tracker_state.py`).
- `OnnxSession`, `OnnxSessionConfig`, `CpuSession`.
- `RTMPoseDetectorConfig` (a re-export of `RTMWWholebodyDetectorConfig`,
  `keypoint_detectors/rtmpose/wholebody/rtmpose_wholebody_detector.py:16-18`). It is registered at
  `rtmw/wholebody/rtmw_wholebody_detector.py:162`, through the `rtmpose/__init__.py` import.
- `YoloxPersonDetector`, `YoloxPersonDetectorConfig`. The dynamic batch is built in:
  `yolox_person_detector.py:186-193` `prepare=prepare_yolox_onnx`, and `_yolox_dynamic_batch.py:366`.
- The temporal-processing configs `BBoxPolicyConfig`, `BBoxSmoothingConfig`, `KeypointResetPolicyConfig` and
  `KeypointsWithinBBoxRatioConfig` (`temporal_processing_config.py:13,45,88,119`).
- `Observation`.

Missing at 12c477da, and not needed:
- `core/tracker/tracker_presets.py`, `core/sessions/shared_sessions.py` (`SessionRequest`) and
  `tracker_session_requests`. They were imported by the old factory
  (`c5be62ed^:freemocap/core/tracking/tracker_factory.py:27,29,92,116,190`) and exist only in the `sfn26` line.

Missing at 12c477da, and needed. Only these must be added in skellytracker:
1. `core/tracker/task_events.py`, plus the `event_collector` argument on `Tracker.process_batch` and in
   `DetectionStage`. At 12c477da `process_batch` takes only `timings: ProcessingTimer | None` (ST `tracker.py:74`).
   This is the supervisor's port.
2. **A GPU EP for the old `OnnxSession`** (L3 is settled: `cuda` only, through a temporary bridge; see §10.6).
   - Today the old run code runs only on CPU or CoreML: `core/sessions/execution_provider_name.py`
     `ExecutionProviderName = Literal["coreml", "cpu"]`, and `ort_session_utils.py:26-29,113-114` falls back to
     `CPUExecutionProvider`. ST commit 9cb65775 removed the rest.
   - Without this, legacy runs are CPU only, and a legacy GPU comparison is impossible.
   - The smallest version: `OnnxSession.create` builds each model with `core.eps.build_session(...)` when the key is
     not cpu or coreml.
   - The freemocap EP choice reuses `pipeline_runs.run_ep_choice` (`:53`). freemocap's old `application_provider`
     needs the removed `ort_session_utils.provider_loads`, so it does not come back.

**Model files** (read from the code, nothing downloaded):
- The old specs point at openmmlab archives: `rtmw-wholebody.yaml:86-87` `rtmw-x-l_256x192_b1_fp32.onnx`, and
  `yolox.yaml:60-61` `yolox-m_b1_fp32.onnx`.
- They are cached in `~/.cache/skellytracker/models` (`sessions/model_registry.py:26`), and downloaded only when
  missing (`:155-158`). This machine has them.
- The seam refuses to start when a file is not in the cache, so a run never downloads.
- These are not the 2.0 files (2.0 uses fixed-batch exports such as `rtmw-wholebody133-l-256_b3_fp32.onnx`). Whether
  the weights are the same is unverified. This matters for comparability (part (d)).

**(b) Old point names**

- The old RTMW emits `body.<sfn26 name>` (`body.nose`, `body.left_hand_root`; `rtmw_wholebody_detector.py:34`,
  `coco133_tracked_points.yaml`).
- The aggregator maps by `detector_type` and 2.0 names (`tracker_mappings.py:13`, `mapping_paths.py:16`), so old
  names would silently map nothing.
- No old-to-new map exists in freemocap; the old-recording reader only refuses old names (`saved_observations.py:47`).
- The seam converts the old names with skellytracker's `to_canonical`. It builds an `InstanceKeypoints` from the old
  xy and visibility and the run's `output_schema["wholebody"]`. This gives the derived centres too, which a rename
  table would miss.
- The old order matches the 2.0 groups (body 0-22, face 23-90, left hand 91-111, right hand 112-132), and boxes and
  `detector_ran` pass through.
- One test checks that the legacy output names equal `detector_point_names("rtmpose")`. Which `point_names` the value
  must carry is unverified.
- "Realtime only, nothing saved" holds.
  - Nothing in `core/pipeline/realtime`, `core/streaming` or `api/websocket` writes a file.
  - LSL and VMC stream live (`streaming/outputs/source.py:71-100`).
  - `CharucoRecorderNode` buffers ChArUco only (`charuco_recorder_node.py:36`).
  - Auto-process after a recording uses the posthoc slice (`RecordingControlPanel.tsx:105-106`).
  - One caveat: an external LSL recorder captures the legacy stream labelled `rtmpose`. Its provenance JSON
    (`lsl.py:388`) has no detector field.
- **Scores:** old RTMW scores are raw SimCC. The old detector default is `confidence_threshold: float = 0.004`
  (`rtmw_wholebody_detector.py:45`), and sfn26 then applied the aggregator's 0.4 gate (`camera_node_config.py:45`).
  The legacy path keeps that and does not apply `rtmpose_confidence_threshold` (0.5 is on the calibrated scale).

**(c) The choice in config, contract and UI**

- Recommended: a realtime-only field `legacy_tracker_benchmark: bool = False` on
  `RealtimeSkeletonInferenceNodeConfig` (`realtime_skeleton_inference_node_config.py:5-20`). `detector_type` stays
  `"rtmpose"`, so mapping, overlays, the wire `tracker_id` and the UI need no aliases.
- A new `detector_type` value would key at least eight lookups:
  - `pipeline_runs.py:17` and `:102-119`;
  - `mapping_paths.py:15`;
  - `channel_helpers.py:54`;
  - `tracker_definitions.py:13`;
  - `onnx_router.py:59`;
  - `message_composer.py:89`;
  - the UI `DetectorType` that posthoc shares (`mocap-slice.ts:37`).
- The field passes through `realtime_skeleton_inference_node.py:147-155` into `InferenceRegistration`.
- `_start_run` branches to the legacy run, and raises `ValueError` unless `mode == InferenceMode.REALTIME`. So
  posthoc can never start a legacy run. `MocapTaskConfig` has no such field, and `tracker_adapter.py:100` builds its
  own registration.
- Changing the field rebuilds inference (`realtime_pipeline.py:389`).
- The contract gets one boolean (`openapi.json` `RealtimeSkeletonInferenceNodeConfig` near `:7732`, plus `schema.ts`).
- The UI gets a toggle "Legacy tracker (benchmark)" in the realtime processing settings, under
  `import.meta.env.DEV` (precedent `ThreeJsScene.tsx:115`). Benchmarks can also set it through the realtime API.
- The alternative, if a detector value is wanted: `legacy_benchmark_yolox_rtmw` in the camera-node Literal only (not
  `mocap_task_config.py:74`, so posthoc returns 422), aliased to `"rtmpose"` at each lookup above. This is question
  L2 in §10.6.
- The seam is one new file, `freemocap/core/tracking/legacy_tracker_run.py`. It holds:
  - the Tracker and session build;
  - the name translation;
  - the cache-only check;
  - the task-event conversion.

  The remaining edits are the field, its pass-through, the `_start_run` branch, the contract boolean and the DEV
  toggle. Each one carries the comment `# Deleted at skellytracker stage 2.4 (legacy tracker benchmark).` Deleting
  them is one commit.

**(d) One timeline for legacy and 2.0**

The legacy stages are the old `detection_stage.py` at 94d5fcae. Task ids are `{frame}:{cam}:skeleton_inference:{stage}`
or the batch form.

| 2.0 span (node ids at 12c477da) | Legacy stage | Comparable |
|---|---|---|
| `person.inference` | `object_detection_infer` (`:511`, around `run_batched`) | yes, with caveats: 2.0 pads a fixed batch; the redetect policies differ (legacy redetects all cameras together, `:426-438`); different files |
| `wholebody.inference` | `keypoint_detection_infer` (`:608`) | yes, with caveats: 2.0 `batch_size` counts cameras, not crops; different files |
| `pipeline.run` | `predict_batch` (freemocap, around `tracker.process_batch`) | about the same: both are the whole call; `pipeline.run` excludes freemocap's `observations_from_results` (`inference_service.py:263`) |
| `frame_read` (freemocap) | `frame_read` | yes: same code |
| `person.preprocess` / `.postprocess` | none (only `context.timings`, `:503`) | no |
| `wholebody.preprocess` | `crop` (`:551`) plus an untimed preprocess | no |
| `wholebody.postprocess` | `keypoint_detection` (`:634`; includes translate, miss/reset and smoothing) | no |
| glue `.run` (trigger, box, crop smoothing, points box) | `bbox_reuse`, `bbox_smoothing`, `keypoint_tracked_bbox` | loose only: different filters and rules |

- The timeline tags each row with its engine (legacy or 2.0) and pairs only the comparable rows.
- `PRETTY_STAGE_LABELS`, `SKELETON_INFERENCE_STAGE_ORDER` and the indent sets (B `pipelineTaskTopology.ts:53-212`) get
  the 2.0 names.
- The 2.0 node ids change with the box rename (ADR-2RWC, ST `803c33fa`). The table must be re-read at that head when
  the step is built.

### 10.5 (e) Size and commit order

The new PM order replaces §7. Each step is tested on its own.

| # | Commit | Size (estimate) |
|---|---|---|
| 1 | Backend timing model and its unit tests (§7) | about 500 lines |
| 2 | Realtime coarse producers (charuco, predict_batch) and the shared start time and flush interval | about 150 |
| 3 | Per-client 2.0 timing sink: `InferenceRegistration.timing_sink`, `start_detector_run` spans, event conversion; a test with a fake run | about 200 |
| 4 | Transport message on the main CBOR transport (if Q4 = A) with a fan-out per client, and codec and reconnect tests | about 300 |
| 5 | UI store, keyed by mode and pipeline id | about 700 (mostly ported) |
| 6 | UI window, route, realtime entry, run selector | about 1,500 (mostly ported) |
| 7 | Posthoc route: real pipeline id, deque, `camera_batch_wait`, progress-panel entry, lag and stall hidden | about 250 |
| 8 | Legacy seam: `legacy_tracker_run.py`, the flag, the name translation, the cache-only check, task events to `PipelineTimingEvent`, tests. It waits for the supervisor's skellytracker port (task events, and the GPU EP for the old `OnnxSession`) | about 400 |
| 9 | System-information endpoint and top panel (§5; Q5, Q6) | about 400 |
| 10 | State doc and a run report | — |

Deletion at ST 2.4: one commit removes `legacy_tracker_run.py` and every line marked
`# Deleted at skellytracker stage 2.4`.

### 10.6 New questions

- **L2 (user or supervisor): how the legacy choice is offered.**
  - A: the realtime-only boolean `legacy_tracker_benchmark`, behind a DEV toggle (recommended: no aliases, and
    posthoc cannot get it).
  - B: a `detector_type` value `legacy_benchmark_yolox_rtmw`, with an alias at every lookup.
- **L3, answered by the user (2026-11-17):** "TRT doesn't work on the legacy models, only CUDA and CPU".
  - The legacy path offers `cuda` and `cpu` only, never `trt-rtx`.
  - The supervisor adds a temporary bridge in skellytracker, marked and deleted at ST 2.4: the old `OnnxSession` takes
    the key `cuda` and builds it through the new EP code, using the `cuda` pack of the EP store.
  - The legacy seam refuses `trt-rtx` with a clear message.
  - When the user's EP choice is `trt-rtx` or Auto, the legacy run uses `cuda` if `core.eps.status()` shows its pack
    usable, else `cpu`. The UI shows the EP it applied, as the 2.0 runs do.
  - Commit 8 waits for the supervisor's SHA and the exact signatures (the bridge and the task events).
  - Commits 1-7 and 9 do not wait for it. Each one waits only for the open questions it depends on: Q3 to Q6, Q8,
    L2 and L4.
- **L4 (user): no downloads.** Recommended: the legacy seam refuses to start when an old model file is not in the
  cache.
