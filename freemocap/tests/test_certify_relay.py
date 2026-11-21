"""The relay hand-in against a fake relay on 127.0.0.1 (skellycertify relay/README.md, "Answers for the app developers").

The relay's test mode is off: an accepted report files a real public issue. These tests fail closed: every
connection that is not to 127.0.0.1 raises, and every POST whose address is not the fake raises before it starts.
"""

import hashlib
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests
import skellytracker
import urllib3.util.connection

from freemocap.system.certify import relay
from freemocap.system.certify.relay import HandInError

MODULE = {"schema": "skellycertify.report/1.0.0",
          "package": {"name": "skellytracker", "version": "2.0.0", "commit": None, "tree_modified": None},
          "kind": "quick", "created_utc": "2026-11-19T10:00:00Z", "host": {"os": {"name": "Windows"}},
          "checks": [{"name": "cuda@10de-2484-0", "result": "fail", "reason": "probe-L3-failed"}],
          "evidence": {"valid": False, "reasons": ["no-version", "no-commit"]}}
ISSUE = "https://github.com/domisjustanumber/skellycertify/issues/7"
# Report ids are opaque (skellytracker gives v4 UUIDs): nothing may read a `quick-` prefix into them.
ID_1, ID_2, ID_9 = ("3f2b8c1e-9a4d-4e7b-b6a1-0c5d2e8f7a90", "c1d2e3f4-5a6b-4c7d-8e9f-a0b1c2d3e4f5",
                    "0d9e8f7a-6b5c-4d3e-9f2a-1b0c9d8e7f6a")
OFF = {"error": "relay-off", "retry": True, "detail": "the relay is switched off"}


class FakeRelay(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), FakeRelayHandler)
        self.answers: list[tuple[int, bytes, float]] = []
        self.received: list[tuple[str, dict, bytes]] = []
        self.health: object = {"enabled": True, "test_mode": False, "schema_major": 1}
        self.health_checks = 0

    def answer(self, status: int, body: object, delay: float = 0.0) -> None:
        self.answers.append((status, body if isinstance(body, bytes) else json.dumps(body).encode(), delay))


class FakeRelayHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.received.append((self.path, dict(self.headers), body))
        status, answer, delay = self.server.answers.pop(0)
        time.sleep(delay)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

    def do_GET(self):
        self.server.health_checks += 1
        answer = json.dumps(self.server.health).encode() if self.path == "/health" else b"{}"
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_relay(tmp_path, monkeypatch):
    server = FakeRelay()
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    fake_url = f"http://127.0.0.1:{server.server_port}"
    real_connect, real_post, real_get = urllib3.util.connection.create_connection, requests.post, requests.get

    def local_only(address, *args, **kwargs):
        assert address[0] == "127.0.0.1", f"a test tried to reach {address[0]}"
        return real_connect(address, *args, **kwargs)

    def guarded_post(url, *args, **kwargs):
        assert url.startswith("http://127.0.0.1:"), f"a test tried to POST to {url}"
        return real_post(url, *args, **kwargs)

    def guarded_get(url, *args, **kwargs):
        assert url.startswith("http://127.0.0.1:"), f"a test tried to GET {url}"
        return real_get(url, *args, **kwargs)

    monkeypatch.setattr(urllib3.util.connection, "create_connection", local_only)
    monkeypatch.setattr(relay.requests, "post", guarded_post)
    monkeypatch.setattr(relay.requests, "get", guarded_get)
    monkeypatch.setenv(relay.RELAY_URL_ENV_VAR, fake_url)
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(tmp_path))
    store = {ID_1: dict(MODULE), ID_2: dict(MODULE, created_utc="2026-11-20T10:00:00Z")}
    server.marks = []
    monkeypatch.setattr(skellytracker, "read_report", lambda report_id: dict(store[report_id]) if report_id in store
                        else (_ for _ in ()).throw(ValueError(report_id)))
    monkeypatch.setattr(skellytracker, "pending_reports", lambda include_handed_in=False: [{"report_id": i} for i in store])
    monkeypatch.setattr(skellytracker, "mark_reports",
                        lambda ids, state, *, reference=None: server.marks.append((list(ids), state, reference)))
    yield server
    server.shutdown()
    server.server_close()


