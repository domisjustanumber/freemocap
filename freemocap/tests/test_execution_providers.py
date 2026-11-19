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


def test_provider_route_gives_each_ep_as_skellytracker_does_in_its_order_without_loading_models():
    from freemocap.api.http.onnx.onnx_router import onnx_router
    from skellytracker.core import eps
    app = FastAPI()
    app.include_router(onnx_router, prefix='/freemocap')
    device = SimpleNamespace(device_key='gpu:0', gpu_key='0000:01:00.0', name='Some GPU', vram_total_bytes=8 * 2**30)
    check = SimpleNamespace(device_key='gpu:0', name='Some GPU', certified=False, local_result='passed', usable=True)
    rows = (SimpleNamespace(key='gpu-ep', label='GPU EP', description='Runs on a GPU.', usable=True, install_hint=None,
                            uses_gpu=True, devices=(device,), checks=(check,)),
            SimpleNamespace(key='other-ep', label='Other EP', description='Needs a pack.', usable=False,
                            install_hint='Run `install other-ep`.', uses_gpu=True, devices=(), checks=()))
    offer = SimpleNamespace(kind='add-pack', ep_key='other-ep', pack_id='other-pack', download_bytes=100, disk_bytes=300,
                            licence_url='https://example.org/licence', note='Run `install other-ep`.')
    status = SimpleNamespace(eps=rows, performance=SimpleNamespace(offers=(offer,)))
    with patch.object(eps, 'status', return_value=status), \
         patch('onnxruntime.InferenceSession') as construct:
        response = TestClient(app).get('/freemocap/onnx/execution_providers')
    assert response.status_code == 200
    assert response.json() == {
        'providers': [
            {'key': 'gpu-ep', 'label': 'GPU EP', 'description': 'Runs on a GPU.', 'usable': True, 'install_hint': None,
             'uses_gpu': True, 'devices': [{'key': 'gpu:0', 'name': 'Some GPU', 'vram_total_bytes': 8 * 2**30}],
             'checks': [{'device_key': 'gpu:0', 'certified': False, 'local_result': 'passed', 'usable': True}]},
            {'key': 'other-ep', 'label': 'Other EP', 'description': 'Needs a pack.', 'usable': False,
             'install_hint': 'Run `install other-ep`.', 'uses_gpu': True, 'devices': [], 'checks': []}],
        'detector_takes_execution_provider': {'rtmpose': True, 'mediapipe': False},
        'auto_offers': [{'kind': 'add-pack', 'ep_key': 'other-ep', 'download_bytes': 100, 'disk_bytes': 300,
                         'licence_url': 'https://example.org/licence', 'note': 'Run `install other-ep`.'}]}
    construct.assert_not_called()


def _pair(local_result, certified, usable, device_key='gpu:0'):
    return SimpleNamespace(device_key=device_key, name=None, certified=certified, local_result=local_result, usable=usable)


@pytest.mark.parametrize('checks,offered', [
    ((_pair(None, True, True),), True),  # certified
    ((_pair('passed', False, True),), True),  # no reviewed row, passed here: the opt-in of a field-test EP
    ((_pair(None, False, False),), False),  # no reviewed row, not checked here
    ((_pair('failed', True, False),), False),  # a local failure wins over a reviewed row
    ((_pair(None, False, False), _pair('passed', False, True, 'gpu:1')), True),  # two GPUs, one usable
    ((), True),  # no device checks (cpu): the EP's own flag
])
def test_usable_eps_follow_the_per_gpu_checks_not_the_ep_wide_flag(checks, offered):
    from freemocap.core.tracking.execution_providers import usable_execution_providers
    rows = [SimpleNamespace(key='some-ep', usable=True, checks=checks), SimpleNamespace(key='off-ep', usable=False, checks=())]
    with patch('freemocap.core.tracking.execution_providers.execution_provider_rows', return_value=rows):
        assert usable_execution_providers() == (['some-ep'] if offered else [])


@pytest.mark.parametrize('change', ['provider', 'model', 'filter', 'timing'])
def test_live_changes_rebuild_only_affected_inference(change):
    pipeline = object.__new__(live.RealtimePipeline)
    pipeline.id = 'live'
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
    elif change == 'filter':
        updated.aggregator_config.realtime_filter_config = updated.aggregator_config.realtime_filter_config.model_copy(update={'gap_duration_s': .6})
    else:
        updated.log_pipeline_times = True
    with patch.object(live.RealtimeSkeletonInferenceNode, 'create') as create:
        pipeline.update_config(updated)
    # Timing is fixed when the pipeline starts: a live change keeps the running value, so the metrics window says it is off.
    assert pipeline.config.log_pipeline_times is False
    if change in ('filter', 'timing'):
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


def test_graph_auto_is_left_to_the_run_and_mediapipe_takes_no_ep():
    """Auto reaches the run as None, so the run takes the recommendation with its options and device."""
    from freemocap.core.pipeline.dataflow.application_pipeline import resolve_tracking_provider
    assert resolve_tracking_provider(PosthocMocapPipelineConfig()) is None
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
    service.provider_status.return_value = [{'pipeline_id': 'live', 'mode': 'realtime', 'requested_provider': None, 'models': [
        {'node': 'wholebody', 'key': 'rtmw-wholebody133@openmmlab-exporter', 'execution_provider': 'gpu-ep', 'device': ['gpu:0', 'gpu:1']}]}]
    with patch('freemocap.app.freemocap_application.get_freemocap_app', return_value=SimpleNamespace(inference_service=service)):
        response = TestClient(app).get('/freemocap/onnx/session_providers')
    assert response.status_code == 200
    client = response.json()[0]
    assert client['requested_provider'] is None
    assert client['models'][0]['execution_provider'] == 'gpu-ep' and client['models'][0]['device'] == ['gpu:0', 'gpu:1']


@pytest.mark.parametrize('suggested', ['new-ep', None])
def test_the_suggestion_route_gives_what_skellytracker_suggests_for_a_legacy_key(suggested):
    from freemocap.api.http.onnx.onnx_router import onnx_router
    app = FastAPI()
    app.include_router(onnx_router, prefix='/freemocap')
    with patch('freemocap.core.tracking.execution_providers.suggested_execution_provider', return_value=suggested) as call:
        response = TestClient(app).get('/freemocap/onnx/execution_providers/suggestion', params={'saved': 'old-ep'})
    assert response.status_code == 200
    assert response.json() == {'saved': 'old-ep', 'suggested': suggested}
    call.assert_called_once_with('old-ep')


def test_the_suggestion_is_skellytrackers_answer_for_the_saved_key():
    from freemocap.core.tracking.execution_providers import suggested_execution_provider
    from skellytracker.core import eps
    with patch.object(eps, 'suggest_execution_provider', return_value='new-ep') as call:
        assert suggested_execution_provider('old-ep') == 'new-ep'
    call.assert_called_once_with('old-ep')
    assert suggested_execution_provider('not-an-ep-key') is None  # the real call: never raises for a string
