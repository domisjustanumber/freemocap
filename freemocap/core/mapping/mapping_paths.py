"""The tracker→standard-human mapping YAML files of the two migrated detector choices.

Until the pipeline switch these keep the tracker names of skellytracker sfn26, because
the trackers still give those names.
"""
from pathlib import Path

_YAML = Path(__file__).parent / "yaml"

RTMPOSE_BODY_MAPPING = _YAML / "rtmpose_body_to_standard_human_mapping.yaml"
RTMPOSE_HAND_MAPPING = _YAML / "rtmpose_hand_to_standard_human_mapping.yaml"
MEDIAPIPE_BODY_MAPPING = _YAML / "mediapipe_body_to_standard_human_mapping.yaml"
MEDIAPIPE_HAND_MAPPING = _YAML / "mediapipe_hand_to_standard_human_mapping.yaml"

STANDARD_HUMAN_MAPPINGS: dict[str, tuple[Path, Path]] = {
    "rtmpose": (RTMPOSE_BODY_MAPPING, RTMPOSE_HAND_MAPPING),
    "mediapipe": (MEDIAPIPE_BODY_MAPPING, MEDIAPIPE_HAND_MAPPING),
}
"""The body file, then the hand file, of each detector choice."""
