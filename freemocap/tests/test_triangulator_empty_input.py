"""Triangulating no points gives empty results: cv2.undistortPoints raises on empty input in OpenCV 4.12 and
returns None in 5.0, so the triangulator must not call it then."""

import numpy as np

from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.triangulation.triangulator import Triangulator


def test_zero_frames_or_zero_points_triangulate_to_empty_arrays():
    cameras = [CameraModel(id=str(index), index=index, image_size=(1280, 720),
                           intrinsics=CameraIntrinsics(fx=900.0, fy=900.0, cx=640.0, cy=360.0),
                           extrinsics=CameraExtrinsics(quaternion_wxyz=[1.0, 0.0, 0.0, 0.0], translation=[index * 100.0, 0.0, 0.0]))
               for index in range(2)]
    triangulator = Triangulator(cameras=cameras)
    for frames, points in ((0, 5), (3, 0)):
        result = triangulator.triangulate(data2d=np.zeros((2, frames, points, 2)), camera_order=triangulator.camera_ids)
        assert result.points_3d.shape == (frames, points, 3)
