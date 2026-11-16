# Removal list: four detector choices

User decision, 2026-11-16: only `rtmpose` and `mediapipe` are migrated. This list removes
`rtmw_mediapipe_hands`, `mediapipe_hands`, `rtmw_onnx_hands` and `dlc`, with the code that only
they use, as one reviewable commit group. The features stay on `sfn26`. The migration doc names
them under "Features this migration removes".

Line numbers are for freemocap `ca0c17cc`, found by grep and reading. Nothing has been run yet.
Paths are relative to the repo root.

## 1. Files to delete whole

### Backend

| File | Importers to edit |
|---|---|
| `freemocap/core/pipeline/realtime/hand_observations.py` (`TrackedHand` association across cameras) | `core/pipeline/realtime/realtime_aggregator_node.py:50`, `pubsub/pubsub_topics.py:24`; tests (§4) |
| `freemocap/api/http/dlc/dlc_router.py`, `freemocap/api/http/dlc/__init__.py` | `api/routers.py:8,35`, `api/openapi_tags.py:21` (tag `DeepLabCut`) |
| `freemocap/core/skeletons/dlc_object_skeleton.py` | `core/skeletons/tracked_skeleton_set.py:42`, `core/pipeline/dataflow/recording_pipeline.py:99` |
| `freemocap/tools/datasets/hand_tracker_comparison.py` | No code importer. Docs: `TRACKER_COMPOSITION_INTEGRATION.md:55`, `freemocap/tools/datasets/README.md:499-505` |

### UI

| File | Importers to edit |
|---|---|
| `freemocap-ui/src/components/mocap-setup/dlc-model-settings.tsx` | `RealtimePipelineConfigTree.tsx:2`, `mocap-detector-settings.tsx:1`, `realtimepipeline-mediapipedetector-settings.tsx:2`, `RealtimeProcessingSettings.tsx:6` |
| `.../mocap-setup/dlc-model-settings.css` | `dlc-model-settings.tsx:7`, `tracker-settings-dialog.tsx:6` |
| `.../mocap-setup/hand-count-input.tsx` | `RealtimePipelineConfigTree.tsx:1`, `detector-setting-rows.tsx:3`, `realtimepipeline-mediapipedetector-settings.tsx:1`, `detector-setting-rows.test.tsx:8` |
| `freemocap-ui/src/services/server/dlc-models.ts`, `dlc-models.test.ts` | `dlc-model-settings.tsx:12-13` |
| `freemocap-ui/src/store/slices/mocap/dlc-execution-settings.ts` | `store/slices/mocap/mocap-thunks.ts:3` |
| `freemocap-ui/e2e/dlc-settings-dialog.spec.ts` | none |

## 2. Edits in backend files that stay

All paths are under `freemocap/`.

- **Configs**
  - `core/pipeline/realtime/camera_node_config.py`:
    - `:17` and `:31`: the Literal becomes `"rtmpose", "mediapipe"`;
    - `:32-34` remove `dlc_model_path`, `dlc_geometry_path` and `dlc_confidence_threshold`;
    - `:35` the comment;
    - `:43` remove `hand_count`;
    - `:70-74` remove `hand_count` and the `dlc_*` entries of `skeleton_settings`. `mediapipe_num_hands`
      stays.
  - `core/pipeline/realtime/realtime_pipeline_config.py:27-34`: delete `validate_dlc_execution`. Its
    import of `model_validator` (`:1`) is then unused.
  - `core/tasks/mocap/mocap_task_config.py`:
    - `:69` the Literal becomes `"rtmpose", "mediapipe"`;
    - `:72` the description;
    - `:74-76` the `dlc_*` fields;
    - `:191-197` the DLC block (keep `:198-201`).
- **Tracker setup**
  - `core/tracking/tracker_factory.py`: `:70-73` the DLC provider branch; `:202-211` the DLC branch;
    `:213` the `hand_count=` argument.
  - `core/tracking/tracker_definitions.py:18`: `COMBINED_WHOLEBODY_DEFINITION` (no users).
- **Skeletons**
  - `core/skeletons/standard_human_skeleton.py:70-90`: `build_hand_bundles`.
  - `core/skeletons/tracked_skeleton_set.py`: `:23` the import; `:40-44` the DLC branch; `:45` the
    condition becomes `skeleton_tracking_enabled`; `:52-53` the hands branch.
