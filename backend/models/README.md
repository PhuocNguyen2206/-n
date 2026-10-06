# Model chạy nhận diện biển số

Để bật nhận diện biển số hai tầng, đặt hai file sau tại thư mục này:

- `plate_best.pt`: phát hiện vùng biển số.
- `chars_best.pt`: đọc ký tự của biển số.

Khi hai file xuất hiện, API sẽ tự ưu tiên chúng và mục **Dữ liệu & Model** trên web hiển thị trạng thái “đọc biển số 2 tầng”. Các file model không được đưa vào Git; xem `docs/THIRD_PARTY_MODELS.md` để biết cách sử dụng ở máy khác.
