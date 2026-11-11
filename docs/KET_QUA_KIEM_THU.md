# Kết quả kiểm thử ngày 12/11/2026

Môi trường: Mac ARM64, Python 3.11, Node.js 22. Dữ liệu kiểm thử nằm trong thư mục tạm; không thêm lượt xe vào cơ sở dữ liệu vận hành.

## Kiểm thử API và lưu ảnh: 9/9 đạt

Các bài này dùng AI giả lập để chủ động kiểm tra quyết định và lưu trữ; chúng không đo độ chính xác nhận diện.

| Bài kiểm thử | Kết quả |
| --- | --- |
| Xe vào, khung hình vào lặp, xe ra: lưu riêng ảnh vào/ra và liên kết phiên đúng | Đạt |
| Ảnh lưu phục vụ qua URL, đúng JPEG, kích thước và màu gần khớp khung PNG đầu vào | Đạt |
| Thiếu biển số: chờ, không tạo ảnh hoặc nhật ký | Đạt |
| Thiếu khuôn mặt: chờ, không tạo ảnh hoặc nhật ký | Đạt |
| Xe ra chưa có lượt vào: từ chối, giữ ảnh bằng chứng | Đạt |
| Khuôn mặt không khớp: từ chối, giữ phiên gửi xe mở | Đạt |
| Hướng di chuyển sai: HTTP 422, không lưu ảnh | Đạt |
| Tệp không có MIME ảnh: HTTP 415, không lưu ảnh | Đạt |
| Tạo lại API client và chạy lại startup: ảnh và nhật ký vẫn đọc được | Đạt |

Chạy lại từ thư mục `backend`:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Mô hình AI thật và frontend

- YOLOv8n + EasyOCR chạy trên ảnh trắng 640 × 480: không phát hiện đối tượng hoặc biển số, không lỗi.
- Bộ phát hiện khuôn mặt trên ảnh trắng: 0 khuôn mặt, không lỗi.
- FaceNet chạy tensor tổng hợp: đầu ra embedding kích thước `(1, 512)`.
- `npm --prefix frontend run build`: TypeScript và Vite hoàn thành thành công.
- `git diff --check`: đạt.

## Giới hạn

Chưa kiểm thử độ chính xác với người/biển số thật hoặc thao tác camera thực tế trên trình duyệt. Model biển số riêng từ Windows chưa được chuyển sang Mac. Việc tạo lại API client kiểm tra tính bền vững qua startup, không phải thử khởi động lại hệ điều hành. Hiện ảnh của lượt bị từ chối nhưng có đủ mặt và biển số cũng được lưu làm bằng chứng; khung hình đang chờ và khung hình vào lặp không tạo ảnh mới.

## Cập nhật chế độ hai webcam — 12/11/2026

Chạy lại sau thay đổi: **12/12 bài đạt**, thời gian chạy unittest 0,103 giây (không bao gồm thời gian import thư viện). Thêm ba bài: ảnh từ hai camera được đưa đúng dịch vụ AI và ghép đúng trái/phải cho cả hướng vào/ra; thiếu một ảnh trong chế độ hai camera trả 422; nội dung giả ảnh bị chặn. Bài hai camera dùng hai ảnh màu khác nhau và kiểm tra điểm ảnh của JPEG đã lưu. Đây là kiểm thử bằng AI giả lập, chưa có thiết bị camera thật.

Frontend build thành công. Kiểm tra trình duyệt xác nhận hai ô Camera khuôn mặt/Camera biển số và lựa chọn hướng ra đổi nhãn của cả hai ô.

## Cập nhật bảo vệ xác nhận và thanh chắn mô phỏng — 12/11/2026

**19/19 bài kiểm thử API đạt**, unittest 0,191 giây (không gồm import). Bổ sung kiểm thử xe đã vào nhưng lúc ra không trích xuất được mặt: có ảnh bằng chứng và yêu cầu chờ; đồng ý ghi `manual_approved` và đóng phiên; từ chối giữ phiên mở; bắt buộc tên/lý do; chặn xác nhận lặp; khôi phục yêu cầu sau tạo lại client; không cho yêu cầu cũ đóng một phiên mới; chặn mã yêu cầu không tồn tại. Bài sai mặt hiện kỳ vọng chờ bảo vệ thay vì từ chối ngay khi có phiên vào.

Đã chạy giao diện riêng trên cổng 5175 cùng API cổng 8011, SQLite và ảnh tổng hợp trong thư mục tạm. Trên trình duyệt đã nhập thông tin người xử lý, tích xác nhận, bấm nút cho xe ra và quan sát trạng thái **MỞ — BẢO VỆ XÁC NHẬN** cùng ảnh đã lưu. API trả HTTP 200. Hai máy chủ kiểm thử được tắt sau kiểm tra; dữ liệu vận hành không bị thêm lượt thử. Frontend build thành công.

Đây là kiểm thử luồng bằng AI giả lập không trả khuôn mặt, không phải thử khẩu trang trên người thật hoặc điều khiển thanh chắn IoT. Tên người xác nhận chưa gắn với tài khoản đăng nhập.
