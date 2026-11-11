# Model chạy nhận diện biển số

Để bật nhận diện biển số hai tầng, đặt hai file sau tại thư mục này:

- `plate_best.pt`: phát hiện vùng biển số.
- `chars_best.pt`: đọc ký tự của biển số.

Khi hai file xuất hiện, API sẽ tự ưu tiên chúng (trừ khi có `license_plate.pt` được ưu tiên làm detector). Khởi động lại API sau khi chép. Kiểm tra mô hình tại `http://127.0.0.1:8000/api/v1/model/status`. Giao diện bảo vệ không có trang huấn luyện; công cụ dữ liệu và mô hình được giữ ở backend. Các file model không được đưa vào Git; xem `docs/THIRD_PARTY_MODELS.md` để biết cách sử dụng ở máy khác.
