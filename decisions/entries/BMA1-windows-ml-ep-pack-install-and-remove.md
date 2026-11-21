# BMA1 — The install and the remove of a Windows ML EP pack

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), F16, J1 to J6,
J10 and Q74).

## Decision

1. **Which EPs.** The app offers the controls only for an EP whose `PackStatus.source` is `windows-ml` (today
   `amdgpu` and `migraphx`). The state must not be `unsupported`, and not `field_test` (a field-test EP with no
   opt-in). The wheel packs (`cuda`, `trt-rtx`) get no install or remove control.
2. **Controls.** Install shows only for `not_installed`. Remove always shows for a shown EP. Remove asks first,
   with "Remove" and "Keep". The app has no Repair button: the user removes, then installs.
3. **Busy rule.** An install or a remove is refused while a pipeline or a check runs. While it runs, it refuses
   each other start ([ADR-FG8V](FG8V-busy-rule-and-admission-lock.md)).
4. **Job.** One install or remove runs at a time, in a thread of the backend
   (`freemocap/system/certify/ep_packs.py`). The routes are `POST /freemocap/certify/ep_pack/install`,
   `POST /freemocap/certify/ep_pack/remove` and `DELETE /freemocap/certify/ep_pack`. The progress and the last
   result ride `app_state.state.certification` (`pack_run`, `last_pack_result`).
5. **Place.** The panel stays beside the EP setting
   (`freemocap-ui/src/components/mocap-setup/ep-pack-panel.tsx`). It moves into the Certification dialog when the
   dialog gets its EP list.
6. **Texts.** The texts of `freemocap-ui/src/services/server/ep-packs.ts` are confirmed as written. A refusal names
   the EP by its label and the action as "provider pack install" or "provider pack remove" (Q74).

## Reason

- skellytracker says that a field-test EP with no opt-in must never be offered, and it refuses its install.
- A Repair of a `stale` or `not_ready` pack would record a package that was present as `was_present`, and a later
  Remove would keep it.
- Remove clears the `pending` record of a cancelled install, so it must always be there.

## Consequences

- The controls of a field-test EP appear only after the CLI opt-in of skellytracker. skellytracker was asked to
  report the install state of a field-test pack.
- The job is tested only with stand-ins. It has never run for real. It needs Windows 11 with an AMD GPU (J10).

## Open work

[open-work.md](../open-work.md)
