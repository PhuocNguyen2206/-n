"""Pipeline nhận diện biển số: phát hiện vùng biển số rồi đọc từng ký tự."""

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import easyocr
import numpy as np

# Ultralytics chỉ lưu cấu hình tạm; tránh bị lỗi quyền khi API chạy từ IDE/dịch vụ.
_yolo_config_dir = Path(tempfile.gettempdir()) / "nhan_dien_ai_ultralytics"
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
    """Nhận diện biển số VN với model detector và model ký tự tùy chọn."""

    def __init__(self) -> None:
        backend_directory = Path(__file__).resolve().parents[2]
        models_directory = backend_directory / "models"
        detector_override = Path(os.getenv("YOLO_MODEL_PATH", "models/license_plate.pt"))
        detector_override = detector_override if detector_override.is_absolute() else backend_directory / detector_override
        shared_detector = models_directory / "plate_best.pt"
        # Prefer the model trained by this project when it is available.  The
        # imported two-stage model remains the automatic fallback.
        self.detector_path = next((path for path in (detector_override, shared_detector) if path.is_file()), backend_directory / "yolov8n.pt")
        self.uses_plate_model = self.detector_path.name in {"plate_best.pt", "license_plate.pt"}
        self.model = YOLO(str(self.detector_path))

        character_override = Path(os.getenv("YOLO_CHARACTER_MODEL_PATH", "models/chars_best.pt"))
        self.character_path = character_override if character_override.is_absolute() else backend_directory / character_override
        self.char_model = YOLO(str(self.character_path)) if self.character_path.is_file() else None
        self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    @staticmethod
    def _normalize_plate(text: str) -> str | None:
        plate = re.sub(r"[^A-Z0-9]", "", text.upper())
        return plate if 7 <= len(plate) <= 10 and any(char.isdigit() for char in plate) else None

    @staticmethod
    def _crop(image: np.ndarray, box: list[int]) -> np.ndarray:
        height, width = image.shape[:2]
        x1, y1, x2, y2 = box
        return image[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]

    def _read_with_character_model(self, candidate: np.ndarray) -> tuple[str | None, float | None]:
        if self.char_model is None or candidate.size == 0:
            return None, None
        result = self.char_model.predict(candidate, conf=0.35, iou=0.5, imgsz=640, verbose=False)[0]
        characters: list[tuple[float, float, str, float]] = []
        for box in result.boxes:
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            class_index = int(box.cls[0].item())
            characters.append(((x1 + x2) / 2, (y1 + y2) / 2, str(result.names[class_index]), float(box.conf[0].item())))
        if not characters:
            return None, None

        ys = [item[1] for item in characters]
        has_two_rows = max(ys) - min(ys) > max(8, candidate.shape[0] * 0.16)
        if has_two_rows:
            divider = (min(ys) + max(ys)) / 2
            top = sorted((item for item in characters if item[1] < divider), key=lambda item: item[0])
            bottom = sorted((item for item in characters if item[1] >= divider), key=lambda item: item[0])
            raw_text = "".join(item[2] for item in top + bottom)
        else:
            raw_text = "".join(item[2] for item in sorted(characters, key=lambda item: item[0]))
        plate = self._normalize_plate(raw_text)
        confidence = sum(item[3] for item in characters) / len(characters)
        return plate, round(confidence, 3) if plate else None

    def _plate_candidates(self, image: np.ndarray, detections: list[ObjectDetection]) -> list[np.ndarray]:
        candidates: list[np.ndarray] = []
        if self.uses_plate_model:
            for item in detections:
                candidate = self._crop(image, item.box)
                if candidate.size:
                    candidates.append(candidate)
        else:
            for item in detections:
                if item.label in {"car", "motorcycle", "bus", "truck"}:
                    x1, y1, x2, y2 = item.box
                    midpoint = y1 + int((y2 - y1) * 0.42)
                    candidate = self._crop(image, [x1, midpoint, x2, y2])
                    if candidate.size:
                        candidates.append(candidate)
        return candidates

    def _read_plate(self, image: np.ndarray, detections: list[ObjectDetection]) -> tuple[str | None, float | None]:
        for candidate in self._plate_candidates(image, detections):
            plate, confidence = self._read_with_character_model(candidate)
            if plate:
                return plate, confidence
            enlarged = cv2.resize(candidate, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            for _box, text, ocr_confidence in self.reader.readtext(enlarged, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-."):
                plate = self._normalize_plate(text)
                if plate and ocr_confidence >= 0.25:
                    return plate, round(float(ocr_confidence), 3)
        return None, None

    def analyze_image(self, image_data: bytes) -> AnalysisResult:
        image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Tệp tải lên không phải ảnh hợp lệ")
        result = self.model.predict(image, conf=0.35, imgsz=640, verbose=False)[0]
        detections = [
            ObjectDetection(
                label=str(result.names[int(box.cls[0].item())]),
                confidence=round(float(box.conf[0].item()), 3),
                box=[int(value) for value in box.xyxy[0].tolist()],
            )
            for box in result.boxes
        ]
        plate_text, plate_confidence = self._read_plate(image, detections)
        model_name = self.detector_path.name
        if self.char_model is not None:
            model_name = f"{model_name} + {self.character_path.name}"
        return AnalysisResult(model_name, self.uses_plate_model, detections, plate_text, plate_confidence)
