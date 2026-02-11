"""USB camera capture module using OpenCV."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CameraCapture:
    camera_index: int
    image_path: str
    captured_at: str  # ISO8601


class FridgeCamera:
    """Capture images from USB cameras attached to the fridge."""

    def __init__(
        self, camera_indices: list[int] | None = None, save_dir: str = "/tmp/fridge"
    ) -> None:
        self._camera_indices = camera_indices or [0]
        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)

    def capture_all(self) -> list[CameraCapture]:
        """Capture from all configured cameras and return saved image paths."""
        results: list[CameraCapture] = []
        for idx in self._camera_indices:
            results.append(self.capture(idx))
        return results

    def capture(self, camera_index: int) -> CameraCapture:
        """Capture a single frame from the specified camera."""
        try:
            import cv2
        except ImportError:
            raise ImportError(
                "opencv-python is required: pip install opencv-python"
            ) from None

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError(
                f"カメラ {camera_index} を開けませんでした。"
                f"接続を確認してください。"
            )

        try:
            ret, frame = cap.read()
            if not ret or frame is None:
                raise RuntimeError(
                    f"カメラ {camera_index} からフレームを取得できませんでした。"
                )

            now = datetime.now(timezone.utc)
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            filename = f"cam{camera_index}_{timestamp}.jpg"
            filepath = self._save_dir / filename

            cv2.imwrite(str(filepath), frame)

            return CameraCapture(
                camera_index=camera_index,
                image_path=str(filepath),
                captured_at=now.isoformat(),
            )
        finally:
            cap.release()

    @staticmethod
    def list_cameras(max_check: int = 10) -> list[int]:
        """List available USB camera indices by probing."""
        try:
            import cv2
        except ImportError:
            raise ImportError(
                "opencv-python is required: pip install opencv-python"
            ) from None

        available: list[int] = []
        for i in range(max_check):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available
