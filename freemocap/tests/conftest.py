"""Session-wide test setup.

Lives at the test-package root so every test gets it, including ones that never touch
the pipeline fixtures.
"""

import os
from pathlib import Path

import pytest
from tempfile import mkdtemp
from skellylogs.handlers.websocket_log_queue_handler import create_websocket_log_queue


def _isolate_user_folders() -> None:
    """Keep the suite out of the user's skellytracker store, engine cache and freemocap data folder.

    Set in `os.environ` before any test, so spawned children inherit it. The installed EP packs stay
    readable: each pack folder of the real store is joined into the scratch store (nothing is copied),
    while verdicts, sessions, reports and refs are written in the scratch store only.
    """
    import subprocess

    from skellytracker.core.eps import store

    real_store = store.store_root()
    scratch = Path(mkdtemp(prefix="fmc-user-"))
    scratch_store = scratch / "eps"
    scratch_store.mkdir()
    if real_store.is_dir():
        for pack in real_store.iterdir():
            if pack.is_dir() and not pack.name.startswith(".") and pack.name not in {"refs", "reports", "sessions"}:
                subprocess.run(["cmd", "/c", "mklink", "/J", str(scratch_store / pack.name), str(pack)], check=True, capture_output=True)
    os.environ[store.STORE_VARIABLE] = str(scratch_store)
    os.environ[store.CACHE_VARIABLE] = str(scratch / "ep-cache")
    os.environ.setdefault("FREEMOCAP_BASE_FOLDER", str(scratch / "freemocap_data"))
    os.environ.setdefault("FREEMOCAP_TEST_MEDIA_DIR", str(scratch / "test-media"))  # not the real shared folder


def pytest_configure(config):
    """Use fresh scratch space instead of a Windows temp root shared across users."""
    # The certify relay files a real public issue and the start-up retry sends any kept outbox file:
    # no test may reach it. `relay_url()` reads this at each call; the relay tests set the fake address themselves.
    os.environ["FREEMOCAP_CERTIFY_RELAY_URL"] = ""
    _isolate_user_folders()
    if config.option.basetemp is not None:
        return
    # Keep video paths below Windows limits; avoid pytest's shared per-user root.
    config.option.basetemp = mkdtemp(prefix="fmc-")


@pytest.fixture(scope="session", autouse=True)
def websocket_log_queue() -> None:
    """Create the websocket log queue before any test runs.

    `PipelineIPC.__init__` calls `get_websocket_log_queue()` unconditionally, and that
    raises `ValueError: Websocket log queue not created yet` unless something created it
    first. In the real app `configure_logging()` does that at startup; tests never call it,
    so anything that stands up a pipeline dies on construction.

    Autouse and session-scoped rather than opt-in, because the failure mode is a new test
    file forgetting a fixture it has no reason to know about. The call is idempotent.
    """
    create_websocket_log_queue()


@pytest.fixture(autouse=True)
def no_real_download(request, monkeypatch):
    """No fast test downloads a recording: the real `catalog.download` raises unless the test stubs it or `requests.get`
    (an earlier test ran the real level full and downloaded the 167 MB sample twice). shortcut: in-process only; a spawn
    child (the full benchmark's job) needs its stand-in for freemocap's `certify` instead."""
    if request.node.get_closest_marker("e2e") or request.node.get_closest_marker("slow"):
        return
    import requests
    from freemocap.tools.datasets import catalog
    real_get, real_download = requests.get, catalog.download

    def guarded(url, *args, **kwargs):
        if requests.get is real_get:
            raise AssertionError(f"a test reached a real download of {url}; stub catalog.download")
        return real_download(url, *args, **kwargs)

    monkeypatch.setattr(catalog, "download", guarded)


def pytest_sessionfinish(session, exitstatus):
    """Prevent leftover multiprocessing.Queue feeder threads from hanging exit.

    Every multiprocessing.Queue registers an untimed atexit finalizer that
    joins its internal feeder thread regardless of daemon status. Across the
    e2e/slow pipeline tests, dozens of Queues get created (pubsub topics,
    per-node progress queues, skellylogs' process-wide websocket log queue,
    skellycam's own camera-event pubsub, ...); some end up with a feeder
    thread parked forever writing to a pipe nobody reads anymore (e.g. a
    child process died, or -- for the websocket log queue -- nothing ever
    drains it in a plain pytest run once its OS pipe buffer fills). Any one
    of those makes Py_FinalizeEx block forever, so pytest prints its summary
    but the process never exits (see PR #896 CI investigation).

    We've since closed off several of these leaks at the source (see
    freemocap/pubsub/pubsub_abcs.py and
    freemocap/core/pipeline/abcs/base_node_abc.py), but some live in
    third-party dependencies (skellycam, skellylogs) we don't control from
    here. This sweep is the reliable backstop: cancel every live Queue's
    join-thread finalizer at session end so exit can never hang on one we
    missed.

    Unlike the two source-level fixes above (which skip the flush-wait while
    the app could still be running), this one is unconditionally safe: it
    only runs once the whole pytest session is ending, so by definition
    nothing is left to read a message anyway, flushed or not.
    """
    import gc
    import multiprocessing.queues

    for obj in gc.get_objects():
        if isinstance(obj, multiprocessing.queues.Queue):
            try:
                obj.cancel_join_thread()
            except Exception:
                pass