- **Realtime aggregator**, `core/pipeline/realtime/realtime_aggregator_node.py`:
  - `:50` the `HandAssociation` import, and `:60` `build_reconstruction_states` (used only at
    `:957`);
  - `:406-407`, and the `hand_states.clear()` at `:518`, `:530`, `:547`, `:595`, `:615` and `:855`;
  - `:504-509`, `:865-874`;
  - `:886` remove `and detector_type != "mediapipe_hands"`;
  - `:949-968` becomes a plain list of `(bundle, state, filter_result)`;
  - `:969`, `:995` the key is always `bundle.model_id`;
  - `:1003` the filter; `:1033` `hand_observations=`.
  - Keep the detector change detection at `:542-544`.
- **Other realtime and pubsub**
  - `core/pipeline/realtime/temporal_pipeline.py:65,67-77`: the `"hands"` branch. `:7` `replace`
    is then unused.
  - `core/pipeline/realtime/realtime_pipeline.py:17,80,209,324,403-405,432,434-439`: the DLC
    `tracker_metadata`.
  - `pubsub/pubsub_topics.py:24,156,167-168`: `hand_observations`.
- **Streaming**
  - `core/streaming/message_composer.py`:
    - `:16-17` and `:36-39` imports (`TEMPORAL_STATUS_LABELS` is imported again at `:91`);
    - `:47-49`, `:61`;
    - `:72-79` one subject for each skeleton;
    - `:81`, `:97`;
    - `:111-113` `tracker_id=skeleton.detector_type`, with no `handedness` and no `connection_groups`;
    - `:119-143` the DLC block;
    - `:175-179`.
  - `core/streaming/message_model.py:540,545`: `TrackerObservation.handedness`. Keep
    `connection_groups` (§3).
  - `core/streaming/producers/producer_contexts.py:15,32,48,51`.
  - `core/streaming/producers/overlay_producer.py`: `:10-11`, `:21-41`, `:60-70` the hand branch
    (keep `camera_2d_detections`), `:62` `stage_path=`.
  - `core/streaming/producers/keypoints_producer.py:30-35`: the hand branch.
  - `core/streaming/producers/box_producer.py:43-44`: `skeleton.detector_type == "dlc" or`.
  - `core/streaming/channel_helpers.py`: `:57-59` the three entries of `_OBSERVATION_BY_DETECTOR`;
    `:86`, `:99-100`, `:113-125` the `stage_path` parameter (only hand and DLC bundles set it).
  - `api/websocket/websocket_server.py:33,161,211,214-220,288`: `independent_trackers`.
- **HTTP and posthoc**
  - `api/routers.py:8,35` and `api/openapi_tags.py:21`.
  - `core/pipeline/dataflow/recording_pipeline.py`:
    - `:96-100` becomes `bundles = (build_standard_human_bundle(...),)`;
    - `:109-115`;
    - `:206-208`, `:212-213` (`model_only` is always False);
    - `:231-233`;
    - `:242` becomes `== "rtmpose"`.
  - `core/pipeline/dataflow/application_pipeline.py:145-146`: the label dict keeps `rtmpose` and
    `mediapipe`.
  - `core/pipeline/posthoc/annotation_style.py:138-152`: the DLC branch.
  - `core/pipeline/dataflow/saved_observation_source.py:23`: the `'dlc_'` prefix.
- **Tools**
  - `tools/datasets/__main__.py:41` and `tools/machine_benchmarks.py:344`: drop
    `rtmw_mediapipe_hands` from the choices.
  - `tools/datasets/README.md:3-8,499-505`.

## 3. Code that looks hand- or DLC-only but stays

- skellytracker `mediapipe_hand_names` and `hand_connections`: `tracker_profile("mediapipe")` builds
  the MediaPipe keypoints and edges from them. freemocap reaches them through `tracker_profile`:
  - `standard_human_skeleton.py:58-59`;
  - `tracker_definitions.py:11-14`;
  - `channel_helpers.py:69` (the crop paths).
  Only the direct imports go (`standard_human_skeleton.py:72`, `message_composer.py:17`). This
  whole profile use goes later with the presets (migration doc §2 item 1).
- `mediapipe_num_hands` (`camera_node_config.py:44`, `mocap_task_config.py:133`) belongs to the
  `mediapipe` choice.
