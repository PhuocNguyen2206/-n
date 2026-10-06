# Model biển số được tích hợp

Hệ thống hỗ trợ pipeline hai tầng để đọc biển số:

1. `backend/models/plate_best.pt`: phát hiện vùng biển số.
2. `backend/models/chars_best.pt`: phát hiện ký tự trong vùng biển số, sau đó ghép theo thứ tự đọc.

Hai model này được cung cấp từ repository `thinhdang1104/license-plate-recognition` theo sự cho phép của tác giả mà chủ dự án đã xác nhận ngày 06/10/2026. Model chỉ được dùng cho mục đích đồ án/học tập theo sự đồng ý đó.

Các file `.pt` không được đưa vào Git để tránh công khai lại model khi không có một giấy phép phân phối riêng. Muốn chạy ở máy khác, hãy chép cả hai file trên vào đúng thư mục `backend/models/`.