def _viewed(ids=(ID_1,), note=None) -> tuple[list[str], str | None, str, bytes]:
    _, body = relay.report_file_for(list(ids), note)
    return list(ids), note, hashlib.sha256(body).hexdigest(), body


def test_a_200_marks_the_reports_covered_after_the_exact_viewed_bytes_went_out(fake_relay, tmp_path):
    ids, note, sha, body = _viewed((ID_1, ID_2), "first try")
    fake_relay.answer(200, {"issue_url": ISSUE, "issue_number": 7, "file_path": "inbox/2026/x.md", "duplicate": False})
    outcome = relay.send_report(ids, note, sha)
    assert outcome == {"state": "covered", "issue_url": ISSUE, "issue_number": 7, "duplicate": False, "error": None,
                       "offer_issue_form": False}
    path, headers, sent = fake_relay.received[0]
    assert (path, headers["Content-Type"], sent) == ("/reports", "text/markdown; charset=utf-8", body)
    assert fake_relay.marks == [([ID_1, ID_2], "covered", ISSUE)]
    assert relay.outbox_entries() == [] and not list((tmp_path / "certify" / "outbox").iterdir())
    assert (tmp_path / "certify" / "certify-report-20261119T100000Z.md").read_bytes() == body


def test_the_same_reports_in_any_order_give_the_same_file(fake_relay):
    assert relay.report_file_for([ID_1, ID_2], "n") == relay.report_file_for([ID_2, ID_1], "n")


def test_a_duplicate_is_covered_too(fake_relay):
    fake_relay.answer(200, {"issue_url": ISSUE, "issue_number": 7, "file_path": "inbox/2026/x.md", "duplicate": True})
    outcome = relay.send_report(*_viewed()[:3])
    assert (outcome["state"], outcome["duplicate"]) == ("covered", True)
    assert fake_relay.marks == [([ID_1], "covered", ISSUE)]


@pytest.mark.parametrize(("status", "error", "retry", "detail"), [
    (400, "empty-body", False, "the body must be the report file"),
    (404, "not-found", False, "no route"),
    (413, "too-large", False, "the limit is 262144 bytes"),
    (415, "wrong-type", False, "send text/markdown or text/plain in UTF-8"),
    (422, "missing-field", False, "report.modules[0].kind"),
    (422, "privacy-rule", False, 5),
    (422, "bad-value", False, "report.modules[0]"),  # e.g. a module id that is not a v4 UUID
    (429, "rate-limited", True, "too many reports from this address"),
    (429, "busy", True, "the relay is busy"),
    (503, "daily-cap", True, "the relay daily limit is reached"),
    (503, "credential-rejected", True, "GitHub refused the relay credential"),
    (503, "github-rate-limited", True, "GitHub rate limit; try again later"),
    (503, "github-unavailable", True, "GitHub is not available; try again later"),
    (503, "relay-misconfigured", True, "the relay has no valid configuration"),
    (503, "internal-error", True, "<b>x</b>"),
    (503, "internal-error", False, "the flag decides, not the status"),
])
def test_each_relay_error_acts_on_retry(fake_relay, status, error, retry, detail):
    fake_relay.answer(status, {"error": error, "retry": retry, "detail": detail})
    outcome = relay.send_report(*_viewed()[:3])
    expected_error = {"status": status, "error": error, "retry": retry, "detail": str(detail)}
    assert outcome == {"state": "kept" if retry else "refused", "issue_url": None, "issue_number": None,
                       "duplicate": False, "error": expected_error, "offer_issue_form": not retry}
    [entry] = relay.outbox_entries()
    assert (entry["failed_attempts"], entry["last_error"], entry["retry_pending"]) == (1, expected_error, retry)
    assert fake_relay.marks == []


@pytest.mark.parametrize("answer", [
    (502, b"<html>bad gateway</html>"),
    (200, b"not json"),
    (200, {"issue_url": "https://github.com/someone/else/issues/7", "issue_number": 7, "duplicate": False}),
    (200, {"issue_url": "http://github.com/domisjustanumber/skellycertify/issues/7", "issue_number": 7}),
    (200, {"issue_url": "javascript:alert(1)", "issue_number": 7}),
    (200, {"issue_url": ISSUE, "issue_number": 8}),
])
def test_a_malformed_or_untrusted_answer_keeps_the_file_and_marks_nothing(fake_relay, answer):
    fake_relay.answer(*answer)
    outcome = relay.send_report(*_viewed()[:3])
    assert (outcome["state"], outcome["issue_url"], outcome["error"]["error"]) == ("kept", None, "bad-response")
    assert fake_relay.marks == [] and relay.outbox_entries()[0]["retry_pending"]


