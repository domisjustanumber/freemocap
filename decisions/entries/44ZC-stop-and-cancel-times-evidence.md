# 44ZC — Shutdown, cancel and stop times

**Status:** evidence; used by [FS1H](FS1H-exit-notice-and-shutdown.md), 2026-11-21 (measurements recorded in the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md); migrated, direct
commit).

## Decision

1. **Idle shutdown.** From `POST /shutdown` to the exit of an idle backend: 1353, 1313 and 1351 ms, with no kill.
   A backend that held a GPU EP session in a post-hoc run exited in 1.5 s, with no marker left. A shutdown with
   cameras attached was not measured.
2. **Cancel of a full run.** The server ended the run 0.05 to 0.27 s after the `DELETE`, at each point of a pair. A
   cancel during a pair of the recording benchmark ended the run 0.31 s later, with no child process left.
3. **Kill leaves markers.** When the cancel killed the pair child at once, the unclean-exit markers of
   skellytracker stayed. Two cancels marked DirectML on the RTX 3070 as `unclean-exits`, and the next run gave that
   pair `ep-not-passed`.
4. **Stop grace.** With `STOP_GRACE_SECONDS` 1.5, the pair child ends its session itself, then the kill comes. The
   cancel then took 0.8 to 1.7 s, left no marker, and the next run ran each pair.
5. **Realtime check.** A cancel took 0.3 to 2.7 s with a clean end once the session ran. Before the session, the
   fresh copy was killed after the 3 s grace, before a model loaded. The session shutdown after a stop took 0.2 to
   2.0 s.

## Reason

- [ADR-FS1H](FS1H-exit-notice-and-shutdown.md) items 1 and 4 rest on these numbers: the 10 s grace of the Electron
  close is far above the idle shutdown, and a child must end its own session before a kill.

## Evidence

- System: i7-14700K, RTX 3070 (and RTX 3060 for the post-hoc shutdown), Windows. A scratch EP store.
- Method: direct runs and the PowerShell procedure of G9 in the checkpoint, with no script. The checkpoint sections
  "Decisions of the third grilling" (G9), "Exit signal and shutdown", "Defects of the second real run" (item 7) and
  "Realtime session quick check" hold the numbers.
- The first cancel time of 31 s came from the wait of the UI script, not from the server.
