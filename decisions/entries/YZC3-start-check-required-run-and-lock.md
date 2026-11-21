# YZC3 — The start check: when it is required, what it runs, the lock and the release

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), decisions 12 to
15, J11, J12, J16, J17, the fifth grilling, Q59, Q63, Q79 and Q80).

## Decision

1. **Reviewed OS row.** A reviewed row says "this OS is certified for freemocap". The rows are the Python constant
   `REVIEWED_OS_ROWS` in `freemocap/system/certify/start_check.py`, so a frozen build needs no data file. The key
   is `os_name`, `os_release`, `os_arch`, the build family (the Windows build, the macOS major, the Linux
   `ID-VERSION_ID`), the freemocap major.minor and `kind: full`. A row also holds its issue number and review
   date. A new freemocap minor version needs a new row.
2. **Required.** The start check is required when no reviewed row matches and
   `<base data folder>/certify/start-check.json` on the server host holds no record for the current version set
   (freemocap, skellycam, skellytracker) and OS key. An unchecked GPU EP alone never makes it required.
3. **What it runs.** The start check runs skellycam's quick part first, when it exists. Then it runs the
   `certify("quick")` of freemocap, then the `certify("quick")` of skellytracker with no EP named. skellytracker
   then checks each GPU EP pair with no reviewed pass in its bundled evidence, field-test EPs included. One click
   starts it.
4. **Record.** A freemocap pass is recorded with the version set. A crash in the own part of freemocap writes
   `{"versions", "os", "crashed": <check>}`, and the start check is not asked again until a package version
   changes. A freemocap module that ends `fail` writes the same marker with its first failed check. A later pass
   overwrites the marker. A failure or a crash in the part of skellytracker writes nothing.
5. **Lock.** While the start check is required, the dialog opens in a required mode with no cross, no Close and no
   Escape. The rest of the app is `inert` and dimmed, the expand button of the collapsed sidebar included. The
   server connection panel, the log terminal and the Electron menu stay usable. The server refuses each camera and
   pipeline start ([ADR-FG8V](FG8V-busy-rule-and-admission-lock.md)). The lock comes from the current
   `certification.start_required` of the server, never from client history.
6. **Release.** A start check that ends other than by a cancel releases the app for this server session. The
   dialog then stays open, so that its results show. After a cancel, the app stays locked when the own part of
   freemocap had not passed. A restart with no record brings the lock back.
7. **Stable controls.** The start button and the Certification button never disable and never change their label,
   also after a failed start check. A refused start shows the sentence of the server.
8. **Blender path.** The `blender` check uses the Blender path chosen in the Blender settings, else the best guess.
   `POST /freemocap/certify/start_check` takes the optional body `{blenderExePath}` from the UI.
9. **Gate of the full benchmark.** For the full benchmark, a crash marker counts as no pass
   (`start_check_needed(crash_skips=False)`). A reviewed row, a recorded pass or "nothing to check" admit it.
   `start_required` does not change for this.

## Reason

- An OS item with no reviewed row has no evidence that freemocap runs there. The quick check gives that evidence
  in less than 2 minutes.
- A GPU EP has its own check when the user selects it
  ([ADR-WKE6](WKE6-unchecked-pairs-in-the-ep-setting.md)). It must not block the start.
- A crash or a failure that blocks each start would lock the user out of the app. The report of the failure stays
  in the share list.
- The Blender path chosen by the user lives only in the store of the UI.

## Consequences

- A system that failed the own part of freemocap shows no start check until a version changes. The Certification
  button can run it again.
- Only the item of freemocap gates the lock until skellycam's part exists.

## Alternatives rejected

- **Record any finished check.** Before Q80 only a pass was recorded, and a failed check was asked again at each
  start. Q59 and Q80 replaced that for the own part of freemocap.
- **A YAML file of reviewed rows.** A frozen build would need a data file.

## Not repeated

- Do not keep the lock or the release in client state. A restart of the server must give the lock back from the
  server message.

## Open work

[open-work.md](../open-work.md)
