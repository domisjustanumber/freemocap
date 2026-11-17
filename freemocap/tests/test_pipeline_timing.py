"""Tests for pipeline timing task events, the stage timer and the relay helpers."""
from __future__ import annotations

import multiprocessing

from freemocap.core.pipeline.pipeline_stage_timer import MAX_EVENTS_PER_FLUSH, PipelineStageTimer
from freemocap.core.pipeline.pipeline_timing_events import (
    PipelineTimingEventStore,
    cap_events_by_frame_window,
    compute_timing_lag_info,
)
from freemocap.core.pipeline.pipeline_timing_task_ids import (
    batch_task_id,
)
from freemocap.pubsub.pubsub_topics import PipelineTimingEvent, PipelineTimingMessage


# ═══════════════════════════════════════════════════════════════════════════════
# Task ID helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeterministicTaskIds:
    def test_batch_task_id(self) -> None:
        assert batch_task_id(
            frame_number=7,
            node_kind="skeleton_inference",
            stage="predict_batch",
        ) == "7:batch:skeleton_inference:predict_batch"


# ═══════════════════════════════════════════════════════════════════════════════
# PipelineStageTimer
# ═══════════════════════════════════════════════════════════════════════════════

class TestDroppedEventAccounting:
    def test_timer_drops_events_when_buffer_full(self) -> None:
        timer = PipelineStageTimer(name="test")
        for index in range(MAX_EVENTS_PER_FLUSH + 5):
            timer.record_task_event(
                PipelineTimingEvent(
                    task_id=f"{index}:batch:test:stage",
                    stage="stage",
                    node_kind="test",
                    frame_number=index,
                    duration_ms=1.0,
                ),
            )
        assert len(timer.events) == MAX_EVENTS_PER_FLUSH
        assert timer.dropped_events == 5

    def test_record_simple_elapsed_ms(self) -> None:
        timer = PipelineStageTimer(name="test")
        timer.record("predict_batch", 12.5)
        timer.record("predict_batch", 7.5)
        assert timer.samples["predict_batch"] == [12.5, 7.5]

    def test_maybe_flush_publishes_and_clears(self) -> None:
        timer = PipelineStageTimer(name="test_node", flush_interval=0.0)
        pub_queue: multiprocessing.Queue = multiprocessing.Queue()

        # Accumulate one event (record_task_event also records the duration sample).
        timer.record_task_event(
            PipelineTimingEvent(
                task_id="1:batch:skeleton_inference:predict_batch",
                stage="predict_batch",
                node_kind="skeleton_inference",
                frame_number=1,
                duration_ms=3.0,
            ),
        )
        timer.dropped_events = 2  # simulate prior drops

        timer.maybe_flush(
            publication_queue=pub_queue,
            node_kind="skeleton_inference",
            camera_id="cam_0",
        )

        assert not pub_queue.empty()
        msg: PipelineTimingMessage = pub_queue.get_nowait()
        assert msg.node_kind == "skeleton_inference"
        assert msg.node_label == "test_node"
        assert msg.camera_id == "cam_0"
        assert msg.samples == {"predict_batch": [3.0]}
        assert len(msg.events) == 1
        assert msg.dropped_timing_events == 2

        # Internal state is cleared after flush.
        assert timer.samples["predict_batch"] == []
        assert timer.events == []
        assert timer.dropped_events == 0

    def test_maybe_flush_skips_when_empty(self) -> None:
        timer = PipelineStageTimer(name="test", flush_interval=0.0)
        pub_queue: multiprocessing.Queue = multiprocessing.Queue()
        timer.maybe_flush(publication_queue=pub_queue, node_kind="test")
        assert pub_queue.empty()

    def test_first_flush_waits_one_interval_on_the_perf_counter_clock(self) -> None:
        timer = PipelineStageTimer(name="test", flush_interval=60.0)
        timer.record("stage", 1.0)
        pub_queue: multiprocessing.Queue = multiprocessing.Queue()
        timer.maybe_flush(publication_queue=pub_queue, node_kind="test")
        assert pub_queue.empty()
        timer.last_flush -= 60.0
        timer.maybe_flush(publication_queue=pub_queue, node_kind="test")
        assert pub_queue.get(timeout=5.0).samples == {"stage": [1.0]}


