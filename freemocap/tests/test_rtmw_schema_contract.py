"""Core takes the RTMW point names and edges of the skellytracker 2.0 run, with the saved application identity."""

import subprocess
import sys

from freemocap.core.tasks.mocap.tracker_mappings import tracker_keypoint_names
from freemocap.core.tracking.pipeline_runs import detector_connections, detector_point_names
from freemocap.core.tracking.tracker_definitions import RTMPOSE_WHOLEBODY_DEFINITION


def test_the_definition_keeps_its_saved_name_and_takes_the_run_names_and_edges():
    definition = RTMPOSE_WHOLEBODY_DEFINITION
    assert definition.name == 'rtmpose_wholebody'
    assert definition.tracked_points == detector_point_names('rtmpose')
    assert definition.connections == detector_connections('rtmpose')
    assert tracker_keypoint_names('rtmpose') == tuple(sorted(definition.tracked_points))


def test_schema_imports_do_not_load_native_inference_libraries():
    result = subprocess.run([sys.executable, '-B', '-c',
        'import sys; '
        'import freemocap.core.tracking.tracker_definitions; '
        'import freemocap.core.tasks.mocap.tracker_mappings; '
        'assert "onnxruntime" not in sys.modules, "onnxruntime"; assert "mediapipe" not in sys.modules, "mediapipe"'],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
