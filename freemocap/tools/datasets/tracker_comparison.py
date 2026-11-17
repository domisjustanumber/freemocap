"""Tracking-boundary parity/timing checks; never publishes accepted recording data.

Run each detector/EP case in a separate process. The EP is a skellytracker key as a free string;
skellytracker refuses an unknown one. Baseline is the existing
InferenceService with sequential camera reads, not the complete posthoc pipeline.
Both paths use identical model configuration and full recording coverage.
"""
import argparse
from dataclasses import asdict, dataclass, field
import json
import math
import multiprocessing
from pathlib import Path
from time import perf_counter

import numpy as np
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.core.pipeline.dataflow.tracker_adapter import SkellyTrackerAdapter, TrackedCameraFrame, recording_timestamps_ms
from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources, VideoSourceFinished
from freemocap.core.pipeline.inference_service import InferenceService, InferenceRegistration, InferenceMode, InferenceRequest
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper
from freemocap.core.tracking.execution_providers import execution_provider_rows
from freemocap.core.tracking.pipeline_runs import PIPELINE_KEYS, detector_takes_execution_provider
from .catalog import TEST_DATA, SAMPLE_DATA


def observation_document(observation) -> dict:
    return json.loads(json.dumps(asdict(observation), default=lambda value: value.tolist()))


@dataclass
class NumericalComparison:
    numerical_values: int = 0
    exact_differences: int = 0
    outside_tolerance: int = 0
    structural_differences: int = 0
    maximum_absolute_error: float = 0.0
    squared_error: float = 0.0
    examples: list[str] = field(default_factory=list)

    def compare(self, expected, actual, path: str = "observation") -> None:
        if isinstance(expected, dict) and isinstance(actual, dict):
            if expected.keys() != actual.keys():
                self._structural(path + ": different keys")
            for key in expected.keys() & actual.keys():
                self.compare(expected[key], actual[key], f"{path}.{key}")
        elif isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                self._structural(path + ": different lengths")
            for index, (left, right) in enumerate(zip(expected, actual)):
                self.compare(left, right, f"{path}[{index}]")
        elif isinstance(expected, float) and isinstance(actual, (float, int)) and not isinstance(actual, bool):
            if not math.isfinite(expected) or not math.isfinite(actual):
                if not (math.isnan(expected) and math.isnan(actual)) and expected != actual:
                    self._structural(path + ": different nonfinite masks")
                return
            difference = abs(expected - actual)
            self.numerical_values += 1
            self.exact_differences += difference != 0
            self.maximum_absolute_error = max(self.maximum_absolute_error, difference)
            self.squared_error += difference * difference
            # Tight same-backend regression threshold, not a measurement accuracy claim.
            if difference > 1e-6:
                self.outside_tolerance += 1
                if len(self.examples) < 10:
                    self.examples.append(f"{path}: {expected} != {actual}")
        elif type(expected) is not type(actual) or expected != actual:
            self._structural(path + ": different identity/value")

    def _structural(self, message: str) -> None:
        self.structural_differences += 1
        if len(self.examples) < 10:
            self.examples.append(message)

    def report(self) -> dict:
        return {**asdict(self), "rms_error": math.sqrt(self.squared_error / max(1, self.numerical_values)),
                "absolute_tolerance": 1e-6,
                "passed": self.outside_tolerance == self.structural_differences == 0}


DETECTORS = ("charuco", "mediapipe", "rtmpose")


