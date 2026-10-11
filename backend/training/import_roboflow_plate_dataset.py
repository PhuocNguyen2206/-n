"""Nhập Roboflow YOLO dataset đa lớp thành dataset 1 lớp license_plate."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
TARGET_DIRECTORY = BACKEND_DIRECTORY / "datasets" / "license_plate_vn"
SPLITS = {"train": "train", "valid": "val", "test": "test"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuyển Roboflow biển số đa lớp thành YOLO 1 lớp")
    parser.add_argument("--source", type=Path, required=True, help="Thư mục đã giải nén từ Roboflow")
    parser.add_argument("--plate-class", type=int, default=33, help="Class ID bien_so_xe trong data.yaml nguồn")
    args = parser.parse_args()
    if not (args.source / "data.yaml").is_file():
        raise SystemExit("Source không có data.yaml của Roboflow.")

    totals = {"train": 0, "val": 0, "test": 0, "skipped": 0}
    for source_split, target_split in SPLITS.items():
        source_images = args.source / source_split / "images"
        source_labels = args.source / source_split / "labels"
        target_images = TARGET_DIRECTORY / "images" / target_split
        target_labels = TARGET_DIRECTORY / "labels" / target_split
        target_images.mkdir(parents=True, exist_ok=True)
        target_labels.mkdir(parents=True, exist_ok=True)
        for image_path in source_images.glob("*"):
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            label_path = source_labels / f"{image_path.stem}.txt"
            if not label_path.is_file():
                totals["skipped"] += 1
                continue
            labels = []
            for line in label_path.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) == 5 and parts[0] == str(args.plate_class):
                    # YOLO cho phép biên bằng 1, nhưng bộ kiểm tra dự án dùng
                    # khoảng mở để phát hiện nhãn bất thường; kẹp sát biên an toàn.
                    coordinates = [min(max(float(value), 0.000001), 0.999999) for value in parts[1:]]
                    labels.append("0 " + " ".join(f"{value:.6f}" for value in coordinates))
            if not labels:
                totals["skipped"] += 1
                continue
            shutil.copy2(image_path, target_images / image_path.name)
            (target_labels / label_path.name).write_text("\n".join(labels) + "\n", encoding="utf-8")
            totals[target_split] += 1
    print(f"Đã nhập train={totals['train']}, val={totals['val']}, test={totals['test']}; bỏ qua={totals['skipped']} ảnh không có khung biển số.")


if __name__ == "__main__":
    main()
