"""An earlier backend on the preferred port is asked to shut down before it is killed (its EP exit notice)."""
import subprocess
import sys

import pytest

from freemocap.utilities.kill_process_on_port import kill_process_on_port

_FAKE_BACKEND = """
import os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
record, leaves = sys.argv[1], sys.argv[2] == 'leaves'
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        with open(record, 'a') as output:
            output.write(self.path + '\\n')
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{}')
        if leaves:
            threading.Timer(0.2, os._exit, (0,)).start()
    def log_message(self, *args):
        pass
server = HTTPServer(('127.0.0.1', 0), Handler)
print(server.server_port, flush=True)
server.serve_forever()
"""


@pytest.fixture
def fake_backend(tmp_path):
    started = []

    def start(behaviour):
        record = tmp_path / 'requests.txt'
        process = subprocess.Popen([sys.executable, '-c', _FAKE_BACKEND, str(record), behaviour],
                                   stdout=subprocess.PIPE, text=True)
        started.append(process)
        return process, int(process.stdout.readline()), record
    yield start
    for process in started:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        process.stdout.close()


def test_backend_that_accepts_shutdown_exits_without_a_kill(fake_backend):
    process, port, record = fake_backend('leaves')
    kill_process_on_port(port, grace_seconds=10.0)
    assert record.read_text().splitlines() == ['/shutdown']
    assert process.wait(timeout=10) == 0


def test_process_still_on_the_port_after_the_grace_period_is_killed(fake_backend):
    process, port, record = fake_backend('stays')
    kill_process_on_port(port, grace_seconds=0.5)
    assert record.read_text().splitlines() == ['/shutdown']
    assert process.wait(timeout=10) != 0
