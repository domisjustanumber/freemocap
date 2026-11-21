# FS1H — The exit notice and the shutdown

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), decisions 31 and
32, G9 and G10).

## Decision

1. **Electron close.** A close of the app sends `POST /shutdown` to the backend. It waits `SHUTDOWN_GRACE_MS`. It
   kills the process tree only as the fallback, and only one time for each close
   (`freemocap-ui/electron/main/services/python-server.ts`). `SHUTDOWN_GRACE_MS` stays 10 s until the owner
   measures a shutdown with cameras attached. The measurement procedure is G9 of the checkpoint.
2. **Exit notice.** The first act of the backend on a requested exit is `skellytracker.note_exit_requested()`. It
   is called in `POST /shutdown` through `to_thread`, before `close_camera_groups()`. It is called in
   `serve_application` when the reload stop is first seen and no fatal error set the kill flag. It is called in
   the SIGINT and SIGTERM handler of `freemocap/__main__.py`. It is not called on the fatal-error path.
3. **The rule of skellytracker (skellytracker ADR-ER5X item 5).** Only the process that opened a GPU EP session
   writes a session marker. An end of that process with no clean interpreter exit and no notice counts as an
   unclean exit. Two in a row mark the pair failed. Thus a process that held a GPU EP session must give the notice
   before it ends on purpose by `os._exit`, terminate or kill. It must never give the notice on a crash or a hang.
4. **A child ends its own session.** freemocap must ask a child process that holds a GPU EP session to end. The
   child ends its session and gives the notice. A kill comes only after a grace time:
   - the dataset preparation worker: a stop file, exit code 130, the kill after 10 s;
   - a pair child of the full benchmark: `STOP_GRACE_SECONDS` (1.5 s) in `freemocap/certification.py`;
   - the fresh copy of the realtime quick check: the closed stdin, then `REALTIME_STOP_GRACE_SECONDS` (3 s).

   The certify children of skellytracker write no marker, so their kill adds no count.
5. **A stale backend.** A start without `--port` sends `POST /shutdown` to the process that holds port 53117. It
   waits 5 s, and then it kills that process (`freemocap/utilities/kill_process_on_port.py`).
6. **Tools.** `tracker_matrix` and `machine_benchmarks` wait for their child, which ends by itself on Ctrl+C.

## Reason

- The old close killed the backend tree each time, and the shutdown ran two times.
- A kill of a process with a GPU session leaves the marker of skellytracker. In the second real full run, two
  cancels marked DirectML on the RTX 3070 as `unclean-exits`, and the next run did not use that pair
  ([ADR-44ZC](44ZC-stop-and-cancel-times-evidence.md)).
- The owner chose "fix now, measure later" for the grace time, because no environment on the dev system ran the
  current freemocap at that time.

## Consequences

- An orphaned preparation worker runs to its end. The stale-backend request adds up to about 10 s to a start after
  a crash. Both stay as built (G10).

## Evidence

- [ADR-44ZC](44ZC-stop-and-cancel-times-evidence.md): the idle shutdown time, the cancel times and the stop
  grace.

## Not repeated

- Do not call `note_exit_requested()` on a crash path or in a process that is not about to end. A hang must keep
  its count.
- `os._exit` skips `atexit`, so the clean-exit removal of the marker of skellytracker does not run. Give the
  notice before `os._exit`.

## Open work

[open-work.md](../open-work.md)
