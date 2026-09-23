"""Kiểm tra dataset YOLO trước khi train biển số."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def inspect_split(dataset_root: Path, split: str) -> tuple[int, int, list[str]]:
    images = list((dataset_root / "images" / split).glob("*"))
    image_files = [file for file in images if file.suffix.lower() in IMAGE_SUFFIXES]
    issues: list[str] = []
    labeled = 0
    for image in image_files:
        label = dataset_root / "labels" / split / f"{image.stem}.txt"
        if not label.is_file():
            issues.append(f"Thiếu nhãn: {label.relative_to(dataset_root)}")
            continue
        lines = [line.strip() for line in label.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            issues.append(f"Nhãn rỗng: {label.relative_to(dataset_root)}")
            continue
        valid = True
        for line_number, line in enumerate(lines, 1):
            values = line.split()
            try:
                category, *coordinates = [float(value) for value in values]
                if len(values) != 5 or int(category) != 0 or any(value <= 0 or value >= 1 for value in coordinates):
                    raise ValueError
            except ValueError:
                issues.append(f"Nhãn không hợp lệ: {label.relative_to(dataset_root)} dòng {line_number}")
                valid = False
        labeled += int(valid)
    return len(image_files), labeled, issues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "datasets" / "license_plate_vn")
    args = parser.parse_args()
    total_images = total_labeled = 0
    all_issues: list[str] = []
    for split in ("train", "val", "test"):
        images, labeled, issues = inspect_split(args.dataset, split)
        total_images += images
        total_labeled += labeled
        all_issues.extend(issues)
        print(f"{split}: {images} ảnh, {labeled} ảnh nhãn hợp lệ")
    print(f"Tổng: {total_images} ảnh, {total_labeled} ảnh sẵn sàng train")
    if not total_images:
        raise SystemExit("Dataset đang trống. Thêm ảnh và nhãn trước khi train.")
    if all_issues:
        print("\nLỗi cần sửa:")
        print("\n".join(f"- {issue}" for issue in all_issues[:30]))
        raise SystemExit(f"Dataset chưa hợp lệ ({len(all_issues)} lỗi).")


if __name__ == "__main__":
    main()
