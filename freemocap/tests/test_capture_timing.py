import numpy as np
import pytest
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE
from freemocap.core.tracking.capture_timing import capture_timestamp_ms


def frame(before, after):
    record = np.zeros(1, dtype=np.dtype([('frame_metadata', FRAME_METADATA_DTYPE)])).view(np.recarray)
    record.frame_metadata.timestamps.pre_frame_grab_ns = before
    record.frame_metadata.timestamps.post_frame_grab_ns = after
    return record


def test_each_camera_gets_its_own_capture_midpoint_and_keeps_skipped_frame_duration():
    first, second = frame(1_000_000_000, 1_002_000_000), frame(1_002_000_000, 1_004_500_000)
    assert capture_timestamp_ms(first) == 1001.0
    assert capture_timestamp_ms(second) == 1003.25
    first.frame_metadata.frame_number = 9999  # Scheduling identity is not elapsed time.
    assert capture_timestamp_ms(first) == 1001.0
    assert capture_timestamp_ms(frame(1_100_000_000, 1_102_000_000)) - capture_timestamp_ms(first) == 100.0


def test_invalid_capture_timing_is_rejected():
    with pytest.raises(ValueError): capture_timestamp_ms(frame(20, 10))
    with pytest.raises(ValueError): capture_timestamp_ms(frame(-1, 10))
