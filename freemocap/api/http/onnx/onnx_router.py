import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

onnx_router = APIRouter(prefix="/onnx", tags=["ONNX"])


class ExecutionProviderDevice(BaseModel):
    key: str
    name: str | None
    vram_total_bytes: int | None


class ExecutionProviderCheck(BaseModel):
    """skellytracker's `DeviceCheck` of an EP on one GPU of this host: the GPU is offered only when `usable`."""
    device_key: str
    certified: bool
    local_result: str | None  # "passed" or "failed": the last quick check here; None with none
    usable: bool
    local_cause: str | None  # "unclean-exits": the failure is two unclean exits in a row, not a quick check; else None


class ExecutionProviderOption(BaseModel):
    key: str
    label: str
    description: str
    usable: bool
    install_hint: str | None
    uses_gpu: bool
    devices: list[ExecutionProviderDevice]
    checks: list[ExecutionProviderCheck]


class ExecutionProviderOffer(BaseModel):
    """An offer of skellytracker's Auto recommendation for this host, as `InstallOffer` gives it."""
    kind: str
    ep_key: str | None
    download_bytes: int | None
    disk_bytes: int | None
    licence_url: str | None
    note: str


class AvailableExecutionProvidersResponse(BaseModel):
    providers: list[ExecutionProviderOption]
    detector_takes_execution_provider: dict[str, bool]
    auto_offers: list[ExecutionProviderOffer]


