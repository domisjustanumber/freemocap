# WP3Z — The shared test media folder

**Status:** accepted, 2026-11-21 (owner; migrated from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md), the fifth
grilling, the recording benchmark, Q68 and "Pin at 0342ecb8").

## Decision

1. **One folder for each user.** The test media of the certify runs is in one folder for each user, outside the data
   of each package. Other packages use it too. The rule is in the skellycertify spec (section 2.8).
2. **Location.** `get_test_media_dir()` in `freemocap/system/default_paths.py` gives
   `%LOCALAPPDATA%\freemocap\test-media`, else `~/.cache/freemocap/test-media`. The environment variable
   `FREEMOCAP_TEST_MEDIA_DIR` overrides it.
3. **The app passes it.** The app passes the location to each package. The start check passes it to skellytracker
   always. skellytracker falls back to its bundled file when the folder does not hold it. The full benchmark passes
   it to each package. The pair quick check passes no folder.
4. **No copy.** freemocap copies nothing into the folder. A file that the run reads from its package is reported
   as `bundled`, a file from the folder as `shared`.
5. **Archives.** An archive is one file, `<sha256>.zip`, in the folder.
6. **Clean-up.** The clean-up of a full benchmark keeps each file that was in the folder before the run
   ([ADR-5ZRX](5ZRX-full-benchmark-offer-consent-lock-and-clean-up.md)).

## Reason

- Two packages that need the same test file then download it one time.
- The owner chose the `freemocap` folder over a `skellycertify` folder (Q68). No code removes
  `%LOCALAPPDATA%\freemocap`, and the uninstaller keeps the app data.
- A report must say which file gave a result. A copy would make a bundled file look shared.

## Not repeated

- Do not let a test use the real folder. `freemocap/tests/conftest.py` points the override at a scratch folder.
