# JDH9 — The Certification button and dialog: the layout and the texts of the owner

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../../current-work-plans/02-pipeline/ep-certification-integration.md), decisions 25 to
27, J7 and the three rounds of the owner's notes of 2026-11-20).

## Decision

1. **Button.** The "Certification" button is in the main navigation strip, right after the Streaming and Playback
   tabs (`src/components/certification/CertificationDialog.tsx`, `src/layout/BasePanelLayout.tsx`). It is always
   visible and never disabled, and its label is fixed. A suffix comes from the current server state:
   `· quick check 1 of 3` while a check runs, else `· N failure(s) to file` when a pending report has a failure, else
   `· N to file`. The button is dimmed while disconnected.
2. **One dialog.** The dialog is the one place of certification. The start check is the same dialog in a required
   mode. "File report" of a failure opens it.
3. **Texts of the owner.** These texts are the words of the owner. Change them only with the owner:
   - title: "Certify FreeMoCap on this system"; the dialog shows no host name;
   - sub-title while the start check is required: "FreeMoCap has not run on this type of system before, so we need
     to run some checks to confirm things work before launching.";
   - the heading of the check table: "Quick system checks to run:"; its start button: "Start now";
   - the share heading: "Help FreeMoCap by sharing your (anonymous) results"; the count line: "Share N reports with
     FreeMoCap"; the note label: "Anything you'd like to tell us?";
   - the paragraph: "We'd love your help to know this is a good configuration for FreeMoCap to run on in the
     future, if you'd like to submit your anonymous certification report click the Submit report button below. If
     you want to see what we'll get before it sends, click the View report button first.";
   - the send button: "Submit report" or "Submit reports" (lower-case second word, the count from the server);
   - the full benchmark paragraph: "If you have the time (approx 5 to 10 mins), we'd really appreciate the results
     from a full benchmark run on your system." The time figure is replaced by the measured total.
4. **Layout.** Buttons must look like buttons, not only text. The dialog must not jump while the checks run. It has
   a clear table of the checks with their status and a moving icon that shows that the work goes on. The gap
   between the table and the start button and the gap between "Start now" and the share heading are small. The
   reports do not show in the dialog until the checks are complete.
5. **Close and Continue.** The bottom button "Close" changes to "Continue" when the start check is complete.
6. **View report.** "View report" opens the report in a second pop-up, not in the first dialog. The pop-up reads the
   file as Markdown: the summary for a person at the top, the JSON below it. The Markdown reader is in-house
   (`src/services/server/report-markdown.ts`) and interprets no HTML.
7. **Report footer.** The footer of the report pop-up has the close action at the left and the send action at the
   right, in blue. The send action is the Submit action while the relay can take the file, else "Save file and open
   issue form". The pop-up shows the share heading, so that it is clear what the send does.
8. **Sending.** While the send runs, the send button reads "Sending...", dimmed, with the turning icon. The icon has
   a transparent background. After a successful send the button briefly shows "Sent!", the pop-ups close, the app
   opens and a web browser opens the issue that the send made.
9. **J7 choices.** A hand-in line shows the issue link and the report count, but no date. "Open again" of an
   issue-form hand-in opens the form, not the saved file.

## Reason

- The owner wrote these texts on 2026-11-20 after seeing the dialog. "Reports to hand in" sounded like school work.
  The tone must be about the certification of hardware to help FreeMoCap.
- A dialog that jumps while the checks run looks broken. A moving icon shows that the app has not frozen.
- The first inline view of the file made the UI blurry.

## Consequences

- The coordinator added some texts and figures that the owner has not confirmed. They are listed in
  [open-work.md](../open-work.md).

## Open work

[open-work.md](../open-work.md)
