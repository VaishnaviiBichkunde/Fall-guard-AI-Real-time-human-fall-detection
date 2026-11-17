import base64
import os
import tempfile

import cv2
import numpy as np


def frame_to_data_uri(frame: np.ndarray) -> str:
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("A three-channel camera frame is required.")

    try:
        encoded_ok, encoded_frame = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 80],
        )
    except cv2.error as exc:
        raise RuntimeError("OpenCV could not encode the captured camera frame.") from exc

    if not encoded_ok:
        raise RuntimeError("OpenCV could not encode the captured camera frame.")

    encoded = base64.b64encode(encoded_frame).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


class CameraProcessLock:
    def __init__(self, path=None):
        self._path = path
        self._file = None
        self._unlock = None

    def acquire(self, camera_index: int):
        if self._file is not None:
            return True, None

        lock_path = self._path or os.path.join(
            tempfile.gettempdir(), f"fall_guard_ai_camera_{camera_index}.lock"
        )
        try:
            lock_file = open(lock_path, "a+b")
        except OSError as exc:
            return False, f"Could not reserve exclusive webcam access: {exc}"

        try:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
        except OSError as exc:
            lock_file.close()
            return False, f"Could not prepare exclusive webcam access: {exc}"

        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                self._unlock = lambda: msvcrt.locking(
                    lock_file.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._unlock = lambda: fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_UN,
                )
        except OSError:
            lock_file.close()
            return (
                False,
                "This webcam is already in use by another Fall Guard server. "
                "Stop the other app instances and try again.",
            )

        self._file = lock_file
        return True, None

    def release(self):
        lock_file, self._file = self._file, None
        unlock, self._unlock = self._unlock, None
        if lock_file is None:
            return

        try:
            if unlock is not None:
                lock_file.seek(0)
                unlock()
        finally:
            lock_file.close()
