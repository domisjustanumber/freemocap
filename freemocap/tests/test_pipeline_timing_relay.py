"""The pipeline-timing message, its shared reader and the per-connection interest that gates it."""
import asyncio
import multiprocessing
import time
from queue import Queue
from types import SimpleNamespace

import cbor2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.camera.config.camera_config import CameraConfig

from freemocap.api.websocket import websocket_connect
from freemocap.api.websocket.send_serializer import SendSerializer
from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.core.pipeline.posthoc.calibration_pipeline import CalibrationPipeline
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline, new_timing_records
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistry
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.streaming.message_model import (
    MessageEnvelope,
    PipelineTimingStreamMessage,
    encode_message,
)
from freemocap.core.streaming.pipeline_timing_relay import PipelineTimingRelay
from freemocap.core.tasks.background_task_state import BackgroundTaskState
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import PipelineTimingEvent, PipelineTimingMessage, PipelineTimingTopic
from freemocap.tests.test_websocket_disconnect import ClientLogBuffer


def _event(frame: int, node_kind: str = "camera", **overrides) -> PipelineTimingEvent:
    fields = dict(task_id=f"{node_kind}:{frame}", stage="read", node_kind=node_kind, camera_id="cam0", frame_number=frame,
                  start_time_ns=5_000_000_000 + frame, end_time_ns=5_002_000_000 + frame, duration_ms=2.0)
    return PipelineTimingEvent(**{**fields, **overrides})


@pytest.fixture
def pubsub():
    manager = PubSubTopicManager.create(global_kill_flag=multiprocessing.Value("b", False))
    yield manager
    manager.close()


def _pipeline(pubsub: PubSubTopicManager, pipeline_id: str = "abc123") -> RealtimePipeline:
    """A started pipeline with live-looking nodes over a real pubsub; nothing runs in it."""
    pipeline = RealtimePipeline.__new__(RealtimePipeline)
    pipeline.id = pipeline_id
    pipeline.pubsub = pubsub
    pipeline.started = True
    pipeline.camera_group = SimpleNamespace(error=None, id="group1", configs={"cam0": CameraConfig(camera_id="cam0", camera_index=0, framerate=30.0)})
    pipeline.camera_nodes = {"cam0": SimpleNamespace(is_alive=True)}
    pipeline.aggregation_node = SimpleNamespace(is_alive=True)
    pipeline.skeleton_inference_node = None
    pipeline.charuco_recorder_node = None
    pipeline.config = SimpleNamespace(log_pipeline_times=True)
    pipeline._timing_subscription = None
    return pipeline


def _publish(pubsub: PubSubTopicManager, *events: PipelineTimingEvent, dropped: int = 0) -> None:
    pubsub.publish(PipelineTimingTopic, PipelineTimingMessage(
        node_kind="camera", camera_id="cam0", samples={"read": [2.0]}, events=list(events), dropped_timing_events=dropped))
    pubsub.drain()


def _decoded_until(relay: PipelineTimingRelay, pipelines: dict, predicate) -> list[dict]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        _, messages = relay.latest(pipelines)
        decoded = [cbor2.loads(message) for message in messages]
        if predicate(decoded):
            return decoded
        time.sleep(0.01)
    pytest.fail("The relay never built the expected timing message")


def test_the_message_is_self_contained_and_round_trips():
    event = _event(7, parent_task_ids=["camera:6"], batch_size=2, camera_id=None)
    message = PipelineTimingStreamMessage(
        envelope=MessageEnvelope(sequence=3), mode="realtime", pipeline_id="abc123", camera_group_id="group1",
        realtime_pipeline_active=True, log_pipeline_times_enabled=True, configured_camera_fps_hz=30.0,
        per_node={"aggregator": {"triangulate": [1.5]}}, per_camera={"cam0": {"read": [2.0, 2.5]}}, events=(event,),
        relay_perf_counter_ns=2**40, dropped_timing_events=4, node_lag={"aggregator": 2},
        incomplete_frames=(8, 9), stale_nodes=("skeleton_inference",))
    decoded = cbor2.loads(encode_message(message))
    assert decoded == {
        "kind": "pipeline_timing", "version": 0, "timestamp": 0.0, "sequence": 3,
        "mode": "realtime", "pipeline_id": "abc123", "camera_group_id": "group1",
        "realtime_pipeline_active": True, "log_pipeline_times_enabled": True, "configured_camera_fps_hz": 30.0,
        "per_node": {"aggregator": {"triangulate": [1.5]}}, "per_camera": {"cam0": {"read": [2.0, 2.5]}},
        # None fields are left out, as in every kind.
        "events": [{"task_id": "camera:7", "parent_task_ids": ["camera:6"], "stage": "read", "node_kind": "camera",
                    "frame_number": 7, "start_time_ns": 5_000_000_007, "end_time_ns": 5_002_000_007,
                    "duration_ms": 2.0, "batch_size": 2}],
        "clock_domain": "perf_counter", "relay_perf_counter_ns": 2**40, "dropped_timing_events": 4,
        "node_lag": {"aggregator": 2}, "incomplete_frames": [8, 9], "stale_nodes": ["skeleton_inference"],
    }


