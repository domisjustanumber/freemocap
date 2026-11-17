"""A board pose needs 6 finite corners: skellytracker's anipose export fills an absent board with NaN corners.

OpenCV 4.12 returned ret=True with a NaN pose for an all-NaN row; OpenCV 5.0 returns ret=True with a zero
pose, which seeded every camera at the origin and broke the calibration.
"""

from unittest import TestCase

import cv2
import numpy as np
from skellytracker.core.detectors.calibration import CharucoBoardDefinition

from freemocap.core.tasks.calibration.charuco_board.charuco_board_ops import estimate_pose_points, get_object_points
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


class CharucoPoseEstimateTests(TestCase):
    def setUp(self) -> None:
        self.board = CharucoBoardDefinition(squares_x=7, squares_y=5, square_length_mm=50.0)
        self.camera = CameraModel(
            id="test-camera", index=0, image_size=(640, 480),
            intrinsics=CameraIntrinsics(fx=640.0, fy=640.0, cx=320.0, cy=240.0),
            extrinsics=CameraExtrinsics(quaternion_wxyz=[1.0, 0.0, 0.0, 0.0], translation=[0.0, 0.0, 0.0]),
        )
        self.object_points = get_object_points(self.board)
        self.ids = np.arange(len(self.object_points), dtype=np.int32).reshape(-1, 1)
        self.rvec, self.tvec = np.array([0.1, -0.2, 0.05]), np.array([-100.0, -50.0, 800.0])
        projected, _ = cv2.projectPoints(self.object_points, self.rvec, self.tvec,
                                         self.camera.intrinsics.to_camera_matrix(), self.camera.intrinsics.to_dist_coeffs_5())
        self.corners = projected.astype(np.float32)

    def test_all_nan_row_is_no_pose(self) -> None:
        corners = np.full_like(self.corners, np.nan)
        self.assertEqual(estimate_pose_points(self.board, self.camera, corners, self.ids), (None, None))

    def test_fewer_than_six_finite_corners_is_no_pose(self) -> None:
        corners = np.full_like(self.corners, np.nan)
        corners[:5] = self.corners[:5]
        self.assertEqual(estimate_pose_points(self.board, self.camera, corners, self.ids), (None, None))

    def test_partial_row_uses_its_finite_corners(self) -> None:
        corners = self.corners.copy()
        corners[8:] = np.nan
        rvec, tvec = estimate_pose_points(self.board, self.camera, corners, self.ids)
        np.testing.assert_allclose(rvec.ravel(), self.rvec, atol=1e-4)
        np.testing.assert_allclose(tvec.ravel(), self.tvec, atol=1e-2)
