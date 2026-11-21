# WKC0 — Level quick: what it shows, the time budget and the session checks

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), the fifth
grilling, Q53 to Q58, and the realtime session quick check).

## Decision

1. **Level quick.** freemocap follows the level quick of skellycertify (skellycertify
   [ADR-M8J1](https://github.com/domisjustanumber/skellycertify/blob/0cd5e8c2a8c2f6ee8b3262f0426033c7b1d5a72e/decisions/entries/M8J1-quick-and-full-levels-defined.md)).
   The whole quick run takes no more than 2 minutes for all packages together. It downloads nothing. It must show
   that a recording, a realtime session and a post-hoc session can each start and run, where a package has them.
2. **Shares.** The quick shares are skellycam 30 s, skellytracker 65 s and freemocap 25 s
   (`QUICK_BUDGET_SECONDS` in `freemocap/certification.py`). skellytracker sets its share in its own repository.
   freemocap does not pass or assume the share of skellytracker. The "up to about N seconds" of the UI is the sum
   of the plans.
3. **The quick checks of freemocap.** freemocap has eight quick checks: `build-identity`, `spawn-child`,
   `bundle-imports`, `data-folder`, `posthoc-session`, `realtime-session`, `install-facts` and `blender`. The module
   docstring of `freemocap/certification.py` gives the pass rule and the reason codes of each check.
4. **Session checks.** `posthoc-session` and `realtime-session` run the sessions of freemocap in its own processes
   on the bundled frames of skellytracker (`certify_frames`). The two run one after the other. With no model files
   a session check is `not-run` with `models-missing`. `over-budget` and `test-media-missing` also give `not-run`.
   A `not-run` session check never fails the start check.
5. **Realtime in a fresh copy.** `realtime-session` runs in a fresh copy of the app, started only for the check,
   with the bundled frames fed through a stand-in camera group
   (`freemocap/system/certify/stand_in_cameras.py`). The copy starts with `--certify-realtime`, which `run_main` of
   `freemocap/__main__.py` reads before a server starts. The copy starts no HTTP server, opens no port and no
   camera, starts no Electron and reads no app settings. The guard of `PubSubTopicManager.create` stays: it refuses
   each process that is not a main process. The check starts only when `REALTIME_SECONDS` fits in what is left of
   the budget.
6. **Pairs.** The quick part of skellytracker checks only the pairs with no reviewed pass in its bundled evidence.
7. **Test images.** The test images are bundled in skellytracker. They can also be in the shared test media
   folder ([ADR-WP3Z](WP3Z-shared-test-media-folder.md)).
8. **skellycam's quick part.** With no camera plugged in, its camera rows read "not checked". Nothing fails, and
   the app opens. A camera counts as checked for each model (USB vendor id and product id) on this system. An
   unchecked camera is checked when the user first asks the app to open it: a pop-up and a lock as for the start
   check, about 30 s, and then the cameras start. A camera that is only plugged in starts no check.

## Reason

- A user must be able to run the level quick at each start, with no wait and no download.
- The share of freemocap was 15 s. The two session checks need more ([ADR-1S0R](1S0R-quick-level-run-times-evidence.md)).
  The owner moved it to 25 s and the cap of skellytracker from 75 s to 65 s, so the sum stays at 2 minutes.
- `PubSubTopicManager.create` refuses a child process. A fresh copy is a main process, and the guard keeps its
  protection.
- A missing model file is a gap of the install, not a failure of the system.

## Consequences

- The fresh copy is not tested in a frozen build. [open-work.md](../open-work.md) lists it.
- The stand-in camera group sets the internals of a skellycam `CameraGroup`, because skellycam has no public
  constructor of a group without its camera manager.

## Evidence

- [ADR-1S0R](1S0R-quick-level-run-times-evidence.md): the quick run times on the dev system.

## Alternatives rejected

- **Run the realtime session in the certify child.** `PubSubTopicManager.create` refuses it.
- **Remove the guard of `PubSubTopicManager.create`.** The owner kept it.
- **40 s for each package.** A provisional split of the coordinator. The owner replaced it with Q56 and Q58.

## Open work

[open-work.md](../open-work.md)
