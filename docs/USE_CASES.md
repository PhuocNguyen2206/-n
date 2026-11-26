# Use case — Kiểm soát phương tiện tại cổng trường

Phạm vi giao diện vận hành: Tổng quan, Giám sát cổng, Đối chiếu & lưu lượng, Nhật ký, Ủy quyền lấy xe và Tài khoản. Mọi API nghiệp vụ và ảnh bằng chứng yêu cầu đăng nhập; chỉ `/api/v1/health` và `/api/v1/model/status` công khai. Quản trị viên quản lý tài khoản bảo vệ; bảo vệ chỉ đổi được mật khẩu của mình.

## Tác nhân

| Tác nhân | Vai trò |
| --- | --- |
| Người điều khiển xe | Đưa xe và khuôn mặt vào vùng quan sát |
| Bảo vệ | Đăng nhập, chọn camera, giám sát kết quả, duyệt xe ra, ghi ủy quyền lấy xe hộ, tra cứu ảnh |
| Quản trị viên | Như bảo vệ, thêm quyền tạo/khóa tài khoản |
| Chủ xe, người lấy xe hộ | Chủ xe đã gửi xe nhờ người khác lấy ra; người lấy hộ cho chụp mặt và đọc MSSV/CCCD |
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

Bảo vệ chọn khoảng thời gian, đọc biển số, hướng di chuyển, quyết định và lý do; bấm ảnh thu nhỏ để mở bằng chứng. Trang Nhật ký truy vấn toàn bộ SQLite theo biển số và khoảng thời gian, phân trang 20 lượt. Màn hình Tổng quan chỉ hiện 6 lượt gần nhất. Bấm dòng nhật ký mở đúng ảnh theo mã sự kiện, kèm biển số, hướng, thời gian, kết quả và lý do; nếu ảnh không được lưu hoặc đã mất, giao diện thông báo thay vì hiện ảnh của lượt khác.

## UC-05 — Đối chiếu và xem lưu lượng

Màn hình đối chiếu hiển thị một phiên từ danh sách gần đây, với ảnh vào/ra nếu có. Biểu đồ tổng hợp các sự kiện đã tải trong ngày, không phải báo cáo đầy đủ toàn bộ bãi xe. Cần bổ sung API tổng hợp nếu mở rộng quy mô.

## Công cụ phát triển mô hình

Người thực hiện đồ án thao tác trong `backend/training/`, `backend/datasets/` và `backend/models/`. Kiểm tra mô hình tại `GET /api/v1/model/status`, tài liệu API tại `/docs`. Chưa có trang quản trị có xác thực/phân quyền; không mô tả như một chức năng đã hoàn thành trong báo cáo.

## UC-06 — Bảo vệ xác nhận xe ra

Điều kiện: biển số có phiên vào đang mở và có yêu cầu xác minh khuôn mặt chưa xử lý. Màn hình giữ ảnh của yêu cầu và tạm dừng quét cổng. Bảo vệ so sánh ảnh vào/ra, kiểm tra người/xe trực tiếp, nhập tên, lý do và xác nhận. Nếu cho ra, ghi `manual_approved`, gắn ảnh của yêu cầu vào lượt ra và đóng phiên; thanh chắn mô phỏng đổi sang mở. Nếu từ chối, ghi `denied`, phiên vẫn mở. Yêu cầu đã xử lý hoặc phiên đã đóng không được duyệt lại. Tên người xử lý là dữ liệu nhập, chưa có xác thực đăng nhập. Không có phần cứng barrier.

## UC-07 — Ủy quyền lấy xe hộ (xe mượn)

Điều kiện: bảo vệ đã đăng nhập; xe đang có lượt vào mở (đang ở trong bãi).

1. Chủ xe báo bảo vệ (gặp trực tiếp hoặc gọi điện) rằng người C sẽ lấy xe X ra.
2. Bảo vệ mở **Ủy quyền lấy xe**, nhập biển số X, tên chủ xe, tên và MSSV/CCCD của C, thời hạn (tối đa 24 giờ), ghi chú.
3. Bảo vệ chụp mặt C từ camera khuôn mặt hoặc chọn ảnh. Hệ thống trích đặc trưng FaceNet và lưu ủy quyền gắn với đúng lượt gửi xe.
4. Lúc ra, nếu mặt người lái không khớp người lúc vào, hệ thống so tiếp với các ủy quyền còn hiệu lực của lượt đó. Khớp (≥ ngưỡng) thì cho phép, ghi lý do "Người được ủy quyền lấy xe", đóng phiên và đánh dấu ủy quyền đã dùng.

Ngoại lệ: biển số không có lượt vào mở → không tạo được ủy quyền. Ảnh không có mặt rõ → yêu cầu chụp lại. Ủy quyền hết hạn, đã hủy, đã dùng, hoặc người ra không khớp ủy quyền → chuyển bảo vệ kiểm tra (UC-06). Chủ xe tự lấy xe ra → các ủy quyền chưa dùng của lượt đó hết hiệu lực.

## UC-08 — Đăng nhập và quản lý tài khoản

1. Người dùng nhập tên đăng nhập và mật khẩu. Hệ thống cấp cookie phiên HttpOnly (12 giờ).
2. Tài khoản mới hoặc tài khoản quản trị mặc định phải đổi mật khẩu trước khi dùng chức năng khác.
3. Quản trị viên tạo tài khoản bảo vệ (mật khẩu tạm) hoặc khóa tài khoản; tài khoản bị khóa mất phiên ngay.

Ngoại lệ: sai mật khẩu → báo lỗi chung, không tiết lộ tài khoản có tồn tại hay không. Hết phiên → quay về màn hình đăng nhập.
