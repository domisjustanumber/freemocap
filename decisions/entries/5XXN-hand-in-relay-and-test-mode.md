# 5XXN — The hand-in: the share list, the relay, the issue form and the test mode

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), decisions 22 to 24
and 29, R1 to R5, F19, F20, G2, G3, H5, H6, J7, J13, J18 and the fifth grilling).

## Decision

1. **Nothing automatic.** A run sends nothing. A file goes out only after the person viewed it and chose to send
   it. "send" and "opened" carry the report ids, the note and the SHA-256 of the viewed file. The backend builds the
   file again and answers 409 `file-changed` when the SHA-256 differs.
2. **One hand-in.** One hand-in is one file and one issue with each pending report of that backend host. A passed
   quick check alone gives no hand-in prompt. A failure report is always offered, also for a pair with a reviewed
   row.
3. **Stores.** skellytracker keeps its reports and their states. freemocap keeps its own reports with a `pass` or
   `fail` check in `<base data folder>/certify/reports/<id>.json` and their states in
   `<base data folder>/certify/hand-in.json`, with the shapes and rules of skellytracker: `pending_reports()`,
   `read_report()` and `mark_reports(ids, state, *, reference=None)` with the states `pending`, `opened` and
   `covered`. An older quick pass whose passed checks a newer pass repeats is pruned. Failures, handed-in reports and
   `full` reports stay. The hand-in routes merge the two stores. Each mark goes to the store that holds the id.
4. **Retry.** On "send", the exact accepted bytes go to `<base data folder>/certify/outbox/` with a retry count. Only
   that file is sent again, byte for byte, at the next backend start. The backend acts on the `retry` flag of the
   error body, never on the status number. After the first send and 3 failed retries, or `retry: false`, the app
   offers the issue form. 413 and 422 are permanent: the app offers the issue form at once. For 422 `privacy-rule`
   it tells the person the rule number. A 200 with an issue of skellycertify marks the reports `covered` with the
   issue link, and deletes the outbox copy.
5. **Relay off.** Only a clear `enabled: false` from `GET /health` means that the relay is off. A failed or unclear
   health check goes on to the normal send. When the relay is off, the app offers the issue form at once, keeps no
   outbox copy and counts no retry. The dialog makes no health call when it opens.
6. **Address.** The relay address is one constant in freemocap (`RELAY_URL`), with the override
   `FREEMOCAP_CERTIFY_RELAY_URL`. It has no UI. An empty address means that the relay is off, and the hand-in
   offers only the issue form.
7. **Issue form.** "Save file and open issue form" saves the file with a browser download and opens
   `issues/new?template=certify-report.yml`. It counts as handed in (`opened`). "Not sent" marks the reports
   pending again and deletes each outbox file that holds them. It is also offered on a file that waits for a retry.
8. **Shared state.** "Opened" lives on the backend, and all users of that host share it.
9. **No reminder.** The idle notice and "Do not remind me" stay unbuilt until the passive record exists. The suffix
   of the Certification button is the only reminder.
10. **Test mode.** The relay stays in test mode until the owner did one real send of a report and saw its issue. The
    first real send is the owner's, from the hand-in UI. No agent and no test contacts the real relay.
    `freemocap/tests/conftest.py` sets `FREEMOCAP_CERTIFY_RELAY_URL` to empty for each test. Tests use a fake relay
    on `127.0.0.1` only.

## Reason

- The person must know what leaves the system. A resend of the same bytes is safe, because the relay finds the
  earlier issue by its SHA-256.
- The `retry` flag is the contract of the relay. A status number can mean two things.
- The relay makes an issue in a public repository. A test send files a real issue.
- A backend host with no internet must still reach the issue form.

## Consequences

- A real relay 200 was never seen from the app. [open-work.md](../open-work.md) lists the real send.

## Alternatives rejected

- **An Electron save call.** The browser download already works in Electron. The call is built only if the save
  dialog does not appear in the manual check (H5).
- **"Do not ask again" and a per-session reminder.** Not built until the passive record exists (H6).

## Not repeated

- Do not add data to a file after the person accepted it. Retry only the accepted bytes.
- Do not make a link from a reference that is not an issue address of skellycertify on github.com.

## Open work

[open-work.md](../open-work.md)
