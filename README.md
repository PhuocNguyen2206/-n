# Hệ thống quản lý phương tiện tích hợp AI

MVP cho đồ án nhận diện biển số và khuôn mặt người điều khiển tại cổng trường.

## Thành phần

- `backend/`: REST API FastAPI, SQLite và quy tắc đối soát chủ xe.
- `frontend/`: dashboard React cho bảo vệ và quản trị viên.
- `docker-compose.yml`: chạy đồng thời API và giao diện.

## Chạy nhanh bằng Docker

```bash
docker compose up --build
```

- Dashboard: `http://localhost:5173`
- API và tài liệu Swagger: `http://localhost:8000/docs`

## Luồng kiểm soát hiện có

1. Camera/AI gửi biển số, mã khuôn mặt (hoặc ID người đã xác thực) và độ tin cậy.
2. API tìm phương tiện theo biển số, sau đó xác nhận chủ xe hoặc quyền mượn xe còn hiệu lực.
3. Hệ thống lưu lượt vào/ra, trả về trạng thái `approved`, `manual_review` hoặc `denied`.

Mô-đun AI hiện là điểm tích hợp rõ ràng tại `backend/app/services/vision.py`. Khi có dataset và model đã huấn luyện, thay bộ mô phỏng bằng YOLO + OCR + ArcFace mà không đổi API/dashboard.
