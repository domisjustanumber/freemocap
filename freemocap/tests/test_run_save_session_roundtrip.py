"""A saved descriptor with a non-finite camera assignment fitness error reads back as the same recording.

JSON stores the non-finite error as null; comparing the in-memory descriptor with its read-back failed
with "Recording changed after selecting the processing run" (4 of 10 fresh posthoc runs after a bad
calibration).
"""

import math

from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata, RunDescriptor, SensorGroup
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.parquet_storage.parquet_writer import publish_recording
from freemocap.core.recording.result_processing.run_save_session import RunSaveSession
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def _metadata(median_error: float) -> RecordingMetadata:
    fitness = {"status": "poor", "mean_cost": 1.0, "cameras": [{"camera_id": "0", "observed_points": 10,
        "qualifying_frames": 3, "valid_fraction": 0.0, "median_error": median_error, "p90_error": math.inf}]}
    run = RunDescriptor(sensor_groups={"group": SensorGroup(clock_description="group", sample_count=1)},
        sources={}, reference_frames={}, models={}, channels=(),
        processing={"camera_group:group": {"camera_assignment": {"status": "poor", "fitness": fitness}}})
    return RecordingMetadata(recording_id="recording", selected_run_id=0, runs={0: run})


def test_non_finite_fitness_error_is_stored_as_null_and_reads_back_unchanged(tmp_path):
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    accepted = _metadata(median_error=math.inf)
    session = RunSaveSession(source_run_id=0, target_run_id=0, expected_metadata=None)
    for _ in range(10):
        publish_recording(structure=structure, metadata=accepted, batches=[])
        session.accept(accepted)
        back = read_metadata(path=structure.data_parquet_path)
        camera = back.runs[0].processing["camera_group:group"]["camera_assignment"]["fitness"]["cameras"][0]
        assert (camera["median_error"], camera["p90_error"]) == (None, None)
        session.check(back)


def test_a_real_change_is_still_reported():
    session = RunSaveSession(source_run_id=0, target_run_id=0, expected_metadata=None)
    session.accept(_metadata(median_error=math.inf))
    try:
        session.check(_metadata(median_error=1.5))
    except ValueError as error:
        assert "Recording changed" in str(error)
    else:
        raise AssertionError("a changed descriptor passed the save check")
