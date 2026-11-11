# Use case — Kiểm soát phương tiện tại cổng trường

Phạm vi giao diện vận hành: Tổng quan, Giám sát cổng, Đối chiếu & lưu lượng, Nhật ký. Không có trang xử lý ngoại lệ hoặc huấn luyện mô hình riêng dành cho bảo vệ. Xác nhận xe ra thủ công được tích hợp tại màn hình giám sát. Backend vẫn giữ API kỹ thuật về dữ liệu, mô hình và lượt thủ công để tương thích; việc bỏ menu không đồng nghĩa có cơ chế phân quyền hay khóa API.

## Tác nhân

| Tác nhân | Vai trò |
| --- | --- |
| Người điều khiển xe | Đưa xe và khuôn mặt vào vùng quan sát |
| Bảo vệ | Chọn camera, giám sát kết quả và tra cứu ảnh |
| Webcam | Hai webcam: một thu mặt, một thu biển số; chọn hướng vào/ra để thử lần lượt |
| Hệ thống | Đọc biển số, trích đặc trưng khuôn mặt, đối chiếu và lưu lượt |

## UC-01 — Ghi nhận xe vào

Điều kiện: API hoạt động, camera được cấp quyền, đã có mô hình phù hợp.

1. Bảo vệ chọn hướng lối vào, webcam mặt và webcam biển số rồi bật hai camera.
2. Hệ thống gửi khung hình để đọc biển số và trích đặc trưng các khuôn mặt.
3. Nếu đủ dữ liệu và chưa có phiên mở cho biển số, hệ thống tạo phiên gửi xe.
4. Lưu ảnh bằng chứng, nhật ký và các đặc trưng khuôn mặt.
5. Hiển thị ảnh đã lưu, biển số và thời gian tại làn.

Khung hình tự động thiếu mặt hoặc biển số: chờ, không tạo nhật ký mới. Biển số đã có phiên mở: bỏ qua khung vào lặp, không tạo ảnh mới.

## UC-02 — Xác minh xe ra

1. Bảo vệ dừng camera, chuyển hướng lối ra, bật lại hai camera; gửi ảnh mặt và biển số trong một yêu cầu.
2. Tìm phiên đang mở theo biển số.
3. So sánh khuôn mặt với các đặc trưng đã lưu của phiên đó.
4. Nếu điểm tương đồng lớn nhất đạt ngưỡng hiện hành 0,45: cho phép và đóng phiên.
5. Lưu ảnh và nhật ký; hiển thị kết quả.

Không có phiên vào: từ chối. Có phiên vào nhưng mặt không khớp hoặc không thấy mặt: tạo yêu cầu chờ bảo vệ. Nếu đủ mặt và biển số, lượt bị từ chối cũng lưu ảnh bằng chứng. Thiếu dữ liệu trong chế độ tự động: chờ. Ngưỡng 0,45 là cấu hình hiện tại, chưa phải kết quả tối ưu trên tập kiểm thử thực tế.

## UC-03 — Giám sát thiết bị

Bảo vệ tìm camera, chọn hai webcam khác nhau theo vai trò mặt/biển số và hướng kiểm tra. Khi camera đang chạy, lựa chọn hướng/thiết bị bị khóa; dừng camera trước khi đổi. Mỗi chu kỳ quét gửi ảnh mặt trước, biển số sau với `paired_cameras=true`; API xử lý khuôn mặt chỉ ở ảnh thứ nhất và biển số chỉ ở ảnh thứ hai. Ảnh bằng chứng ghép hai ảnh theo thứ tự trái/phải. Hai ảnh cùng chu kỳ là giả định một người/xe đang thử, không phải đồng bộ phần cứng hoặc theo dõi nhiều xe. Kết quả cho phép là quyết định phần mềm, chưa điều khiển barrier vật lý.

## UC-04 — Tra cứu nhật ký

Bảo vệ chọn khoảng thời gian, đọc biển số, hướng di chuyển, quyết định và lý do; bấm ảnh thu nhỏ để mở bằng chứng. Giới hạn hiện tại: API trả mặc định 20 lượt gần nhất, giao diện hiển thị tối đa 6 lượt phù hợp. Bộ lọc áp dụng trên dữ liệu đã tải, chưa phải truy vấn toàn bộ lịch sử.

## UC-05 — Đối chiếu và xem lưu lượng

Màn hình đối chiếu hiển thị một phiên từ danh sách gần đây, với ảnh vào/ra nếu có. Biểu đồ tổng hợp các sự kiện đã tải trong ngày, không phải báo cáo đầy đủ toàn bộ bãi xe. Cần bổ sung API tổng hợp nếu mở rộng quy mô.

## Công cụ phát triển mô hình

Người thực hiện đồ án thao tác trong `backend/training/`, `backend/datasets/` và `backend/models/`. Kiểm tra mô hình tại `GET /api/v1/model/status`, tài liệu API tại `/docs`. Chưa có trang quản trị có xác thực/phân quyền; không mô tả như một chức năng đã hoàn thành trong báo cáo.

## UC-06 — Bảo vệ xác nhận xe ra

Điều kiện: biển số có phiên vào đang mở và có yêu cầu xác minh khuôn mặt chưa xử lý. Màn hình giữ ảnh của yêu cầu và tạm dừng quét cổng. Bảo vệ so sánh ảnh vào/ra, kiểm tra người/xe trực tiếp, nhập tên, lý do và xác nhận. Nếu cho ra, ghi `manual_approved`, gắn ảnh của yêu cầu vào lượt ra và đóng phiên; thanh chắn mô phỏng đổi sang mở. Nếu từ chối, ghi `denied`, phiên vẫn mở. Yêu cầu đã xử lý hoặc phiên đã đóng không được duyệt lại. Tên người xử lý là dữ liệu nhập, chưa có xác thực đăng nhập. Không có phần cứng barrier.