def test_without_interest_nothing_is_subscribed_or_built(pubsub):
    relay, pipeline = PipelineTimingRelay(interval_s=0.0), _pipeline(pubsub)
    assert relay.latest({pipeline.id: pipeline}) == (0, ())
    assert pipeline._timing_subscription is None
    assert len(pubsub.topics[PipelineTimingTopic].subscriptions) == 0


def test_the_store_builds_a_capped_window_with_per_message_counts(pubsub):
    relay, pipeline = PipelineTimingRelay(interval_s=0.0), _pipeline(pubsub)
    pipelines = {pipeline.id: pipeline}
    relay.add_interest(object())
    relay.latest(pipelines)  # the first build subscribes
    _publish(pubsub, *(_event(frame) for frame in range(1, 13)), dropped=3)
    (message,) = _decoded_until(relay, pipelines, lambda decoded: decoded and decoded[0]["events"])
    assert message["sequence"] == relay._build
    assert (message["pipeline_id"], message["camera_group_id"], message["mode"]) == ("abc123", "group1", "realtime")
    assert message["realtime_pipeline_active"] and message["log_pipeline_times_enabled"]
    assert message["configured_camera_fps_hz"] == 30.0 and message["clock_domain"] == "perf_counter"
    # The window keeps the newest frame_window + frame_buffer frames.
    assert [event["frame_number"] for event in message["events"]] == list(range(6, 13))
    assert message["dropped_timing_events"] == 3 and message["per_camera"] == {"cam0": {"read": [2.0]}}
    assert message["node_lag"] == {} and message["incomplete_frames"] == [] and message["stale_nodes"] == []
    # The next build still carries the stored events; the per-message counts are of its own interval.
    later = cbor2.loads(relay.latest(pipelines)[1][0])
    assert later["events"] == message["events"] and later["dropped_timing_events"] == 0 and later["per_camera"] == {}
    assert len(pubsub.topics[PipelineTimingTopic].subscriptions) == 1


def test_the_last_interest_ending_releases_the_subscription_and_a_new_one_resubscribes(pubsub):
    relay, pipeline = PipelineTimingRelay(interval_s=0.0), _pipeline(pubsub)
    pipelines = {pipeline.id: pipeline}
    connection = object()
    relay.add_interest(connection)
    relay.latest(pipelines)
    _publish(pubsub, _event(1))
    _decoded_until(relay, pipelines, lambda decoded: decoded and decoded[0]["events"])
    relay.remove_interest(connection)
    assert pipeline._timing_subscription is None and len(pubsub.topics[PipelineTimingTopic].subscriptions) == 0
    assert relay.latest(pipelines)[1] == ()
    _publish(pubsub, _event(2))  # published while nobody listens: not kept
    reconnected = object()
    relay.add_interest(reconnected)
    relay.latest(pipelines)
    _publish(pubsub, _event(3))
    (message,) = _decoded_until(relay, pipelines, lambda decoded: decoded and decoded[0]["events"])
    assert [event["frame_number"] for event in message["events"]] == [3]


def _timing_app(pipeline: RealtimePipeline, relay: PipelineTimingRelay):
    app = FastAPI()
    app.state.global_kill_flag = SimpleNamespace(value=False)
    app.state.fatal_error = None
    app.include_router(websocket_connect.websocket_router)
    service = SimpleNamespace(
        to_state_dict=lambda: {}, posthoc_pipeline_manager=SimpleNamespace(task_snapshot=TaskRegistry().snapshot, pipelines={}),
        sync_job_manager=SimpleNamespace(task_state=BackgroundTaskState()),
        realtime_pipeline_manager=SimpleNamespace(pipelines={pipeline.id: pipeline}), pipeline_timing_relay=relay)

    async def idle():
        await asyncio.Event().wait()

    def connection_server(*, websocket, fastapi_app):
        server = WebsocketServer.__new__(WebsocketServer)
        server.websocket = websocket
        server._global_kill_flag = fastapi_app.state.global_kill_flag
        server._websocket_should_continue = True
        server._serializer = SendSerializer(websocket)
        server._display_image_sizes = None
        server.ws_tasks = []
        server._app = service
        server._relay = SimpleNamespace(run=idle)
        server._log_relay = ClientLogBuffer(Queue())
        return server
    return app, connection_server


