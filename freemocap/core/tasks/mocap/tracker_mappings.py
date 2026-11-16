"""Application-facing access to the detector point names and the freemocap-owned mappings."""
from freemocap.core.mapping.composite_tracker_mapping import CompositeTrackerMapping
from freemocap.core.mapping.mapping_paths import STANDARD_HUMAN_MAPPINGS
from freemocap.core.mapping.tracker_mapping import TrackerMapping
from freemocap.core.tracking.pipeline_runs import detector_point_names


def tracker_keypoint_names(detector_type: str) -> tuple[str, ...]:
    """Publish the detector's point names in Core's established sorted channel order."""
    return tuple(sorted(detector_point_names(detector_type)))

def load_standard_human_mapping(detector_type: str) -> CompositeTrackerMapping:
    return CompositeTrackerMapping(tuple(TrackerMapping.from_yaml(path) for path in STANDARD_HUMAN_MAPPINGS[detector_type]))
