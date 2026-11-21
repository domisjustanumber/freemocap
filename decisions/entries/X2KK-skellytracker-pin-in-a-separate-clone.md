# X2KK — The skellytracker pin is a separate clone

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), decision 1, H4,
"After the grilling" and "Pin at 0342ecb8").

## Decision

1. **Clone.** freemocap takes skellytracker from a separate clone, `../skellytracker-pin`, detached at one commit.
   `[tool.uv.sources]` of `pyproject.toml` names it as an editable path. The comment beside it names the commit.
2. **Model files.** The ONNX files of the clone are hard links to the files in
   `../skellytracker/skellytracker/core/model_zoo`.
3. **When to move.** The pin moves only to a pushed skellytracker commit with green CI, or to a commit that the
   skellytracker session names. Before a move, the fast suite of freemocap must pass against the commit.
4. **How to move.** Run `git -C ../skellytracker-pin fetch ../skellytracker <hash>` and then
   `git -C ../skellytracker-pin checkout --detach <hash>`. Update the comment in `pyproject.toml`. When the
   `pyproject.toml` of skellytracker did not change, `uv.lock` does not change, and no `uv sync` or `uv lock` is
   necessary. Check that the move adds no new model file. When it does, add its hard link.

## Reason

- The working checkout of skellytracker changes under the tests of freemocap while the skellytracker session
  works.
- A git-URL pin fails: an installed skellytracker holds no ONNX file, and its sidecars give no `url`.
- skellytracker has no SemVer version yet. The owner makes the version numbers.

## Consequences

- CI cannot build this branch while the sources are local paths.
- The checkpoint records each pin move with its commit and its suite results.

## Alternatives rejected

- **A git `rev` in `[tool.uv.sources]`.** See the reason.
- **The working checkout `../skellytracker` with no pin.** It was the rule of H4, until the owner chose the clone
  on 2026-11-20.

## Not repeated

- A pin to a commit that is not pushed holds work that CI did not check. Prefer a pushed commit with green CI.