- Axis handedness (`message_model.py:72-75,144,153`, SDK `message-contract.ts:42`,
  `freemocap-stream frames.py:28,37`) is a coordinate convention, not hands.
- `TemporalPipeline` for the main points (`realtime_aggregator_node.py:408`).
- The standard-human hand geometry:
  - the rtmpose and mediapipe tests in `test_hand_reconstruction_contract.py:1-117`, whose
    `tracked_hands` is imported by `test_reconstruction_anchor.py:12` and
    `test_recording_batch_reconstruction.py:18`;
  - the hand colours at `annotation_style.py:23-36,57-69`;
  - `streaming/outputs/vmc.py:65`.
- Model-less trackers on the wire (`TrackerObservation.connection_groups`, `model_id=None`) are a
  generic protocol feature:
  - freemocap-stream `frames.py:117-135`;
  - SDK `frame-resolution.ts:262`;
  - UI tests `frame-resolution.test.ts:8-22`, `receive-reuse.test.ts:48-65` and
    `skeleton-overlay.test.ts:78-96`.
- Old DLC recordings need these to load:
  - `object_geometry` and `RigidObjectGeometry` (`core/skeletons/rigid_object_geometry.py`);
  - `TrackedSkeletonBundle.tracker_stage_path` (`tracked_skeleton_bundle.py:106-107`);
  - `ModelDefinition.object_geometry` (`message_model.py:328-414`), with SDK `message-contract.ts:139`.
- `api/http/onnx/` is the generic EP router.
- The UI MediaPipe confidence rows.

## 4. Tests

- Delete these files, all in `freemocap/tests/`:
  - `test_dlc_application.py`, `test_dlc_rigid_object.py`, `test_dlc_streaming.py`;
  - `test_experimental_onnx_hands.py` (the env var `SKELLYTRACKER_HAND_CANDIDATE_DIR`);
  - `test_onnx_hand_benchmark.py`, `test_independent_hand_views.py`.
- Trim:
  - `test_hand_reconstruction_contract.py:118-153`: the test with two right hands.
  - `test_combined_tracker_integration.py`:
    - `:14` drop `"rtmw_mediapipe_hands"`;
    - `:41-45`, `:48-56`: delete the combined tests, or point the board test at
      `skeleton_tracker_config`;
    - `:61` change it to `"rtmpose"`.
  - `test_detector_streaming.py:20-21` (the filter), `:68-70` (the hybrid branch).
  - `test_model_presentation.py:32,64`.
  - `reference_recordings/test_realtime_pipeline.py`: `:221-243` the `mediapipe_hands` branch;
    `:282-295` the two replay tests.

## 5. UI and SDK

- **UI source** (`freemocap-ui/src/`)
  - `components/mocap-setup/detector-options.ts:8-9,12-17`.
  - `store/slices/realtime/realtime-types.ts:13,15,22-24,31`.
  - `store/slices/mocap/mocap-slice.ts`:
    - `:58` the Literal;
    - `:83-87`, `:204-208` the `dlc*` state;
    - `:315-317`, `:522` `mocapDlcSettingsChanged`;
    - `:231-236` map saved values (§7).
  - `store/slices/mocap/mocap-thunks.ts:3,17,38-39,69,311-312`.
  - `store/slices/realtime/realtime-settings.ts:18-40`, with its callers `realtime-slice.ts:6,97` and
    `realtime-thunks.ts:11,58-68`.
  - `store/slices/realtime/realtime-thunks.ts:21-22,26,44,68`.
  - `hooks/useRealtimePipelineSync.ts:35,48`.
  - `components/control-panels/realtime-panel/RealtimePipelineConfigTree.tsx`:
    - `:1-2,5`;
    - the DLC conditionals: `:86,134,146,171,177,189,194,197,217,347,418`;
    - the ONNX hands: `:94-96,109-111,128`;
    - `:205,220,249,254,269-272,274,277`.
  - `components/pipeline-progress/realtime/realtimepipeline-mediapipedetector-settings.tsx:1-2,34-38,43-58,65-67,86-88,120-122,136,143`.
  - `components/realtime-processing/RealtimeProcessingSettings.tsx:6,30,39,58`.
  - `components/mocap-setup/mocap-detector-settings.tsx:1,48-49,62,65,68`.
  - `components/mocap-setup/detector-setting-rows.tsx:2-3,9,23,49-52,110-117,129-137,148-149,157,160-212`.
  - `components/mocap-setup/processing-sections.tsx:79-81`.
  - `components/realtime-processing/realtime-switches.ts:10,24-26,31-32,38,49`.
  - `services/server/server-helpers/image-overlay/skeleton-overlay-renderer.ts:220-223`: the hand
    label.
  - Comments: `tracker-settings-dialog.css:1`, `realtime-settings.css:102`.
