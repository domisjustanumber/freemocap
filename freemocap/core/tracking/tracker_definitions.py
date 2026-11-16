"""Application names for the point schemas of the detector choices."""
from pydantic import BaseModel

from freemocap.core.tracking.pipeline_runs import detector_connections, detector_point_names

class TrackerDefinition(BaseModel):
    name: str
    tracked_points: tuple[str, ...]
    connections: tuple[tuple[str, str], ...]

def tracker_definition(detector_type: str) -> TrackerDefinition:
    # Preserve existing recording source identifiers.
    saved_name = {"rtmpose": "rtmpose_wholebody", "mediapipe": "mediapipe_wholebody"}[detector_type]
    return TrackerDefinition(name=saved_name, tracked_points=detector_point_names(detector_type),
                             connections=detector_connections(detector_type))

RTMPOSE_WHOLEBODY_DEFINITION = tracker_definition("rtmpose")
MEDIAPIPE_WHOLEBODY_DEFINITION = tracker_definition("mediapipe")
