"""Regenerate the message-model golden fixtures (CBOR bytes).

Run from project/freemocap::

    uv run python -m freemocap.tests.streaming_fixtures.regenerate_message_golden

These fixtures are the cross-language parity anchors: the TS fixtures under
``freemocap-ui/src/services/server/transport/__fixtures__/`` must be BYTE-IDENTICAL
copies of these files (the Python guard test ``test_golden_fixtures.py`` pins the
Python side; copy the regenerated .bin files into the UI directory after any
intentional change).

Re-running REWRITES the fixtures, and therefore IS a contract change.
"""
from __future__ import annotations

from pathlib import Path

import cbor2

from freemocap.core.streaming.message_model import (
    STANDARD_HUMAN_MODEL_ID,
    AppStateMessage,
    AppStateSnapshot,
    CertificationAuto,
    CertificationHost,
    CertificationItem,
    CertificationPair,
    CertificationResult,
    CertificationRun,
    CertificationSnapshot,
    EpPackResult,
    EpPackRun,
    PendingReport,
    PipelineHold,
    CalibratedCamera,
    CameraCalibrationMatch,
    CameraExtrinsicsMessage,
    CameraIntrinsicsMessage,
    CameraRotation,
    ChannelBlock,
    ChannelKind,
    CoordinateConvention,
    FrameMessage,
    MessageEnvelope,
    ModelDefinition,
    ModelInstance,
    encode_message,
)
from freemocap.core.streaming.rest_geometry import (
    ModelConnectionGroup,
    ModelLandmarkGroup,
    PrimaryAxis,
    RestLandmark,
    RestSegment,
)

FIXTURE_DIR = Path(__file__).parent


def build_convention_message() -> bytes:
    return cbor2.dumps(CoordinateConvention().to_cbor_message())


def build_model_message() -> bytes:
    # A synthetic 2-segment model; the spine orientation is a non-exact unit
    # quaternion (90 deg about z) — it pins "no float16 downcast" on scalar
    # floats in the TS parity test. The model is dimensionless: lengths and rest
    # positions are fractions of body height, as the standard human's are.
    model = ModelDefinition(
        model_id=STANDARD_HUMAN_MODEL_ID,
        segments=(
            RestSegment(
                name="hips",
                parent=None,
                primary_axis=PrimaryAxis(value="y"),
                rest_orientation=(1.0, 0.0, 0.0, 0.0),
                length_proportion=0.1,
            ),
            RestSegment(
                name="spine",
                parent="hips",
                primary_axis=PrimaryAxis(value="y"),
                rest_orientation=(0.7071067811865476, 0.0, 0.0, 0.7071067811865476),
                length_proportion=0.2,
            ),
        ),
        landmarks=(
            RestLandmark(name="hips_center", rest_position=(0.0, 0.0, 0.0)),
            RestLandmark(name="neck_center", rest_position=(0.0, 0.0, 0.2)),
        ),
        connections=(("hips", "spine"),),
        # Landmark-level structure with its colour already resolved — the only kind of
        # structure a one-segment model (a charuco board) can offer.
        landmark_groups=(
            ModelLandmarkGroup(
                name="trunk_points",
                landmark_names=("hips_center", "neck_center"),
                color="#4488ff",
            ),
        ),
        landmark_connections=(
            ModelConnectionGroup(
                name="trunk_outline",
                pairs=(("hips_center", "neck_center"),),
                color="#14ff14",
            ),
        ),
        scale_reference_name="body_height",
    )
    return cbor2.dumps(model.to_cbor_message())


