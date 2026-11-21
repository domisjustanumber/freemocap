# GZ9H — The report file: format 1.6.0, its parts, the note and the test media record

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), decision 10, G4,
the relay follow-up, formats 1.4.0 to 1.6.0, the note cleaning, Q69, Q71, Q77 and Q78).

## Decision

1. **Format.** freemocap follows skellycertify report format 1.6.0 (skellycertify
   [ADR-9FHP](https://github.com/domisjustanumber/skellycertify/blob/0cd5e8c2a8c2f6ee8b3262f0426033c7b1d5a72e/decisions/entries/9FHP-format-1-6-0.md)).
   The text of the spec is the authority. The module of freemocap, the report of a crash record and the file
   declare `skellycertify.report/1.6.0`. A move to a later format needs the owner.
2. **No rewrite.** The writer keeps the schema id of each module report. freemocap never rewrites the report of a
   package. Old pending reports with old ids pass through unchanged.
3. **One file.** The file is `certify-report-<yyyymmddThhmmssZ>.md`. `freemocap/system/certify/report_file.py`
   builds it at hand-in from `read_report()` of the chosen reports, as a pure function of the module reports, the
   note and the `app` block. Several modules of one package and modules of several packages can be in one file. The
   modules are in the order of `created_utc`, then of report id, so the same reports give the same bytes. The file is
   kept under `<base data folder>/certify/` when the user accepts it ("send" or "opened").
4. **Time.** The file name and the header take the earliest `created_utc` of the reports.
5. **Parts.** The Markdown part follows section 4.2 of the spec. A summary table has rows only for a failed section
   (for a failed check when a module has no sections). A file with no failed row has no table. The JSON block holds
   each check.
6. **Components.** Each check of the module of freemocap has `module` (`certification.COMPONENTS`). Each such check
   that ended `pass`, `fail` or `record-only` gets a `component` item with its result. A Blender that is not
   installed gives the check `not-run` with `not-installed` and the `component` item `skipped` with
   `not-installed`. The file prints it as "skipped (not installed)".
7. **Test media.** The module of freemocap lists each test file that its checks used, with the SHA-256 of the bytes
   and the size. `quick_frames.zip` (`bundled`, or `shared` when the shared folder holds it) is listed when a
   session check ran on the frames. `freemocap_sample_data.zip` (`shared`) is listed when `recording` checked the
   SHA-256 of the archive.
8. **Note.** `clean_note()` in `report_file.py` cleans the note. `cleanNote` in
   `freemocap-ui/src/services/server/certification-hand-in.ts` mirrors it. The shared cases are in
   `clean-note-cases.json`. The dialog shows the cleaned text while the user types. The note stops at 2000
   characters. The note is written before the user views the file, because it is part of the file.
9. **Harmless printing.** A value that looks like an IPv4 address and link markup are printed harmlessly in the
   Markdown part only. The JSON block keeps each value.
10. **Privacy.** The builder refuses a file that breaks privacy rules 1 to 11 of the spec. The module of freemocap
    holds no path. The `app` block has no tree-modified flag. freemocap builds `host.gpus` of its module from
    `probe_host()` of skellytracker.
11. **Public commit.** A freemocap module counts only as a record (`commit-not-public`) until its commit is on a
    pushed branch of the public repository of freemocap. A push is the decision of the owner.

## Reason

- The person must see the file that is sent. A pure builder gives the same bytes for "View report" and for "Send",
  and the relay finds a resent file by its SHA-256.
- A build time in the file would change the bytes between the view and the send.
- The report is public. The note is free text from the person and can hold a path, a name or a link.
- A reviewer must know which test file gave a result.

## Consequences

- The relay that is deployed predates 1.6.0. It can refuse a file of freemocap until it is deployed again.
- skellytracker at the pin can write an older 1.x schema id in its module. The relay checks each module on its own.

## Alternatives rejected

- **Build the file at run time.** It was replaced: the file is built at hand-in from the chosen reports.
- **One file for each package.** The spec allows modules of several packages in one file (spec 1.1.0).

## Not repeated

- Do not change the order or the bytes of a module. The `file-changed` check compares the SHA-256 of the viewed
  file.

## Open work

[open-work.md](../open-work.md)