def run_comparison(*, recording: Path, detector: str, execution_provider: str, output: Path) -> dict:
    if detector not in DETECTORS:
        raise ValueError(f"Unknown tracker comparison detector: {detector}")
    case = f"{detector}_{execution_provider}"
    output.mkdir(parents=True, exist_ok=False)
    report = {"case": case, "recording": str(recording), "status": "running",
              "scope": "tracking-boundary parity; not full pipeline acceptance", "paths": {}, "provider_evidence": []}
    report_path = output / "report.json"

    def save():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        (output / "report.txt").write_text(render_comparison(report), encoding="utf-8")

    save()
    if detector == "charuco":
        report.update(status="unsupported", reason="Charuco detection runs outside the skellytracker 2.0 pipeline run (create_detector); there is no inference-service path to compare.")
        save()
        return report
    takes_execution_provider = detector_takes_execution_provider(detector)
    if not takes_execution_provider and execution_provider != "cpu":
        report.update(status="unsupported", reason=f"The {detector} pipeline takes no execution provider; {execution_provider} was not run.")
        save()
        return report
    # An unknown key goes on to skellytracker, which refuses it; a known one that is not usable is not run.
    row = next((row for row in execution_provider_rows() if row.key == execution_provider), None)
    if takes_execution_provider and row is not None and not row.usable:
        report.update(status="unsupported", reason=f"The EP {execution_provider} is not usable on this host "
                      f"({row.install_hint or 'skellytracker gives no install hint'}); no CPU fallback was run.")
        save()
        return report
    try:
        sources = RecordingVideoSources.resolve(recording)
        timestamps_ms = recording_timestamps_ms(sources)
        report["temporal_input"] = "recording group timestamps, relative milliseconds, both paths"
        report["timestamp_provenance"] = {
            "group": sources.group_timing.method,
            "cameras": {source.camera_id: source.camera_timing.method for source in sources.camera_sources},
            "meaning": "Recording timeline: measured timestamps where available, otherwise inferred from video FPS",
        }
        report["frame_counts"] = {source.camera_id: source.video_metadata.frame_count for source in sources.camera_sources}
        report["video_metadata"] = {source.camera_id: source.video_metadata.model_dump(mode="json")
                                    for source in sources.camera_sources}
        detector_type = detector
        provider = execution_provider
        report["tracker"] = {"detector_type": detector_type, "pipeline": PIPELINE_KEYS[detector_type]}
        report["execution_provider"] = provider
        from .preparation import software_identity
        report["software_identity"] = software_identity()
        baseline_dir = output / "baseline_observations"
        baseline_dir.mkdir()
        camera_indices = {source.camera_id: index for index, source in enumerate(sources.camera_sources)}
        camera_timing = {source.camera_id: source.camera_timing for source in sources.camera_sources}
        detection_coverage = {mode: {"observations_with_visible_points": 0, "visible_points": 0}
                              for mode in ("baseline", "adapter")}
        comparison = NumericalComparison()

        def check_providers(service):
            evidence = service.provider_status()
            report["provider_evidence"].append(evidence)
            if any(model["execution_provider"] != provider for client in evidence for model in client["models"]):
                raise RuntimeError(f"Requested {provider} but obtained {evidence}")

        def consume(camera, frame, observation, mode, timestamp_s):
            path = baseline_dir / f"{camera_indices[camera]}-{frame}.json"
            document = {"observation": observation_document(observation), "timestamp_s": timestamp_s}
            points = observation.to_keypoints()
            visible = int((np.isfinite(points.xyz).all(axis=1) & (points.visibility > 0)).sum())
            detection_coverage[mode]["visible_points"] += visible
            detection_coverage[mode]["observations_with_visible_points"] += visible > 0
            if mode == "baseline":
                path.write_text(json.dumps(document), encoding="utf-8")
            else:
                comparison.compare(json.loads(path.read_text(encoding="utf-8")), document, f"{camera}/{frame}")

        for mode in ("baseline", "adapter"):
            flag = multiprocessing.Value("b", False)
            registry = WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.THREAD)
            service = InferenceService(worker_registry=registry)
            performance = PerformanceReport()
            count = 0
            started = perf_counter()
            service.start()
            try:
                if mode == "baseline":
                    client = service.register(InferenceRegistration(
                        pipeline_id="baseline", mode=InferenceMode.POSTHOC, detector_type=detector_type,
                        camera_ids=tuple(camera_indices), execution_provider=provider, shutdown_flag=flag,
                    ))
                    try:
                        group = VideoGroupHelper.from_recording_path(recording_path=str(recording))
                        try:
                            for frame in range(group.frame_count):
                                with performance.measure("baseline.camera_read"):
                                    images = {camera: video.read_frame_number(frame) for camera, video in group.videos.items()}
                                observations = client.submit(InferenceRequest(frame_number=frame, images=images, performance=performance,
                                    timestamps_ms={camera: timestamps_ms[frame] for camera in images})).result(timeout=300)
                                if frame == 0:
                                    check_providers(service)
                                for camera, observation in observations.items():
                                    consume(camera, frame, observation, mode, camera_timing[camera].timestamps_s[frame])
                                    count += 1
                        finally:
                            group.close()
                    finally:
                        client.close()
                else:
                    adapter = SkellyTrackerAdapter(inference_service=service, detector_type=detector_type,
                                                   performance_report=performance, execution_provider=provider)
                    from contextlib import closing
                    terminal_cameras = set()
                    with closing(adapter.track_recording(sources=sources, execution_id="adapter", shutdown_flag=flag)) as events:
                        for event in events:
                            if isinstance(event, TrackedCameraFrame):
                                if count == 0:
                                    check_providers(service)
                                consume(event.frame_key.camera, event.frame_key.frame, event.observation, mode, event.timestamp_s)
                                count += 1
                            elif isinstance(event, VideoSourceFinished):
                                if event.outcome.value != "succeeded" or event.camera_id in terminal_cameras:
                                    raise RuntimeError(f"Invalid terminal camera outcome: {event}")
                                terminal_cameras.add(event.camera_id)
                    if terminal_cameras != set(camera_indices):
                        raise RuntimeError("Missing terminal camera outcomes")
                expected_count = sum(report["frame_counts"].values())
                if count != expected_count:
                    raise ValueError(f"Incomplete observation coverage: {count}/{expected_count}")
            finally:
                service.close()
                registry.remove_dead()
                elapsed = perf_counter() - started
                report["paths"][mode] = dict(elapsed_s=elapsed, observations=count,
                    detection_coverage=detection_coverage[mode],
                    camera_images_per_s=count / elapsed, timings=performance.snapshot(),
                    timing_scope="includes setup, loading, inference, diagnostic serialization/comparison and cleanup")
                save()
        report["comparison"] = comparison.report()
        report["status"] = "passed" if report["comparison"]["passed"] else "parity_failed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    save()
    return report