def build_frame_message() -> bytes:
    segment_origins = ChannelBlock.from_float32_rows(
        kind=ChannelKind.SEGMENT_ORIGINS,
        columns=("x", "y", "z"),
        rows=[[0.0, 0.0, 0.0], [0.0, 0.0, 100.0]],
    )
    rotations_world = ChannelBlock.from_float32_rows(
        kind=ChannelKind.ROTATIONS_WORLD,
        columns=("w", "x", "y", "z"),
        rows=[[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
    )
    # The frame's `cameras` array describes EVERY live camera. Pin both shapes: one
    # the calibration covers, and one it does not (null intrinsics/extrinsics, which a
    # consumer must handle without dereferencing them).
    calibrated_camera = CalibratedCamera(
        id="cam-golden-0",
        index=0,
        rotation=CameraRotation.NONE,
        image_size=(1280, 720),
        intrinsics=CameraIntrinsicsMessage(
            fx=900.0, fy=900.0, cx=640.0, cy=360.0, k1=0.0, k2=0.0, p1=0.0, p2=0.0
        ),
        extrinsics=CameraExtrinsicsMessage(
            quaternion_wxyz=(1.0, 0.0, 0.0, 0.0),
            translation=(0.0, 0.0, 0.0),
        ),
        match_kind=CameraCalibrationMatch.EXACT,
        calibration_camera_id="cam-golden-0",
    )
    uncalibrated_camera = CalibratedCamera.unmatched(
        camera_id="cam-golden-1",
        camera_index=1,
        rotation=CameraRotation.CLOCKWISE_90,
        image_size=(720, 1280),
    )
    frame = FrameMessage(
        envelope=MessageEnvelope(timestamp=1.5),
        frame_number=99,
        cameras=(calibrated_camera, uncalibrated_camera),
        instances=(
            ModelInstance(
                instance_id=0,
                model_id=STANDARD_HUMAN_MODEL_ID,
                channels=(segment_origins, rotations_world),
                # The instance is where a size lives: the model above is dimensionless.
                # 1700 mm of `body_height`, the unit that model names.
                fitted_scale_mm=1700.0,
            ),
        ),
        image=b"\xff\xd8\xffgolden-fake-jpeg",
    )
    return encode_message(frame)


def build_app_state_message() -> bytes:
    # The `certification` field: a running quick check of one EP on one GPU, the latest result, one item per EP per
    # GPU with skellytracker's facts, Auto's choice with a candidate that needs a check, what runs, the hand-in list,
    # a running EP install with Windows ML's fraction and how the last install or remove ended.
    pair = CertificationPair(execution_provider="golden-ep", device_key="gpu:10de:2484:0")
    certification = CertificationSnapshot(
        host=CertificationHost(name="golden-host", os="Windows 11 Home 26H2"),
        run=CertificationRun(level="quick", items=(pair,), state="running", done=2, total=5, seconds_estimate=45),
        last_result=CertificationResult(execution_provider="other-ep", device_key="gpu:10de:2484:0",
                                        result="fail", reason="probe-l3-failed"),
        items=(
            CertificationItem(execution_provider="golden-ep", label="Golden EP", device_key="gpu:10de:2484:0",
                              device_name="NVIDIA GeForce RTX 3070", certified=False, usable=False,
                              reason_code="quick-check-needed", reason="no reviewed result and no quick check"),
            CertificationItem(execution_provider="other-ep", label="Other EP", device_key="gpu:10de:2484:0",
                              device_name="NVIDIA GeForce RTX 3070", certified=True, local_result="failed",
                              local_cause="unclean-exits", usable=False),
        ),
        auto=CertificationAuto(execution_provider="cpu-ep", device_key=None, needs_check=(pair,)),
        gpu_held_by=(PipelineHold(kind="posthoc", id="abc123"),),
        pending_reports=(PendingReport(report_id="quick-20261119T120000Z", has_failure=True),),
        pack_run=EpPackRun(action="install", execution_provider="golden-ml-ep", phase="download", fraction=0.25),
        last_pack_result=EpPackResult(action="remove", execution_provider="golden-ml-ep", result="failed",
                                      reason="package-not-removed"),
    )
    return encode_message(AppStateMessage(server_pid=4242, state=AppStateSnapshot(certification=certification)))


MESSAGES = {
    "message_convention_golden.bin": build_convention_message,
    "message_model_golden.bin": build_model_message,
    "message_frame_golden.bin": build_frame_message,
    "message_app_state_golden.bin": build_app_state_message,
}


def main() -> None:
    for filename, builder in MESSAGES.items():
        data = builder()
        path = FIXTURE_DIR / filename
        path.write_bytes(data)
        print("wrote %s (%d bytes)" % (path, len(data)))


if __name__ == "__main__":
    main()
