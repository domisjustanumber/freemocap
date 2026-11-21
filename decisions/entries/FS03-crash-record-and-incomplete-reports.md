# FS03 — The crash record and the incomplete reports, at both levels

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), "Crash, both
levels" of the fifth grilling, the crash record, Q59, Q80 and format 1.6.0).

## Decision

1. **Crash record.** While a check runs, freemocap writes the name of the running check to a small file:
   `<base data folder>/certify/running-check.json` (the level, the pair and the newest progress message). It
   rewrites the file at each new progress message. It removes the file at each ordinary end of the check
   (`freemocap/system/certify/crash_record.py`).
2. **Found at launch.** A crash record found at launch records the running check as `fail` with `crashed`, and the
   unfinished checks as `not-run` with `interrupted`. The check is not run again automatically. Its report is in
   the share list, marked incomplete. A crash of the child process ends in the same record.
3. **Pair failure.** At level quick, a crashed check counts as failed for its provider and GPU only. At level full,
   only a crashed `:probe` or `:video` check fails its pair. freemocap writes the pair failure through the public
   `record_failed_pair` of skellytracker. An EP or GPU that the system no longer has is logged, not raised.
4. **Start check.** A crash in the own part of freemocap during the start check writes the crash marker of
   [ADR-YZC3](YZC3-start-check-required-run-and-lock.md) item 4.
5. **Incomplete report.** A cancelled or crashed run keeps its finished stages in a report that the user can share.
   The report is marked incomplete, and the other checks are "not run". The share list shows "incomplete" on its
   line.
6. **Abandon.** When the backend dies during a run, the running `certify()` of each package gets `abandon`
   (skellycertify format 2.4). It stops as for a cancel, with its clean-up, and no report goes to the hand-in list.
   The child ends when `certify()` returns, or after `CANCEL_GRACE_SECONDS`. Between two packages it ends at once.

## Reason

- A crash can be a fault of the system that the user must report. A check that crashed and runs again by itself
  can crash the app at each launch.
- A crash of one check says nothing about the other pairs, so only its own pair fails.
- The finished stages of a long run are evidence. A cancel must not lose them.
- A child whose backend died has no one to report to. It must stop its work and end.

## Consequences

- The refresh gap of 0.5 s can lose the newest progress message before a crash.
- `coreml` has no device in its check name, so a crash gives no pair failure for it.
- A crash record of a freemocap run lists the test media of its progress ([ADR-GZ9H](GZ9H-report-file-and-format-1-6-0.md)).

## Alternatives rejected

- **Run the crashed check again at the next launch.** The owner rejected it: the check could crash again.

## Not repeated

- A child whose backend died must not skip its own cancel path. Before the fix, one crash gave two reports.

## Open work

[open-work.md](../open-work.md)
