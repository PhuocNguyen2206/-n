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
# Khuôn mặt phải "rõ" mới được dùng để cho xe qua. Lớp 1: độ tin cậy của MTCNN (mặt bị che thường thấp hơn).
# Đo trên 300 ảnh LFW: 0,995 loại 1 mặt rõ, bắt được 228 mặt bị che mắt và 39 mặt bị che miệng.
FACE_MIN_CONFIDENCE = _float("FACE_MIN_CONFIDENCE", 0.995)
# Lớp 2: hỏi VLM xem mắt, mũi, miệng có bị che không. Đo: đúng 78/80 mặt rõ; bắt thêm 65/80 mặt bị che mắt đã lọt lớp 1.
FACE_VLM_CHECK = os.getenv("FACE_VLM_CHECK", "1").strip().lower() in {"1", "true", "yes", "on"}
# Hai xe đi sát nhau: chỉ xét biển to nhất (xe gần cổng nhất). Biển thứ hai to từ mức này (theo diện tích)
# so với biển to nhất thì coi như có hai xe ngang nhau, cổng không quyết định.
CROWDED_PLATE_RATIO = _float("CROWDED_PLATE_RATIO", 0.6)
# Khuôn mặt hẹp hơn mức này so với mặt người lái bị coi là người phía sau, không tính vào xe đang quét.
FACE_MIN_RELATIVE_SIZE = _float("FACE_MIN_RELATIVE_SIZE", 0.6)
# Dung lượng tối đa của một ảnh tải lên (MB).
MAX_UPLOAD_MB = _float("MAX_UPLOAD_MB", 10)
# Phiên đăng nhập của bảo vệ (giờ).
SESSION_HOURS = _float("SESSION_HOURS", 12)
# Tài khoản quản trị tạo lần đầu khi cơ sở dữ liệu chưa có tài khoản nào.
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
# Chế độ "Xem thử": khách chưa đăng nhập được gửi ảnh để thử nhận diện (không lưu). Mặc định tắt.
GUEST_DEMO = os.getenv("GUEST_DEMO", "0").strip().lower() in {"1", "true", "yes", "on"}
# Giới hạn chung cho mọi khách, để người ngoài không làm nghẽn máy chủ đang chạy cổng thật.
GUEST_DEMO_PER_MINUTE = int(_float("GUEST_DEMO_PER_MINUTE", 30))
GUEST_DEMO_MAX_PIXELS = 25_000_000
# Đặt COOKIE_SECURE=1 khi chạy sau HTTPS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0").strip().lower() in {"1", "true", "yes", "on"}
