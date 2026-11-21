# Decision log: entry template

Use this template for a new entry. The [Rules](README.md#rules) of the index apply. This file is not
in the read path: read it when you write an entry.

The file name is `<ID>-<short-slug>.md`. Get `<ID>` from
`uv run python tools/check_decision_log.py --new`. The ID is in upper case. Put the file in
`entries/` of the log that the placement rule of [`AGENTS.md`](../AGENTS.md#5-decision-log) gives:
the root log or the log of a module.

```markdown
# <ID> — <title>

**Status:** <proposed | accepted | evidence>, <YYYY-MM-DD> (<source>).
**Depends on:** <repo> XXXX (<status> on YYYY-MM-DD), <permalink>

## Decision

## Reason

## Consequences

## Evidence

## Alternatives rejected

## Not repeated

## Open work
```

- **Status.** `accepted` is a decision. `evidence` is a measurement. `proposed` waits for a
  decision. A later status change sets `rejected`,
  `superseded by XXXX`, `absorbed into <path>#<anchor>, …`, `evidence; used by XXXX` or `done` (see the
  [Rules](README.md#rules)). The source says who decided or where the entry comes from, for example
  "user" or "backfilled from #81".
- **Depends on.** Optional. Write it only when the entry waits for a decision of another repo. Use a
  permalink that pins a full SHA on the default branch of that repo.
- **Decision.** What is decided, written so that a reader can apply it. An entry that supersedes an
  old entry links the heading that states each kept rule, and writes text only for a changed rule and
  for a kept rule that no heading states.
- **Absorb at landing.** When the absorb documents state all the rules of the entry, absorb it in
  the last commit of the group that writes it ([Rules](README.md#rules)).
- **Reason.** Why. Each entry gives its own reasons.
- **Consequences.** Optional. What becomes harder, what must change later and what the decision
  costs.
- **Evidence.** Write this section only when there is evidence: measurements with their tool, its
  version and the script in `scripts/` of the log that holds the entry, or code facts with their
  file and function.
- **Alternatives rejected.** The options that were examined and not used, with the reason for each.
  Omit the section when there are none.
- **Not repeated.** Pitfalls already found. Omit the section when there are none.
- **Open work.** Optional. Write only a link to the [open-work.md](open-work.md) of the log that
  holds the entry. Put the open-work items in that file, not in the entry.
