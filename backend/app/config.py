"""Cấu hình đọc từ biến môi trường, có giá trị mặc định dùng cho demo."""

import os
from pathlib import Path

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def data_directory() -> Path:
    """Thư mục chứa SQLite và ảnh bằng chứng (mặc định ``backend/data``)."""
    configured = Path(os.getenv("DATA_DIR", "data"))
    return configured if configured.is_absolute() else BACKEND_DIRECTORY / configured


# Ngưỡng cosine của FaceNet. Đánh giá trên LFW (6.000 cặp): 0,45 cho FAR 0,37 %, FRR 1,73 %.
FACE_MATCH_THRESHOLD = _float("FACE_MATCH_THRESHOLD", 0.45)
# OCR đọc đúng định dạng nhưng có ký tự độ tin cậy thấp hơn mức này thì hỏi thêm VLM.
OCR_MIN_CHAR_CONFIDENCE = _float("OCR_MIN_CHAR_CONFIDENCE", 0.5)
# Dung lượng tối đa của một ảnh tải lên (MB).
MAX_UPLOAD_MB = _float("MAX_UPLOAD_MB", 10)
# Phiên đăng nhập của bảo vệ (giờ).
SESSION_HOURS = _float("SESSION_HOURS", 12)
# Tài khoản quản trị tạo lần đầu khi cơ sở dữ liệu chưa có tài khoản nào.
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
# Đặt COOKIE_SECURE=1 khi chạy sau HTTPS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0").strip().lower() in {"1", "true", "yes", "on"}
