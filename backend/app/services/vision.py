"""Pipeline nhận diện biển số kết hợp.

1. YOLOv8 (``license_plate.pt``) phát hiện vùng biển số.
2. ``chars_best.pt`` đọc từng ký tự trong vùng đó (nhanh, ~0,1 s/ảnh).
3. Gọi VLM Qwen2.5-VL qua Ollama đọc lại (xem ``services/vlm.py``) khi bước 2
   không ra kết quả, sai định dạng biển số Việt Nam, hoặc đúng định dạng nhưng
   có ký tự độ tin cậy thấp (``OCR_MIN_CHAR_CONFIDENCE``).
"""

import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Ultralytics chỉ lưu cấu hình tạm; tránh bị lỗi quyền khi API chạy từ IDE/dịch vụ.
_yolo_config_dir = Path(tempfile.gettempdir()) / "nhan_dien_ai_ultralytics"
_yolo_config_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(_yolo_config_dir))
from ultralytics import YOLO

from .. import config
from .vlm import VlmPlateReader, is_valid_vn_plate


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
    plate_source: str | None = None  # "ocr" | "vlm" | None
    ocr_text: str | None = None
    vlm_text: str | None = None
    vlm_ms: float | None = None
    ocr_min_confidence: float | None = None
    crowded: bool = False  # hai biển số to gần bằng nhau trong cùng khung


def _area(box: list[int]) -> int:
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def _overlaps(first: list[int], second: list[int]) -> bool:
    """Hai khung chồng lên nhau đáng kể: cùng một biển bị dò hai lần."""
    shared = _area([max(first[0], second[0]), max(first[1], second[1]), min(first[2], second[2]), min(first[3], second[3])])
    return shared > 0.3 * min(_area(first), _area(second))


def plates_by_distance(detections: list[ObjectDetection]) -> list[ObjectDetection]:
    """Các biển số khác nhau, xếp từ gần cổng nhất (to nhất). Bỏ qua khung dò yếu nếu đã có khung chắc hơn."""
    sure = [item for item in detections if item.confidence >= 0.5] or detections
    plates: list[ObjectDetection] = []
    for item in sorted(sure, key=lambda item: _area(item.box), reverse=True):
        if not any(_overlaps(item.box, kept.box) for kept in plates):
            plates.append(item)
    return plates


class VisionService:
    """Nhận diện biển số VN với model detector và model ký tự tùy chọn."""

    def __init__(self, vlm_reader: VlmPlateReader | None = None) -> None:
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
        self.vlm = vlm_reader if vlm_reader is not None else VlmPlateReader()
        # API chạy phân tích trong threadpool; model Ultralytics không an toàn khi gọi song song.
        self._yolo_lock = threading.Lock()

    @staticmethod
    def _normalize_plate(text: str) -> str | None:
        plate = re.sub(r"[^A-Z0-9]", "", text.upper())
        return plate if 7 <= len(plate) <= 10 and any(char.isdigit() for char in plate) else None

    @staticmethod
    def _crop(image: np.ndarray, box: list[int]) -> np.ndarray:
        height, width = image.shape[:2]
        x1, y1, x2, y2 = box
        return image[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]

    def _read_with_character_model(self, candidate: np.ndarray) -> tuple[str | None, float | None, float | None]:
        """Trả về (biển số, độ tin cậy trung bình, độ tin cậy ký tự thấp nhất)."""
        if self.char_model is None or candidate.size == 0:
            return None, None, None
        result = self.char_model.predict(candidate, conf=0.35, iou=0.5, imgsz=640, verbose=False)[0]
        characters: list[tuple[float, float, str, float]] = []
        for box in result.boxes:
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            class_index = int(box.cls[0].item())
            characters.append(((x1 + x2) / 2, (y1 + y2) / 2, str(result.names[class_index]), float(box.conf[0].item())))
        if not characters:
            return None, None, None

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
        if not plate:
            return None, None, None
        return plate, round(confidence, 3), round(min(item[3] for item in characters), 3)

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

    def _read_plate(self, image: np.ndarray, detections: list[ObjectDetection]) -> tuple[str | None, float | None, float | None]:
        """Đọc bằng chars_best; trả về kết quả hợp lệ đầu tiên, nếu không có thì kết quả thô đầu tiên."""
        fallback: tuple[str | None, float | None, float | None] = (None, None, None)
        for candidate in self._plate_candidates(image, detections):
            plate, confidence, min_confidence = self._read_with_character_model(candidate)
            if plate and is_valid_vn_plate(plate):
                return plate, confidence, min_confidence
            if plate and fallback[0] is None:
                fallback = (plate, confidence, min_confidence)
        return fallback

    def _detect_and_read(self, image: np.ndarray) -> tuple[list[ObjectDetection], str | None, float | None, float | None]:
        prediction = self.model.predict(image, conf=0.35, imgsz=640, verbose=False)[0]
        detections = [
            ObjectDetection(
                label=str(prediction.names[int(box.cls[0].item())]),
                confidence=round(float(box.conf[0].item()), 3),
                box=[int(value) for value in box.xyxy[0].tolist()],
            )
            for box in prediction.boxes
        ]
        # Với model biển số: chỉ đọc biển của xe gần nhất, không "đọc hộ" biển xe phía sau.
        readable = plates_by_distance(detections)[:1] if self.uses_plate_model else detections
        plate_text, plate_confidence, min_confidence = self._read_plate(image, readable)
        return detections, plate_text, plate_confidence, min_confidence

    def analyze_image(self, image_data: bytes) -> AnalysisResult:
        image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Tệp tải lên không phải ảnh hợp lệ")
        with self._yolo_lock:
            detections, plate_text, plate_confidence, min_confidence = self._detect_and_read(image)
        model_name = self.detector_path.name
        if self.char_model is not None:
            model_name = f"{model_name} + {self.character_path.name}"
        result = AnalysisResult(model_name, self.uses_plate_model, detections, plate_text, plate_confidence,
                                plate_source="ocr" if plate_text else None, ocr_text=plate_text,
                                ocr_min_confidence=min_confidence)
        plates = plates_by_distance(detections) if self.uses_plate_model else []
        result.crowded = len(plates) > 1 and _area(plates[1].box) >= config.CROWDED_PLATE_RATIO * _area(plates[0].box)
        # Tầng dự phòng VLM: đã thấy biển số mà OCR đọc rỗng, sai định dạng, hoặc
        # đúng định dạng nhưng có ký tự không chắc chắn. Đo trên tập test: ngưỡng
        # 0,5 bắt được 2/3 lỗi OCR "đúng định dạng nhưng sai ký tự", chỉ thêm 1 lượt
        # gọi VLM trên 49 biển OCR đọc đúng.
        unsure = min_confidence is not None and min_confidence < config.OCR_MIN_CHAR_CONFIDENCE
        if detections and (not is_valid_vn_plate(plate_text) or unsure):
            target = image
            if len(plates) > 1:  # nhiều xe trong khung: chỉ đưa vùng quanh biển gần nhất cho VLM
                left, top, right, bottom = plates[0].box
                width, height = right - left, bottom - top
                target = self._crop(image, [left - width, top - height, right + width, bottom + height])
            reading = self.vlm.read_plate(target)
            if reading is not None:
                result.vlm_text, result.vlm_ms = reading.raw_text, reading.elapsed_ms
                if reading.plate:
                    result.plate_text, result.plate_confidence, result.plate_source = reading.plate, None, "vlm"
                    result.model_name = f"{model_name} + {self.vlm.model}"
        return result