def test_a_timeout_and_a_refused_connection_keep_the_file(fake_relay, monkeypatch):
    monkeypatch.setattr(relay, "TIMEOUT_SECONDS", (2, 0.3))
    fake_relay.answer(200, {"issue_url": ISSUE, "issue_number": 7, "duplicate": False}, delay=1.0)
    outcome = relay.send_report(*_viewed()[:3])
    assert (outcome["state"], outcome["error"]["error"], outcome["error"]["detail"]) == ("kept", "network", "ReadTimeout")
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    monkeypatch.setenv(relay.RELAY_URL_ENV_VAR, f"http://127.0.0.1:{port}")
    relay.retry_outbox()
    [entry] = relay.outbox_entries()
    assert (entry["failed_attempts"], entry["last_error"]["error"]) == (2, "network")
    assert fake_relay.marks == []


def test_after_the_first_send_and_three_failed_retries_the_issue_form_is_offered(fake_relay):
    busy = {"error": "busy", "retry": True, "detail": "the relay is busy"}
    for _ in range(4):
        fake_relay.answer(429, busy)
    relay.send_report(*_viewed()[:3])
    for _ in range(3):
        relay.retry_outbox()  # one retry at each backend start
    [entry] = relay.outbox_entries()
    assert (entry["failed_attempts"], entry["retry_pending"], entry["offer_issue_form"]) == (4, False, True)
    relay.retry_outbox()
    assert len(fake_relay.received) == 4


def test_the_outbox_copy_survives_a_crash_between_write_and_send(fake_relay, monkeypatch):
    ids, note, sha, body = _viewed()
    real_send = relay.send_entry
    monkeypatch.setattr(relay, "send_entry", lambda sha256: (_ for _ in ()).throw(RuntimeError("the app died")))
    with pytest.raises(RuntimeError):
        relay.send_report(ids, note, sha)
    assert fake_relay.received == [] and fake_relay.marks == []
    [entry] = relay.outbox_entries()
    assert (entry["sha256"], entry["failed_attempts"], entry["retry_pending"]) == (sha, 0, True)
    monkeypatch.setattr(relay, "send_entry", real_send)
    fake_relay.answer(200, {"issue_url": ISSUE, "issue_number": 7, "duplicate": False})
    relay.retry_outbox()  # the next backend start
    assert fake_relay.received[0][2] == body
    assert fake_relay.marks == [([ID_1], "covered", ISSUE)] and relay.outbox_entries() == []


def test_a_changed_file_too_large_file_or_relay_off_sends_nothing(fake_relay, monkeypatch):
    ids, note, sha, _ = _viewed()
    with pytest.raises(HandInError) as changed:
        relay.send_report(ids, "a note added after viewing", sha)
    assert changed.value.code == "file-changed"
    monkeypatch.setattr(relay, "RELAY_MAX_BYTES", 100)
    outcome = relay.send_report(ids, note, sha)
    assert (outcome["state"], outcome["error"]["error"], outcome["offer_issue_form"]) == ("refused", "too-large", True)
    monkeypatch.setenv(relay.RELAY_URL_ENV_VAR, "")
    with pytest.raises(HandInError) as off:
        relay.send_report(ids, note, sha)
    assert off.value.code == "relay-off"
    relay.retry_outbox()
    assert fake_relay.received == [] and relay.outbox_entries() == []
    with pytest.raises(HandInError) as unknown:
        relay.report_file_for([ID_9], None)
    assert unknown.value.code == "unknown-report"


def test_a_relay_switched_off_offers_the_issue_form_and_keeps_no_copy_and_counts_no_retry(fake_relay):
    ids, note, sha, _ = _viewed()
    fake_relay.health = {"enabled": False, "test_mode": False, "schema_major": 1}
    with pytest.raises(HandInError) as off:
        relay.send_report(ids, note, sha)
    assert (off.value.code, off.value.detail) == ("relay-off", relay.RELAY_OFF_DETAIL)
    assert fake_relay.received == [] and relay.outbox_entries() == [] and fake_relay.marks == []
    fake_relay.health = {"enabled": True, "test_mode": False, "schema_major": 1}
    fake_relay.answer(503, OFF)  # switched off between the health check and the POST
    with pytest.raises(HandInError) as off_at_post:
        relay.send_report(ids, note, sha)
    assert off_at_post.value.code == "relay-off"
    assert len(fake_relay.received) == 1 and relay.outbox_entries() == [] and fake_relay.marks == []


