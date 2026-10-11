# Nguồn dataset

## Vietnamese-license-plate v6

- Nguồn: Roboflow Universe, `vietnameselisenceplate/vietnamese-license-plate-olqpu`, version 6.
- License: CC BY 4.0.
- Dùng để huấn luyện model **phát hiện vùng biển số** trong đồ án.
- Dataset gốc có 34 lớp gồm ký tự và `bien_so_xe`; script `backend/training/import_roboflow_plate_dataset.py` chỉ giữ lớp `bien_so_xe`, chuyển thành lớp `license_plate` (ID 0) cho model detector của dự án.

Tài liệu/trang dataset: https://universe.roboflow.com/vietnameselisenceplate/vietnamese-license-plate-olqpu/dataset/6
