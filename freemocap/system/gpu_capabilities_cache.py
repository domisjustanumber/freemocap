"""Cached GPU / execution-provider introspection from skellytracker."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import skellytracker.utilities.gpu_utils as gpu_utils
from skellytracker.trackers.rtmpose_tracker.rtmpose_session import WHOLEBODY_MODE_CONFIG
from skellytracker.utilities.gpu_utils import (
    ExecutionProviderInfo,
    ExecutionProvidersInfo,
    GpuInfo,
    ModelCatalogEntry,
    PoseModelInfo,
)

logger = logging.getLogger(__name__)

# Canonical UI labels — TensorRT RTX (`trt-trx`) is distinct from legacy TensorRT (`trt`).
_EP_DISPLAY_NAMES: dict[str, str] = {
    "trt-trx": "TensorRT RTX",
    "trt": "TensorRT",
    "cuda": "CUDA",
    "directml": "DirectML",
    "coreml": "CoreML",
    "cpu": "CPU",
}


def _cuda_version_to_str(version: tuple[int, int] | None) -> str | None:
    if version is None:
        return None
    return f"{version[0]}.{version[1]}"


def _serialize_gpu(g: GpuInfo) -> dict[str, Any]:
    return {
        "id": g.id,
        "name": g.name,
        "vendor": g.vendor,
        "vram_bytes": g.vram_bytes,
        "online": g.online,
        "driver_version": g.driver_version,
        "cuda_driver_max": _cuda_version_to_str(g.cuda_driver_max),
        "cuda_required_min": _cuda_version_to_str(g.cuda_required_min),
        "cuda_meets_nvidia_eps": g.cuda_meets_nvidia_eps,
    }


def _serialize_ep(ep: ExecutionProviderInfo) -> dict[str, Any]:
    return {
        "id": ep.id,
        "display_name": _EP_DISPLAY_NAMES.get(ep.id, ep.display_name),
        "available": ep.available,
        "recommended": ep.recommended,
        "optimal": ep.optimal,
        "install_recommended": ep.install_recommended,
        "driver_cuda_compatible": ep.driver_cuda_compatible,
        "capabilities": {
            "fixed_batch_sizes": ep.capabilities.fixed_batch_sizes,
            "downcasting": ep.capabilities.downcasting,
            "quantization": ep.capabilities.quantization,
        },
        "doc_url": ep.doc_url,
    }


def _serialize_execution_providers(info: ExecutionProvidersInfo) -> dict[str, Any]:
    return {
        "providers": [_serialize_ep(ep) for ep in info.providers],
        "recommended_provider_id": info.recommended_provider_id,
        "optimal_provider_id": info.optimal_provider_id,
        "install_recommended_provider_id": info.install_recommended_provider_id,
    }


def _serialize_detection_model(m: ModelCatalogEntry) -> dict[str, Any]:
    return {
        "id": m.id,
        "display_name": m.display_name,
    }


def _serialize_pose_model(m: PoseModelInfo) -> dict[str, Any]:
    return {
        "id": m.id,
        "display_name": m.display_name,
        "requires_detector": m.requires_detector,
    }


def _serialize_mode_defaults() -> dict[str, dict[str, str]]:
    defaults: dict[str, dict[str, str]] = {}
    for mode, (det_key, _, pose_key, _) in WHOLEBODY_MODE_CONFIG.items():
        defaults[mode] = {
            "detector_model": det_key,
            "pose_model": pose_key,
        }
    return defaults


@dataclass
class GpuCapabilitiesSnapshot:
    """Serializable GPU capabilities for API responses."""

    gpus: list[dict[str, Any]]
    execution_providers: dict[str, Any]
    detection_models: list[dict[str, Any]]
    pose_models: list[dict[str, Any]]
    mode_defaults: dict[str, dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gpus": self.gpus,
            "execution_providers": self.execution_providers,
            "detection_models": self.detection_models,
            "pose_models": self.pose_models,
            "mode_defaults": self.mode_defaults,
        }


_cached_execution_providers: ExecutionProvidersInfo | None = None


def warm_execution_provider_cache() -> None:
    """Probe ORT execution providers once at startup."""
    global _cached_execution_providers
    try:
        _cached_execution_providers = gpu_utils.list_execution_providers()
        logger.info(
            "Cached execution providers: recommended=%s optimal=%s",
            _cached_execution_providers.recommended_provider_id,
            _cached_execution_providers.optimal_provider_id,
        )
    except Exception:
        logger.exception("Failed to cache execution providers")
        _cached_execution_providers = None


def build_gpu_capabilities_snapshot() -> GpuCapabilitiesSnapshot:
    """Build a fresh snapshot (GPUs refreshed; EP list from startup cache)."""
    gpus = gpu_utils.list_installed_gpus()
    ep_info = _cached_execution_providers
    if ep_info is None:
        try:
            ep_info = gpu_utils.list_execution_providers()
        except Exception:
            logger.exception("Failed to list execution providers")
            ep_info = ExecutionProvidersInfo(
                providers=tuple(),
                recommended_provider_id=None,
                optimal_provider_id=None,
                install_recommended_provider_id=None,
            )

    detection_models = gpu_utils.list_detection_models()
    pose_models = [
        m for m in gpu_utils.list_pose_models() if m.id.startswith("rtmw-")
    ]

    return GpuCapabilitiesSnapshot(
        gpus=[_serialize_gpu(g) for g in gpus],
        execution_providers=_serialize_execution_providers(ep_info),
        detection_models=[_serialize_detection_model(m) for m in detection_models],
        pose_models=[_serialize_pose_model(m) for m in pose_models],
        mode_defaults=_serialize_mode_defaults(),
    )
