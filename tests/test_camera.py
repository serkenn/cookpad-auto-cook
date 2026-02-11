"""Tests for fridge camera module (mocked OpenCV)."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cookpad.fridge.camera import CameraCapture, FridgeCamera


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def mock_cv2():
    """Inject a mock cv2 module into sys.modules."""
    mock = MagicMock()
    with patch.dict(sys.modules, {"cv2": mock}):
        yield mock


class TestFridgeCamera:
    def test_init_creates_save_dir(self, tmp_dir):
        save_dir = Path(tmp_dir) / "sub" / "dir"
        cam = FridgeCamera(camera_indices=[0], save_dir=str(save_dir))
        assert save_dir.exists()

    def test_capture_success(self, mock_cv2, tmp_dir):
        """Successful capture saves a file and returns CameraCapture."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.imwrite.return_value = True

        cam = FridgeCamera(camera_indices=[0], save_dir=tmp_dir)
        result = cam.capture(0)

        assert isinstance(result, CameraCapture)
        assert result.camera_index == 0
        assert result.captured_at  # ISO8601 string
        mock_cap.release.assert_called_once()

    def test_capture_camera_not_found(self, mock_cv2, tmp_dir):
        """RuntimeError when camera cannot be opened."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.VideoCapture.return_value = mock_cap

        cam = FridgeCamera(camera_indices=[0], save_dir=tmp_dir)
        with pytest.raises(RuntimeError, match="カメラ 0"):
            cam.capture(0)

    def test_capture_read_failure(self, mock_cv2, tmp_dir):
        """RuntimeError when frame read fails."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_cv2.VideoCapture.return_value = mock_cap

        cam = FridgeCamera(camera_indices=[0], save_dir=tmp_dir)
        with pytest.raises(RuntimeError, match="フレームを取得"):
            cam.capture(0)
        mock_cap.release.assert_called_once()

    def test_capture_all(self, mock_cv2, tmp_dir):
        """capture_all captures from all configured cameras."""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.imwrite.return_value = True

        cam = FridgeCamera(camera_indices=[0, 1], save_dir=tmp_dir)
        results = cam.capture_all()

        assert len(results) == 2
        assert results[0].camera_index == 0
        assert results[1].camera_index == 1

    def test_list_cameras(self, mock_cv2):
        """list_cameras probes indices and returns available ones."""
        caps = {}
        for i in range(10):
            m = MagicMock()
            m.isOpened.return_value = i in (0, 2)
            caps[i] = m

        mock_cv2.VideoCapture.side_effect = lambda i: caps[i]

        result = FridgeCamera.list_cameras()
        assert result == [0, 2]
