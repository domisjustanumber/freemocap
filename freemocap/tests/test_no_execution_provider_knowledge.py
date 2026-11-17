"""freemocap keeps no knowledge of execution providers or GPU tools: skellytracker lists, recommends and checks them."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (ROOT / "freemocap", ROOT / "freemocap-ui" / "src")
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs"}
PATTERNS = (
    re.compile(r"""(["'`])(cuda|trt-rtx|coreml|directml|trt)\1"""),  # an EP key literal
    re.compile(r"\b[A-Z][A-Za-z]+ExecutionProvider\b"),  # an ONNX Runtime provider name
    re.compile(r"nvidia-smi|\bwmic\b|\blspci\b|system_profiler", re.IGNORECASE),  # a host GPU command
)
ALLOWED: dict[tuple[str, str], str] = {  # (path, line) -> the reason; empty since part 3 of the migration
    ("freemocap/core/tracking/legacy_tracker_run.py", 'CUDA, TRT_RTX = "cuda", "trt-rtx"'):  # Deleted at skellytracker stage 2.4 (legacy tracker benchmark).
        "user ruling L3: the old session runs cpu or cuda, never trt-rtx",  # Deleted at skellytracker stage 2.4 (legacy tracker benchmark).
}


def test_no_source_file_names_an_ep_an_ort_provider_or_a_gpu_command():
    found = set()
    for source in SOURCES:
        for path in source.rglob("*"):
            if path.suffix not in SUFFIXES or path == Path(__file__).resolve() or {"node_modules", "__pycache__"} & set(path.parts):
                continue
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if any(pattern.search(line) for pattern in PATTERNS):
                    found.add((path.relative_to(ROOT).as_posix(), line.strip()))
    assert found - ALLOWED.keys() == set(), "ask skellytracker instead (skellytracker.core.eps, skellytracker.core.system)"
    assert ALLOWED.keys() - found == set(), "remove the allowlist entries that no longer match"
