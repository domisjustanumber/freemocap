"""The metrics window's system information endpoint and the live load of the pipeline_timing messages."""
import json
import os
import re
import socket
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cbor2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellytracker.core import eps as st_eps
from skellytracker.core import system as st_system
from skellytracker.core.eps.records import EpCandidate, EpRecommendation, EpStatus, InstallOffer, PackStatus, RecommendationSource, RunDevice
from skellytracker.core.metrics import GpuProcessSample, GpuSample, LiveSample, ProcessSample
from skellytracker.core.system import (
    EnvironmentInfo, GpuInfo, HostInfo, LibraryVersion, LoadedLibrariesInfo, NvidiaGpuInfo, NvidiaRuntimeInfo, PythonInfo, RuntimeInfo,
)

from freemocap.api.http.onnx.onnx_router import onnx_router
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline
from freemocap.core.streaming.live_load import LiveLoadSampler, live_load_of
from freemocap.core.streaming.message_model import LiveLoad, MessageEnvelope, PipelineTimingStreamMessage, encode_message
from freemocap.core.streaming.pipeline_timing_relay import PipelineTimingRelay

STORE_ROOT = str(Path.home() / "AppData" / "skellytracker-eps")
NVIDIA = GpuInfo(key="0000:01:00.0", vendor="nvidia", name="Some NVIDIA GPU", pci_bus_id="0000:01:00.0", pci_vendor_id=0x10DE,
                 pci_device_id=0x2484, driver_version="610.88", vram_total_bytes=8 * 2**30,
                 nvidia=NvidiaGpuInfo(uuid="GPU-secret-uuid", compute_capability="8.6", brand="geforce"))
NO_IDS = GpuInfo(key="LUID-1", vendor="other", name="Display adapter")
HOST = HostInfo(os_name="Windows", os_release="11", os_version="10.0.26300", arch="AMD64", memory_total_bytes=64 * 2**30,
                os_build=26300, cpu_name="Some CPU", cpu_physical_cores=8, cpu_logical_cores=16, cpu_max_frequency_hz=3_400_000_000,
                gpus=(NVIDIA, NO_IDS))
DEVICE = "gpu:10de:2484:0"
CHOSEN = EpCandidate(ep_key="gpu-ep", ep_name="GpuEp", status="ready", device_key=DEVICE)
RECOMMENDATION = EpRecommendation(form="performance", hardware_class="nvidia-cc80", chosen=CHOSEN, precision="fp16",
    source=RecommendationSource(catalog_revision="r", row_id="nvidia-cc80"),
    skipped=(EpCandidate(ep_key="pack-ep", ep_name="Nv", status="not_installed", reason="the pack is not installed"),),
    offers=(InstallOffer(kind="add-pack", ep_key="pack-ep", download_bytes=110_000_000, note="Run `skellytracker-eps install pack-ep`."),
            InstallOffer(kind="none-available")))
STATUS = EpStatus(ort_version="1.31.1", catalog_revision="r", core_matches_pin=False, platform_tag="win_amd64", store_root=STORE_ROOT,
    store_free_bytes=1, host=HOST, performance=RECOMMENDATION, accuracy=RECOMMENDATION, warnings=("onnxruntime 1.30 is installed.",),
    eps=(PackStatus(key="gpu-ep", label="NVIDIA CUDA", state="ready", usable=True, uses_gpu=True,
                    devices=(RunDevice(device_key=DEVICE, gpu_key=NVIDIA.key, name=NVIDIA.name, vram_total_bytes=NVIDIA.vram_total_bytes),)),
         PackStatus(key="pack-ep", label="TensorRT RTX", state="not_installed", install_hint="Run `skellytracker-eps install pack-ep`.")))
RUNTIME = RuntimeInfo(skellytracker_version="2.0.0", python_version="3.13.18", skellytracker_commit="0a50c719", mediapipe_version="1.2.2",
                      ort_packages=("onnxruntime",), ort_version="1.31.1", ep_names=("CpuEp",),
                      nvidia=NvidiaRuntimeInfo(driver_supported_cuda_version="13.3"))
ENVIRONMENT = EnvironmentInfo(python=PythonInfo("CPython", "3.13.18", "main, Oct 26 2026", "MSC v.1944"),
                              argv=(str(Path.home() / "freemocap" / "run.py"),))


def _client(app_state) -> TestClient:
    app = FastAPI()
    app.include_router(onnx_router, prefix="/freemocap")
    patcher = patch("freemocap.app.freemocap_application.get_freemocap_app", return_value=app_state)
    patcher.start()
    return TestClient(app), patcher


def _app_state(realtime: list[dict], posthoc: dict | None = None):
    return SimpleNamespace(inference_service=Mock(provider_status=Mock(return_value=realtime)),
                           posthoc_pipeline_manager=SimpleNamespace(pipelines=posthoc or {}))


