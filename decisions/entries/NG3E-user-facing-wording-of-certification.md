# NG3E — The words that a user reads: "system", the confirmed sentences and the reason sentences

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), F12, G1, H3, J6,
item 3 of the order of work of the fifth grilling, Q61, Q66, Q67, Q69 and Q74).

## Decision

1. **"System".** The word for the computer is "system" in each text that a user can read: the UI labels, the
   messages that the server sends to the UI and the report file. "Device" is only for a GPU or a camera. A user text
   never says "PC" or "machine". The rule does not apply to code identifiers, log lines, plan documents and test
   names.
2. **Confirmed sentences.** These sentences are confirmed by the owner. Change them only with the owner:
   - the five pair states and the six quick-check result texts of
     [ADR-WKE6](WKE6-unchecked-pairs-in-the-ep-setting.md);
   - the texts of the EP pack panel in `freemocap-ui/src/services/server/ep-packs.ts` (J6) and the refusal
     sentences of the provider pack of [ADR-BMA1](BMA1-windows-ml-ep-pack-install-and-remove.md) (Q74);
   - `REASON_TEXT.crashed`: "it stopped unexpectedly and will not run again automatically" (Q61);
   - the row words "Partly done", "Failed" for a crashed check and "Skipped" for a Blender that is not installed
     (Q66, Q67, Q69);
   - the texts of the Certification dialog that the owner wrote (freemocap-ui
     [ADR-JDH9](../../freemocap-ui/decisions/entries/JDH9-certification-dialog-layout-and-owner-texts.md)).
3. **Reason sentences.** The UI shows a plain sentence for each reason code that it knows (`REASON_TEXT` in
   `freemocap-ui/src/services/server/execution-providers.ts`), not the raw code. A report file keeps the codes and
   the check names.
4. **Labels.** A label never changes with the history of the client. A refusal or a failure shows as a sentence
   beside the control.

## Reason

- Mac users do not have a "PC". "Device" already means a GPU or a camera in the app.
- A raw code such as `models-missing` tells a user nothing.
- The reviewer reads the codes, so the report keeps them.

## Alternatives rejected

- **"Machine".** It was the rule of G1 from 2026-11-19. The owner replaced it with "system" on 2026-11-20.
- **"Device" for the computer.** It was the first wording of F12.

## Open work

[open-work.md](../open-work.md)
