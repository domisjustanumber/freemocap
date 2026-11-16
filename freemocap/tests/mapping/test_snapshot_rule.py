"""A snapshot and the channels it maps come from one recording (freemocap.core.mapping)."""
from dataclasses import fields

import numpy as np

from freemocap.core.mapping.composite_tracker_mapping import CompositeTrackerMapping
from freemocap.core.mapping.tracker_mapping import TrackerMapping, TrackerMappingSnapshot


def test_snapshot_fields_keep_their_names_and_order():
    assert [field.name for field in fields(TrackerMappingSnapshot)] == [
        "entries", "prefix", "known_tracker_keypoints", "passthrough"]


def test_old_and_new_name_snapshots_restore_side_by_side():
    old = TrackerMapping(entries={"left_acromion": "left_shoulder", "head_center": ["left_ear", "right_ear"]})
    new = TrackerMapping(entries={"left_acromion": "body/left_shoulder",
                                  "head_center": ["body/left_ear", "body/right_ear"]})
    old_snapshot, = old.mapping_snapshots()
    new_snapshot, = new.mapping_snapshots()
    old_points = {"left_shoulder": np.array([1.0, 2.0, 3.0]), "left_ear": np.zeros(3), "right_ear": np.full(3, 2.0)}
    new_points = {f"body/{name}": value for name, value in old_points.items()}

    old_mapped = CompositeTrackerMapping((old_snapshot.restore(),)).apply(old_points)
    new_mapped = CompositeTrackerMapping((new_snapshot.restore(),)).apply(new_points)

    assert old_mapped.keys() == new_mapped.keys() == {"left_acromion", "head_center"}
    for name in old_mapped:
        np.testing.assert_array_equal(old_mapped[name], new_mapped[name])
    # Each snapshot maps only the channels of its own recording.
    assert CompositeTrackerMapping((old_snapshot.restore(),)).apply(new_points) == {}
