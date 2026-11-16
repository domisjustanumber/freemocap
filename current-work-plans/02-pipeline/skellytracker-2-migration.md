# freemocap → skellytracker 2.0.0 (`pipelines` and `detectors`)

Branch `sidecar-implementation`, made from `upstream/sfn26` at freemocap `ca0c17cc`. Its skellytracker
pair is `upstream/sfn26` at `2d356a6c`.

The contract:
- `../skellytracker/specs/pipeline/`;
- the headings 1.6, 1.10 and "freemocap migration" of
  `../skellytracker/specs/sidecar-implementation-plan.md` (branch `dom/sidecar-implementation`).

The first design, for `development-streaming`, is on the local branch
`sidecar-implementation-dev-streaming`.

Status: Phase A was redone on `sfn26`. No code is changed. Line numbers are for `ca0c17cc`. "ST"
means skellytracker `sfn26` `2d356a6c`. Paths are relative to `freemocap/`, except where they
start with `./` (the repo root).

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
    SDK. The removal list is §6.
- Still open with the user: who owns the standard-human mapping (freemocap, or a skellytracker
  mapping API). Design nothing on it yet.

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

## 5. Sharing, lifetime and threads (input to the 1.10 investigation)

The conclusions of the first design stay:

- no session is shared between realtime and posthoc, because posthoc has its own pool for each
  recording;
- no lease for each stream: one run for each camera group and one for each recording;
- the thread rules and the start time are requirements.

`sfn26` adds two points:

- A realtime processing failure stops the whole realtime pipeline.
- `InferenceService.close` joins for 10 s and raises if native code still runs.
