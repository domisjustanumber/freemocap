"""Adapt SkellyCam capture timestamps to the millisecond time of a pipeline frame."""
import numpy as np


def capture_timestamp_ms(frame_record: np.recarray) -> float:
    """The capture midpoint of one camera frame, in ms of the skellycam clock.

    Use the same pre/post-grab midpoint convention as recorded camera timing.
    Keep integer nanoseconds until the final conversion; processing delay and
    frame ordinals do not determine elapsed time.
    """
    timestamps = frame_record.frame_metadata.timestamps
    before = int(timestamps.pre_frame_grab_ns[0])
    after = int(timestamps.post_frame_grab_ns[0])
    if before < 0 or after < before:
        raise ValueError('Invalid pre/post-grab capture timestamps')
    return (before + after) / 2_000_000
