# Pipeline metrics port: plan (stage PM)

Status: PLAN ONLY, 2026-11-17. No code has changed for it. The user's decisions are in §8 and are open.

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
