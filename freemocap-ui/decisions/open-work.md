# Open work

This file holds the open work of the [decision log](README.md) of `freemocap-ui/`. The open work for
two or more modules is in the root log: [root open work](../../decisions/open-work.md). Read the items that
apply to your task. Delete an item when its work is done. The PR that closes an item records the
result.

- **Texts and figures of the coordinator in the Certification dialog.** They are built, and the owner has not
  confirmed them ([ADR-JDH9](entries/JDH9-certification-dialog-layout-and-owner-texts.md)):
  - "Nothing to share right now.", "Shared as issue #N", "Already shared as issue #N", "Not shared: ... Use the issue
    form.", "Not shared yet: ...", "Could not record that the report was shared:";
  - "Your results appear here when the checks are done.";
  - the sentence above the report footer: "Submit report(s) sends this report to the FreeMoCap team as a public
    issue on GitHub." or "Save file and open issue form saves this report and opens the GitHub form to attach it
    to.";
  - the footer labels "Do not send and open FreeMoCap" (the owner wrote "Do no send"; read as "not") and "Send
    report(s) and open FreeMoCap" (plural by the Submit rule), and "Sending..." also on the button of the first
    dialog;
  - "Sent!" for 1.5 s;
  - the describing sub-title when the start check is not required; a send without a prior view; "Continue" also when
    the dialog opens again later in the same server session; the dialog anchored 10vh from the top.
- **Per-check rows in the start-check table.** The table has one row for each package. A row for each check needs
  the server to send the name and state of each check in the `certification` snapshot.
