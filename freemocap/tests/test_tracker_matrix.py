"""One broken native subprocess must not erase evidence or skip other detectors."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from freemocap.tools.datasets.tracker_matrix import run_matrix, compare_backend_observations
from freemocap.tools.datasets import tracker_comparison  # Load native dependencies before mocking subprocess.Popen.


class FakeCase:
    """A `subprocess.Popen` stand-in: `wait()` runs `effect(command)`, which returns the exit code or raises."""

    def __init__(self, effect, command, **kwargs):
        self.effect, self.command, self.kill = effect, command, Mock()

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        return False

    def wait(self, timeout=None):
        self.returncode = self.effect(self.command)
        return self.returncode


class TrackerMatrixTests(unittest.TestCase):
    def test_cross_backend_reports_pixel_distance_and_missingness_separately(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for backend, coordinates, visibility in (
                ("cpu", [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0]], [1.0, 1.0]),
                ("gpu-ep", [[3.0, 4.0, 0.0], [float("nan"), float("nan"), 0.0]], [1.0, 0.0]),
            ):
                directory = root / backend
                (directory / "baseline_observations").mkdir(parents=True)
                report = dict(case=f"rtmpose_{backend}", status="passed", recording="same-recording",
                              frame_counts={"camera": 1}, tracker={}, temporal_input="same-timeline")
                (directory / "report.json").write_text(json.dumps(report))
                document = {"observation": {"stages": {"body": {
                    "detector_ran": True, "keypoints": {"names": ["a", "b"], "xyz": coordinates, "visibility": visibility},
                }}}}
                (directory / "baseline_observations/0-0.json").write_text(json.dumps(document))
            report = compare_backend_observations(root / "cpu", root / "gpu-ep")
            self.assertEqual(report["status"], "measured")
            pixels = report["body_xy_pixel_distances"]
            self.assertEqual(pixels["maximum_px"], 5.0)
            self.assertEqual(pixels["matched_visible_points"], 1)
            self.assertEqual(pixels["different_visible_masks"], 1)
            self.assertNotIn("passed", report["comparison"])

    def test_crashed_and_truncated_cases_do_not_stop_later_datasets(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "matrix"

            def run(command):
                case_output = Path(command[-1])
                case_output.mkdir()
                if "rtmpose_cpu" in case_output.name:
                    (case_output / "report.json").write_text('{"status":', encoding="utf-8")
                return 1

            rows = [SimpleNamespace(key="cpu"), SimpleNamespace(key="gpu-ep")]  # The cases come from skellytracker's EP rows.
            with (patch("freemocap.tools.datasets.tracker_matrix.subprocess.Popen",
                        side_effect=lambda command, **kwargs: FakeCase(run, command)) as calls,
                  patch("freemocap.core.tracking.execution_providers.execution_provider_rows", return_value=rows)):
                result = run_matrix(datasets=["test_data", "sample_data"], recordings_root=Path(temporary), output=output)
            self.assertEqual(result, 1)
            self.assertEqual(calls.call_count, 8)
            reports = json.loads((output / "matrix.json").read_text(encoding="utf-8"))
            self.assertEqual(len(reports), 8)
            self.assertIn(["test_data", "rtmpose", "--execution-provider", "gpu-ep"], [call.args[0][4:8] for call in calls.call_args_list])
            self.assertTrue(all(report["status"] == "failed" for report in reports))
            self.assertEqual(json.loads((output / "sample_data-cpu-versus-gpu-ep.json").read_text())["status"], "not_compared")

    def test_ctrl_c_leaves_the_case_to_end_itself(self):
        """The case gets the Ctrl+C itself; a kill would be an unclean exit of its GPU EP session."""
        def interrupted(command):
            raise KeyboardInterrupt

        cases = []
        with TemporaryDirectory() as temporary:
            with (patch("freemocap.tools.datasets.tracker_matrix.subprocess.Popen",
                        side_effect=lambda command, **kwargs: cases.append(FakeCase(interrupted, command)) or cases[-1]),
                  patch("freemocap.core.tracking.execution_providers.execution_provider_rows",
                        return_value=[SimpleNamespace(key="gpu-ep")]),
                  self.assertRaises(KeyboardInterrupt)):
                run_matrix(datasets=["test_data"], recordings_root=Path(temporary), output=Path(temporary) / "matrix")
        cases[0].kill.assert_not_called()

    def test_missing_backend_evidence_is_not_a_pass(self):
        with TemporaryDirectory() as temporary:
            result = compare_backend_observations(Path(temporary) / "cpu", Path(temporary) / "gpu-ep")
            self.assertEqual(result["status"], "not_compared")
