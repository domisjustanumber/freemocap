# ENY6 — Test isolation of the certification work

**Status:** proposed, 2026-11-21 (backfilled from the
[certification checkpoint](../../current-work-plans/02-pipeline/ep-certification-integration.md); the owner
confirmed only item 1).

## Decision

1. **No relay.** `freemocap/tests/conftest.py` sets `FREEMOCAP_CERTIFY_RELAY_URL` to empty for each test. A test
   that sends uses a fake relay on `127.0.0.1`. Each non-local connection and each POST that does not go to the fake
   raises ([ADR-5XXN](5XXN-hand-in-relay-and-test-mode.md) item 10).
2. **Scratch stores.** `freemocap/tests/conftest.py` points the EP store, the EP cache, the base data folder and
   `FREEMOCAP_TEST_MEDIA_DIR` at temporary folders for the whole run. A test must not write the real stores or the
   real test media folder.
3. **No download.** In the fast suite the real `catalog.download` raises, unless the test replaces it or
   `requests.get`. A test that reaches the full level of freemocap gives the child a stand-in for `certify`. No test
   runs the real full level of skellytracker.
4. **No hardware change.** No test installs or removes an EP pack. The tests replace `install()` and `remove()` of
   skellytracker with stand-ins.
5. **No real camera.** The realtime quick check uses the stand-in camera group. No test opens a real camera.
6. **pytest.** Never run pytest with `-p no:logging`.

## Reason

- A test that writes the EP store of the dev system changes the pairs that the app offers.
- One test once ran the real full level and downloaded the sample archive two times before it was replaced.
- A test send files a real public issue.

## Open work

[open-work.md](../open-work.md)