def _kinds(client, count: int) -> list[str]:
    """The kinds of the next `count` binary messages."""
    kinds = []
    while len(kinds) < count:
        message = client.receive()
        assert message["type"] != "websocket.close"
        if "bytes" in message:
            kinds.append(cbor2.loads(message["bytes"])["kind"])
    return kinds


def _next_timing(client) -> dict:
    for _ in range(50):
        message = client.receive()
        assert message["type"] != "websocket.close"
        if "bytes" in message and (decoded := cbor2.loads(message["bytes"]))["kind"] == "pipeline_timing":
            return decoded
    pytest.fail("No pipeline timing message arrived")


def _next_timing_with_events(client) -> dict:
    for _ in range(40):
        if (message := _next_timing(client))["events"]:
            return message
    pytest.fail("No pipeline timing message with events arrived")


def test_two_windows_see_the_same_events(monkeypatch, pubsub):
    pipeline, relay = _pipeline(pubsub), PipelineTimingRelay()
    app, connection_server = _timing_app(pipeline, relay)
    monkeypatch.setattr(websocket_connect, "WebsocketServer", connection_server)
    with TestClient(app) as client, client.websocket_connect("/websocket/connect") as first, \
            client.websocket_connect("/websocket/connect") as second:
        first.send_json({"pipelineTiming": True})
        second.send_json({"pipelineTiming": True})
        _next_timing(first), _next_timing(second)  # both read through the one subscription now
        _publish(pubsub, *(_event(frame) for frame in range(1, 4)))
        events = [_next_timing_with_events(window)["events"] for window in (first, second)]
        assert events[0] == events[1] and [event["frame_number"] for event in events[0]] == [1, 2, 3]
        assert len(pubsub.topics[PipelineTimingTopic].subscriptions) == 1


def test_only_connections_that_ask_get_timing_and_a_reconnect_asks_again(monkeypatch, pubsub):
    pipeline, relay = _pipeline(pubsub), PipelineTimingRelay()
    app, connection_server = _timing_app(pipeline, relay)
    monkeypatch.setattr(websocket_connect, "WebsocketServer", connection_server)
    with TestClient(app) as client:
        with client.websocket_connect("/websocket/connect") as metrics, \
                client.websocket_connect("/websocket/connect") as viewer:
            metrics.send_json({"pipelineTiming": True})
            assert _next_timing(metrics)["pipeline_id"] == "abc123"
            # The viewer never asked: its progress snapshots keep coming, timing never does.
            assert "pipeline_timing" not in _kinds(viewer, 5)
        deadline = time.monotonic() + 5
        while relay._interested and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not relay._interested and pipeline._timing_subscription is None
        with client.websocket_connect("/websocket/connect") as reconnected:
            # A new connection starts without interest until it declares it again.
            assert "pipeline_timing" not in _kinds(reconnected, 4)
            reconnected.send_json({"pipelineTiming": True})
            _next_timing(reconnected)
            _publish(pubsub, _event(4))
            assert [event["frame_number"] for event in _next_timing_with_events(reconnected)["events"]] == [4]
            reconnected.send_json({"pipelineTiming": False})
            deadline = time.monotonic() + 5
            while relay._interested and time.monotonic() < deadline:
                time.sleep(0.01)
            assert not relay._interested


def test_an_invalid_interest_closes_only_that_connection(monkeypatch, pubsub):
    pipeline, relay = _pipeline(pubsub), PipelineTimingRelay()
    app, connection_server = _timing_app(pipeline, relay)
    monkeypatch.setattr(websocket_connect, "WebsocketServer", connection_server)
    with TestClient(app) as client, client.websocket_connect("/websocket/connect") as invalid:
        invalid.send_json({"pipelineTiming": "yes"})
        for _ in range(20):
            message = invalid.receive()
            if message["type"] == "websocket.close":
                assert message["code"] == 1008
                break
        else:
            pytest.fail("The invalid client was not closed")
    assert not relay._interested and not app.state.global_kill_flag.value


