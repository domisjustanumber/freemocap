"""Free a port at backend start: ask an earlier backend there to shut down, then kill what still holds it."""
import logging
from urllib.request import Request, urlopen

import psutil

logger = logging.getLogger(__name__)
SHUTDOWN_GRACE_SECONDS = 5.0


def _port_owners(port: int) -> list[psutil.Process]:
    owners = []
    for proc in psutil.process_iter(['pid']):
        if proc.info['pid'] == 0:  # the kernel
            continue
        try:
            if any(conn.laddr and conn.laddr.port == port for conn in proc.net_connections(kind='inet')):
                owners.append(proc)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return owners


def kill_process_on_port(port: int, *, grace_seconds: float = SHUTDOWN_GRACE_SECONDS) -> None:
    """An earlier backend may hold a GPU EP session: `POST /shutdown` gives skellytracker its exit notice first,
    so the kill after it is not counted as an unclean exit of that EP."""
    owners = _port_owners(port)
    if not owners:
        return
    try:
        with urlopen(Request(f"http://127.0.0.1:{port}/shutdown", method="POST"), timeout=grace_seconds):
            pass
        owners = psutil.wait_procs(owners, timeout=grace_seconds)[1]
    except OSError as error:  # not a backend with /shutdown, or it did not answer
        logger.warning(f"Process on port {port} did not accept POST /shutdown ({error})")
    for proc in owners:
        logger.warning(f"Process already running on port {port} (PID {proc.pid}); killing it")
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