@onnx_router.get("/execution_providers")
def get_available_execution_providers() -> AvailableExecutionProvidersResponse:
    """Each EP of this host as skellytracker gives it, in its order, whether each detector takes an EP, and the offers
    of skellytracker's Auto recommendation (install a pack, update a driver).

    The run checks its EP again when it starts."""
    try:
        from freemocap.core.tracking.execution_providers import execution_provider_status
        from freemocap.core.tracking.pipeline_runs import PIPELINE_KEYS, detector_takes_execution_provider
        status = execution_provider_status()
        return AvailableExecutionProvidersResponse(
            providers=[ExecutionProviderOption(
                key=row.key, label=row.label, description=row.description, usable=row.usable,
                install_hint=row.install_hint, uses_gpu=row.uses_gpu,
                devices=[ExecutionProviderDevice(key=device.device_key, name=device.name, vram_total_bytes=device.vram_total_bytes)
                         for device in row.devices],
                checks=[ExecutionProviderCheck(device_key=check.device_key, certified=check.certified,
                                               local_result=check.local_result, usable=check.usable,
                                               local_cause=check.local_cause)
                        for check in row.checks]) for row in status.eps],
            detector_takes_execution_provider={detector: detector_takes_execution_provider(detector) for detector in PIPELINE_KEYS},
            auto_offers=[ExecutionProviderOffer(kind=offer.kind, ep_key=offer.ep_key, download_bytes=offer.download_bytes,
                disk_bytes=offer.disk_bytes, licence_url=offer.licence_url, note=offer.note)
                for offer in status.performance.offers])
    except Exception as e:
        logger.exception(f"Error listing ONNX execution providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ExecutionProviderSuggestion(BaseModel):
    saved: str
    suggested: str | None


@onnx_router.get("/execution_providers/suggestion")
def get_execution_provider_suggestion(saved: str) -> ExecutionProviderSuggestion:
    """The EP key that replaces a key saved by FreeMoCap before skellytracker 2, as skellytracker suggests it on this
    host; `suggested` None means Auto."""
    from freemocap.core.tracking.execution_providers import suggested_execution_provider
    return ExecutionProviderSuggestion(saved=saved, suggested=suggested_execution_provider(saved))


@onnx_router.get("/session_providers")
def get_session_providers() -> list[dict]:
    """For each live or posthoc run, the EP the user selected and each model node as skellytracker reports it:
    key, version, sidecar_sha256, size, precision, the applied `execution_provider` and `device`. Empty models
    means the run has not started yet, or runs no model."""
    from freemocap.app.freemocap_application import get_freemocap_app
    return get_freemocap_app().inference_service.provider_status()


# - System information of the metrics window: an allow-list of skellytracker's fields, with no absolute path
#   (the EP store root, argv), no hostname and no GPU UUID. -
class SystemHost(BaseModel):
    os_name: str
    os_release: str
    os_version: str
    os_build: str | None
    arch: str
    cpu_name: str | None
    cpu_physical_cores: int | None
    cpu_logical_cores: int | None
    cpu_max_frequency_hz: int | None
    memory_total_bytes: int
    is_wsl: bool
    is_vm: bool | None
    hypervisor: str | None
    container_runtime: str | None
    probe_errors: list[str]


class SystemGpu(BaseModel):
    """`device_key` is None for a GPU with no PCI ids."""
    device_key: str | None
    name: str | None
    vendor: str
    driver_version: str | None
    vram_total_bytes: int | None
    is_integrated: bool | None
    compute_capability: str | None
    brand: str | None


class LoadedLibrary(BaseModel):
    name: str
    version: str | None
    source: str


class SystemRuntime(BaseModel):
    python_implementation: str
    python_version: str
    python_build: str
    python_compiler: str
    skellytracker_version: str
    skellytracker_commit: str | None
    ort_version: str | None
    ort_packages: list[str]
    ort_ep_names: list[str]
    mediapipe_version: str | None
    driver_supported_cuda_version: str | None
    loaded_libraries: list[LoadedLibrary]
    probe_errors: list[str]


class SystemEpRow(BaseModel):
    key: str
    label: str
    state: str
    usable: bool
    install_hint: str | None
    devices: list[ExecutionProviderDevice]


class SystemEpCandidate(BaseModel):
    ep_key: str
    device_key: str | None
    status: str
    reason: str | None


class SystemRecommendation(BaseModel):
    """skellytracker's performance recommendation for this host."""
    hardware_class: str
    chosen: SystemEpCandidate
    precision: str
    skipped: list[SystemEpCandidate]
    offers: list[ExecutionProviderOffer]


class SystemEpStatus(BaseModel):
    ort_version: str | None
    core_matches_pin: bool
    providers: list[SystemEpRow]
    recommendation: SystemRecommendation
    warnings: list[str]


class SystemRunModel(BaseModel):
    """One model node of a run as the run reports it; `device_names` follow `device` (one key or a list)."""
    node: str
    key: str | None
    version: str | None = None
    size: str | None = None
    precision: str | None = None
    engine: str | None = None
    execution_provider: str | None = None
    device: str | list[str] | None = None
    device_names: list[str | None] = []


class SystemRun(BaseModel):
    """A live run: `mode` and `pipeline_id` name it as its pipeline_timing messages do."""
    mode: str
    pipeline_id: str
    requested_provider: str | None
    models: list[SystemRunModel]


class SystemInformationResponse(BaseModel):
    host: SystemHost
    gpus: list[SystemGpu]
    runtime: SystemRuntime
    execution_providers: SystemEpStatus
    runs: list[SystemRun]


def _candidate(candidate) -> SystemEpCandidate:
    return SystemEpCandidate(ep_key=candidate.ep_key, device_key=candidate.device_key, status=str(candidate.status),
                             reason=candidate.reason)


def _run_models(models: list[dict], gpu_names: dict[str, str | None]) -> list[SystemRunModel]:
    result = []
    for model in models:
        device = model.get("device")
        keys = [] if device is None else [device] if isinstance(device, str) else list(device)
        result.append(SystemRunModel(
            node=str(model.get("node")), key=model.get("key"), version=model.get("version"), size=model.get("size"),
            precision=model.get("precision"), engine=model.get("engine"), execution_provider=model.get("execution_provider"),
            device=device, device_names=[gpu_names.get(key) for key in keys]))
    return result


def posthoc_run_status(pipelines: dict) -> list[dict]:
    """The `provider_status()` of each running posthoc mocap run's own inference service, named by the run's
    pipeline id (its inference client is named after its graph)."""
    from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline
    return [{**status, "pipeline_id": pipeline_id}
            for pipeline_id, pipeline in list(pipelines.items())
            if isinstance(pipeline, MocapPipeline) and pipeline.alive
            for service in list(pipeline.inference_services) for status in service.provider_status()]


def system_information(live_runs: list[dict]) -> SystemInformationResponse:
    """`live_runs` is `InferenceService.provider_status()` of each live run, with `mode` and `pipeline_id` as
    its timing messages name it."""
    from skellytracker.core.eps import status
    from skellytracker.core.system import gpu_device_keys, probe_environment, probe_host, probe_loaded_libraries, probe_runtime
    host, runtime, python, loaded, eps = probe_host(), probe_runtime(), probe_environment().python, probe_loaded_libraries(), status()
    device_keys = {gpu.key: device_key for device_key, gpu in gpu_device_keys(host)}
    gpus = [SystemGpu(device_key=device_keys.get(gpu.key), name=gpu.name, vendor=gpu.vendor, driver_version=gpu.driver_version,
                      vram_total_bytes=gpu.vram_total_bytes, is_integrated=gpu.is_integrated,
                      compute_capability=gpu.nvidia.compute_capability if gpu.nvidia else None,
                      brand=gpu.nvidia.brand if gpu.nvidia else None) for gpu in host.gpus]
    gpu_names = {gpu.device_key: gpu.name for gpu in gpus if gpu.device_key}
    libraries = [*loaded.libraries, *(loaded.nvidia.libraries if loaded.nvidia else ())]
    performance = eps.performance
    return SystemInformationResponse(
        host=SystemHost(
            os_name=host.os_name, os_release=host.os_release, os_version=host.os_version,
            os_build=None if host.os_build is None else str(host.os_build), arch=host.arch, cpu_name=host.cpu_name,
            cpu_physical_cores=host.cpu_physical_cores, cpu_logical_cores=host.cpu_logical_cores,
            cpu_max_frequency_hz=host.cpu_max_frequency_hz, memory_total_bytes=host.memory_total_bytes,
            is_wsl=host.virtualization.is_wsl, is_vm=host.virtualization.is_vm, hypervisor=host.virtualization.hypervisor,
            container_runtime=host.container.runtime if host.container else None, probe_errors=list(host.probe_errors)),
        gpus=gpus,
        runtime=SystemRuntime(
            python_implementation=python.implementation, python_version=python.version, python_build=python.build,
            python_compiler=python.compiler, skellytracker_version=runtime.skellytracker_version,
            skellytracker_commit=runtime.skellytracker_commit, ort_version=runtime.ort_version,
            ort_packages=list(runtime.ort_packages), ort_ep_names=list(runtime.ep_names),
            mediapipe_version=runtime.mediapipe_version,
            driver_supported_cuda_version=runtime.nvidia.driver_supported_cuda_version if runtime.nvidia else None,
            loaded_libraries=[LoadedLibrary(name=library.name, version=library.version, source=library.source) for library in libraries],
            probe_errors=[*runtime.probe_errors, *loaded.probe_errors]),
        execution_providers=SystemEpStatus(
            ort_version=eps.ort_version, core_matches_pin=eps.core_matches_pin,
            providers=[SystemEpRow(
                key=row.key, label=row.label, state=str(row.state), usable=row.usable, install_hint=row.install_hint,
                devices=[ExecutionProviderDevice(key=device.device_key, name=device.name, vram_total_bytes=device.vram_total_bytes)
                         for device in row.devices]) for row in eps.eps],
            recommendation=SystemRecommendation(
                hardware_class=performance.hardware_class, chosen=_candidate(performance.chosen), precision=performance.precision,
                skipped=[_candidate(candidate) for candidate in performance.skipped],
                # An offer with no note is not shown, as on the EP menu: no text is made up.
                offers=[ExecutionProviderOffer(kind=offer.kind, ep_key=offer.ep_key, download_bytes=offer.download_bytes,
                                               disk_bytes=offer.disk_bytes, licence_url=offer.licence_url, note=offer.note)
                        for offer in performance.offers if offer.note is not None]),
            warnings=list(eps.warnings)),
        runs=[SystemRun(mode=run["mode"], pipeline_id=run["pipeline_id"], requested_provider=run.get("requested_provider"),
                        models=_run_models(run.get("models", []), gpu_names)) for run in live_runs],
    )


@onnx_router.get("/system_information")
def get_system_information() -> SystemInformationResponse:
    """skellytracker's host, GPUs (with device keys), runtime and loaded libraries, EP status and performance
    recommendation, and the models of each live run (realtime, legacy and posthoc), for the metrics window.

    The probes cache themselves per process; the loaded libraries are read again on each request, in the backend
    process where the inference service runs as a thread, because they change once a session loads its EP."""
    from freemocap.app.freemocap_application import get_freemocap_app
    app = get_freemocap_app()
    return system_information(app.inference_service.provider_status() + posthoc_run_status(app.posthoc_pipeline_manager.pipelines))