def _mocap(pipeline_id: str, statuses: list[dict], alive: bool = True) -> MocapPipeline:
    pipeline = MocapPipeline.__new__(MocapPipeline)
    pipeline.id, pipeline.started = pipeline_id, True
    pipeline.worker = SimpleNamespace(is_alive=lambda: alive)
    pipeline.inference_services = [Mock(provider_status=Mock(return_value=statuses))]
    return pipeline


@pytest.fixture
def faked_probes(monkeypatch):
    loaded = iter([LoadedLibrariesInfo(), LoadedLibrariesInfo(libraries=(LibraryVersion("cudnn", "9.1", "module:cudnn64_9"),))])
    monkeypatch.setattr(st_system, "probe_host", lambda: HOST)
    monkeypatch.setattr(st_system, "probe_runtime", lambda: RUNTIME)
    monkeypatch.setattr(st_system, "probe_environment", lambda: ENVIRONMENT)
    monkeypatch.setattr(st_system, "probe_loaded_libraries", lambda: next(loaded))
    monkeypatch.setattr(st_eps, "status", lambda: STATUS)


def _assert_private(text: str) -> None:
    assert STORE_ROOT not in text and str(Path.home()) not in text and str(Path.home()).replace("\\", "/") not in text
    assert socket.gethostname() not in text
    assert not re.search(r'"[A-Za-z]:[\\/]|"/(home|Users|usr|opt|tmp)/', text), "an absolute path is in the response"


def test_the_endpoint_gives_the_six_static_groups_from_skellytracker_and_nothing_private(faked_probes):
    realtime = [{"pipeline_id": "live", "mode": "realtime", "requested_provider": None, "models": [
        {"node": "wholebody", "key": "rtmw", "version": "1", "size": "m", "precision": "fp16", "execution_provider": "gpu-ep",
         "device": [DEVICE, "gpu:0000:0000:9"], "sidecar_sha256": "abc"}]},
        {"pipeline_id": "legacy", "mode": "realtime", "requested_provider": "gpu-ep", "models": [
            {"node": "person", "key": "yolox", "engine": "legacy", "file": "yolox.onnx", "execution_provider": "gpu-ep", "device": None}]}]
    posthoc = {"posthoc-run": _mocap("posthoc-run", [{"pipeline_id": "recording-graph", "mode": "posthoc", "requested_provider": None,
               "models": [{"node": "wholebody", "key": "rtmw", "execution_provider": "cpu", "device": None}]}]),
               "ended": _mocap("ended", [{"pipeline_id": "recording-graph", "mode": "posthoc", "models": []}], alive=False)}
    client, patcher = _client(_app_state(realtime, posthoc))
    try:
        first = client.get("/freemocap/onnx/system_information")
        second = client.get("/freemocap/onnx/system_information")
    finally:
        patcher.stop()
    assert first.status_code == 200, first.text
    body = first.json()
    assert set(body) == {"host", "gpus", "runtime", "execution_providers", "runs"}
    assert body["host"]["cpu_logical_cores"] == 16 and body["host"]["os_build"] == "26300" and body["host"]["is_vm"] is None
    assert [(gpu["device_key"], gpu["name"], gpu["compute_capability"]) for gpu in body["gpus"]] == [
        (DEVICE, "Some NVIDIA GPU", "8.6"), (None, "Display adapter", None)]
    runtime = body["runtime"]
    assert (runtime["skellytracker_version"], runtime["skellytracker_commit"], runtime["driver_supported_cuda_version"],
            runtime["python_build"]) == ("2.0.0", "0a50c719", "13.3", "main, Oct 26 2026")
    # The loaded libraries are read again on each request: they change once a session loads its EP.
    assert runtime["loaded_libraries"] == []
    assert second.json()["runtime"]["loaded_libraries"] == [{"name": "cudnn", "version": "9.1", "source": "module:cudnn64_9"}]
    providers = body["execution_providers"]
    assert [(row["key"], row["state"], row["usable"], row["install_hint"]) for row in providers["providers"]] == [
        ("gpu-ep", "ready", True, None), ("pack-ep", "not_installed", False, "Run `skellytracker-eps install pack-ep`.")]
    assert providers["providers"][0]["devices"] == [{"key": DEVICE, "name": "Some NVIDIA GPU", "vram_total_bytes": 8 * 2**30}]
    recommendation = providers["recommendation"]
    assert (recommendation["chosen"]["ep_key"], recommendation["chosen"]["device_key"], recommendation["precision"]) == ("gpu-ep", DEVICE, "fp16")
    assert recommendation["skipped"][0]["reason"] == "the pack is not installed"
    assert [offer["ep_key"] for offer in recommendation["offers"]] == ["pack-ep"], "an offer with no note is not shown"
    assert providers["core_matches_pin"] is False and providers["warnings"] == ["onnxruntime 1.30 is installed."]
    runs = {(run["mode"], run["pipeline_id"]): run for run in body["runs"]}
    assert set(runs) == {("realtime", "live"), ("realtime", "legacy"), ("posthoc", "posthoc-run")}
    model = runs["realtime", "live"]["models"][0]
    assert (model["key"], model["size"], model["precision"], model["device"]) == ("rtmw", "m", "fp16", [DEVICE, "gpu:0000:0000:9"])
    assert model["device_names"] == ["Some NVIDIA GPU", None]
    assert runs["realtime", "legacy"]["models"][0]["engine"] == "legacy" and runs["realtime", "legacy"]["models"][0]["device_names"] == []
    assert runs["posthoc", "posthoc-run"]["models"][0]["execution_provider"] == "cpu"
    text = first.text
    _assert_private(text)
    assert "GPU-secret-uuid" not in text and "argv" not in text and "store_root" not in text


