# Hệ thống quản lý phương tiện trường học tích hợp AI

Sản phẩm đồ án kiểm soát phương tiện tại cổng trường bằng hai luồng ảnh: biển số xe và khuôn mặt người điều khiển.

## Chức năng đã có

- Đăng ký chủ xe, biển số và mẫu khuôn mặt.
- Quét riêng ảnh khuôn mặt và ảnh xe/biển số, phù hợp mô phỏng hai camera.
- Màn hình làn xe thời gian thực: mở hai luồng camera, quét tự động mỗi 3 giây và hiển thị quyết định cho phép/từ chối tại chỗ.
- YOLOv8 phát hiện xe/người; EasyOCR đọc ký tự biển số; FaceNet tạo đặc trưng khuôn mặt trên CPU.
- Cơ chế fail-closed: chỉ `approved` khi biển số thuộc xe đã đăng ký và khuôn mặt hợp lệ. Mọi trường hợp khác bị từ chối và ghi nhật ký.
- Phiên gửi xe: khi xe vào, hệ thống ghi nhận chủ xe và những người đi cùng đã đăng ký; lúc xe ra, một trong những người đó điều khiển xe vẫn hợp lệ.
- Dashboard cho bảo vệ: thống kê, danh sách chủ xe, trạng thái khuôn mặt, nhật ký vào/ra và lý do từ chối.
- API REST có Swagger để tích hợp camera thực tế: `http://localhost:8000/docs`.

## Chạy sản phẩm

```bash
docker compose up --build
```

- Dashboard: `http://localhost:5173`
- API: `http://localhost:8000/api/v1/health`
- Swagger: `http://localhost:8000/docs`

Khi phát triển cục bộ, chạy API từ `backend` và frontend từ `frontend`; trang web dùng `http://127.0.0.1:5174`.

## Luồng demo

1. Đăng ký một chủ xe với ảnh chân dung rõ và biển số.
2. Khi xe vào có nhiều người, chọn nhiều ảnh khuôn mặt và một ảnh biển số; tất cả người đã đăng ký được ghi vào phiên gửi xe.
3. Ở `Quét kiểm soát cổng`, chọn ảnh khuôn mặt và ảnh biển số, rồi chọn xe vào hoặc xe ra.
4. Xem quyết định và chi tiết trong `Nhật ký ra vào`.

## Camera thực tế

Mục `Làn xe thời gian thực` dùng camera được trình duyệt cấp quyền. Bấm `Bật camera tại làn xe`, chọn lối vào hoặc lối ra rồi bấm `Bắt đầu quét tự động`. Khi triển khai tương tự cổng thương mại, thay camera trình duyệt bằng hai camera IP/RTSP (một camera góc mặt, một camera góc biển số) và kết nối đầu ra relay/barrier với quyết định `approved` của API.

## Mô hình và dữ liệu

YOLOv8, EasyOCR và FaceNet được tự tải lần đầu khi sử dụng. Để đạt chỉ tiêu độ chính xác của đề tài trên dữ liệu thực tế, cần huấn luyện model biển số riêng từ dữ liệu đã gán nhãn và đặt tệp trọng số tại `backend/models/license_plate.pt`. Trọng số mô hình và ảnh khuôn mặt không được đưa lên GitHub.
