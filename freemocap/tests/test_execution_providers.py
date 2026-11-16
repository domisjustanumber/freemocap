"""Requested EP propagation with the skellytracker 2.0 EP keys, and the provider routes."""
import queue
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.pipeline.realtime import realtime_pipeline as live


@pytest.mark.parametrize('provider', [None, 'cpu', 'any-ep-key'])
def test_settings_keep_any_ep_key_for_skellytracker_to_check(provider):
    config = PosthocMocapPipelineConfig(executionProvider=provider)
    assert config.model_dump(by_alias=True)['executionProvider'] == provider
    assert live.RealtimePipelineConfig(skeleton_inference_node_config={'execution_provider': provider}).skeleton_inference_node_config.execution_provider == provider


def test_a_key_that_skellytracker_does_not_have_fails_the_run_start_with_its_message():
    from skellytracker.core.errors import EpRequestError
    from freemocap.core.tracking.pipeline_runs import start_detector_run
    with pytest.raises(EpRequestError, match="'any-ep-key' is not an EP key"):
        start_detector_run(detector_type='rtmpose', camera_ids=['0'], running_mode='live', execution_provider='any-ep-key')


@pytest.mark.parametrize('saved,expected', [
    ({'graphExecutionProvider': 'other-ep'}, 'other-ep'),
    ({'graph_execution_provider': 'other-ep'}, 'other-ep'),
    ({'graphExecutionProvider': 'auto'}, None),
    ({'executionProvider': 'cpu', 'graphExecutionProvider': 'other-ep'}, 'cpu'),
    ({'executionProvider': None, 'graphExecutionProvider': 'other-ep'}, None),
])
def test_a_saved_graph_provider_keeps_its_meaning_and_is_not_written_again(saved, expected):
    config = PosthocMocapPipelineConfig.model_validate(saved)
    assert config.execution_provider == expected
    written = set(config.model_dump(by_alias=True)) | set(config.model_dump())
    assert not {'graphExecutionProvider', 'graph_execution_provider'} & written


def test_provider_route_lists_the_key_and_label_of_each_usable_ep_in_skellytracker_order_without_loading_models():
    from freemocap.api.http.onnx.onnx_router import onnx_router
    from skellytracker.core import eps
    app = FastAPI()
    app.include_router(onnx_router, prefix='/freemocap')
    rows = (SimpleNamespace(key='other-ep', label='Other EP', state='ready'),
            SimpleNamespace(key='gpu-ep', label='GPU EP', state='not_installed'), SimpleNamespace(key='cpu', label='CPU', state='builtin'))
    with patch.object(eps, 'status', return_value=SimpleNamespace(eps=rows)), \
         patch('onnxruntime.InferenceSession') as construct:
        response = TestClient(app).get('/freemocap/onnx/execution_providers')
    assert response.status_code == 200
    assert response.json() == {'available': [{'key': 'other-ep', 'label': 'Other EP'}, {'key': 'cpu', 'label': 'CPU'}]}
    construct.assert_not_called()


@pytest.mark.parametrize('change', ['provider', 'model', 'filter'])
def test_live_changes_rebuild_only_affected_inference(change):
    pipeline = object.__new__(live.RealtimePipeline)
    pipeline.config = live.RealtimePipelineConfig()
    pipeline.config.camera_node_config.skeleton_tracking_enabled = True
    pipeline._calibration_update_pending = False
    pipeline.skeleton_inference_node = Mock(is_alive=True)
    original = pipeline.skeleton_inference_node
    pipeline.camera_group = Mock()
    pipeline.camera_group.id = 'cameras'
    pipeline.camera_nodes = {'camera': Mock()}
    pipeline.worker_registry = Mock()
    pipeline.inference_service = Mock()
    pipeline.ipc = Mock()
    pipeline.pubsub = Mock()
    updated = pipeline.config.model_copy(deep=True)
    if change == 'provider':
        updated.skeleton_inference_node_config.execution_provider = 'cpu'
    elif change == 'model':
        updated.camera_node_config.rtmpose_model_name = 'rtmw-l-m_256x192'
    else:
        updated.aggregator_config.realtime_filter_config = updated.aggregator_config.realtime_filter_config.model_copy(update={'gap_duration_s': .6})
    with patch.object(live.RealtimeSkeletonInferenceNode, 'create') as create:
        pipeline.update_config(updated)
    if change == 'filter':
        original.shutdown.assert_not_called()
        create.assert_not_called()
    else:
        original.shutdown.assert_called_once()
        create.assert_called_once()
        create.return_value.start.assert_called_once()
    pipeline.camera_group.close.assert_not_called()
    pipeline.inference_service.close.assert_not_called()


