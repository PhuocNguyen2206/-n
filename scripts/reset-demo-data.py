"""Chuẩn bị dữ liệu sạch trước buổi demo mà KHÔNG xóa gì.

Chuyển cơ sở dữ liệu SQLite và ảnh bằng chứng hiện tại vào
``backend/data/backup-<thời gian>/``. Lần chạy API tiếp theo tạo cơ sở dữ liệu
mới (tài khoản quản trị mặc định admin / admin123, bắt buộc đổi mật khẩu).
Muốn quay lại dữ liệu cũ: tắt API rồi chép các tệp trong thư mục backup về.

Chạy khi đã TẮT API:
    Windows: backend\\.venv\\Scripts\\python.exe scripts\\reset-demo-data.py
    macOS:   backend/.venv/bin/python scripts/reset-demo-data.py
"""

import shutil
from datetime import datetime
from pathlib import Path

data = Path(__file__).resolve().parents[1] / "backend" / "data"
targets = [data / "vehicle_ai.db", data / "vehicle_ai.db-journal", data / "evidence"]
existing = [path for path in targets if path.exists()]
if not existing:
    print("Không có dữ liệu cũ; không cần làm gì.")
    raise SystemExit(0)
backup = data / f"backup-{datetime.now():%Y%m%d-%H%M%S}"
backup.mkdir(parents=True)
for path in existing:
    shutil.move(str(path), str(backup / path.name))
    print(f"Đã chuyển {path.name} -> {backup}")
print("Xong. Khởi động lại API để tạo dữ liệu mới.")
