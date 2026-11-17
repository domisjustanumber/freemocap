"""PipelineTimingRelay: one reader of each pipeline's timing, shared by every connection.

A shared drain would split the events between connections, so the relay alone drains each
pipeline's `PipelineTimingTopic` subscription into that pipeline's rolling event store and
builds one message per pipeline at most every `PIPELINE_TIMING_INTERVAL_S`. Each interested
connection sends its own copy of the newest build. Interest is per connection and lasts as
long as it: with no interested connection there is no subscription, no build and no send.

A running posthoc mocap run has no pubsub: the relay drains the bounded buffer its tracking
appends to (`MocapPipeline.timing_records`) and sends the newest frames that have a
`pipeline.run` event, without the realtime lag and staleness rules (a slow CPU run is not stale).
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field

from freemocap.core.pipeline.pipeline_timing_events import (
    PIPELINE_RUN_SPAN,
    PipelineTimingEventStore,
    SkellytrackerTimingEvents,
    cap_events_by_frame_window,
    compute_timing_lag_info,
)
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline
from freemocap.core.pipeline.pipeline_timing_task_ids import CLOCK_DOMAIN_PERF_COUNTER
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.streaming.message_model import MessageEnvelope, PipelineTimingStreamMessage, encode_message
from freemocap.pubsub.pubsub_topics import PipelineTimingMessage

PIPELINE_TIMING_INTERVAL_S = 0.25
PIPELINE_TIMING_FRAME_WINDOW = 5
PIPELINE_TIMING_FRAME_BUFFER = 2
PIPELINE_TIMING_RETAIN_FRAMES = 20
PIPELINE_TIMING_MAX_CONTEXTLESS = 64


def _merge_samples(per_node: dict[str, dict[str, list[float]]], per_camera: dict[str, dict[str, list[float]]],
                   message: PipelineTimingMessage) -> None:
    if message.node_kind == "camera" and message.camera_id:
        bucket = per_camera.setdefault(str(message.camera_id), {})
    else:
        bucket = per_node.setdefault(message.node_kind, {})
    for stage, values in message.samples.items():
        bucket.setdefault(stage, []).extend(float(value) for value in values)


def configured_camera_fps_hz(pipeline: RealtimePipeline) -> float | None:
    """The slowest configured camera rate, or None unless every pipeline camera sets one."""
    rates: list[float] = []
    for camera_id in pipeline.camera_ids:
        rate = getattr(pipeline.camera_configs.get(camera_id), "framerate", None)
        if rate is None or rate <= 0:
            return None
        rates.append(float(rate))
    return min(rates) if rates else None


@dataclass
class _PipelineTiming:
    pipeline: RealtimePipeline
    store: PipelineTimingEventStore = field(default_factory=PipelineTimingEventStore)
    last_seen: dict[str, float] = field(default_factory=dict)


@dataclass
class _PosthocTiming:
    converter: SkellytrackerTimingEvents
    store: PipelineTimingEventStore = field(default_factory=PipelineTimingEventStore)


class PipelineTimingRelay:
    def __init__(self, interval_s: float = PIPELINE_TIMING_INTERVAL_S) -> None:
        self._interval_s = interval_s
        self._interested: set[object] = set()
        self._pipelines: dict[str, _PipelineTiming] = {}
        self._posthoc: dict[str, _PosthocTiming] = {}
        self._build = 0
        self._built_at: float | None = None
        self._messages: tuple[bytes, ...] = ()

    def add_interest(self, connection: object) -> None:
        self._interested.add(connection)

    def remove_interest(self, connection: object) -> None:
        self._interested.discard(connection)
        if not self._interested:
            for timing in self._pipelines.values():
                timing.pipeline.release_timing_subscription()
            self._pipelines.clear()
            self._posthoc.clear()
            self._built_at, self._messages = None, ()

    def latest(self, pipelines: Mapping[str, RealtimePipeline],
               posthoc_pipelines: Mapping[str, object] | None = None) -> tuple[int, tuple[bytes, ...]]:
        """The number and encoded messages of the newest build; builds again once the interval has passed.

        `posthoc_pipelines` is the posthoc manager's pipelines; only running mocap runs report timing.
        """
        if not self._interested:
            return self._build, ()
        now = time.perf_counter()
        if self._built_at is None or now - self._built_at >= self._interval_s:
            for pipeline_id in [known for known in self._pipelines if known not in pipelines]:
                self._pipelines.pop(pipeline_id).pipeline.release_timing_subscription()
            self._build += 1
            self._built_at = now
            running = {pipeline_id: pipeline for pipeline_id, pipeline in list((posthoc_pipelines or {}).items())
                       if isinstance(pipeline, MocapPipeline) and pipeline.started and pipeline.alive}
            # A run that ended is forgotten; the client drops a run that went silent.
            self._posthoc = {pipeline_id: timing for pipeline_id, timing in self._posthoc.items() if pipeline_id in running}
            self._messages = tuple(encode_message(self._message(pipeline_id, pipeline, now))
                                   for pipeline_id, pipeline in list(pipelines.items())) + tuple(
                encode_message(self._posthoc_message(pipeline_id, pipeline)) for pipeline_id, pipeline in running.items())
        return self._build, self._messages

    def _message(self, pipeline_id: str, pipeline: RealtimePipeline, now: float) -> PipelineTimingStreamMessage:
        timing = self._pipelines.get(pipeline_id)
        if timing is None or timing.pipeline is not pipeline:
            timing = self._pipelines[pipeline_id] = _PipelineTiming(pipeline=pipeline)
        active = pipeline.alive
        enabled = pipeline.config.log_pipeline_times
        per_node: dict[str, dict[str, list[float]]] = {}
        per_camera: dict[str, dict[str, list[float]]] = {}
        dropped = 0
        if active:
            for message in pipeline.drain_timing_messages():
                _merge_samples(per_node, per_camera, message)
                dropped += int(message.dropped_timing_events)
                timing.store.ingest(message.events)
                timing.last_seen[message.node_kind] = now
        if not (active and enabled):
            timing.store.clear()
            timing.last_seen.clear()
        timing.store.prune(retain_frames=PIPELINE_TIMING_RETAIN_FRAMES, max_contextless=PIPELINE_TIMING_MAX_CONTEXTLESS)
        events = timing.store.snapshot()
        fps = configured_camera_fps_hz(pipeline)
        lag = compute_timing_lag_info(events, configured_fps_hz=fps, last_seen=timing.last_seen, now=now)
        # Send only frames every active node kind has reached; a stalled kind does not hold the window back.
        safe_latest_frame = lag["safe_latest_frame"]
        complete = [] if safe_latest_frame is None else [
            event for event in events
            if event.node_kind not in lag["stale_nodes"]
            and (event.frame_number is None or event.frame_number <= safe_latest_frame)]
        capped, _ = cap_events_by_frame_window(
            complete, frame_window=PIPELINE_TIMING_FRAME_WINDOW, frame_buffer=PIPELINE_TIMING_FRAME_BUFFER)
        return PipelineTimingStreamMessage(
            envelope=MessageEnvelope(sequence=self._build),
            mode="realtime",
            pipeline_id=pipeline_id,
            camera_group_id=pipeline.camera_group_id,
            realtime_pipeline_active=active,
            log_pipeline_times_enabled=enabled,
            configured_camera_fps_hz=fps,
            per_node=per_node,
            per_camera=per_camera,
            events=tuple(capped),
            clock_domain=CLOCK_DOMAIN_PERF_COUNTER,
            relay_perf_counter_ns=time.perf_counter_ns(),
            dropped_timing_events=dropped,
            node_lag=dict(lag["node_lag"]),
            incomplete_frames=tuple(lag["incomplete_frames"]),
            stale_nodes=tuple(lag["stale_nodes"]),
        )

    def _posthoc_message(self, pipeline_id: str, pipeline: MocapPipeline) -> PipelineTimingStreamMessage:
        timing = self._posthoc.get(pipeline_id)
        if timing is None:
            timing = self._posthoc[pipeline_id] = _PosthocTiming(converter=SkellytrackerTimingEvents(pipeline_id=pipeline_id))
        records = pipeline.timing_records
        timing.store.ingest(timing.converter.convert([records.popleft() for _ in range(len(records))]))
        timing.store.prune(retain_frames=PIPELINE_TIMING_RETAIN_FRAMES, max_contextless=PIPELINE_TIMING_MAX_CONTEXTLESS)
        events = timing.store.snapshot()
        # A frame is complete once its tracker call ended; its camera wait arrives before that.
        done = max((event.frame_number for event in events
                    if event.stage == PIPELINE_RUN_SPAN and event.frame_number is not None), default=None)
        complete = [] if done is None else [
            event for event in events if event.frame_number is None or event.frame_number <= done]
        capped, _ = cap_events_by_frame_window(
            complete, frame_window=PIPELINE_TIMING_FRAME_WINDOW, frame_buffer=PIPELINE_TIMING_FRAME_BUFFER)
        return PipelineTimingStreamMessage(
            envelope=MessageEnvelope(sequence=self._build),
            mode="posthoc",
            pipeline_id=pipeline_id,
            camera_group_id=None,
            recording_name=pipeline.recording_info.recording_name,
            realtime_pipeline_active=True,
            log_pipeline_times_enabled=True,
            events=tuple(capped),
            clock_domain=CLOCK_DOMAIN_PERF_COUNTER,
            relay_perf_counter_ns=time.perf_counter_ns(),
        )
