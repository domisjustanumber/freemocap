# G28R — Run times of the full benchmark and the frame count

**Status:** evidence; used by [HT08](HT08-full-benchmark-stages-order-measures-and-rows.md), 2026-11-21
(measurements recorded in the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md); migrated, direct
commit).

## Decision

1. **Frame count.** With 150 frames, the CPU session took 19.5 s. With 300 frames, the CPU pair took 40.1 and
   38.7 s from start to end (2 runs). The session set `BENCHMARK_FRAMES` to 300 after this trial, as the owner
   directed ("count set after measurement on the dev PC").
2. **freemocap part.** The plan gave 165 s (download 20 s, preparation 10 s, 45 s for each pair, Blender 20 s). The
   freemocap part measured 147.7 and 144.5 s.
3. **skellytracker part.** The full plan of skellytracker had 38 checks and an estimate of 333 s. A full run of
   DirectML on the RTX 3070 took about 80 s at the pin `03e5b3bb`. On 2026-11-20 a full run on the dev system measured 316 s against a plan
   estimate of about 8 minutes.
4. **Whole run.** The owner accepted a full run of about 15 to 25 minutes (skellycam 6 to 11 minutes,
   skellytracker about 5 minutes, plus the benchmark of freemocap).

## Reason

- [ADR-HT08](HT08-full-benchmark-stages-order-measures-and-rows.md) item 4 sets the frame count. 300 frames give
  about 40 s for each CPU pair, inside the 45 s estimate of each pair.
- [ADR-5ZRX](5ZRX-full-benchmark-offer-consent-lock-and-clean-up.md) item 7 replaced the first figure "approx 5 to
  10 mins" with the total of the plans.

## Evidence

- System: i7-14700K, RTX 3070 and UHD 770, Windows. A scratch EP store. CUDA and TensorRT RTX were not installed
  in it, so they were not measured.
- Method: direct runs of the full level, with no script. The checkpoint sections "Recording benchmark",
  "Full benchmark run" and "Decisions of the third grilling" (G11) hold the numbers.
- Not measured: a real download through the app, a whole full run in the real window, Linux and macOS.
