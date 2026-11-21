# FG8V — The busy rule: nothing runs while a check runs, and one admission lock

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), decision 20, F7,
F8, H1, H2, J8 and item 1 of the order of work of the fifth grilling).

## Decision

1. **A check waits for no work.** A check is an EP pair quick check, the start check or the full benchmark. The
   server refuses a check start with 409 `pipelines-running`, with the holders in `gpu_held_by`, while one of
   these runs (the `kind` is in brackets): a realtime pipeline or its startup (`realtime`), a recording
   (`recording`), a connected camera group with no realtime pipeline (`cameras`), a post-hoc mocap or calibration
   pipeline (`posthoc`), a sync job (`sync`), an export of each kind, Blender included (`export`), the file copy of
   a video import (`import`), the Blender add-on install (`blender-addon`), and an EP pack install or remove
   (`ep-pack`).
2. **No work starts during a check.** While a check runs, the server refuses each of those starts with 409
   `quick-check-running` and the facts of the run. While an EP pack job runs, it refuses them with 409
   `ep-pack-running`.
3. **Start check required.** While the start check is required, the server refuses each camera start and each
   pipeline start with 409 `start-check-required` and one sentence.
4. **Always allowed.** Reads, the cancel of a check, the shutdown, the close and the pause of cameras, the camera
   detection, the stop of a recording, the cancel of a pipeline, a sync job or an export, the open of a `.blend`
   file in Blender and the save of a calibration transform.
5. **No queue.** A refusal is the answer to that request only. The server stores no gate and queues nothing. After
   the check ends, the user starts the work again.
6. **Stable controls.** The UI shows the sentence of the server beside the control. The control keeps its label and
   stays clickable.
7. **One lock.** `QuickCheckManager.admission_lock` in `freemocap/system/certify/quick_check.py` closes the race of
   two starts in one instant. A check reads the holders and sets its run under the lock. Each other start checks
   for a run and registers a claim (`PipelineHold(kind, "starting")`) under the lock. The lock is never held across
   a long start. `FreemocapApplication.pipeline_holds()` is the one list of what runs.
8. **Names.** `pipelines-running`, `gpu_held_by` and `PipelineHold` are historical names. They cover all work,
   CPU work and cameras included. `kind` is an open string in the message model and in the client schema.

## Reason

- The owner: "nothing runs while the check is running". A check measures the system. Other work changes the
  result and can hold the GPU or the cameras.
- A gate that the client stores goes stale after a restart. The self-describing transport rule of
  [`AGENTS.md`](../../AGENTS.md#self-describing-transport-is-an-intentional-invariant) requires a refusal that is
  the answer to one request.
- Before the lock, a start and a check admitted in the same instant could both get through.

## Consequences

- The new 409 answers of the sync, export and camera routes are not declared in OpenAPI, as the older answers of
  the realtime, recording and post-hoc routes are not.
- The camera start of skellycam's router in `freemocap/app/app.py` goes through `camera_starts_admitted`. The UI
  starts a recording through that route.

## Evidence

- `test_a_start_and_a_check_admitted_at_once_cannot_both_get_through` fails when the lock is removed from the
  claim.

## Not repeated

- Do not add a work start route without its admission (`admitted(kind)` or `quick_checks.admit(kind)`). The
  skellycam recording route was such a gap.
- Do not disable or relabel a control because a request was refused.
