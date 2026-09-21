"""Pipeline YOLOv8 cho ảnh camera.

Đặt model biển số đã huấn luyện tại ``models/license_plate.pt`` để thay model
COCO mặc định. Model mặc định nhận diện người, xe máy và ô tô, nhưng không có
lớp biển số xe.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


@dataclass
class ObjectDetection:
    label: str
    confidence: float
    box: list[int]


@dataclass
class AnalysisResult:
    model_name: str
    uses_plate_model: bool
    detections: list[ObjectDetection]


class VisionService:
    def __init__(self) -> None:
        plate_model = Path(os.getenv("YOLO_MODEL_PATH", "models/license_plate.pt"))
        self.uses_plate_model = plate_model.is_file()
        self.model_path = str(plate_model if self.uses_plate_model else Path("yolov8n.pt"))
        self.model = YOLO(self.model_path)

    def analyze_image(self, image_data: bytes) -> AnalysisResult:
        image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Tệp tải lên không phải ảnh hợp lệ")
        result = self.model.predict(image, conf=0.35, imgsz=640, verbose=False)[0]
        detections = []
        for box in result.boxes:
            class_index = int(box.cls[0].item())
            detections.append(ObjectDetection(
                label=str(result.names[class_index]),
                confidence=round(float(box.conf[0].item()), 3),
                box=[int(value) for value in box.xyxy[0].tolist()],
            ))
        return AnalysisResult(Path(self.model_path).name, self.uses_plate_model, detections)
