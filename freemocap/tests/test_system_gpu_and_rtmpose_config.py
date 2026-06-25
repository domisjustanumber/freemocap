"""Tests for GET /freemocap/system/gpu and RTMPose session config wiring."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.system.system_router import system_router
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_error import RealtimePipelineErrorMessage
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node import (
    RealtimeSessionConfigError,
    _build_session,
)
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node_config import (
    RealtimeSkeletonInferenceNodeConfig,
)
from freemocap.system.gpu_capabilities_cache import GpuCapabilitiesSnapshot
from skellytracker.trackers.rtmpose_tracker.rtmpose_detector import RTMPoseDetectorConfig
from skellytracker.utilities.gpu_utils import resolve_provider
from skellytracker.utilities.gpu_utils.ort_session_utils import OnnxExecutionProviderStartupError


@pytest.fixture
def system_client() -> TestClient:
    app = FastAPI()
    app.include_router(system_router, prefix="/freemocap")
    return TestClient(app)


class TestSystemGpuEndpoint:
    def test_gpu_endpoint_response_shape(self, system_client: TestClient) -> None:
        snapshot = GpuCapabilitiesSnapshot(
            gpus=[
                {
                    "id": "gpu-0",
                    "name": "Test GPU",
                    "vendor": "nvidia",
                    "vram_bytes": 8 * 1024**3,
                    "online": True,
                    "driver_version": "550.00",
                    "cuda_driver_max": "12.4",
                    "cuda_required_min": "12.0",
                    "cuda_meets_nvidia_eps": True,
                },
            ],
            execution_providers={
                "providers": [
                    {
                        "id": "cuda",
                        "display_name": "CUDA",
                        "available": True,
                        "recommended": True,
                        "optimal": True,
                        "install_recommended": False,
                        "driver_cuda_compatible": True,
                        "capabilities": {
                            "fixed_batch_sizes": False,
                            "downcasting": False,
                            "quantization": False,
                        },
                        "doc_url": "https://example.com",
                    },
                ],
                "recommended_provider_id": "cuda",
                "optimal_provider_id": "cuda",
                "install_recommended_provider_id": None,
            },
            detection_models=[{"id": "yolox-m", "display_name": "YOLOX-M"}],
            pose_models=[
                {
                    "id": "rtmw-x-l_256x192",
                    "display_name": "RTMW-X-L 256x192",
                    "requires_detector": True,
                },
            ],
            mode_defaults={
                "balanced": {
                    "detector_model": "yolox-m",
                    "pose_model": "rtmw-x-l_256x192",
                },
            },
        )

        with patch(
            "freemocap.api.http.system.system_router.build_gpu_capabilities_snapshot",
            return_value=snapshot,
        ):
            response = system_client.get("/freemocap/system/gpu")

        assert response.status_code == 200
        body = response.json()
        assert body["gpus"][0]["name"] == "Test GPU"
        assert body["execution_providers"]["recommended_provider_id"] == "cuda"
        assert body["detection_models"][0]["id"] == "yolox-m"
        assert body["pose_models"][0]["id"] == "rtmw-x-l_256x192"
        assert "balanced" in body["mode_defaults"]


class TestBuildSessionConfig:
    def test_build_session_passes_model_overrides_and_auto_provider(self) -> None:
        pipeline_config = RealtimePipelineConfig(
            camera_node_config=CameraNodeConfig(
                skeleton_detector_config=RTMPoseDetectorConfig(
                    mode="balanced",
                    detector_model="yolox-tiny",
                    pose_model="rtmw-l-m_256x192",
                ),
            ),
            skeleton_inference_node_config=RealtimeSkeletonInferenceNodeConfig(
                execution_provider=None,
            ),
        )

        captured: list = []

        def fake_create(config):
            captured.append(config)
            return MagicMock(active_provider="cuda")

        with patch(
            "freemocap.core.pipeline.realtime.realtime_skeleton_inference_node.RTMPoseSession.create",
            side_effect=fake_create,
        ):
            session = _build_session(pipeline_config)

        assert session is not None
        assert len(captured) == 1
        session_config = captured[0]
        assert session_config.mode == "balanced"
        assert session_config.detector_model == "yolox-tiny"
        assert session_config.pose_model == "rtmw-l-m_256x192"
        assert session_config.execution_provider is None
        assert not hasattr(session_config, "on_provider_missing")

    def test_build_session_raises_for_non_rtmpose_config(self) -> None:
        pipeline_config = RealtimePipelineConfig()
        pipeline_config.camera_node_config.skeleton_detector_config = MagicMock()

        with pytest.raises(RealtimeSessionConfigError):
            _build_session(pipeline_config)

    def test_build_session_propagates_ep_startup_error(self) -> None:
        pipeline_config = RealtimePipelineConfig(
            skeleton_inference_node_config=RealtimeSkeletonInferenceNodeConfig(
                execution_provider="trt",
            ),
        )
        with patch(
            "freemocap.core.pipeline.realtime.realtime_skeleton_inference_node.RTMPoseSession.create",
            side_effect=OnnxExecutionProviderStartupError(
                "TRT unavailable",
                requested_provider="trt",
                expected_ort_provider="TensorrtExecutionProvider",
            ),
        ):
            with pytest.raises(OnnxExecutionProviderStartupError):
                _build_session(pipeline_config)


class TestExecutionProviderResolution:
    def test_auto_execution_provider_resolves_for_default_config(self) -> None:
        cfg = RealtimePipelineConfig()
        resolved = resolve_provider(
            requested=cfg.skeleton_inference_node_config.execution_provider,
        )
        assert resolved in {"trt-trx", "trt", "cuda", "cpu", "directml", "coreml"}

    def test_explicit_missing_provider_raises(self) -> None:
        with pytest.raises(OnnxExecutionProviderStartupError):
            resolve_provider(
                requested="trt",
                available_ort={"CUDAExecutionProvider", "CPUExecutionProvider"},
            )


class TestRealtimePipelineErrorMessage:
    def test_from_ep_startup_error_maps_fields(self) -> None:
        error = OnnxExecutionProviderStartupError(
            "CUDA session failed",
            model_label="rtmpose",
            requested_provider="cuda",
            expected_ort_provider="CUDAExecutionProvider",
            active_ort_providers=["CPUExecutionProvider"],
            device_id=0,
            install_hint="install gpu extra",
        )
        message = RealtimePipelineErrorMessage.from_ep_startup_error(
            pipeline_id="abc123",
            error=error,
            detector_model="yolox-m",
            pose_model="rtmw-x-l_256x192",
            batch_size=4,
        )
        assert message.pipeline_id == "abc123"
        assert message.requested_execution_provider == "cuda"
        assert message.model_label == "rtmpose"
        assert message.detector_model == "yolox-m"
        assert message.batch_size == 4
        assert message.message_type == "realtime_pipeline_error"
