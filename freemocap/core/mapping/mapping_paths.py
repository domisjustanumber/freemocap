"""The tracker→standard-human mapping YAML files of the two migrated detector choices.

The tracker side holds the point names of skellytracker 2.0: the RTMW canonical names of
`to_canonical`, and the `<group>/<point>` names of MediaPipe Holistic. One hand file serves both:
the RTMW canonical hand names are the MediaPipe hand names.
"""
from pathlib import Path

_YAML = Path(__file__).parent / "yaml"

RTMW_BODY_MAPPING = _YAML / "rtmw_body_to_standard_human.yaml"
MEDIAPIPE_HOLISTIC_BODY_MAPPING = _YAML / "mediapipe_holistic_body_to_standard_human.yaml"
HAND_MAPPING = _YAML / "hand_to_standard_human.yaml"

STANDARD_HUMAN_MAPPINGS: dict[str, tuple[Path, Path]] = {
    "rtmpose": (RTMW_BODY_MAPPING, HAND_MAPPING),
    "mediapipe": (MEDIAPIPE_HOLISTIC_BODY_MAPPING, HAND_MAPPING),
}
"""The body file, then the hand file, of each detector choice."""