@pytest.mark.parametrize('provider', ['cpu', 'any-ep-key'])
def test_graph_receives_each_explicit_provider(provider):
    from freemocap.core.pipeline.dataflow.application_pipeline import resolve_tracking_provider
    assert resolve_tracking_provider(PosthocMocapPipelineConfig(executionProvider=provider)) == provider


def test_graph_auto_takes_the_skellytracker_recommendation_and_mediapipe_takes_no_ep():
    from freemocap.core.pipeline.dataflow.application_pipeline import resolve_tracking_provider
    from skellytracker.core import eps
    for chosen in ('gpu-ep', 'cpu'):
        with patch.object(eps, 'recommend', return_value=SimpleNamespace(chosen=SimpleNamespace(ep_key=chosen, device_key=None), options=())):
            assert resolve_tracking_provider(PosthocMocapPipelineConfig()) == chosen
    for saved in (None, 'any-ep-key'):  # the saved choice of the hidden EP setting
        assert resolve_tracking_provider(PosthocMocapPipelineConfig(detectorType='mediapipe', executionProvider=saved)) is None


def test_camera_node_startup_failure_closes_initialized_resources():
    import multiprocessing
    from multiprocessing.queues import Queue
    from freemocap.core.pipeline.realtime import camera_node as camera
    memory = Mock(spec=camera.CameraSharedMemoryRingBuffer)
    memory.valid = True
    board = Mock()
    ipc = Mock(spec=camera.PipelineIPC)
    ipc.should_continue = True
    frames = Mock(spec=Queue)
    frames.get.side_effect = RuntimeError('frame read failed')
    config = camera.CameraNodeConfig(charuco_tracking_enabled=True)
    with patch.object(camera.CameraSharedMemoryRingBuffer, 'recreate', return_value=memory), \
         patch.object(camera, 'create_charuco_detector', return_value=board):
        with pytest.raises(RuntimeError, match='frame read failed'):
            camera.CameraNode._run(camera_id='camera', config=config, ipc=ipc,
                camera_shm_dto=Mock(spec=camera.SharedMemoryRingBufferDTO),
                shutdown_self_flag=multiprocessing.Value('b', False),
                process_frame_number_sub=frames, pipeline_config_sub=Mock(spec=Queue, **{'get_nowait.side_effect': queue.Empty}),
                camera_output_pub=Mock(spec=Queue), timing_pub=Mock(spec=Queue))
    board.close.assert_called_once()
    memory.close.assert_called_once()
    ipc.shutdown_pipeline.assert_called_once()


def test_session_status_endpoint_reports_actual_values():
    from freemocap.api.http.onnx.onnx_router import onnx_router
    app = FastAPI()
    app.include_router(onnx_router, prefix='/freemocap')
    service = Mock()
    service.provider_status.return_value = [{'pipeline_id': 'live', 'mode': 'realtime', 'models': [
        {'model_name': 'rtmw-wholebody133@openmmlab-exporter', 'requested_provider': None, 'applied_providers': ('gpu-ep',)}]}]
    with patch('freemocap.app.freemocap_application.get_freemocap_app', return_value=SimpleNamespace(inference_service=service)):
        response = TestClient(app).get('/freemocap/onnx/session_providers')
    assert response.status_code == 200
    model = response.json()[0]['models'][0]
    assert model['requested_provider'] is None
    assert model['applied_providers'] == ['gpu-ep']