def render_comparison(report: dict) -> str:
    lines = [f"TRACKER COMPARISON: {report['case']}", f"Status: {report['status']}",
             f"Scope: {report['scope']}", f"Recording: {report['recording']}", "",
             "Coverage (frames per camera):"]
    lines.extend(f"  {camera}: {count}" for camera, count in report.get("frame_counts", {}).items())
    if "timestamp_provenance" in report:
        lines.extend(["", "Timestamp provenance: " + json.dumps(report["timestamp_provenance"])])
    for mode, measurements in report.get("paths", {}).items():
        lines.extend(["", mode.upper(), f"  Observations: {measurements['observations']}",
                      f"  Detection coverage: {measurements.get('detection_coverage', 'not recorded')}",
                      f"  Diagnostic wall time: {measurements['elapsed_s']:.3f} s",
                      f"  Camera images/s (including diagnostics): {measurements['camera_images_per_s']:.2f}",
                      "  Operation                                      Count     Total s     Mean ms"])
        lines.extend(f"  {name:<46} {row['count']:>5} {row['total_s']:>11.3f} {row['mean_ms']:>11.3f}"
                     for name, row in measurements['timings'].items())
    if "comparison" in report:
        comparison = report['comparison']
        lines.extend(["", "NUMERICAL PARITY (same backend)",
            f"  Compared finite values: {comparison['numerical_values']}",
            f"  Nonidentical values: {comparison['exact_differences']}",
            f"  Outside absolute tolerance {comparison['absolute_tolerance']:g}: {comparison['outside_tolerance']}",
            f"  Structural/identity/missingness differences: {comparison['structural_differences']}",
            f"  Maximum absolute difference: {comparison['maximum_absolute_error']:g}",
            "  Aggregate differences span mixed units; this is regression parity, not measurement accuracy."])
    for key in ("reason", "error"):
        if key in report:
            lines.extend(["", f"{key.upper()}: {report[key]}"])
    lines.extend(["", "Session provider evidence: " + json.dumps(report.get("provider_evidence", [])),
        "Wall times include unequal diagnostic I/O and cold/warm setup effects; do not infer a speedup ratio.",
        "Full numerical arrays remain private diagnostic data, not accepted recording outputs."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=("test_data", "sample_data"))
    parser.add_argument("detector", choices=DETECTORS)
    parser.add_argument("--execution-provider", default="cpu", help="A skellytracker EP key (skellytracker-eps status lists them)")
    parser.add_argument("--recordings-root", type=Path, default=Path.home() / "freemocap_data/recordings")
    parser.add_argument("--output", type=Path, required=True, help="New diagnostic directory; must be ignored or outside the repository")
    args = parser.parse_args()
    dataset = TEST_DATA if args.dataset == "test_data" else SAMPLE_DATA
    report = run_comparison(recording=args.recordings_root / dataset.name, detector=args.detector,
                            execution_provider=args.execution_provider, output=args.output)
    print(json.dumps({key: value for key, value in report.items() if key not in ("software_identity", "tracker")}, indent=2), flush=True)
    return 0 if report["status"] in ("passed", "unsupported") else 1


if __name__ == "__main__":
    raise SystemExit(main())
