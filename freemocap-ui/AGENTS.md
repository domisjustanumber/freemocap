# Instructions for `freemocap-ui/`

The root `AGENTS.md` also applies: [root `AGENTS.md`](../AGENTS.md).
This file holds only the rules for the work in this module.

## Decision log

This module has its own decision log: [`decisions/README.md`](decisions/README.md).
The Rules of the root log apply to it: [root Rules](../decisions/README.md#rules).
To write an entry, use the root template [`template.md`](../decisions/template.md).

- Put an entry in this log only when each file that its Decision section names or changes is in
  this module. Its file goes in `decisions/entries/`.
- Put all other entries in the root log [`decisions/`](../decisions/README.md). An entry for two or more modules goes
  there.
- Before you change a file in this module, read the root [`decisions/README.md`](../decisions/README.md) and the root
  [`decisions/open-work.md`](../decisions/open-work.md).
- Then read [`decisions/README.md`](decisions/README.md) and
  [`decisions/open-work.md`](decisions/open-work.md) of this module.
- Then read the Active entries of both logs that apply to your task.

Tools are in the root `tools/`. Scripts are in `scripts/` of the log that holds their entry.

## Module rules

Run the commands of this module in `freemocap-ui/`.
Run `npm install` before the first build or test.
Run the tests with `npm run test`.
Run the type check with `npx tsc --noEmit`.
