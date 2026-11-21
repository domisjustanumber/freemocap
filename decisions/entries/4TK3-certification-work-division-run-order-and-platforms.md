# 4TK3 — Certification: the division of work between the packages, the run order and the platforms

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), sections
"Ownership", decision 9 and "Decisions of the fifth grilling").

## Decision

1. **Owners.** skellytracker owns the execution-provider (EP) state, the EP packs, the Windows ML catalog
   installs, the EP checks, the EP store (local passes, failures, its hand-in list, its saved reports), the
   unclean-exit count, the ONNX Runtime PyInstaller hook, the hardware facts and the live metrics. skellycam owns
   the camera checks and the camera evidence. freemocap owns its own checks, the run of the `certify()` of each
   package, the merge of the module reports into one report file, the local record of a start-check pass, the
   anonymous ping and all of the UI. skellycertify owns the report format, the reviewer procedure and the relay.
   It has no shared code package.
2. **No EP knowledge in freemocap.** freemocap gets each EP fact through the public interface of skellytracker.
   `freemocap/tests/test_no_execution_provider_knowledge.py` checks this. freemocap never edits skellytracker.
   Each change that freemocap needs is a request to the skellytracker session.
3. **Level full.** skellycam owns the cameras, the recording of camera frames, the disk speed, the take load and
   the CPU use of its own processes. skellytracker owns the EP correctness, the GPU JPEG suite and the inference
   timing. freemocap owns the end-to-end post-hoc run on a known-good recording, the Blender export when Blender
   is installed, the app and install facts, and only the write access to its data folder. No package runs a
   whole-system CPU benchmark. freemocap makes no second recording.
4. **No repeated work.** The checks of one package must not repeat the work of another package, at each level.
5. **Run order.** The packages run in this order: skellycam, skellytracker, freemocap. freemocap must use the new
   skellytracker pipelines, not the legacy pipelines. It runs only on the providers that passed the checks of
   skellytracker.
6. **Contract.** Each package gives `certify(level, progress=None, cancel=None)` and `certify_plan(level)`, as the
   skellycertify report format states. freemocap runs the packages in a `spawn` child process. It sends `progress`
   through a queue and `cancel` as a `multiprocessing.Event`.
7. **Platform validation.** All system, platform, hardware and EP validation is done through the certify process
   in freemocap builds. Thus a Linux or macOS certification run needs a freemocap build on that platform. Each
   platform is validated on its own. Linux and macOS do not wait for Windows.
8. **skellycam's part.** skellycam's part joins when the skellycam session names a green commit with
   `skellycam.certify`. Until then, freemocap adds no placeholder for it.

## Reason

- One owner for each fact prevents two packages from checking one thing with two rules.
- The owner made the freemocap session the authority for the division of level full. The other sessions follow
  it.
- freemocap must know which providers passed before it runs a pipeline on them. skellycam must check the cameras
  before the other packages use the system.
- A source tree is not what a user runs. Only a build shows the bundle, the paths and the process model of the
  system of a user.

## Consequences

- A change of a check that crosses a package boundary needs a request to the session of that package.
- The skellycam part is not built. [open-work.md](../open-work.md) lists it.

## Alternatives rejected

- **A whole-system CPU benchmark in one package.** It repeats the work of the other packages, and it measures
  nothing that one package owns.
- **Windows first, the other platforms later.** On 2026-11-20 the owner replaced this rule: each platform is
  validated on its own.

## Not repeated

- Do not add an EP name, an EP rule or a detector rule to freemocap. Ask skellytracker for an interface.

## Open work

[open-work.md](../open-work.md)
