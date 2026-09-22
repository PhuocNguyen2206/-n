# Kế hoạch hoàn thiện và demo bảo vệ đồ án

## Mục tiêu demo

Trình diễn luồng xe vào - xe ra theo thời gian thực: AI quét, bảo vệ nhận quyết định, ảnh bằng chứng được lưu và có thể đối chiếu lại.

## Tiến độ

| Hạng mục | Trạng thái | Tiêu chí hoàn thành |
| --- | --- | --- |
| Camera thời gian thực 2 làn | Đã có | Nhận được hình từ webcam/DroidCam |
| Nhận diện khuôn mặt | Đã có | Vẽ khung mặt trực tiếp trên video |
| YOLO & OCR cơ bản | Đã có | Phát hiện người/xe; đọc biển số khi ảnh đủ rõ |
| Nhật ký và lọc theo giờ | Đã có | Có ảnh bằng chứng và lọc khoảng thời gian |
| So sánh ảnh vào - ra | Đã có | Hiển thị song song ảnh, biển số và kết luận |
| Bảng điều khiển bảo vệ/barrier | Đã có | Đèn xanh/đỏ, quyết định lớn, trạng thái barrier |
| Biểu đồ lượt xe theo giờ | Đã có | Cập nhật theo dữ liệu trong ngày |
| Tự nhận làn theo camera | Đã có | Camera 01 gửi lượt vào, Camera 02 gửi lượt ra |
| Model biển số Việt Nam riêng | Cần dữ liệu | Huấn luyện/đưa vào model chuyên biệt |
| Kết nối barrier phần cứng | Tùy chọn | Relay/Arduino nhận lệnh mở khi được duyệt |

## Kịch bản trình diễn hội đồng

1. Mở web, chọn DroidCam cho làn vào và làn ra.
2. Cho khuôn mặt và xe vào khung hình; hệ thống ghi nhận lượt vào.
3. Trình bày ảnh/lượt vào được lưu trong nhật ký.
4. Cho cùng người xuất hiện ở làn ra; hệ thống hiển thị đối chiếu ảnh vào-ra và trạng thái cho phép.
5. Dùng khuôn mặt khác để mô phỏng tình huống rủi ro; hệ thống chuyển cảnh báo đỏ và barrier giữ nguyên.
6. Mở biểu đồ để trình bày lưu lượng xe trong ngày và dùng bộ lọc lịch sử theo giờ.

## Lưu ý khi bảo vệ

- Dùng ảnh/camera đủ sáng, mặt rõ, biển số không rung hoặc quá xa.
- Không tuyên bố độ chính xác tuyệt đối: nêu rõ bản demo dùng YOLO tổng quát; model biển số Việt Nam chuyên biệt là hướng mở rộng có dữ liệu được gán nhãn.
- Không lưu nhận dạng cá nhân dài hạn ngoài mục tiêu demo; chỉ dùng ảnh bằng chứng/lượt xe theo chính sách nhà trường.
