"""One skellytracker `LiveSampler` of the backend process, sampled at 1 Hz from one background thread.

The inference service runs as a thread in the backend process, so the backend pid is the inference pid.
The thread runs only while the timing relay has an interested connection; never per frame.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from threading import Event, Lock, Thread

from freemocap.core.streaming.message_model import LiveGpuLoad, LiveLoad

logger = logging.getLogger(__name__)

LIVE_LOAD_INTERVAL_S = 1.0


def _skellytracker_sample() -> Callable[[], LiveLoad]:
    from skellytracker.core.metrics import LiveSampler
    from skellytracker.core.system import gpu_device_keys
    sampler, pid = LiveSampler(), os.getpid()
    # `GpuSample.key` is the PCI bus id (`GpuInfo.key`); the UI and the models use device keys.
    devices = {gpu.key: (device_key, gpu.name) for device_key, gpu in gpu_device_keys()}
    return lambda: live_load_of(sampler.sample((pid,)), devices, pid)


def live_load_of(sample, devices: dict[str, tuple[str, str | None]], pid: int,
                 interval_s: float = LIVE_LOAD_INTERVAL_S) -> LiveLoad:
    """A `LiveLoad` from skellytracker's `LiveSample`, with each GPU joined to its device key and name."""
    process = next((process for process in sample.processes if process.pid == pid), None)
    return LiveLoad(
        sample_perf_counter_ns=sample.perf_counter_ns, interval_s=interval_s,
        memory_used_bytes=sample.memory_used_bytes, memory_available_bytes=sample.memory_available_bytes,
        cpu_utilization=sample.cpu_utilization,
        process_cpu_utilization=None if process is None else process.cpu_utilization,
        process_rss_bytes=None if process is None else process.rss_bytes,
        process_vram_used_bytes=None if process is None else process.vram_used_bytes,
        gpus=tuple(LiveGpuLoad(
            device_key=devices.get(gpu.key, (None, None))[0], name=devices.get(gpu.key, (None, None))[1],
            utilization=gpu.utilization, vram_used_bytes=gpu.vram_used_bytes, vram_free_bytes=gpu.vram_free_bytes,
            process_vram_used_bytes=next((entry.vram_used_bytes for entry in gpu.processes or () if entry.pid == pid), None))
            for gpu in sample.gpus),
        sample_errors=tuple(sample.sample_errors))


class LiveLoadSampler:
    """`start()` runs the sampling thread, `stop()` ends it and forgets the sample; `latest` is the newest sample."""

    def __init__(self, interval_s: float = LIVE_LOAD_INTERVAL_S,
                 make_sample: Callable[[], Callable[[], LiveLoad]] = _skellytracker_sample) -> None:
        self._interval_s = interval_s
        self._make_sample = make_sample
        self._sample: Callable[[], LiveLoad] | None = None
        self._lock = Lock()
        self._stop: Event | None = None
        self.latest: LiveLoad | None = None

    @property
    def running(self) -> bool:
        return self._stop is not None

    def start(self) -> None:
        with self._lock:
            if self._stop is not None:
                return
            stop = self._stop = Event()
        Thread(target=self._loop, args=(stop,), name="LiveLoadSampler", daemon=True).start()

    def stop(self) -> None:
        with self._lock:
            if self._stop is not None:
                self._stop.set()
            self._stop, self.latest = None, None

    def _loop(self, stop: Event) -> None:
        while not stop.is_set():
            try:
                if self._sample is None:
                    self._sample = self._make_sample()
                sample = self._sample()
            except Exception:  # a failed sample must not end the timing messages
                logger.exception("skellytracker's live load could not be sampled")
            else:
                with self._lock:
                    if not stop.is_set():
                        self.latest = sample
            stop.wait(self._interval_s)
