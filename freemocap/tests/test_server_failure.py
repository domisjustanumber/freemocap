"""Fatal application failures stop serving; client disconnects do not."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI, Request, WebSocket
from starlette.websockets import WebSocketDisconnect
from uvicorn import Config, Server

from freemocap.api.websocket import websocket_connect
from freemocap.api.http.app import shutdown
from freemocap.app import app as app_module
from freemocap.app.serve_application import serve_application
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.skeletons.tracked_skeleton_set import build_tracked_skeletons


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.state.global_kill_flag = SimpleNamespace(value=False)
    application.state.fatal_error = None
    return application


async def test_connection_constructor_failure_does_not_stop_app_or_reject_reconnect(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = FileNotFoundError("human_skeleton.yaml")
    constructor = Mock(side_effect=error)
    monkeypatch.setattr(websocket_connect, "WebsocketServer", constructor)
    send = AsyncMock()
    scope = {"type": "websocket", "app": app, "path": "/websocket/connect", "headers": []}
    socket = WebSocket(scope=scope, receive=AsyncMock(return_value={"type": "websocket.connect"}), send=send)
    await websocket_connect.websocket_server_connect(websocket=socket)
    assert not app.state.global_kill_flag.value
    assert app.state.fatal_error is None
    assert send.call_args.args[0]["code"] == 1011
    await websocket_connect.websocket_server_connect(
        websocket=WebSocket(scope=scope, receive=AsyncMock(return_value={"type": "websocket.connect"}), send=send),
    )
    assert constructor.call_count == 2


async def test_disconnect_does_not_stop_app(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(websocket_connect, "WebsocketServer", Mock(side_effect=WebSocketDisconnect(code=1000)))
    socket = WebSocket(
        scope={"type": "websocket", "app": app, "path": "/websocket/connect", "headers": []},
        receive=AsyncMock(return_value={"type": "websocket.connect"}), send=AsyncMock(),
    )
    await websocket_connect.websocket_server_connect(websocket=socket)
    assert not app.state.global_kill_flag.value
    assert app.state.fatal_error is None


async def test_fatal_flag_drives_uvicorn_exit(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    notice = Mock()
    monkeypatch.setattr("skellytracker.note_exit_requested", notice)
    server = Server(config=Config(app=app))
    server.started = True
    error = FileNotFoundError("human_skeleton.yaml")

    async def serve() -> None:
        app.state.fatal_error = error
        app.state.global_kill_flag.value = True
        while not server.should_exit:
            await asyncio.sleep(0)

    monkeypatch.setattr(server, "serve", serve)
    with pytest.raises(RuntimeError, match="fatal application error") as raised:
        await asyncio.wait_for(serve_application(server=server, app=app), timeout=2)
    assert raised.value.__cause__ is error
    assert server.should_exit
    notice.assert_not_called()  # a crash still counts as an unclean exit of a GPU EP


async def test_failed_startup_is_not_success(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    server = Server(config=Config(app=app))
    monkeypatch.setattr(server, "serve", AsyncMock())
    with pytest.raises(RuntimeError, match="startup failed"):
        await serve_application(server=server, app=app)


async def test_log_reader_failure_stops_server(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    server = Server(config=Config(app=app))
    server.started = True
    app.state.log_relay = Mock()
    app.state.log_relay.check_health.side_effect = RuntimeError("Application log queue reader failed")

    async def serve() -> None:
        while not server.should_exit:
            await asyncio.sleep(0)

    monkeypatch.setattr(server, "serve", serve)
    with pytest.raises(RuntimeError, match="log queue reader failed"):
        await asyncio.wait_for(serve_application(server=server, app=app), timeout=2)
    assert server.should_exit


async def test_missing_resources_fail_startup_and_cleanup(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    application = Mock()
    telemetry_shutdown = Mock()
    error = FileNotFoundError("human_skeleton.yaml")
    monkeypatch.setattr(app_module, "logger", Mock())
    monkeypatch.setattr(app_module, "get_freemocap_app", Mock(return_value=application))
    monkeypatch.setattr(app_module, "build_tracked_skeletons", Mock(side_effect=error))
    monkeypatch.setattr(app_module, "shutdown_telemetry", telemetry_shutdown)
    with pytest.raises(FileNotFoundError, match="human_skeleton.yaml"):
        async with app_module.app_lifespan(app=app):
            pytest.fail("Startup accepted missing resources")
    assert app.state.global_kill_flag.value
    assert app.state.fatal_error is error
    application.close.assert_called_once_with()
    telemetry_shutdown.assert_called_once_with()


def test_installed_default_skeleton_resources_load() -> None:
    assert build_tracked_skeletons(camera_node_config=CameraNodeConfig())


async def test_uvicorn_startup_failure_propagates(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    error = FileNotFoundError("human_skeleton.yaml")
    monkeypatch.setattr(app_module, "logger", Mock())
    monkeypatch.setattr(app_module, "build_tracked_skeletons", Mock(side_effect=error))
    monkeypatch.setattr(app_module, "get_freemocap_app", Mock(return_value=Mock()))
    monkeypatch.setattr(app_module, "shutdown_telemetry", Mock())
    app.router.lifespan_context = app_module.app_lifespan
    server = Server(config=Config(app=app, lifespan="on", log_config=None))
    with pytest.raises(RuntimeError, match="fatal application error") as raised:
        await asyncio.wait_for(serve_application(server=server, app=app), timeout=2)
    assert raised.value.__cause__ is error
    assert not server.started


async def test_shutdown_request_returns_and_stops_server(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutdown, "logger", Mock())
    monkeypatch.setattr(shutdown, "close_camera_groups", AsyncMock())
    monkeypatch.setattr("skellytracker.note_exit_requested", Mock())
    response = await shutdown.shutdown_server(
        request=Request(scope={"type": "http", "app": app, "path": "/shutdown", "headers": []}),
    )
    assert response.status_code == 200
    assert app.state.global_kill_flag.value
    server = Server(config=Config(app=app))
    server.started = True

    async def serve() -> None:
        while not server.should_exit:
            await asyncio.sleep(0)

    monkeypatch.setattr(server, "serve", serve)
    await asyncio.wait_for(serve_application(server=server, app=app), timeout=2)
    assert server.should_exit


async def test_shutdown_signal_sends_the_exit_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    import signal
    from threading import Event

    import freemocap.__main__ as entry
    from skellycam.core.ipc.process_management import worker_registry
    from skellycam.utilities import wait_functions

    handlers = {}
    notice = Mock()
    servers = []
    monkeypatch.setattr("skellytracker.note_exit_requested", notice)
    monkeypatch.setattr(entry, "logger", Mock())
    monkeypatch.setattr(signal, "signal", lambda signum, handler: handlers.__setitem__(signum, handler))
    monkeypatch.setattr(worker_registry, "WorkerRegistry", Mock())
    monkeypatch.setattr(wait_functions, "await_1s", AsyncMock())
    monkeypatch.setattr(app_module, "create_fastapi_app", Mock(return_value=FastAPI()))

    async def serve_application(*, server: Server, app: FastAPI, reload_stop: object) -> None:
        handlers[signal.SIGINT](signal.SIGINT, None)  # as uvicorn re-raises a captured Ctrl+C after it stops
        servers.append(server)

    monkeypatch.setattr(entry, "serve_application", serve_application)
    await entry._run_application(False, Mock(), Event(), server_port=1)
    notice.assert_called_once_with()
    assert servers[0].should_exit