def test_the_start_up_retry_counts_no_retry_while_the_relay_is_off(fake_relay):
    fake_relay.answer(429, {"error": "busy", "retry": True, "detail": "the relay is busy"})
    relay.send_report(*_viewed()[:3])
    fake_relay.health = {"enabled": False, "test_mode": False, "schema_major": 1}
    relay.retry_outbox()
    fake_relay.health = {"enabled": True, "test_mode": False, "schema_major": 1}
    fake_relay.answer(503, OFF)
    relay.retry_outbox()
    assert len(fake_relay.received) == 2  # the first send and the POST answered relay-off
    [entry] = relay.outbox_entries()
    assert (entry["failed_attempts"], entry["last_error"]["error"], entry["retry_pending"]) == (1, "busy", True)


def test_the_send_route_answers_relay_off_as_409(fake_relay):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from freemocap.api.http.certify.certify_router import certify_router

    app = FastAPI()
    app.include_router(certify_router)
    ids, note, sha, _ = _viewed()
    fake_relay.health = {"enabled": False, "test_mode": False, "schema_major": 1}
    refused = TestClient(app).post("/certify/hand_in/send", json={"report_ids": ids, "note": note, "sha256": sha})
    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "relay-off",
                                                                      "detail": relay.RELAY_OFF_DETAIL})


def test_a_new_choice_replaces_the_kept_file_and_the_issue_form_drops_it(fake_relay):
    fake_relay.answer(429, {"error": "busy", "retry": True, "detail": "the relay is busy"})
    relay.send_report(*_viewed()[:3])
    fake_relay.answer(429, {"error": "busy", "retry": True, "detail": "the relay is busy"})
    ids, note, sha, _ = _viewed((ID_1, ID_2), "with both")
    relay.send_report(ids, note, sha)
    assert [entry["sha256"] for entry in relay.outbox_entries()] == [sha]
    relay.mark_opened(ids, note, sha)
    assert relay.outbox_entries() == [] and fake_relay.marks == [([ID_1, ID_2], "opened", None)]


def test_the_default_address_is_the_real_relay_and_the_guard_refuses_it(fake_relay, monkeypatch):
    monkeypatch.delenv(relay.RELAY_URL_ENV_VAR)
    assert relay.relay_url() == relay.RELAY_URL == "https://skellycertify-relay.dom-dd0.workers.dev"
    with pytest.raises(AssertionError, match="tried to GET"):  # the health check comes first
        relay.send_report(*_viewed()[:3])
    assert fake_relay.received == [] and fake_relay.marks == []


def test_issue_url_or_none_accepts_only_issues_of_the_relay_repository():
    assert relay.issue_url_or_none(ISSUE) == ISSUE
    for bad in (None, 7, ISSUE + "#x", ISSUE + "/", "https://github.com.evil/domisjustanumber/skellycertify/issues/7",
                "https://github.com/domisjustanumber/skellycertify/pull/7", ISSUE.replace("7", "0")):
        assert relay.issue_url_or_none(bad) is None


