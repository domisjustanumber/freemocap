"""Helpers for pipeline task events: the clock, the relay's rolling store, the frame window and node lag."""
from __future__ import annotations

import time
from collections.abc import Iterable

from freemocap.pubsub.pubsub_topics import PipelineTimingEvent


def perf_counter_ns() -> int:
    """Cross-process comparable high-resolution clock in nanoseconds."""
    return time.perf_counter_ns()


def span_event(
        *,
        task_id: str,
        stage: str,
        node_kind: str,
        frame_number: int,
        start_time_ns: int,
        end_time_ns: int,
        camera_id: str | None = None,
        batch_size: int | None = None,
) -> PipelineTimingEvent:
    """One measured span as a task event, its duration from its perf_counter_ns ends."""
    return PipelineTimingEvent(
        task_id=task_id, stage=stage, node_kind=node_kind, camera_id=camera_id, frame_number=frame_number,
        start_time_ns=start_time_ns, end_time_ns=end_time_ns,
        duration_ms=(end_time_ns - start_time_ns) / 1e6, batch_size=batch_size,
    )


class PipelineTimingEventStore:
    """Rolling, frame-keyed event buffer that survives drain cycles.

    Events are upserted by ``task_id`` so a node that flushes later than its
    peers does not lose its bars before the next websocket drain. Retention is
    frame-based: framed events older than ``retain_frames`` behind the newest
    frame are dropped, and contextless (``frame_number is None``) events are
    bounded by count using a monotonic ``_seen`` sequence.
    """

    def __init__(self) -> None:
        self._events: dict[str, PipelineTimingEvent] = {}
        self._seen: dict[str, int] = {}
        self._counter = 0

    def ingest(self, events: Iterable[PipelineTimingEvent]) -> None:
        for event in events:
            self._counter += 1
            self._events[event.task_id] = event
            self._seen[event.task_id] = self._counter

    def prune(self, *, retain_frames: int, max_contextless: int) -> None:
        framed = [
            event.frame_number
            for event in self._events.values()
            if event.frame_number is not None
        ]
        if framed:
            min_frame = max(framed) - retain_frames
            for task_id in list(self._events):
                event = self._events[task_id]
                if event.frame_number is not None and event.frame_number < min_frame:
                    self._remove(task_id)

        contextless = [
            task_id
            for task_id, event in self._events.items()
            if event.frame_number is None
        ]
        if len(contextless) > max_contextless:
            contextless.sort(key=lambda tid: self._seen.get(tid, 0))
            for task_id in contextless[: len(contextless) - max_contextless]:
                self._remove(task_id)

    def _remove(self, task_id: str) -> None:
        self._events.pop(task_id, None)
        self._seen.pop(task_id, None)

    @property
    def latest_frame(self) -> int | None:
        framed = [
            event.frame_number
            for event in self._events.values()
            if event.frame_number is not None
        ]
        return max(framed) if framed else None

    def snapshot(self) -> list[PipelineTimingEvent]:
        return list(self._events.values())

    def clear(self) -> None:
        self._events.clear()
        self._seen.clear()


def cap_events_by_frame_window(
        events: list[PipelineTimingEvent],
        *,
        frame_window: int = 5,
        frame_buffer: int = 2,
) -> tuple[list[PipelineTimingEvent], int]:
    """Keep events intersecting the latest ``frame_window`` frames plus buffer."""
    framed = [event for event in events if event.frame_number is not None]
    if not framed:
        return events, 0

    latest_frame = max(event.frame_number for event in framed if event.frame_number is not None)
    min_frame = latest_frame - frame_window - frame_buffer + 1
    kept: list[PipelineTimingEvent] = []
    dropped = 0
    for event in events:
        if event.frame_number is None or event.frame_number >= min_frame:
            kept.append(event)
        else:
            dropped += 1
    return kept, dropped


def compute_timing_lag_info(
        events: list[PipelineTimingEvent],
        *,
        configured_fps_hz: float | None = None,
        last_seen: dict[str, float] | None = None,
        now: float | None = None,
) -> dict[str, object]:
    """Compute per-node-kind lag and incomplete-frame metadata without dropping events.

    Returns a ``lag_info`` dict:
    - ``node_lag``: frames each node kind is behind the leader
    - ``incomplete_frames``: frame numbers missing one or more node kinds
    - ``stale_nodes``: node kinds excluded due to staleness timeout
    - ``safe_latest_frame``: latest frame all active node kinds have reached
      (``None`` when no framed events are present or all nodes are stale)

    The caller applies the ``safe_latest_frame`` ceiling to a send-time snapshot;
    this function never removes events.
    """
    if now is None:
        now = time.perf_counter()

    # Compute latest frame per node kind.
    latest_per_kind: dict[str, int] = {}
    for event in events:
        if event.frame_number is None:
            continue
        node_kind = event.node_kind or "unknown"
        current = latest_per_kind.get(node_kind)
        if current is None or event.frame_number > current:
            latest_per_kind[node_kind] = event.frame_number

    if not latest_per_kind:
        return {
            "node_lag": {},
            "incomplete_frames": [],
            "stale_nodes": [],
            "safe_latest_frame": None,
        }

    # Determine staleness threshold: max(0.5s, 15 frame periods).
    staleness_s = 0.5
    if configured_fps_hz and configured_fps_hz > 0:
        staleness_s = max(staleness_s, 15.0 / configured_fps_hz)

    stale_nodes: list[str] = []
    included_frames: list[int] = []
    for node_kind, frame in latest_per_kind.items():
        if last_seen is None or node_kind not in last_seen:
            # Never reported — still coming online, include it.
            included_frames.append(frame)
        elif now - last_seen[node_kind] > staleness_s:
            # Stalled — exclude from min.
            stale_nodes.append(node_kind)
        else:
            included_frames.append(frame)

    if not included_frames:
        return {
            "node_lag": {},
            "incomplete_frames": [],
            "stale_nodes": stale_nodes,
            "safe_latest_frame": None,
        }

    safe_latest_frame = min(included_frames)

    # Build lag info: how far each node kind is behind the leader.
    leader_frame = max(latest_per_kind.values())
    node_lag: dict[str, int] = {}
    for node_kind, frame in latest_per_kind.items():
        lag = leader_frame - frame
        if lag > 0:
            node_lag[node_kind] = lag

    # Identify incomplete frames: frames beyond safe_latest_frame but within
    # the frame window (at most 50 frames ahead to bound the set).
    incomplete_frames: list[int] = []
    for event in events:
        fn = event.frame_number
        if fn is not None and fn > safe_latest_frame and fn <= safe_latest_frame + 50:
            if fn not in incomplete_frames:
                incomplete_frames.append(fn)
    incomplete_frames.sort()

    return {
        "node_lag": node_lag,
        "incomplete_frames": incomplete_frames,
        "stale_nodes": stale_nodes,
        "safe_latest_frame": safe_latest_frame,
    }
