# Kết quả kiểm thử — cập nhật 27/11/2026

Máy chạy: Windows 11, Intel Core i5-12400F, GPU NVIDIA (Ollama), Python 3.12, Node.js 22.
Toàn bộ số liệu dưới đây chạy lại được bằng lệnh ghi kèm, trên mã nguồn nhánh `hoan-thien-do-an`.

## 1. Kiểm thử tự động: 52/52 bài đạt

```
cd backend
.venv\Scripts\python.exe -m pytest -q tests      # Mac: .venv/bin/python -m pytest -q tests
52 passed in ~11 s
```

Không cần GPU, Ollama hay camera. Mỗi bài dùng SQLite và thư mục ảnh tạm, không đụng dữ liệu vận hành.

| Tệp | Số bài | Nội dung |
|---|---|---|
| `tests/test_api.py` | 19 | Luồng nghiệp vụ qua API thật (FastAPI TestClient) với AI giả lập |
| `tests/test_vlm.py` | 23 | Client Ollama: định dạng biển số, Ollama tắt/thiếu model/lỗi 500, VLM bận, phát hiện chuỗi "8888…" rồi nạp lại model |
| `tests/test_vision_fallback.py` | 10 | Luật kết hợp OCR + VLM: OCR hợp lệ không gọi VLM, OCR rỗng/sai định dạng/kém tin cậy thì gọi VLM |

Các bài trong `test_api.py`:

| Nhóm | Kịch bản kiểm tra |
|---|---|
| Đăng nhập | API nghiệp vụ và ảnh bằng chứng trả 401 khi chưa đăng nhập; mật khẩu mặc định phải đổi trước khi dùng (403); mật khẩu mới < 8 ký tự bị từ chối; đăng xuất mất quyền; bảo vệ không tạo được tài khoản; tài khoản bị khóa mất phiên ngay |
| Xe vào / ra | Chủ xe vào rồi ra: cho phép, đóng phiên, lưu ảnh vào/ra đúng phiên, ảnh ghép mặt trái – biển phải; ra lần hai bị từ chối; khung hình vào lặp không ghi thêm nhật ký; người ngồi sau lấy xe ra được; 4 lượt vào đồng thời chỉ tạo 1 phiên |
| Bảo vệ duyệt | Người lạ lấy xe → chờ bảo vệ, có độ giống khuôn mặt; quét lại dùng lại đúng yêu cầu; không thấy mặt → chờ bảo vệ; duyệt ghi tên theo tài khoản đăng nhập (bỏ qua tên gửi kèm); duyệt lần hai 409; từ chối giữ phiên mở; yêu cầu cũ không đóng được phiên mới |
| Dữ liệu lỗi | Tệp không phải ảnh 415; ảnh hỏng 422; thiếu một ảnh ở chế độ hai camera 422; hướng sai 422; ảnh vượt dung lượng 413; không lưu ảnh hay nhật ký khi lỗi; chặn truy cập `../` vào thư mục ảnh |
| Thống kê, nhật ký | Tổng = cho phép + từ chối + chờ xử lý; lọc theo thời điểm; 45 sự kiện qua 3 trang không trùng/thiếu; tìm biển số bỏ dấu phân cách; lọc thời gian múi giờ +07; dữ liệu và yêu cầu chờ còn nguyên sau khởi động lại |

Giới hạn: AI giả lập (mỗi màu ảnh tương ứng một người/biển số) nên các bài này kiểm chứng **logic quyết định**, không đo độ chính xác nhận diện.

## 2. Chạy thật với mô hình thật (27/11/2026)

Chạy API riêng (cổng 8011, thư mục dữ liệu tạm) và giao diện qua proxy Vite, ảnh khuôn mặt LFW và ảnh biển số tập test:

| Kịch bản | Kết quả | Độ giống | Thời gian một lượt |
|---|---|---|---|
| Chủ xe vào, ra bằng ảnh khác của chính người đó | Cho phép | 0,90 | 0,23 s |
| Người khác lấy xe | Chờ bảo vệ | 0,04 | 0,23 s |
| Bảo vệ duyệt trên giao diện (một nút bấm) | `manual_approved`, thanh chắn mô phỏng mở | | |
| Xe chưa vào mà ra | Từ chối | | 0,19 s |
| Ảnh camera mặt không có người | Từ chối (không thấy khuôn mặt) | | 0,14 s |

Lượt đầu tiên sau khi khởi động API mất khoảng 1,5 s vì nạp mô hình.

### Đọc biển số trên tập test (76 ảnh có đáp án)

| Tập | Số ảnh | Chỉ OCR (YOLOv8 + chars_best) | Kết hợp OCR + VLM | Thời gian trung vị / p90 |
|---|---|---|---|---|
| Bỏ 7 ảnh biển bị cắt (như benchmark) | 69 | 49 (71,0 %) | **63 (91,3 %)** | |
| Biển rõ (`day_du`) | 66 | 48 (72,7 %) | **61 (92,4 %)** | 144 ms / 2,35 s |

VLM được gọi ở 17/76 ảnh nên p90 khoảng 2,3 s. Luật mới (hỏi VLM khi ký tự OCR có độ tin cậy < 0,5) gọi thêm VLM cho 2 biển OCR đọc đúng định dạng nhưng sai ký tự (`53X794327`, `51H09468`). VLM cũng không đọc được hai ảnh này nên trên tập test kết quả **không đổi**; luật được giữ vì không làm sai thêm biển nào và có ích khi VLM đọc được.

### Lỗi Ollama đã sửa

Với Ollama 0.40.18, một ảnh cụ thể (tập test, `82K37689`, nén JPEG chất lượng 92) làm runner hỏng: từ đó **mọi** câu trả lời, kể cả câu hỏi chữ, đều là `888888…` cho tới khi model được nạp lại. Trước khi sửa: 32/60 lượt đọc liên tiếp hỏng. Sau khi sửa (phát hiện chuỗi lặp, gỡ model, đọc lại bằng PNG): 0/60.

## 3. Khuôn mặt (LFW)

Chi tiết tại `02_Ket_qua_so_sanh_model/02_Khuon_mat_FaceNet_ArcFace/GIAI_THICH_KET_QUA.md`. Tại ngưỡng 0,45 trên 6.000 cặp LFW: độ chính xác 98,95 %, FAR 0,37 %, FRR 1,73 %, khoảng 49 ms/ảnh trên CPU.

## 4. Chưa kiểm thử

- Thử thật tại cổng trường với camera, mũ bảo hiểm, khẩu trang, ánh sáng ban đêm (phiếu `docs/MAU_KIEM_THU_THUC_TE.csv`).
- Nhiều xe/người cùng lúc trong một khung hình, hai làn vào/ra chạy đồng thời.
- Chạy sau HTTPS; tải lâu dài (nhiều giờ, hàng nghìn lượt).

## Lịch sử

Bản 12/11/2026 ghi "22/22 bài kiểm thử API đạt" nhưng bộ test đó không được đưa vào mã nguồn nên không chạy lại được. Bộ `tests/test_api.py` hiện tại viết lại và mở rộng các kịch bản đó (thêm đăng nhập, giới hạn dung lượng, đồng thời).
