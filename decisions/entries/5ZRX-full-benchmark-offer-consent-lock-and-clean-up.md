# 5ZRX — The full benchmark: the offer, the consent step, the lock and the clean-up

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), the fifth
grilling, Q62, Q64, Q72 and Q79).

## Decision

1. **Name.** The button is "Full benchmark". It runs the full tests of each package.
2. **Offer.** The app offers the full benchmark only after the start check passed
   ([ADR-YZC3](YZC3-start-check-required-run-and-lock.md) item 9). It offers it also from the Certification
   button. It is never required. The server refuses a start before that pass with `start-check-not-passed`.
3. **Consent step.** Before the run, the dialog shows a consent step in line. It has a table of the downloads
   (name, source host, size and the total), the time estimate of each package, the checkbox "remove benchmark data
   after a successful run", on by default, and Start and Cancel. Nothing downloads before Start.
4. **Downloads guard.** `POST /freemocap/certify/full_benchmark` takes the names of the downloads that the consent
   step listed. When the current plan needs a download that the consent did not list, the server refuses with
   `downloads-changed`. The UI then reads the plan again and shows the new consent step. The guard compares the
   names only. The UI reads the plan again at each opening of the consent step.
5. **Lock.** The app is locked during the run, as during the start check. One gate (`appLocked`) covers the
   `inert` layer, the keyboard shortcuts and the menu actions. "Cancel check" stays usable, and a cancel unlocks
   the app at once.
6. **Clean-up.** After a successful run with the checkbox on, the clean-up removes what the run downloaded and the
   processing output of the run. It keeps the report, the bundled test images and the files that were in the
   shared test media folder before the run. After a failed or a cancelled run, it removes nothing. A partial or
   wrong download is always deleted. freemocap gets `remove_data` only when each earlier package passed. A
   reported-only failure ([ADR-HT08](HT08-full-benchmark-stages-order-measures-and-rows.md) item 7) does not stop
   the clean-up. The start of a run replaces the work folder of an earlier run.
7. **Time.** A full run of about 15 to 25 minutes is accepted. The dialog shows the total from the plans of the
   packages, not a fixed figure.
8. **Result.** The result is one more report in the share list. It is never pruned.

## Reason

- A download needs the consent of the user, who sees the source and the size first.
- A plan can change between the opening of the consent step and Start, for example when an archive was deleted.
  The user must not get a download that the consent did not list.
- A failed or cancelled run keeps its data, so that the failure can be examined and a re-run downloads nothing.
- The full benchmark changes the stores of the packages. An unfinished start check gives no base for it.

## Consequences

- The first estimate "approx 5 to 10 mins" was replaced by the measured total
  ([ADR-G28R](G28R-full-benchmark-run-times-evidence.md)).
- No full benchmark has run in a real window from start to end with a real download.
  [open-work.md](../open-work.md) lists it.

## Evidence

- [ADR-G28R](G28R-full-benchmark-run-times-evidence.md): the full run times on the dev system.

## Alternatives rejected

- **A separate consent window.** The owner kept the consent step in line in the dialog (Q64).

## Not repeated

- A consent that listed more downloads than the plan needs now is not refused.

## Open work

[open-work.md](../open-work.md)
