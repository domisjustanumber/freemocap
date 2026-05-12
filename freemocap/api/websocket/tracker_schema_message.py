"""
Tracker-schema handshake message.

Sent once when a WebSocket client connects, and rebroadcast if the pipeline's
tracker configuration changes. Carries every active tracker's
`TrackedObjectDefinition` so the frontend can render points and connections
without hardcoding any tracker schema.
"""
from typing import Any

import msgspec
from skellytracker.trackers.base_tracker.tracked_object_definition import TrackedObjectDefinition
from skellytracker.trackers.rtmpose_tracker.names_and_connections import RTMPOSE_WHOLEBODY_DEFINITION
from skellytracker.trackers.mediapipe_tracker.names_and_connections import MEDIAPIPE_HOLISTIC_DEFINITION

from freemocap.api.websocket.websocket_message_types import WebsocketMessageType


class TrackerSchemasMessage(msgspec.Struct):
    """Dict of `tracker_id -> TrackedObjectDefinition.model_dump()`.

    Values are pre-serialized to plain dicts because msgspec.Struct cannot
    carry arbitrary Pydantic models directly. The frontend treats the inner
    dicts as the canonical TS `TrackedObjectDefinition` shape.
    """
    schemas: dict[str, dict[str, Any]]
    message_type: WebsocketMessageType = WebsocketMessageType.TRACKER_SCHEMAS


def collect_active_tracker_schemas() -> dict[str, dict[str, Any]]:
    """Return tracker schemas the UI may need for realtime overlays.

    Both RTMPose whole-body and MediaPipe holistic are included so the client
    can switch detector mode without reconnecting.
    """
    active: tuple[TrackedObjectDefinition, ...] = (
        RTMPOSE_WHOLEBODY_DEFINITION,
        MEDIAPIPE_HOLISTIC_DEFINITION,
    )
    return {definition.name: definition.model_dump() for definition in active}
