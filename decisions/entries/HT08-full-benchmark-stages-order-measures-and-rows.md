# HT08 — The full benchmark: the stages, the order, the measures, the failures and the rows

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), the fifth
grilling, the recording benchmark, Q62, Q64, Q66, Q67 and Q69).

## Decision

1. **Order of the pairs.** In the part of skellytracker and in the benchmark of freemocap, the pairs run in this
   order: first the unknown providers (no reviewed pass for the provider, the GPU model and the OS in the bundled
   evidence), then the known-fastest, then the CPU as the baseline, then the rest. The known-fastest is the first
   reviewed pair in the `status().eps` order of skellytracker, which is its order of preference (today TensorRT
   RTX).
2. **Pairs.** A pair runs in the benchmark of freemocap only when its `DeviceCheck.usable` is true after the run of
   skellytracker. Else it is `not-run` with `ep-not-passed`.
3. **Recording.** The benchmark uses the freemocap sample recording `freemocap_sample_data.zip` from `SAMPLE_DATA`
   of `freemocap/tools/datasets/catalog.py`. The archive is kept in the shared test media folder as
   `<sha256>.zip` ([ADR-WP3Z](WP3Z-shared-test-media-folder.md)). The cut copy is in the work folder
   `<base data folder>/certify/benchmark`.
4. **Frame count.** Each pair processes a fixed number of frames: `BENCHMARK_FRAMES` (300) of each of the 3 videos,
   in the codec of the sample ([ADR-G28R](G28R-full-benchmark-run-times-evidence.md)).
5. **Measures.** For each stage, the report gives ms/frame with FPS. The numbers come from the
   `PerformanceReport` of the session, read with the code that `freemocap/tools/machine_benchmarks.py` uses. A
   frame is one synchronized frame set. The summary items are the seven stages inference, tracking,
   triangulation, filtering, reconstruction, saving and exports. The one-off session setup is a startup time, not
   a stage.
6. **Blender.** The Blender export runs one time, on the recording of the first finished pair, and it is timed as
   its own row. It runs only when Blender is already installed. The app never installs Blender for it. With no
   Blender, the check is `not-run` with `not-installed`, and its row reads "Skipped". The run uses the Blender path
   chosen in the settings, else the best guess.
7. **Failures.** A provider that fails its probe, video or live check is treated as after a failed quick check: the
   pair is failed on this system. A failed JPEG check (`<label>:jpeg`, `<label>:jpeg:<name>`) and a failed timing
   row (`<label>:pipeline-<n>`) are reported only. They do not change the result of the package. The UI lists them
   in a "Reported only" line.
8. **Progress.** The progress shows one row for each provider and GPU pair, with its state and a turning icon, and
   a count of the finished checks. It shows no percentage and no time remaining. The rows of each package are under
   a heading with the package name. A row can read "Partly done", "Failed" (also for a crashed check) or
   "Skipped". The rows stay after the run ends, until the next full run starts.
9. **Count.** The count and the total take only the check names with at most one `:`, and skip the pairs that the
   plan lists in `details.not_run`. The count of freemocap equals the `total` of its plan.

## Reason

- An unknown provider gives the most new evidence, so it runs first. The known-fastest and the CPU give the
  reference numbers.
- A JPEG check or a timing row measures a part, not the use of the provider in a session. Its failure must not
  mark a provider failed.
- A fixed frame count makes the numbers of two systems comparable.
- The Blender install is large, and it is the choice of the user.

## Consequences

- The Markdown file cannot print "skipped" for a check. It prints the `component` item
  ([ADR-GZ9H](GZ9H-report-file-and-format-1-6-0.md)).
- Labels come from `check_label` of skellytracker.

## Evidence

- [ADR-G28R](G28R-full-benchmark-run-times-evidence.md): the frame count and the run times.

## Not repeated

- Do not count a `<label>:jpeg:<name>` or an `:exit` row as a check. The count then goes past the total.
- A child must close and join its progress queue before it puts its result. Else the last progress message is lost.

## Open work

[open-work.md](../open-work.md)
