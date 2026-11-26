"""Luật kết hợp trong VisionService: OCR trước, VLM chỉ khi OCR rỗng hoặc sai định dạng."""

import threading
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services import vision as vision_module
from app.services.vision import ObjectDetection, VisionService
from app.services.vlm import VlmReading


class FakeVlm:
    model = "qwen2.5vl:3b"

    def __init__(self, plate="59F113860"):
        self.plate, self.calls = plate, 0

    def read_plate(self, image, wait=False):
        self.calls += 1
        return VlmReading(self.plate, self.plate or "???", 1500.0)


def make_service(ocr_text, detections, vlm, min_confidence=0.9):
    service = VisionService.__new__(VisionService)  # bỏ qua việc nạp model .pt
    service.detector_path = Path("license_plate.pt")
    service.character_path = Path("chars_best.pt")
    service.char_model = object()
    service.uses_plate_model = True
    service.vlm = vlm
    service._yolo_lock = threading.Lock()
    service._detect_and_read = lambda image: (detections, ocr_text, 0.8 if ocr_text else None, min_confidence if ocr_text else None)
    return service


IMAGE_BYTES = cv2.imencode(".jpg", np.full((64, 64, 3), 200, np.uint8))[1].tobytes()
BOX = [ObjectDetection("license_plate", 0.9, [1, 1, 40, 30])]


def test_valid_ocr_does_not_call_vlm():
    vlm = FakeVlm()
    result = make_service("51F79512", BOX, vlm).analyze_image(IMAGE_BYTES)
    assert result.plate_text == "51F79512" and result.plate_source == "ocr" and vlm.calls == 0


@pytest.mark.parametrize("ocr_text", [None, "3T677141", "59FFLMJUGU"])
def test_vlm_used_when_ocr_missing_or_invalid(ocr_text):
    vlm = FakeVlm("60T78671")
    result = make_service(ocr_text, BOX, vlm).analyze_image(IMAGE_BYTES)
    assert vlm.calls == 1
    assert result.plate_text == "60T78671" and result.plate_source == "vlm" and result.ocr_text == ocr_text
    assert "qwen2.5vl:3b" in result.model_name


def test_no_detection_means_no_vlm_call():
    vlm = FakeVlm()
    result = make_service(None, [], vlm).analyze_image(IMAGE_BYTES)
    assert result.plate_text is None and vlm.calls == 0


def test_vlm_unusable_keeps_ocr_result():
    vlm = FakeVlm(plate=None)
    result = make_service("3T677141", BOX, vlm).analyze_image(IMAGE_BYTES)
    assert result.plate_text == "3T677141" and result.plate_source == "ocr" and vlm.calls == 1


def test_invalid_image_raises():
    with pytest.raises(ValueError):
        make_service(None, BOX, FakeVlm()).analyze_image(b"not an image")


def test_low_confidence_valid_ocr_asks_vlm_and_prefers_it():
    vlm = FakeVlm("51H09488")
    result = make_service("51H09468", BOX, vlm, min_confidence=0.46).analyze_image(IMAGE_BYTES)
    assert vlm.calls == 1 and result.plate_text == "51H09488" and result.plate_source == "vlm"
    assert result.ocr_text == "51H09468"


def test_confident_valid_ocr_skips_vlm():
    vlm = FakeVlm("51H09488")
    result = make_service("51H09468", BOX, vlm, min_confidence=0.8).analyze_image(IMAGE_BYTES)
    assert vlm.calls == 0 and result.plate_text == "51H09468"


def test_low_confidence_ocr_kept_when_vlm_cannot_read():
    vlm = FakeVlm(plate=None)
    result = make_service("51H09468", BOX, vlm, min_confidence=0.46).analyze_image(IMAGE_BYTES)
    assert vlm.calls == 1 and result.plate_text == "51H09468" and result.plate_source == "ocr"
