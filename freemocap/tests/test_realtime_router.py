"""Tests for realtime apply router zero-camera validation."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.camera_group.camera_group import CameraGroup

from freemocap.api.http.realtime.realtime_messages import REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE
from freemocap.api.http.realtime.realtime_router import realtime_router, RealtimePipelineCreateResponse
from freemocap.core.pipeline.realtime.realtime_camera_selection import (
    camera_ids_for_realtime_pipeline as _camera_ids_for_realtime_pipeline,
)
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig

_resolve_camera_ids = getattr(
    _camera_ids_for_realtime_pipeline,
    "__wrapped__",
    _camera_ids_for_realtime_pipeline,
)


@pytest.fixture
def realtime_client() -> TestClient:
    app = FastAPI()
    app.include_router(realtime_router, prefix="/freemocap")
    return TestClient(app)


def _mock_pipeline(*, pipeline_id: str = "pipe_1") -> MagicMock:
    pipeline = MagicMock()
    pipeline.id = pipeline_id
    pipeline.shutdown = MagicMock()
    return pipeline


def _mock_app(*, camera_keys: list[str] | None = None) -> MagicMock:
    app = MagicMock()
    keys = camera_keys or ["cam_a"]
    camera_group = cast(
        CameraGroup,
        SimpleNamespace(id="group_a", configs={key: object() for key in keys}),
    )
    app.camera_group_manager.create_or_update_camera_group = AsyncMock(return_value=camera_group)
    app.realtime_pipeline_manager.create_pipeline = MagicMock()
    return app


class TestRealtimeApplyRouter:
    def test_zero_camera_ids_returns_422(self, realtime_client: TestClient) -> None:
        mock_app = _mock_app(camera_keys=["cam_a", "cam_b"])
        body = {
            "cameraConfigs": {"cam_a": {"name": "A"}},
            "realtimeCameraIds": [],
            "realtimeConfig": {},
        }

        with patch("freemocap.api.http.realtime.realtime_router.get_freemocap_app", return_value=mock_app):
            with patch(
                "freemocap.api.http.realtime.realtime_router.camera_ids_for_realtime_pipeline",
                return_value=[],
            ):
                response = realtime_client.post("/freemocap/realtime/apply", json=body)

        assert response.status_code == 422
        assert response.json()["detail"] == REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE
        mock_app.realtime_pipeline_manager.create_pipeline.assert_not_called()

    def test_zero_camera_ids_leaves_existing_pipeline_unchanged(
        self, realtime_client: TestClient
    ) -> None:
        existing = _mock_pipeline()
        mock_app = _mock_app(camera_keys=["cam_a"])
        mock_app.realtime_pipeline_manager.pipelines = {"pipe_1": existing}

        body = {
            "cameraConfigs": {"cam_a": {"name": "A"}},
            "realtimeCameraIds": [],
            "realtimeConfig": {},
        }

        with patch("freemocap.api.http.realtime.realtime_router.get_freemocap_app", return_value=mock_app):
            with patch(
                "freemocap.api.http.realtime.realtime_router.camera_ids_for_realtime_pipeline",
                return_value=[],
            ):
                response = realtime_client.post("/freemocap/realtime/apply", json=body)

        assert response.status_code == 422
        assert mock_app.realtime_pipeline_manager.pipelines["pipe_1"] is existing
        existing.shutdown.assert_not_called()
        mock_app.realtime_pipeline_manager.create_pipeline.assert_not_called()

    def test_unknown_realtime_camera_ids_returns_422_without_mocked_resolver(
        self, realtime_client: TestClient
    ) -> None:
        mock_app = _mock_app(camera_keys=["cam_a"])
        body = {
            "cameraConfigs": {"cam_a": {"name": "A"}},
            "realtimeCameraIds": ["cam_missing"],
            "realtimeConfig": {},
        }

        with patch("freemocap.api.http.realtime.realtime_router.get_freemocap_app", return_value=mock_app):
            with patch(
                "freemocap.api.http.realtime.realtime_router.camera_ids_for_realtime_pipeline",
                _resolve_camera_ids,
            ):
                response = realtime_client.post("/freemocap/realtime/apply", json=body)

        assert response.status_code == 422
        assert response.json()["detail"] == REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE
        mock_app.realtime_pipeline_manager.create_pipeline.assert_not_called()

    def test_successful_apply_response_contract(self, realtime_client: TestClient) -> None:
        mock_app = _mock_app()
        pipeline = MagicMock()
        pipeline.id = "abc123"
        pipeline.config = RealtimePipelineConfig()
        pipeline.camera_group = SimpleNamespace(id="group_a")
        mock_app.realtime_pipeline_manager.create_pipeline.return_value = pipeline

        body = {
            "cameraConfigs": {"cam_a": {"name": "A"}},
            "realtimeCameraIds": ["cam_a"],
            "realtimeConfig": {},
        }

        with patch("freemocap.api.http.realtime.realtime_router.get_freemocap_app", return_value=mock_app):
            with patch(
                "freemocap.api.http.realtime.realtime_router.camera_ids_for_realtime_pipeline",
                return_value=["cam_a"],
            ):
                with patch(
                    "freemocap.api.http.realtime.realtime_router.RealtimePipelineCreateResponse.from_pipeline",
                    return_value=RealtimePipelineCreateResponse(
                        pipeline_id="abc123",
                        execution_provider=None,
                    ),
                ):
                    response = realtime_client.post("/freemocap/realtime/apply", json=body)

        assert response.status_code == 200
        payload = response.json()
        assert payload["pipeline_id"] == "abc123"
        assert "execution_provider" in payload
        assert "camera_group_id" not in payload
        assert "active_execution_provider" not in payload
        assert "requested_execution_provider" not in payload