def test_the_endpoint_on_this_machine_has_no_absolute_path_or_hostname():
    client, patcher = _client(_app_state([]))
    try:
        response = client.get("/freemocap/onnx/system_information")
    finally:
        patcher.stop()
    assert response.status_code == 200, response.text
    assert response.json()["host"]["memory_total_bytes"] > 0
    _assert_private(response.text)
    assert st_eps.status().store_root not in response.text


def _sample(cpu: float | None = 0.25) -> LiveSample:
    return LiveSample(perf_counter_ns=123, memory_used_bytes=10, memory_available_bytes=20, cpu_utilization=cpu,
                      processes=(ProcessSample(pid=7, cpu_utilization=0.1, rss_bytes=300, vram_used_bytes=400),),
                      gpus=(GpuSample(key=NVIDIA.key, utilization=0.5, vram_used_bytes=None, vram_free_bytes=600,
                                      processes=(GpuProcessSample(pid=7, vram_used_bytes=None),)),
                            GpuSample(key="unknown-bus", utilization=None)))


def test_a_live_sample_is_joined_to_device_keys_and_keeps_missing_values_none():
    load = live_load_of(_sample(), {NVIDIA.key: (DEVICE, NVIDIA.name)}, pid=7)
    assert (load.cpu_utilization, load.process_cpu_utilization, load.process_rss_bytes, load.process_vram_used_bytes) == (0.25, 0.1, 300, 400)
    known, unknown = load.gpus
    assert (known.device_key, known.name, known.utilization, known.vram_used_bytes, known.vram_free_bytes,
            known.process_vram_used_bytes) == (DEVICE, NVIDIA.name, 0.5, None, 600, None)
    assert (unknown.device_key, unknown.utilization) == (None, None)
    first = live_load_of(_sample(cpu=None), {}, pid=99)
    assert (first.cpu_utilization, first.process_cpu_utilization, first.process_rss_bytes) == (None, None, None)


def _wait_for(predicate, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.005)


def test_the_sampler_runs_only_while_a_connection_is_interested_and_its_sample_rides_every_message():
    calls = []
    load = LiveLoad(sample_perf_counter_ns=5, interval_s=0.01, memory_used_bytes=1, memory_available_bytes=2)
    sampler = LiveLoadSampler(interval_s=0.01, make_sample=lambda: lambda: calls.append(1) or load)
    relay = PipelineTimingRelay(interval_s=0.0, live_load=sampler)
    posthoc = {"run": _mocap("run", [])}
    posthoc["run"].timing_records, posthoc["run"].recording_info = None, SimpleNamespace(recording_name="session_1")
    assert relay.latest({}, posthoc) == (0, ()) and not sampler.running
    time.sleep(0.05)
    assert not calls, "no sample without an interested connection"
    first, second = object(), object()
    relay.add_interest(first)
    relay.add_interest(second)
    assert sampler.running
    _wait_for(lambda: sampler.latest is not None)
    (message,) = map(cbor2.loads, relay.latest({}, posthoc)[1])
    assert message["live_load"] == {"sample_perf_counter_ns": 5, "interval_s": 0.01, "memory_used_bytes": 1,
                                    "memory_available_bytes": 2, "gpus": [], "sample_errors": []}
    relay.remove_interest(first)
    assert sampler.running, "another connection is still interested"
    relay.remove_interest(second)
    assert not sampler.running and sampler.latest is None
    time.sleep(0.05)
    stopped = len(calls)
    time.sleep(0.1)
    assert len(calls) == stopped, "the thread stops with the last interest"


def test_a_message_before_the_first_sample_has_no_live_load_and_a_failed_sample_keeps_the_thread():
    assert "live_load" not in cbor2.loads(encode_message(PipelineTimingStreamMessage(envelope=MessageEnvelope(sequence=1))))
    attempts = []

    def sample():
        attempts.append(1)
        raise OSError("no counters")
    sampler = LiveLoadSampler(interval_s=0.01, make_sample=lambda: sample)
    sampler.start()
    try:
        _wait_for(lambda: len(attempts) >= 3)
        assert sampler.running and sampler.latest is None
    finally:
        sampler.stop()
