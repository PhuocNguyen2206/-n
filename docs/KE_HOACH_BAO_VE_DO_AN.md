# Chuẩn bị báo cáo và bảo vệ tốt nghiệp

## Phạm vi sản phẩm hiện tại

Ứng dụng kiểm soát phương tiện ở cổng trường bằng biển số và khuôn mặt theo phiên vào/ra. Giao diện bảo vệ gồm bốn mục: Tổng quan, Giám sát cổng, Đối chiếu & lưu lượng, Nhật ký. Công cụ huấn luyện nằm ở backend, không đưa vào luồng vận hành.

Đã kiểm tra tự động phần lưu ảnh, liên kết phiên và một số quyết định nghiệp vụ bằng AI giả lập. Các mô hình thật đã chạy suy luận với dữ liệu tổng hợp. Những kiểm tra này chưa chứng minh độ chính xác nhận diện trong môi trường thật. Xem [biên bản kiểm thử](KET_QUA_KIEM_THU.md).

## Việc cần làm trước buổi demo thực tế

- Chép model từ Windows vào `backend/models/`, khởi động lại API, lưu kết quả `/api/v1/model/status` để biết chính xác model nào được dùng.
- Kết nối hai webcam riêng: một thu khuôn mặt, một thu biển số; chọn hướng kiểm tra vào/ra để thử lần lượt. Kiểm tra ánh sáng, khoảng cách và khung hình trước khi đo.
- Chạy `bash scripts/dev-mac.sh`; mở `http://127.0.0.1:5174`.
- Dùng người tham gia và xe đã đồng ý thử nghiệm. Chọn camera, bấm Bật camera rồi xác nhận hai luồng hình.
- Sao lưu `backend/data/` khi API đã tắt; giữ riêng dữ liệu demo và dữ liệu đo. Không commit ảnh khuôn mặt, cơ sở dữ liệu hoặc trọng số vào Git.

## Kịch bản demo khoảng 7–10 phút

1. Nêu bài toán: chỉ cho xe ra khi biển số có phiên vào và người đi ra khớp một người đã vào cùng xe.
2. Mở Tổng quan, giải thích trạng thái kết nối; chuyển Giám sát và chọn hai webcam.
3. Người A cùng xe X vào: kiểm tra quyết định cho phép, ảnh đã lưu và nhật ký.
4. Dừng camera, chọn hướng lối ra rồi bật lại. Người B cùng biển số X ra: kỳ vọng từ chối, phiên vẫn mở. Thực hiện trước bước 5 để phiên vào còn tồn tại.
5. Người A cùng xe X ra: kỳ vọng cho phép và đóng phiên; mở Đối chiếu để chỉ ảnh vào/ra.
6. Xe Y chưa có lượt vào xin ra: kỳ vọng từ chối.
7. Che mặt hoặc đưa biển số ra khỏi khung: kỳ vọng chờ dữ liệu, không kết luận nhận diện thành công.
8. Mở Nhật ký, chọn thời gian và ảnh bằng chứng. Nêu giới hạn lịch sử đang hiển thị.

Nếu camera hoặc API gặp lỗi, dừng demo tự động và kiểm tra kết nối. Có thể trình diễn quy trình bảo vệ xác nhận tại Giám sát cổng, nhưng không tuyên bố đã mở barrier vật lý. Chuẩn bị video ghi lại một lần chạy thật làm phương án dự phòng; ghi rõ đây là video.

## Bố cục báo cáo đề xuất

| Chương | Nội dung và minh chứng cần có |
| --- | --- |
| 1. Bài toán và phạm vi | Nhu cầu cổng trường, tác nhân, điều kiện vận hành, tiêu chí nghiệm thu |
| 2. Cơ sở lý thuyết | Phát hiện biển số, OCR, phát hiện mặt, embedding và cosine similarity; dẫn đúng nguồn mô hình đã sử dụng |
| 3. Phân tích và thiết kế | Use case, kiến trúc React → FastAPI → dịch vụ AI/SQLite, luồng vào/ra, bảng dữ liệu và nơi lưu ảnh |
| 4. Hiện thực | Công nghệ, cấu hình Mac, model thực tế được nạp, ảnh chụp bốn màn hình vận hành |
| 5. Thực nghiệm | Bộ dữ liệu, cách chia tập, điều kiện webcam, phương pháp đo, số liệu thô, lỗi và kết quả |
| 6. Kết luận | Phần đạt được, giới hạn, hướng cải tiến có thứ tự ưu tiên |