# ═══════════════════════════════════════════════════════════════════════════════
# cap_events_by_frame_window
# ═══════════════════════════════════════════════════════════════════════════════

class TestCapEventsByFrameWindow:
    def test_keeps_latest_frames(self) -> None:
        events = [
            PipelineTimingEvent(task_id=f"{frame}:agg:x", stage="x", node_kind="aggregator", frame_number=frame)
            for frame in range(10)
        ]
        kept, dropped = cap_events_by_frame_window(events, frame_window=3, frame_buffer=0)
        assert dropped == 7
        assert {event.frame_number for event in kept} == {7, 8, 9}


# ═══════════════════════════════════════════════════════════════════════════════
# PipelineTimingEventStore
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineTimingEventStore:
    @staticmethod
    def _event(task_id: str, frame_number: int | None) -> PipelineTimingEvent:
        return PipelineTimingEvent(task_id=task_id, stage="x", node_kind="camera", frame_number=frame_number)

    def test_upsert_dedupes_by_task_id(self) -> None:
        store = PipelineTimingEventStore()
        store.ingest([self._event("a", 1)])
        store.ingest([self._event("a", 1)])
        assert len(store.snapshot()) == 1

    def test_prune_keeps_latest_retain_frames(self) -> None:
        store = PipelineTimingEventStore()
        store.ingest([self._event(f"{frame}", frame) for frame in range(20)])
        store.prune(retain_frames=5, max_contextless=4)
        frames = {event.frame_number for event in store.snapshot()}
        # keep the newest frame plus `retain_frames` of history behind it.
        assert frames == {14, 15, 16, 17, 18, 19}

    def test_contextless_bounded_and_update_moves_to_newest(self) -> None:
        store = PipelineTimingEventStore()
        for frame in range(5):
            store.ingest([self._event(f"c{frame}", None)])
        store.ingest([self._event("c0", None)])  # update oldest -> now newest
        store.prune(retain_frames=5, max_contextless=3)
        remaining = {event.task_id for event in store.snapshot()}
        assert len(remaining) == 3
        assert "c0" in remaining
        assert "c1" not in remaining

    def test_clear_empties_store(self) -> None:
        store = PipelineTimingEventStore()
        store.ingest([self._event("a", 1)])
        store.clear()
        assert store.snapshot() == []
        assert store.latest_frame is None


# ═══════════════════════════════════════════════════════════════════════════════
# compute_timing_lag_info
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeTimingLagInfo:
    @staticmethod
    def _event(task_id: str, node_kind: str, frame_number: int) -> PipelineTimingEvent:
        return PipelineTimingEvent(task_id=task_id, stage="x", node_kind=node_kind, frame_number=frame_number)

    def test_never_drops_events_and_reports_lag(self) -> None:
        events = [
            self._event("c1", "camera", 10),
            self._event("s1", "skeleton_inference", 8),
        ]
        lag_info = compute_timing_lag_info(
            events,
            last_seen={"camera": 0.0, "skeleton_inference": 0.0},
            now=0.0,
        )
        assert lag_info["safe_latest_frame"] == 8
        assert lag_info["node_lag"] == {"skeleton_inference": 2}
        assert lag_info["incomplete_frames"] == [10]
        assert lag_info["stale_nodes"] == []

    def test_stale_node_excluded_from_safe(self) -> None:
        events = [
            self._event("c1", "camera", 10),
            self._event("s1", "skeleton_inference", 8),
        ]
        lag_info = compute_timing_lag_info(
            events,
            last_seen={"camera": 0.0, "skeleton_inference": -10.0},
            now=0.0,
        )
        assert lag_info["safe_latest_frame"] == 10
        assert lag_info["stale_nodes"] == ["skeleton_inference"]

    def test_empty_input_returns_none_safe(self) -> None:
        lag_info = compute_timing_lag_info([], now=0.0)
        assert lag_info["safe_latest_frame"] is None
        assert lag_info["node_lag"] == {}
        assert lag_info["incomplete_frames"] == []
        assert lag_info["stale_nodes"] == []
