"""Application-facing access to Tracker-owned schemas and freemocap-owned mappings."""
from skellytracker.core.io.tracker_profiles import tracker_profile

from freemocap.core.mapping.composite_tracker_mapping import CompositeTrackerMapping
from freemocap.core.mapping.mapping_paths import STANDARD_HUMAN_MAPPINGS
from freemocap.core.mapping.tracker_mapping import TrackerMapping


def tracker_keypoint_names(detector_type: str) -> tuple[str, ...]:
    """Publish Tracker's declared keypoints in Core's established sorted channel order."""
    return tuple(sorted(tracker_profile(detector_type).keypoint_names))

def load_standard_human_mapping(detector_type: str) -> CompositeTrackerMapping:
    return CompositeTrackerMapping(tuple(TrackerMapping.from_yaml(path) for path in STANDARD_HUMAN_MAPPINGS[detector_type]))