def test_the_routes_view_send_and_list_the_hand_in(fake_relay, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from freemocap.api.http.certify.certify_router import certify_router

    app = FastAPI()
    app.include_router(certify_router)
    client = TestClient(app)
    selection = {"report_ids": [ID_1], "note": "it failed twice"}
    viewed = client.post("/certify/hand_in/file", json=selection).json()
    assert viewed["file_name"] == "certify-report-20261119T100000Z.md" and viewed["fits_relay"]
    assert hashlib.sha256(viewed["content"].encode()).hexdigest() == viewed["sha256"]
    refused = client.post("/certify/hand_in/file", json={**selection, "note": "adapter 00:1a:2b:3c:4d:5e"})
    assert (refused.status_code, refused.json()["detail"]) == (422, {"code": "privacy-rule", "detail": "4"})
    changed = client.post("/certify/hand_in/send", json={**selection, "note": "edited", "sha256": viewed["sha256"]})
    assert (changed.status_code, changed.json()["detail"]["code"]) == (409, "file-changed")
    fake_relay.answer(422, {"error": "privacy-rule", "retry": False, "detail": 3})
    sent = client.post("/certify/hand_in/send", json={**selection, "sha256": viewed["sha256"]}).json()
    assert (sent["state"], sent["offer_issue_form"], sent["error"]["detail"]) == ("refused", True, "3")
    monkeypatch.setattr(skellytracker, "pending_reports", lambda include_handed_in=False: [
        {"report_id": ID_1, "kind": "quick", "created_utc": "2026-11-19T10:00:00Z", "has_failure": True,
         "evidence_valid": False, "state": "covered", "reference": "https://evil.example/issues/7"}])
    listed = client.get("/certify/hand_in").json()
    assert listed["relay_enabled"] and listed["reports"][0]["reference"] is None
    assert listed["reports"][0]["incomplete"] is False, "its run ended (no `cancelled` or `interrupted` reason)"
    assert listed["outbox"][0]["last_error"]["error"] == "privacy-rule" and listed["outbox"][0]["offer_issue_form"]
    opened = client.post("/certify/hand_in/opened", json={**selection, "sha256": viewed["sha256"]}).json()
    assert opened["outbox"] == [] and fake_relay.marks[-1] == ([ID_1], "opened", None)


def test_not_sent_makes_reports_pending_again_and_deletes_the_kept_files(fake_relay, tmp_path):
    fake_relay.answer(200, {"issue_url": ISSUE, "issue_number": 7, "duplicate": False})
    relay.send_report(*_viewed()[:3])  # covered, outbox already empty
    relay.mark_not_sent([ID_1])  # decision 24: also from covered
    assert fake_relay.marks[-1] == ([ID_1], "pending", None)
    fake_relay.answer(429, {"error": "busy", "retry": True, "detail": "the relay is busy"})
    relay.send_report(*_viewed((ID_2,))[:3])
    [entry] = relay.outbox_entries()
    assert entry["retry_pending"]
    relay.mark_not_sent([ID_2])
    assert fake_relay.marks[-1] == ([ID_2], "pending", None)
    assert relay.outbox_entries() == [] and not list((tmp_path / "certify" / "outbox").iterdir())
    relay.retry_outbox()
    assert len(fake_relay.received) == 2  # the first send and the one that failed; nothing after "not sent"


def test_not_sent_with_an_unknown_id_changes_nothing_and_the_route_lists_the_state(fake_relay, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from freemocap.api.http.certify.certify_router import certify_router

    fake_relay.answer(429, {"error": "busy", "retry": True, "detail": "the relay is busy"})
    relay.send_report(*_viewed()[:3])
    real_mark = skellytracker.mark_reports

    def mark(ids, state, *, reference=None):
        if ID_9 in ids:
            raise ValueError(ID_9)
        real_mark(ids, state, reference=reference)

    monkeypatch.setattr(skellytracker, "mark_reports", mark)
    monkeypatch.setattr(skellytracker, "pending_reports", lambda include_handed_in=False: [
        {"report_id": ID_1, "kind": "quick", "created_utc": None, "has_failure": True, "evidence_valid": False,
         "state": "pending", "reference": None}])
    app = FastAPI()
    app.include_router(certify_router)
    client = TestClient(app)
    refused = client.post("/certify/hand_in/not_sent", json={"report_ids": [ID_1, ID_9]})
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "unknown-report")
    assert len(relay.outbox_entries()) == 1
    listed = client.post("/certify/hand_in/not_sent", json={"report_ids": [ID_1]}).json()
    assert listed["outbox"] == [] and fake_relay.marks[-1] == ([ID_1], "pending", None)


# - freemocap's own reports beside skellytracker's (J13, J18) -

OWN = "9b1f6c2a-3d4e-4f5a-8b7c-6d5e4f3a2b1c"


@pytest.fixture
def own_report(fake_relay, monkeypatch):
    """A failed freemocap report in freemocap's real store (the test's data folder) between skellytracker's two."""
    from freemocap import certification

    module = dict(MODULE, id=OWN, created_utc="2026-11-19T11:00:00Z", schema="skellycertify.report/1.1.0",
                  package={"name": "freemocap", "version": "2.0.0-alpha.25", "commit": None, "tree_modified": None},
                  checks=[{"name": "data-folder", "result": "fail", "reason": "PermissionError"}])
    certification._write_json(certification.reports_dir() / f"{OWN}.json", module)
    monkeypatch.setattr(skellytracker, "pending_reports", lambda include_handed_in=False: [
        {"report_id": report_id, "kind": "quick", "created_utc": created, "has_failure": True, "evidence_valid": False,
         "state": "pending", "reference": None} for report_id, created in ((ID_1, "2026-11-19T10:00:00Z"),
                                                                         (ID_2, "2026-11-20T10:00:00Z"))])
    return module


def _own_states() -> list[tuple]:
    from freemocap import certification
    return [(row["state"], row["reference"]) for row in certification.pending_reports(include_handed_in=True)]


def test_the_hand_in_list_and_the_file_merge_both_packages_and_keep_each_module(own_report):
    assert [(row["package"], row["report_id"]) for row in relay.hand_in_reports()] == [
        ("skellytracker", ID_1), ("freemocap", OWN), ("skellytracker", ID_2)]
    _, body = relay.report_file_for([OWN, ID_1], None)
    data = json.loads(body.decode("utf-8").split("```json\n")[1].rsplit("```", 1)[0])
    assert data["schema"] == "skellycertify.report/1.5.0" and data["modules"] == [MODULE, own_report]
    assert "| freemocap | | data-folder | fail | PermissionError |" in body.decode("utf-8")


def test_a_kept_file_retried_at_start_marks_each_report_covered_in_its_own_store(fake_relay, own_report):
    ids, note, sha, _ = _viewed((ID_1, OWN))
    server = fake_relay
    server.answer(429, {"error": "busy", "retry": True, "detail": "the relay is busy"})
    assert relay.send_report(ids, note, sha)["state"] == "kept"
    assert server.marks == [] and _own_states() == [("pending", None)]
    server.answer(200, {"issue_url": ISSUE, "issue_number": 7, "duplicate": False})
    relay.retry_outbox()
    assert server.marks == [([ID_1], "covered", ISSUE)] and _own_states() == [("covered", ISSUE)]
    relay.mark_not_sent([OWN, ID_1])
    assert server.marks[-1] == ([ID_1], "pending", None) and _own_states() == [("pending", None)]
    relay.mark_opened(ids, note, sha)
    assert server.marks[-1] == ([ID_1], "opened", None) and _own_states() == [("opened", None)]
    with pytest.raises(HandInError) as unknown:
        relay.mark_not_sent([OWN, ID_9])
    assert unknown.value.code == "unknown-report" and _own_states() == [("opened", None)], "nothing changed"


def test_the_route_lists_each_reports_package(own_report):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from freemocap.api.http.certify.certify_router import certify_router

    app = FastAPI()
    app.include_router(certify_router)
    listed = TestClient(app).get("/certify/hand_in").json()
    assert [(row["package"], row["report_id"]) for row in listed["reports"]] == [
        ("skellytracker", ID_1), ("freemocap", OWN), ("skellytracker", ID_2)]


def test_the_test_session_has_the_relay_off_and_the_start_up_retry_makes_no_call(tmp_path, monkeypatch):
    """The guard of freemocap/tests/conftest.py: no test can post to the real relay."""
    assert relay.relay_url() == ""
    monkeypatch.setenv("FREEMOCAP_BASE_FOLDER", str(tmp_path))
    (tmp_path / "certify" / "outbox").mkdir(parents=True)
    (tmp_path / "certify" / "outbox" / ("a" * 64 + ".md")).write_bytes(b"kept")
    (tmp_path / "certify" / "outbox" / ("a" * 64 + ".json")).write_text(
        json.dumps({"file_name": "x.md", "report_ids": [ID_1], "failed_attempts": 0, "last_error": None}))
    calls = []
    monkeypatch.setattr(relay.requests, "post", lambda *args, **kwargs: calls.append(args))
    assert len(relay.outbox_entries()) == 1
    relay.retry_outbox()
    relay.start_outbox_retry()
    for thread in threading.enumerate():
        if thread.name == "CertifyOutboxRetry":
            thread.join(5)
    assert calls == []