Không dùng kết quả kiểm thử giả lập làm số liệu độ chính xác AI. Nếu chỉ tích hợp model có sẵn, ghi rõ phần tích hợp và phần tự huấn luyện; không nhận kết quả huấn luyện của người khác là của mình. Đối chiếu các hình trong `docs/training-results/` với log và file trọng số gốc trước khi đưa vào báo cáo.

## Phiếu đo thực tế

Dùng [mẫu CSV](MAU_KIEM_THU_THUC_TE.csv), mỗi dòng là một tình huống quan sát được. Các dòng có sẵn là kế hoạch, chưa phải kết quả. Sau mỗi lần chạy, ghi thời gian, điều kiện, biển số thật, kết quả đọc, người A/B bằng mã, quyết định kỳ vọng/thực tế, thời gian phản hồi và tên ảnh. Không điền số liệu ước lượng.

Tối thiểu thử cùng người/cùng xe, khác người/cùng xe, xe chưa vào, thiếu mặt, thiếu biển số, khung vào lặp; lặp lại ở nhiều điều kiện sáng và khoảng cách. Quy mô và tiêu chí đạt cần thống nhất với giảng viên trước khi đo.

Các chỉ tiêu có thể báo cáo từ dữ liệu thực:

- Tỷ lệ đọc đúng toàn bộ biển số = số lượt đọc đúng / số lượt có biển số đủ điều kiện theo quy tắc đã công bố.
- Tỷ lệ quyết định đúng = số lượt quyết định đúng / số tình huống đã gán kết quả kỳ vọng; báo riêng số lượt chờ.
- Tỷ lệ cho nhầm người không hợp lệ và từ chối nhầm người hợp lệ; công bố cả tử số và mẫu số.
- Thời gian phản hồi trung vị và p95 nếu có đủ mẫu, kèm cấu hình phần cứng và model.
- Precision/Recall/mAP cho detector chỉ khi có tập test gán nhãn và đầu ra đánh giá thực tế; không suy ra từ kiểm thử API.

## Giới hạn cần trình bày trung thực

- Model biển số riêng trên Windows chưa được xác minh trên Mac trong các lần kiểm thử đã ghi nhận.
- Chưa đánh giá ánh sáng yếu, góc nghiêng, tốc độ xe, nhiều xe chung khung hình và chống giả mạo bằng ảnh/video.
- Chưa có phân quyền/xác thực, chính sách tự xóa ảnh hoặc tích hợp barrier phần cứng.
- Biểu đồ dùng danh sách sự kiện gần đây, chưa phải báo cáo toàn bộ dữ liệu. Trang Nhật ký đã tìm trên toàn bộ SQLite với phân trang 20 lượt.
- Hai webcam hiện tách vai trò mặt/biển số cho một hướng kiểm tra tại một thời điểm; muốn chạy hai làn đồng thời cần mở rộng thành bốn camera.

## Hồ sơ nên mang khi bảo vệ

Mã nguồn theo commit đã chốt; hướng dẫn chạy; bản báo cáo theo mẫu của trường; slide theo thời lượng quy định; bảng kết quả đo gốc; log đánh giá mô hình; ảnh/video chạy thật; ghi nhận nguồn và quyền sử dụng model/dữ liệu. Chỉ chốt trạng thái “sẵn sàng bảo vệ” sau khi bổ sung và kiểm tra các phần thực nghiệm còn thiếu.

## Bổ sung demo khẩu trang/áo mưa

Tạo lượt vào bình thường, dừng camera và chuyển sang lối ra; dùng cùng biển số, thử che mặt bằng khẩu trang. Nếu không xác minh được mặt, giao diện phải giữ thanh chắn mô phỏng, hiển thị ảnh vào/ra và yêu cầu bảo vệ. Nhập người xử lý, lý do, kiểm tra trực tiếp rồi bấm xác nhận. Kiểm tra trạng thái mở mô phỏng, nhật ký “Bảo vệ cho ra” và phiên đã đóng. Có thể thử chọn “Không cho xe ra” ở lần chạy khác để kiểm tra phiên còn mở. Khẩu trang có thể vẫn được AI nhận diện; ghi đúng kết quả quan sát, không ép diễn giải mọi trường hợp khẩu trang là thất bại.
