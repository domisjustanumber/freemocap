"""A passed generator makes the bundle adjustment repeatable; without one it keeps the global numpy generator (user R1)."""

import cv2
import numpy as np
import pytest

from freemocap.core.tasks.calibration.anipose_calibration.helpers.bundle_adjust import iterative_bundle_adjustment
from freemocap.core.tasks.calibration.anipose_calibration.helpers.freemocap_anipose import BoardObservations
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel

CAMERA_POSES = [((0.0, 0.0, 0.0), (0.0, 0.0, 2000.0)),
                ((0.0, 0.5, 0.0), (-900.0, 0.0, 1900.0)),
                ((0.0, -0.5, 0.0), (900.0, 0.0, 1900.0))]


def scene():
    """Three cameras, 12 board poses of 12 corners, noisy projections; camera 2 misses every third board."""
    data = np.random.default_rng(7)
    grid = np.array([(x * 50.0, y * 50.0, 0.0) for y in range(3) for x in range(4)])
    image_points, object_points, corner_ids, rvecs, tvecs = [], [], [], [], []
    for board in range(12):
        board_r = data.normal(0, 0.3, 3)
        board_t = data.normal(0, 150, 3) + (-75.0, -50.0, 0.0)
        board_matrix = np.eye(4)
        board_matrix[:3, :3], board_matrix[:3, 3] = cv2.Rodrigues(board_r)[0], board_t
        rows = np.full((3, len(grid), 2), np.nan)
        cam_r, cam_t = np.full((3, len(grid), 3), np.nan), np.full((3, len(grid), 3), np.nan)
        for index, (r, t) in enumerate(CAMERA_POSES):
            if index == 2 and board % 3 == 0:
                continue
            camera_matrix = np.eye(4)
            camera_matrix[:3, :3], camera_matrix[:3, 3] = cv2.Rodrigues(np.array(r))[0], t
            in_camera = camera_matrix @ board_matrix
            pose_r = cv2.Rodrigues(in_camera[:3, :3])[0].ravel()
            projected, _ = cv2.projectPoints(grid, pose_r, in_camera[:3, 3], np.array([[800.0, 0, 320], [0, 800.0, 240], [0, 0, 1]]), None)
            rows[index] = projected.reshape(-1, 2) + data.normal(0, 0.5, (len(grid), 2))
            cam_r[index], cam_t[index] = pose_r, in_camera[:3, 3]
        image_points.append(rows)
        object_points.append(grid)
        corner_ids.append(np.full(len(grid), board, dtype=np.int32))
        rvecs.append(cam_r)
        tvecs.append(cam_t)
    observations = BoardObservations(object_points=np.vstack(object_points), corner_ids=np.concatenate(corner_ids),
                                     rotation_vectors=np.concatenate(rvecs, axis=1), translation_vectors=np.concatenate(tvecs, axis=1))
    return np.concatenate(image_points, axis=1), observations


def calibrate(rng):
    """Run from perturbed starting extrinsics; returns the error and every camera parameter."""
    cameras = [CameraModel(id=f"cam{index}", index=index, image_size=(640, 480),
                           intrinsics=CameraIntrinsics(fx=780.0, fy=780.0, cx=320.0, cy=240.0),
                           extrinsics=CameraExtrinsics.from_rodrigues(rvec=np.array(r) + 0.02, tvec=np.array(t) + 20.0))
               for index, (r, t) in enumerate(CAMERA_POSES)]
    points, observations = scene()
    error = iterative_bundle_adjustment(cameras, points, observations, num_iterations=3, max_nfev=20,
                                        num_samples_per_iteration=20, num_samples_full=40, rng=rng)
    params = [(c.intrinsics.fx, c.intrinsics.k1, *c.extrinsics.rodrigues_vector, *c.extrinsics.translation) for c in cameras]
    return error, np.array(params)


def test_the_same_generator_seed_gives_identical_numbers_and_leaves_the_global_generator_alone():
    np.random.seed(123)
    global_state = np.random.get_state()[1].copy()
    first, second = calibrate(np.random.default_rng(0)), calibrate(np.random.default_rng(0))
    assert first[0] == second[0]
    assert np.array_equal(first[1], second[1])
    assert np.array_equal(np.random.get_state()[1], global_state)
    other = calibrate(np.random.default_rng(1))
    assert not np.array_equal(first[1], other[1]), "the generator must reach the resampling, or this test proves nothing"


def test_without_a_generator_the_global_numpy_generator_drives_it_as_before():
    np.random.seed(5)
    first = calibrate(None)
    np.random.seed(5)
    second = calibrate(None)
    assert np.array_equal(first[1], second[1])
    np.random.seed(6)
    assert not np.array_equal(first[1], calibrate(None)[1])
    assert first[0] == pytest.approx(second[0])
