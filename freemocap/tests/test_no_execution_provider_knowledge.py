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
PART_3 = "part 3 of the migration: the tools take an EP key as a free string and a matrix takes its keys from status()"
ALLOWED = {
    ("freemocap/tools/datasets/recording_comparison.py",
     'parser.add_argument("--provider", choices=("cpu", "cuda"), default="cpu")'): PART_3,
    ("freemocap/tools/datasets/tracker_comparison.py",
     'if case == "rtmpose_cuda" and "cuda" not in usable_execution_providers():'): PART_3,
    ("freemocap/tools/datasets/tracker_comparison.py",
     'provider = "cuda" if case == "rtmpose_cuda" else "cpu"'): PART_3,
    ("freemocap/tools/hardware_validation/camera_transition.py",
     "configuration.skeleton_inference_node_config.execution_provider = 'cuda'"): PART_3,
    ("freemocap/tools/hardware_validation/pipeline_run.py",
     "configuration.skeleton_inference_node_config.execution_provider = 'cuda'"): PART_3,
    ("freemocap/tools/sdk_live_validation.py",
     "pipeline.skeleton_inference_node_config.execution_provider = 'cuda'"): PART_3,
    ("freemocap/tests/test_tracker_matrix.py",
     '("cuda", [[3.0, 4.0, 0.0], [float("nan"), float("nan"), 0.0]], [1.0, 0.0]),'): PART_3,
    ("freemocap/tests/test_tracker_matrix.py",
     'report = compare_backend_observations(root / "cpu", root / "cuda")'): PART_3,
    ("freemocap/tests/test_tracker_matrix.py",
     'result = compare_backend_observations(Path(temporary) / "cpu", Path(temporary) / "cuda")'): PART_3,
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