def _mocap(pipeline_id: str = "posthoc-run", alive: list[bool] | None = None) -> MocapPipeline:
    """A started posthoc mocap pipeline whose worker reports `alive[0]`; nothing runs in it."""
    alive = alive if alive is not None else [True]
    pipeline = MocapPipeline.__new__(MocapPipeline)
    pipeline.id, pipeline.started, pipeline.timing_records = pipeline_id, True, new_timing_records()
    pipeline.recording_info = SimpleNamespace(recording_name="session_1")
    pipeline.worker = SimpleNamespace(is_alive=lambda: alive[0])
    return pipeline


def _posthoc_frame(pipeline: MocapPipeline, frame: int, *, tracked: bool = True, start_ns: int = 1_000) -> None:
    """What the tracking of one frame appends: its camera wait, then the run's spans of the call."""
    pipeline.timing_records.append(PipelineTimingEvent(
        task_id=f"{pipeline.id}:{frame}:batch:video_read:graph.camera_batch_wait", stage="graph.camera_batch_wait",
        node_kind="video_read", frame_number=frame, start_time_ns=start_ns, end_time_ns=start_ns + 10, duration_ms=0.00001,
        batch_size=3))
    if tracked:
        images = [{"frame_index": frame, "camera_id": camera} for camera in ("cam0", "cam1", "cam2")]
        for node_id, span in (("wholebody", "inference"), ("pipeline", "run")):
            pipeline.timing_records.append({"images": images, "node_id": node_id, "span": span, "batch_size": 3,
                                            "start_ns": start_ns + 20, "end_ns": start_ns + 30})


def _posthoc_messages(relay: PipelineTimingRelay, posthoc: dict) -> list[dict]:
    return [message for message in map(cbor2.loads, relay.latest({}, posthoc)[1]) if message["mode"] == "posthoc"]


def test_a_posthoc_run_is_built_only_with_interest_and_tagged_with_its_pipeline_id():
    relay, pipeline = PipelineTimingRelay(interval_s=0.0), _mocap()
    posthoc = {pipeline.id: pipeline}
    _posthoc_frame(pipeline, 0)
    assert relay.latest({}, posthoc) == (0, ())
    assert len(pipeline.timing_records) == 3, "without interest the buffer is not read"
    relay.add_interest(object())
    (message,) = _posthoc_messages(relay, posthoc)
    assert (message["mode"], message["pipeline_id"], message["recording_name"]) == ("posthoc", "posthoc-run", "session_1")
    assert "camera_group_id" not in message  # None is left out: a posthoc run has no camera group
    assert message["realtime_pipeline_active"] and message["log_pipeline_times_enabled"]
    stages = [(event["stage"], event["node_kind"]) for event in message["events"]]
    assert stages == [("graph.camera_batch_wait", "video_read"), ("wholebody.inference", "skeleton_inference"),
                      ("pipeline.run", "skeleton_inference")]
    assert all(event["task_id"].startswith("posthoc-run:") for event in message["events"])
    assert not pipeline.timing_records


def test_a_posthoc_run_sends_its_tracked_frames_without_lag_or_stale_filtering():
    relay, pipeline = PipelineTimingRelay(interval_s=0.0), _mocap()
    posthoc = {pipeline.id: pipeline}
    relay.add_interest(object())
    # Events far older than the realtime 0.5 s staleness rule, as from a slow CPU run.
    for frame in range(12):
        _posthoc_frame(pipeline, frame, start_ns=frame)
    _posthoc_frame(pipeline, 12, tracked=False)  # its camera wait is in; its tracker call is not
    (message,) = _posthoc_messages(relay, posthoc)
    assert sorted({event["frame_number"] for event in message["events"]}) == list(range(5, 12))
    assert message["node_lag"] == {} and message["stale_nodes"] == [] and message["incomplete_frames"] == []
    _posthoc_frame(pipeline, 13)
    (later,) = _posthoc_messages(relay, posthoc)
    assert max(event["frame_number"] for event in later["events"]) == 13


def test_no_posthoc_message_after_the_run_ends_and_calibration_gives_none():
    relay, alive = PipelineTimingRelay(interval_s=0.0), [True]
    pipeline = _mocap(alive=alive)
    calibration = CalibrationPipeline.__new__(CalibrationPipeline)
    posthoc = {pipeline.id: pipeline, "calibration-run": calibration}
    relay.add_interest(object())
    _posthoc_frame(pipeline, 0)
    assert [message["pipeline_id"] for message in _posthoc_messages(relay, posthoc)] == ["posthoc-run"]
    alive[0] = False
    _posthoc_frame(pipeline, 1)
    assert _posthoc_messages(relay, posthoc) == []
    assert relay._posthoc == {}
    assert _posthoc_messages(relay, {"calibration-run": calibration}) == []
