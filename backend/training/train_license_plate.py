"""Huấn luyện YOLOv8n nhận diện biển số và đưa model tốt nhất vào dự án."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# Ultralytics only keeps its tiny local settings file here.  Keeping it out of
# the project avoids Windows file-permission conflicts while a server is running.
os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(tempfile.gettempdir()) / "nhan_dien_ai_ultralytics"))

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLOv8 cho biển số Việt Nam")
    parser.add_argument("--data", type=Path, default=BACKEND_DIRECTORY / "datasets" / "license_plate_vn" / "data.yaml")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0", help="0 dùng RTX 3050; dùng cpu nếu cần")
    args = parser.parse_args()

    source_model = BACKEND_DIRECTORY / "yolov8n.pt"
    if not source_model.is_file():
        raise SystemExit("Thiếu backend/yolov8n.pt. Khởi động API một lần hoặc đặt model vào đây.")
    model = YOLO(str(source_model))
    run = model.train(
        data=str(args.data), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        device=args.device, project=str(BACKEND_DIRECTORY / "runs"), name="license_plate", exist_ok=True,
    )
    best_model = BACKEND_DIRECTORY / "runs" / "license_plate" / "weights" / "best.pt"
    if not best_model.is_file():
        raise SystemExit("Không tìm thấy best.pt sau khi train.")
    models_directory = BACKEND_DIRECTORY / "models"
    models_directory.mkdir(exist_ok=True)
    shutil.copy2(best_model, models_directory / "license_plate.pt")

    metrics = model.val(data=str(args.data), imgsz=args.imgsz, device=args.device)
    result = metrics.results_dict
    report = {
        "precision": result.get("metrics/precision(B)"),
        "recall": result.get("metrics/recall(B)"),
        "map50": result.get("metrics/mAP50(B)"),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "model": "models/license_plate.pt",
    }
    metrics_path = BACKEND_DIRECTORY / "data" / "model_metrics.json"
    metrics_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nTrain hoàn tất. Model đã đặt tại backend/models/license_plate.pt")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    del run


if __name__ == "__main__":
    main()
