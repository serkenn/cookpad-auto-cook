"""Raspberry Pi AI HAT vision backend for ingredient detection."""

from __future__ import annotations

from pathlib import Path

from . import DetectedIngredient, VisionBackend

# Mapping from YOLO class labels to Japanese ingredient names and categories.
# This is a representative subset — extend as needed for your model.
_LABEL_MAP: dict[str, tuple[str, str]] = {
    "apple": ("りんご", "果物"),
    "banana": ("バナナ", "果物"),
    "orange": ("オレンジ", "果物"),
    "broccoli": ("ブロッコリー", "野菜"),
    "carrot": ("にんじん", "野菜"),
    "hot dog": ("ソーセージ", "肉"),
    "pizza": ("ピザ", "その他"),
    "donut": ("ドーナツ", "その他"),
    "cake": ("ケーキ", "その他"),
    "sandwich": ("サンドイッチ", "その他"),
    "bottle": ("ボトル飲料", "飲料"),
    "egg": ("卵", "卵"),
    "milk": ("牛乳", "乳製品"),
    "cheese": ("チーズ", "乳製品"),
    "tomato": ("トマト", "野菜"),
    "potato": ("じゃがいも", "野菜"),
    "onion": ("たまねぎ", "野菜"),
    "cabbage": ("キャベツ", "野菜"),
    "lettuce": ("レタス", "野菜"),
    "cucumber": ("きゅうり", "野菜"),
    "fish": ("魚", "魚"),
    "meat": ("肉", "肉"),
    "chicken": ("鶏肉", "肉"),
    "pork": ("豚肉", "肉"),
    "beef": ("牛肉", "肉"),
    "tofu": ("豆腐", "豆腐・大豆"),
    "rice": ("米", "穀物"),
}


class AIHatVisionBackend(VisionBackend):
    """Detect ingredients using Raspberry Pi AI HAT (Hailo) inference.

    Uses a YOLO-based object detection model running on the Hailo accelerator.
    Works offline but may have lower accuracy than cloud-based backends.
    """

    def __init__(
        self, model_path: str = "/usr/share/hailo-models/yolov8s.hef"
    ) -> None:
        self._model_path = model_path

    async def detect_ingredients(
        self, image_paths: list[str]
    ) -> list[DetectedIngredient]:
        try:
            from hailo_platform import (
                HEF,
                ConfiguredInferModel,
                FormatType,
                HailoStreamInterface,
                InferVStreams,
                InputVStreamParams,
                OutputVStreamParams,
                VDevice,
            )
        except ImportError:
            raise ImportError(
                "hailort SDK is required: pip install hailort"
            ) from None

        try:
            import cv2
            import numpy as np
        except ImportError:
            raise ImportError(
                "opencv-python and numpy are required for AI HAT backend"
            ) from None

        hef = HEF(self._model_path)
        target = VDevice()
        network_group = target.configure(hef)
        network_group_params = network_group.create_params()

        input_vstreams_params = InputVStreamParams.make(
            network_group, format_type=FormatType.FLOAT32
        )
        output_vstreams_params = OutputVStreamParams.make(
            network_group, format_type=FormatType.FLOAT32
        )

        input_shape = hef.get_input_vstream_infos()[0].shape
        h, w = input_shape[1], input_shape[2]

        seen: dict[str, DetectedIngredient] = {}

        for image_path in image_paths:
            img = cv2.imread(image_path)
            if img is None:
                continue
            resized = cv2.resize(img, (w, h))
            input_data = np.expand_dims(
                resized.astype(np.float32) / 255.0, axis=0
            )

            with InferVStreams(
                network_group, input_vstreams_params, output_vstreams_params
            ) as infer_pipeline:
                input_dict = {
                    hef.get_input_vstream_infos()[0].name: input_data
                }
                output = infer_pipeline.infer(input_dict)

            # Process detections from the first output layer
            output_name = list(output.keys())[0]
            detections = output[output_name][0]

            for det in detections:
                # Expected format: [x1, y1, x2, y2, confidence, class_id]
                if len(det) < 6:
                    continue
                conf = float(det[4])
                class_id = int(det[5])

                # Map class_id to label via model metadata or fallback
                label = str(class_id)
                if label in _LABEL_MAP:
                    name, category = _LABEL_MAP[label]
                elif label.lower() in _LABEL_MAP:
                    name, category = _LABEL_MAP[label.lower()]
                else:
                    continue  # Skip non-food detections

                if name in seen:
                    if conf > seen[name].confidence:
                        seen[name] = DetectedIngredient(
                            name=name, confidence=conf, category=category
                        )
                else:
                    seen[name] = DetectedIngredient(
                        name=name, confidence=conf, category=category
                    )

        return list(seen.values())
