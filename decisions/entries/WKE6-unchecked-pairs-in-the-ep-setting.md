# WKE6 — Unchecked EP and GPU pairs in the EP setting

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), decisions 16, 17
and 19, the uncertified-EP flow F1 to F12, and H3).

## Decision

A pair is one EP on one GPU. skellytracker refuses, with no override, a pair with no reviewed row and no local
pass, and a pair that failed on this system (skellytracker ADR-ER5X). The quick check is the only way in.

1. **Usable.** Only a pass of the whole quick check makes a pair with no reviewed row usable. This applies to each
   EP, `cuda` and `trt-rtx` included. A pass makes the pair usable on this system at once. freemocap takes the
   usability of a pair only from the `DeviceCheck` flags of that pair, never from the EP state alone.
2. **Field-test EPs.** A passed quick check is the opt-in of a field-test EP (`directml`, `amdgpu`, `migraphx`)
   (skellytracker ADR-21BK item 2). freemocap adds no other click. `recommend()` never returns a field-test EP, so
   Auto never uses one.
3. **Menu.** The menu shows an unchecked pair with its marker. A pair that failed on this system stays visible
   with its reason. A choice of either pair opens the quick-check prompt. The Device row marks each GPU with its
   own state. A pair that is not installed, and a field-test pair with no opt-in, stay hidden.
4. **States.** The UI words five states: reviewed has no marker; "passed on this system, not yet reviewed"; "not
   checked on this system"; "check failed on this system"; "exited uncleanly twice". A field-test EP has no
   marker of its own.
5. **Prompt.** The prompt has two choices: "Run quick check" and "Not now". freemocap has no "Do not ask again"
   and does not call `dismiss_certification`.
6. **Selection.** "Not now", a cancel and a failure keep the EP setting as it was. A pass makes the new pair the
   selection. A second choice of the pair asks again.
7. **One pair.** One prompt checks one pair:
   `certify("quick", execution_providers=[key], device=<the GPU of the Device row>, pipeline=<the pipeline>)`.
8. **Auto.** On Auto, the app runs what `recommend()` chose. When a skipped candidate has `needs_check`, a
   non-blocking notice "A faster option needs a quick check on this system" with "Run quick check" shows beside
   the EP setting. The notice has no dismiss. It follows the observation of the server.
9. **Saved pair refused.** A saved pair that skellytracker refuses makes the start fail visibly, with the reason
   and the quick-check offer. The app never switches to the CPU by itself.
10. **Progress.** The progress is the checks done of the total, with a one-off "up to about N seconds". It has no
    countdown.
11. **Result texts.** The six result texts are "Quick check passed", "Quick check failed: <reason>", "Quick check
    cancelled", "Quick check did not run: <reason>", "Quick check stopped unexpectedly" and "Quick check could
    not start: <reason>". Each shows beside the EP until the next check or a change of the selection.
12. **Hard failure.** A non-finite output, a crash, a hang or two unclean exits in a row mark the pair failed on
    this system, and Auto skips it. The EP never changes during a recording.

## Reason

- skellytracker refuses an unchecked pair with no override (skellytracker ADR-ER5X). A hidden pair gives the user
  no way to check it.
- The `seconds_left` of skellytracker is a sum of ceilings that are not calibrated. A ticking countdown would be
  wrong.
- A choice that the app keeps after a "Not now" or a failure would select a pair that the server refuses.
- A switch to the CPU hides a fault from the user.

## Alternatives rejected

- **Hide each unchecked pair.** It was built first and reversed (F1).
- **"Certify now / later / do not ask again".** The owner replaced it with two choices (F5).
- **A ticking countdown.** See the reason.

## Not repeated

- The `checks` names of skellytracker stay `<key>@<device>` on each system. Read a pair by its
  `(execution_provider, device_key)`, not by parsing a check name.
- Two GPUs of one model share one local result, as a reviewed row does.
