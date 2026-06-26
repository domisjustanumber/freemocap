"""Tests for POST /realtime/apply router behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.realtime.realtime_messages import REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE
from freemocap.api.http.realtime.realtime_router import realtime_router


def _camera_group(config_ids: list[str]) -> MagicMock:
    group = MagicMock()
    group.id = "group_1"
    group.configs = {cid: object() for cid in config_ids}
    return group


@pytest.fixture
def test_client() -> TestClient:
    app = FastAPI()
    app.include_router(realtime_router, prefix="/freemocap")
    return TestClient(app)


class TestRealtimeApplyRouter:
    def test_zero_camera_ids_returns_422(self, test_client: TestClient) -> None:
        mock_app = MagicMock()
        group = _camera_group(["cam_a"])
        mock_app.camera_group_manager.create_or_update_camera_group = AsyncMock(return_value=group)
        mock_app.realtime_pipeline_manager.create_pipeline = MagicMock()

        with patch(
            "freemocap.api.http.realtime.realtime_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post(
                "/freemocap/realtime/apply",
                json={
                    "cameraConfigs": {"cam_a": {"name": "Camera A"}},
                    "realtimeCameraIds": [],
                    "realtimeConfig": {},
                },
            )

        assert response.status_code == 422
        assert response.json()["detail"] == REALTIME_AT_LEAST_ONE_CAMERA_MESSAGE
        mock_app.realtime_pipeline_manager.create_pipeline.assert_not_called()

    def test_successful_apply_response_contract(self, test_client: TestClient) -> None:
        mock_app = MagicMock()
        group = _camera_group(["cam_a"])
        mock_app.camera_group_manager.create_or_update_camera_group = AsyncMock(return_value=group)
        pipeline = MagicMock()
        pipeline.id = "abc123"
        pipeline.config = MagicMock()
        pipeline.config.skeleton_inference_node_config.execution_provider = "cuda"
        mock_app.realtime_pipeline_manager.create_pipeline = MagicMock(return_value=pipeline)

        with patch(
            "freemocap.api.http.realtime.realtime_router.get_freemocap_app",
            return_value=mock_app,
        ):
            response = test_client.post(
                "/freemocap/realtime/apply",
                json={
                    "cameraConfigs": {"cam_a": {"name": "Camera A"}},
                    "realtimeCameraIds": ["cam_a"],
                    "realtimeConfig": {},
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["pipeline_id"] == "abc123"
        assert body["execution_provider"] == "cuda"
        assert "camera_group_id" not in body
        assert "active_execution_provider" not in body
        assert "requested_execution_provider" not in body
