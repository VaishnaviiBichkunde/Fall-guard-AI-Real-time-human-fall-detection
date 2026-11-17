import base64

import cv2
import numpy as np
import pytest

from core.camera_utils import CameraProcessLock, frame_to_data_uri


def test_frame_to_data_uri_encodes_a_displayable_jpeg():
    frame = np.zeros((32, 48, 3), dtype=np.uint8)

    data_uri = frame_to_data_uri(frame)

    assert data_uri.startswith("data:image/jpeg;base64,")
    assert "/media/" not in data_uri
    encoded = base64.b64decode(data_uri.split(",", 1)[1])
    decoded = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == frame.shape


def test_frame_to_data_uri_rejects_invalid_frames():
    with pytest.raises(ValueError, match="three-channel"):
        frame_to_data_uri(np.zeros((32, 48), dtype=np.uint8))


def test_camera_process_lock_allows_only_one_owner(tmp_path):
    lock_path = tmp_path / "camera.lock"
    first = CameraProcessLock(str(lock_path))
    second = CameraProcessLock(str(lock_path))

    acquired, error = first.acquire(0)
    assert acquired
    assert error is None

    acquired, error = second.acquire(0)
    assert not acquired
    assert "already in use" in error

    first.release()
    acquired, error = second.acquire(0)
    assert acquired
    assert error is None
    second.release()
