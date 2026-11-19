"""Client restoration reads server configuration without updating the pipeline."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.realtime.realtime_router import realtime_router
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline


def test_running_config_is_read_only_and_preserves_explicit_selection() -> None:
    config = RealtimePipelineConfig()
    config.aggregator_config.calibration_toml_path = 'C:/selected.toml'
    pipeline = SimpleNamespace(alive=True, config=config, update_config=Mock())
    pipelines = {'live': pipeline}
    application = SimpleNamespace(realtime_pipeline_manager=SimpleNamespace(pipelines=pipelines))
    app = FastAPI()
    app.include_router(realtime_router)
    with patch('freemocap.api.http.realtime.realtime_router.get_freemocap_app', return_value=application):
        with TestClient(app) as client:
            for _ in range(2):
                response = client.get('/realtime/config')
                assert response.status_code == 200
                assert response.json() == config.model_dump(mode='json')
            pipeline.update_config.assert_not_called()
            pipelines.clear()
            assert client.get('/realtime/config').json() is None


def test_temporal_updates_validate_values_and_report_worker_applied_settings() -> None:
    original = RealtimePipelineConfig()
    pipeline = Mock(spec=RealtimePipeline, alive=True, config=original,
        applied_filter_config=original.aggregator_config.realtime_filter_config)
    pipeline.update_config = Mock(side_effect=lambda config: setattr(pipeline, 'config', config))
    pipelines = {'live': pipeline}
    application = SimpleNamespace(realtime_pipeline_manager=SimpleNamespace(pipelines=pipelines))
    app = FastAPI()
    app.include_router(realtime_router)
    updated = RealtimeFilterConfig(gap_duration_s=0.5, prediction_duration_s=0.12).model_dump(mode='json')
    with patch('freemocap.api.http.realtime.realtime_router.get_freemocap_app', return_value=application):
        with TestClient(app) as client:
            initial = client.get('/realtime/filter-config').json()
            assert initial['defaults'] == RealtimeFilterConfig().model_dump(mode='json')
            response = client.put('/realtime/filter-config', json=updated)
            assert response.status_code == 200
            assert response.json()['requested'] == updated
            assert response.json()['applied'] == initial['applied']  # command is not an acknowledgement
            assert pipeline.config.camera_node_config == original.camera_node_config
            assert pipeline.config.aggregator_config.calibration_toml_path == original.aggregator_config.calibration_toml_path
            assert original.aggregator_config.realtime_filter_config.gap_duration_s == 0.3
            pipeline.applied_filter_config = pipeline.config.aggregator_config.realtime_filter_config
            assert client.get('/realtime/filter-config').json()['applied'] == updated
            assert client.put('/realtime/filter-config', json={**updated, 'gap_duration_s': -0.1}).status_code == 422
            assert client.put('/realtime/filter-config', json={**updated, 'max_prediction_frames': 15}).status_code == 422
            pipeline.update_config.assert_called_once()
            pipelines.clear()
            assert client.get('/realtime/filter-config').json()['applied'] is None
            assert client.put('/realtime/filter-config', json=updated).status_code == 409


def test_removed_filter_settings_are_rejected_at_request_boundary() -> None:
    app = FastAPI()
    app.include_router(realtime_router)
    with TestClient(app) as client:
        response = client.post('/realtime/apply', json={'realtimeConfig': {
            'aggregator_config': {'filter_enabled': True},
        }})
        assert response.status_code == 422
        response = client.post('/realtime/apply', json={'realtimeConfig': {
            'camera_node_config': {'enable_keypoint_filter': True},
        }})
        assert response.status_code == 422


def test_preprocess_round_trips_through_the_contract_and_an_unknown_value_is_rejected() -> None:
    import json
    from pathlib import Path
    import pytest
    from pydantic import ValidationError
    from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node_config import RealtimeSkeletonInferenceNodeConfig
    contract = json.loads((Path(__file__).parents[3] / 'packages/freemocap-client/contracts/openapi.json').read_text(encoding='utf-8'))
    published = contract['components']['schemas']['RealtimeSkeletonInferenceNodeConfig']['properties']['preprocess']
    assert published == RealtimeSkeletonInferenceNodeConfig.model_json_schema()['properties']['preprocess']
    assert RealtimeSkeletonInferenceNodeConfig().preprocess == 'auto'
    for value in ('auto', 'cpu', 'gpu'):
        config = RealtimeSkeletonInferenceNodeConfig.model_validate({'preprocess': value})
        assert RealtimeSkeletonInferenceNodeConfig.model_validate(config.model_dump(mode='json')).preprocess == value
    with pytest.raises(ValidationError):
        RealtimeSkeletonInferenceNodeConfig.model_validate({'preprocess': 'GPU'})
    app = FastAPI()
    app.include_router(realtime_router)
    with TestClient(app) as client:
        response = client.post('/realtime/apply', json={'realtimeConfig': {'skeleton_inference_node_config': {'preprocess': 'npu'}}})
        assert response.status_code == 422
