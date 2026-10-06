"""Tạo dataset YOLO từ ảnh/video thô bằng gợi ý biển số tự động."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import cv2

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
RAW_DIRECTORY = BACKEND_DIRECTORY / "datasets" / "raw_media"
DATASET_DIRECTORY = BACKEND_DIRECTORY / "datasets" / "license_plate_vn"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(tempfile.gettempdir()) / "nhan_dien_ai_ultralytics"))


def choose_split(identity: str) -> str:
    bucket = int(hashlib.sha1(identity.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "val" if bucket < 90 else "test"


def yolo_labels(model, frame, confidence: float) -> list[str]:
    result = model.predict(frame, conf=confidence, iou=0.5, imgsz=640, verbose=False)[0]
    height, width = frame.shape[:2]
    labels: list[str] = []
    for box in result.boxes:
        x1, y1, x2, y2 = [max(0.0, value) for value in box.xyxy[0].tolist()]
        x1, x2 = min(x1, width), min(x2, width)
        y1, y2 = min(y1, height), min(y2, height)
        if x2 > x1 and y2 > y1:
            labels.append(f"0 {(x1 + x2) / (2 * width):.6f} {(y1 + y2) / (2 * height):.6f} {(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}")
    return labels


def save_frame(model, frame, identity: str, confidence: float, report: dict) -> None:
    labels = yolo_labels(model, frame, confidence)
    if not labels:
        report["skipped_no_plate"] += 1
        return
    split = choose_split(identity)
    name = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    image_path = DATASET_DIRECTORY / "images" / split / f"auto_{name}.jpg"
    label_path = DATASET_DIRECTORY / "labels" / split / f"auto_{name}.txt"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    if image_path.exists():
        report["skipped_duplicate"] += 1
        return
    cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    label_path.write_text("\n".join(labels) + "\n", encoding="utf-8")
    report["saved"][split] += 1


def frames_from_video(path: Path, seconds: float):
    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 25
    stride = max(1, int(fps * seconds))
    index = 0
    while True:
        success, frame = capture.read()
        if not success:
            break
        if index % stride == 0:
            yield index, frame
        index += 1
    capture.release()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo dataset YOLO từ ảnh/video thô")
    parser.add_argument("--confidence", type=float, default=0.55)
    parser.add_argument("--video-step", type=float, default=2.0, help="Lấy một khung hình mỗi N giây video")
    args = parser.parse_args()
    media_files = sorted(
        item for item in RAW_DIRECTORY.rglob("*")
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    ) if RAW_DIRECTORY.exists() else []
    if not media_files:
        raise SystemExit(f"Thư mục đang trống: {RAW_DIRECTORY}. Hãy chép ảnh/video vào đây trước.")

    from ultralytics import YOLO

    model_path = BACKEND_DIRECTORY / "models" / "plate_best.pt"
    if not model_path.is_file():
        raise SystemExit("Thiếu models/plate_best.pt để tự gợi ý nhãn biển số.")
    model = YOLO(str(model_path))
    report = {"saved": {"train": 0, "val": 0, "test": 0}, "skipped_no_plate": 0, "skipped_duplicate": 0}
    for path in media_files:
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            image = cv2.imread(str(path))
            if image is not None:
                save_frame(model, image, str(path.relative_to(RAW_DIRECTORY)), args.confidence, report)
        elif suffix in VIDEO_EXTENSIONS:
            for index, frame in frames_from_video(path, args.video_step):
                save_frame(model, frame, f"{path.relative_to(RAW_DIRECTORY)}:{index}", args.confidence, report)
    report_path = BACKEND_DIRECTORY / "data" / "dataset_import_report.json"
    try:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        # Báo cáo là tiện ích phụ; không để quyền ghi tệp làm dừng dataset đã tạo.
        pass
    total = sum(report["saved"].values())
    print(f"Đã tạo {total} ảnh có nhãn gợi ý. train={report['saved']['train']}, val={report['saved']['val']}, test={report['saved']['test']}")
    print("Mở LabelImg để kiểm tra/chỉnh các khung nhãn trước khi train.")


if __name__ == "__main__":
    main()
