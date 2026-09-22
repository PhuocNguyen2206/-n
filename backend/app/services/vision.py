"""Pipeline YOLOv8 cho ảnh camera.

Đặt model biển số đã huấn luyện tại ``models/license_plate.pt`` để thay model
COCO mặc định. Model mặc định nhận diện người, xe máy và ô tô, nhưng không có
lớp biển số xe.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import easyocr
import numpy as np

# Không ghi cấu hình YOLO vào thư mục tài khoản Windows; dự án tự mang cấu hình theo data/.
_yolo_config_dir = Path("data/ultralytics").resolve()
_yolo_config_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(_yolo_config_dir))
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
    plate_text: str | None
    plate_confidence: float | None


class VisionService:
    def __init__(self) -> None:
        # Resolve bundled weights from the backend directory so the API works
        # whether it is launched from the project root, a service manager, or IDE.
        backend_directory = Path(__file__).resolve().parents[2]
        configured_model = Path(os.getenv("YOLO_MODEL_PATH", "models/license_plate.pt"))
        plate_model = configured_model if configured_model.is_absolute() else backend_directory / configured_model
        self.uses_plate_model = plate_model.is_file()
        self.model_path = str(plate_model if self.uses_plate_model else backend_directory / "yolov8n.pt")
        self.model = YOLO(self.model_path)
        self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    @staticmethod
    def _normalize_plate(text: str) -> str | None:
        plate = re.sub(r"[^A-Z0-9]", "", text.upper())
        # Biển số Việt Nam thường có 7–10 ký tự, ví dụ 43A112345.
        return plate if 7 <= len(plate) <= 10 and any(char.isdigit() for char in plate) else None

    def _read_plate(self, image: np.ndarray, detections: list[ObjectDetection]) -> tuple[str | None, float | None]:
        candidates: list[np.ndarray] = []
        if self.uses_plate_model:
            for item in detections:
                if "plate" in item.label.lower() or "license" in item.label.lower():
                    x1, y1, x2, y2 = item.box
                    candidates.append(image[max(0, y1):y2, max(0, x1):x2])
        else:
            # Không có model biển số riêng: tìm thử vùng nửa dưới của xe/xe máy.
            for item in detections:
                if item.label in {"car", "motorcycle", "bus", "truck"}:
                    x1, y1, x2, y2 = item.box
                    midpoint = y1 + int((y2 - y1) * 0.42)
                    candidates.append(image[midpoint:y2, max(0, x1):x2])
        for candidate in candidates:
            if candidate.size == 0:
                continue
            enlarged = cv2.resize(candidate, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            for _box, text, confidence in self.reader.readtext(enlarged, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-."):
                plate = self._normalize_plate(text)
                if plate and confidence >= 0.25:
                    return plate, round(float(confidence), 3)
        return None, None

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
        plate_text, plate_confidence = self._read_plate(image, detections)
        return AnalysisResult(Path(self.model_path).name, self.uses_plate_model, detections, plate_text, plate_confidence)
