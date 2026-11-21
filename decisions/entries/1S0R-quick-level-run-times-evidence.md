# 1S0R — Run times of level quick on the dev system

**Status:** evidence; used by [WKC0](WKC0-quick-level-budget-and-session-checks.md), 2026-11-21 (measurements
recorded in the [certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md);
migrated, direct commit).

## Decision

1. **freemocap, seven quick checks.** The quick module of freemocap with `posthoc-session` and without
   `realtime-session` took 10.4, 9.5 and 9.5 s on the CPU (17 s inside pytest). After the pin at `346b77eb` it took
   10.2 s, and after the pin at `0342ecb8` 10.0 s. Its plan estimate is 25 s.
2. **freemocap, eight quick checks.** With `realtime-session`, the module took 20.16, 18.77 and 19.71 s (3 runs).
   `realtime-session` took 8.48 to 8.71 s: 3.01 to 3.35 s for the start of the fresh copy and 5.35 to 5.47 s for
   the session. `posthoc-session` took 9.17 to 10.03 s.
3. **skellytracker.** 11 quick checks (the CPU, DirectML on two GPUs, `mediapipe:smoke`) took 24.4 and 24.6 s
   against a plan estimate of 48 s.
4. **Before the session checks.** A camera-less realtime session in a main process took about 7.4 s. Frame 0 is not
   tracked, because the models load more slowly than the 2 s wait of the aggregator.

## Reason

- The share of freemocap was 15 s. Items 1 and 2 show that the two session checks need more than 15 s and fit in
  25 s. The rule of [ADR-WKC0](WKC0-quick-level-budget-and-session-checks.md) rests on them.

## Evidence

- System: i7-14700K, RTX 3070 and UHD 770, Windows. A scratch EP store, so Auto chose the CPU. Other test runs
  were on the system at the same time as item 2.
- Method: direct runs of the start check and of `certification.certify("quick")`, with no script. The checkpoint
  sections "Owner's answers of 2026-11-21", "Pin at 0342ecb8" and "Realtime session quick check" hold the tables.
- Not measured: a frozen build, a GPU EP in the session checks, Linux and macOS.
