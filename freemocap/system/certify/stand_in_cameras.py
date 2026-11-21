"""The stand-in camera group of the `realtime-session` check (`freemocap/certification.py`): a skellycam `CameraGroup` with
one camera and no device. It owns the group shared memory that skellycam's camera group allocates when its cameras start
(`CameraGroupSharedMemory.create`, the same call and layout), and the check writes its test frames into it as a camera
worker writes captured frames. No camera, camera worker or skellycam process exists.

skellycam has no public constructor of a camera group without its `CameraManager`, which creates the camera workers, so
this subclass sets only the fields that `CaptureGroup` and the realtime pipeline read: `ipc.group_id`, `configs`, `shm`,
`started` and `transport_error`."""
import time
from types import SimpleNamespace

import numpy as np
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.frame_dtype_factories import create_frame_dtype
from skellycam.utilities.create_camera_group_id import create_camera_group_id


class StandInCameraGroup(CameraGroup):
    __repr__ = object.__repr__  # the dataclass repr would walk the shared memory

    def __init__(self, height: int, width: int):  # its own signature: the dataclass one takes the camera workers
        config = CameraConfig(camera_id="0", camera_index=0, resolution=ImageResolution(width=width, height=height),
                              color_channels=3)
        timebase = TimebaseMapping()
        self.ipc = SimpleNamespace(group_id=create_camera_group_id())  # `CameraGroup.id` reads it
        self.configs = {config.camera_id: config}
        self.cameras = None
        self.shm = CameraGroupSharedMemory.create(camera_configs=self.configs, timebase_mapping=timebase, read_only=False)
        self.started = True  # `RealtimePipeline.start` then starts no camera
        self.transport_error = None
        self._frame = np.recarray(1, dtype=create_frame_dtype(config))
        self._frame.frame_metadata.camera_info = config.to_frame_camera_info()[0]
        self._frame.frame_metadata.timebase_mapping = timebase.to_numpy_record_array()[0]

    def write(self, frame_number: int, image: np.ndarray) -> None:
        """Put `image` in shared memory as frame `frame_number`; frames go in order from 0, so ring index = frame number."""
        frame, now = self._frame, time.perf_counter_ns()
        frame.image[0] = image
        frame.frame_metadata.frame_number[0] = frame_number
        for stamp in ("pre_frame_grab_ns", "post_frame_grab_ns", "pre_copy_to_camera_shm_ns", "post_copy_to_camera_shm_ns"):
            getattr(frame.frame_metadata.timestamps, stamp)[0] = now
        self.shm.camera_shms["0"].put_frame(frame_rec_array=frame, overwrite=True)

    def close(self) -> None:
        self.shm.unlink_and_close()