- **UI tests**
  - `detector-setting-rows.test.tsx`: delete `:132-158`. Edit
    `:8,25,39,89,95,98-102,106,122,124-127,212,246-250,255,270,272-276,283`. The tests at `:180` and
    `:239` use the hybrid to reach all four confidence rows; split them between `rtmpose` and
    `mediapipe`.
  - `realtime-switches.test.ts:15,58-68,134,148-150`.
  - `frame-resolution.test.ts:58-72` and `skeleton-overlay.test.ts:71-76`: the hand cases.
- **e2e** (`freemocap-ui/e2e/`)
  - `mocap-backend-contract.spec.ts:6,19,24-26,36,46-49,57-60`: the DLC half.
  - `realtime-processing-control.spec.ts:41`: it uses `'dlc'` to skip calibration loading, so it
    needs another setup.
  - `realtime-startup.spec.ts:70,113`.
  - `skeleton-detector-options.spec.ts:33-42`.
  - `tracker-modal-host.spec.ts:67`.
  - `fixtures/mocap-processing-request.baseline.json:32-33`.
  - The screenshot baselines may need to be made again.
- **SDK** (`packages/freemocap-client/`)
  - `src/transport/message-contract.ts:206` (`handedness`).
  - `src/transport/frame-types.ts:12-13,70`.
  - `src/transport/frame-resolution.ts:120,125-129,266`.
  - Generated files: `src/generated/schema.ts` and `operations.ts` come from `npm run generate`,
    from `contracts/openapi.json`. That file is made again from the running backend's
    `/openapi.json` (`freemocap-ui/UI-REFACTOR-HANDOFF.md:121`). `contracts/coverage.md` comes from
    `npm run coverage`.
  - Hand-kept: `contracts/operations.json:886-937`, `shared/server-contract/operations.json:886-937`
    (`coverage.mjs` checks the count), `shared/server-contract/README.md:56` and
    `tests/browser-bundle.test.mjs:10`.

## 6. Docs that name the four

- `TRACKER_COMPOSITION_INTEGRATION.md`;
- `current-work-plans/02-pipeline/experimental-onnx-hands.md`;
- `freemocap/tools/datasets/README.md`;
- `freemocap-ui/UI-REFACTOR-HANDOFF.md`, `freemocap-ui/UI-TEST-BASELINE.md`;
- `experiments/executable_graph_lab/production_view/DESIGN-SESSION-HANDOFF.md`;
- `benchmarks/WINDOWS-RESULTS-2026-11-04.md:79-80`;
- `shared/server-contract/README.md:56`.

The `benchmarks/results/*.json` files hold old data and stay.

## 7. Old recordings and saved settings

Only posthoc runs save models. Thus an old recording can hold `rtmw_mediapipe_hands` or `dlc`, but
not the two realtime-only choices.

- A restart from saved observations calls
  `freemocap/core/recording/result_processing/saved_observations.py:50`
  `PosthocMocapPipelineConfig.model_validate`, which refuses the two removed values once
  `mocap_task_config.py:69` changes. The old-recording reader must give a clear error at this
  place, for example "recorded with a removed detector; run again from the observations".
- `RecordedModel` forbids extra fields (`recording_model.py:17`). An old DLC rigid recording holds
  `object_geometry` and `tracker_stage_path`, so those fields stay (§3). Otherwise these readers
  break: `playback_queries.py:135`, `saved_spatial_source.py:51` and `saved_reconstruction.py:187`.
- UI saved settings: `mocap-slice.ts:231-236` loads `mocap.config` from local storage as it is. Map
  a saved `'dlc'` or `'rtmw_mediapipe_hands'` to `'rtmpose'`, and drop the `dlc*` keys.
- `CameraNodeConfig` forbids extra fields (`camera_node_config.py:27`), so a client that still sends
  `hand_count` or `dlc_*` gets HTTP 422.

## Not checked

- No test or type check ran, and the OpenAPI files were not made again.
- The skellytracker side was not checked.
- That the backend never saves a realtime config: this is from a grep only.
