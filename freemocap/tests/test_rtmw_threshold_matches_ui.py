"""The UI's default RTMW confidence threshold is the backend's (user T1)."""
from pathlib import Path
import re

from freemocap.core.tracking.pipeline_runs import RTMW_MIN_SCORE

UI_CONSTANT = Path(__file__).parents[2] / "freemocap-ui" / "src" / "types" / "rtmw-confidence.ts"


def test_the_ui_default_is_the_backend_default():
    match = re.search(r"export const RTMW_CONFIDENCE_THRESHOLD = ([0-9.]+);", UI_CONSTANT.read_text(encoding="utf-8"))
    assert match and float(match.group(1)) == RTMW_MIN_SCORE == 0.5
