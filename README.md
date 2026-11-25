# Hệ thống quản lý phương tiện trường học tích hợp AI

Sản phẩm đồ án kiểm soát phương tiện tại cổng trường bằng hai luồng ảnh: biển số xe và khuôn mặt người điều khiển.

## Chức năng đã có

- Quét riêng ảnh khuôn mặt và ảnh xe/biển số, phù hợp mô phỏng hai camera.
- Màn hình làn xe thời gian thực: mở hai luồng camera, quét tự động mỗi 3 giây và hiển thị quyết định cho phép/từ chối tại chỗ.
- Đọc biển số kết hợp: YOLOv8 (`license_plate.pt`) tìm biển, `chars_best.pt` đọc ký tự; khi kết quả rỗng hoặc sai định dạng biển Việt Nam thì VLM **Qwen2.5-VL 3B** (chạy local qua Ollama) đọc lại. FaceNet tạo đặc trưng khuôn mặt trên CPU.
- Không cần đăng ký trước: lúc xe vào, hệ thống lưu biển số và các khuôn mặt xuất hiện trong lượt xe.
- Cơ chế fail-closed: lúc xe ra chỉ `approved` khi biển số có lượt vào đang mở và khuôn mặt khớp với một người được ghi nhận trong lượt vào đó. Mọi trường hợp khác bị từ chối và ghi nhật ký.
- Phiên gửi xe: nếu có nhiều người cùng đi vào xe, chỉ cần một trong các khuôn mặt đó xuất hiện lúc ra là hợp lệ.
- Dashboard cho bảo vệ: thống kê, luồng camera thời gian thực, nhật ký vào/ra và lý do từ chối.
- API REST có Swagger để tích hợp camera thực tế: `http://localhost:8000/docs`.

## Chạy sản phẩm

### Tầng đọc biển số bằng VLM (Windows và Mac giống nhau)

Ollama và model **không nằm trong Git**; mỗi máy cài một lần:

| Bước | Windows | macOS |
|---|---|---|
| 1. Cài Ollama | Tải bộ cài tại https://ollama.com/download | Tải app tại https://ollama.com/download hoặc `brew install ollama` |
| 2. Tải model (~3,2 GB) | `powershell -ExecutionPolicy Bypass -File scripts\setup-vlm.ps1` | `bash scripts/setup-vlm.sh` |
| 3. Chạy dự án | `powershell -ExecutionPolicy Bypass -File scripts\dev-win.ps1` hoặc VS Code task **Run project (Windows)** | `bash scripts/dev-mac.sh` (tự bật Ollama nếu đã cài) |

Kiểm tra tại `http://127.0.0.1:8000/api/v1/model/status`, mục `vlm.available` phải là `true`.
Trên Windows, muốn model nằm ở ổ D: chạy `setx OLLAMA_MODELS D:\OllamaModels` trước bước 2 rồi mở lại terminal.

Cách hoạt động: YOLOv8 + `chars_best.pt` vẫn đọc trước (~0,1 s/ảnh). Chỉ khi kết quả rỗng hoặc
không đúng dạng biển số Việt Nam (`^\d{2}[A-Z][A-Z0-9]?\d{4,5}$`) thì backend mới gửi ảnh cho
VLM (~1–2 s trên GPU). Nhật ký lưu cột `plate_source` (`ocr`/`vlm`); giao diện gắn nhãn **VLM** ở
những lượt được VLM đọc lại. **Nếu Ollama chưa cài hoặc đang tắt, hệ thống vẫn chạy bằng OCR như cũ**,
không báo lỗi. Kết quả đo so sánh trên tập test: OCR 71,0 % → kết hợp 91,3 % biển đọc đúng hoàn toàn
(chi tiết trong thư mục `vlm_benchmark` của đồ án).

Biến môi trường tùy chọn: `VLM_ENABLED=0` (tắt hẳn VLM), `OLLAMA_HOST` (mặc định
`http://127.0.0.1:11434`), `VLM_MODEL` (mặc định `qwen2.5vl:3b`), `VLM_TIMEOUT` (giây, mặc định 30).

Chạy kiểm thử backend: `cd backend` rồi `.venv/bin/python -m pytest -q tests`
(Windows: `.venv\Scripts\python.exe -m pytest -q tests`).

### Máy Mac Apple Silicon đã thiết lập

Môi trường cục bộ dùng Python 3.11 tại `backend/.venv`, Node.js 22 tại
`.tools/` và các thư viện frontend đã cài theo `frontend/pnpm-lock.yaml`.
Không cần Docker để phát triển cục bộ.

Trong terminal tại thư mục gốc dự án, chạy:

```bash
bash scripts/dev-mac.sh
```

Hoặc trong VS Code: **Terminal → Run Task → Run project (Mac)**.
Dashboard: `http://127.0.0.1:5174`; Swagger: `http://127.0.0.1:8000/docs`.
Mở terminal mới trong VS Code để nhận PATH của Node.js và uv.

Khi chuyển từ Windows, cài Ollama + model theo bảng ở trên, tắt API trên máy cũ rồi chép các file `.pt` trong
`backend/models/` sang cùng thư mục trên Mac (gồm `license_plate.pt`,
`plate_best.pt`, `chars_best.pt` nếu có). Muốn giữ phiên gửi xe, ảnh và
dữ liệu cũ, chép cả `backend/data/`. Không chép `.venv` hoặc `node_modules`
từ Windows. Khởi động lại API sau khi chép model.

### Chạy bằng Docker

```bash
docker compose up --build
```

- Dashboard: `http://localhost:5173`
- API: `http://localhost:8000/api/v1/health`
- Swagger: `http://localhost:8000/docs`

Khi phát triển cục bộ, chạy API từ `backend` và frontend từ `frontend`; trang web dùng `http://127.0.0.1:5174`.

## Luồng demo

1. Mở **Giám sát cổng**, tìm và chọn hai webcam riêng: một khuôn mặt, một biển số. Chọn hướng kiểm tra lối vào.
2. Bấm **Bật camera**. Camera khuôn mặt thu mặt người lái; camera biển số thu biển số xe. Hai ảnh được gửi cùng một yêu cầu kiểm tra.
3. Người A và xe X vào: tạo phiên và lưu ảnh; sau đó thử người B với xe X ra để kiểm tra từ chối.
4. Dừng camera, chọn hướng lối ra rồi bật lại. Người A với xe X ra: đối chiếu, cho phép và đóng phiên nếu nhận diện đạt điều kiện.
5. Xem ảnh bằng chứng tại **Nhật ký** và **Đối chiếu & lưu lượng**.

Model chuyên biệt cần được chép sang máy mới trước khi đánh giá khả năng đọc biển số. Kịch bản trên là kế hoạch thử thực tế, không phải kết quả đã đo.

## Use case

Xem các use case, actor, luồng chính và luồng ngoại lệ tại [docs/USE_CASES.md](docs/USE_CASES.md).

## Camera thực tế

Khi quét cổng thành công (kết quả cho phép), ảnh của chính khung hình gửi
để kiểm tra được lưu trên máy chạy backend tại `backend/data/evidence/`.
Tên tệp có dạng `<mã-lượt>_entry.jpg` hoặc `<mã-lượt>_exit.jpg`.
Ô ảnh tại mỗi làn hiển thị ảnh đã lưu, biển số và thời điểm ghi nhận;
bấm **Xem ảnh** để mở ảnh gốc. Có thể xem lại từ ảnh thu nhỏ trong
**Nhật ký**, hoặc so sánh ảnh vào/ra trong **Đối chiếu & lưu lượng**.
Ảnh vẫn còn sau khi đóng trình duyệt hoặc khởi động lại API. Các khung
hình đang chờ đủ biển số/khuôn mặt và khung hình vào lặp không lưu ảnh mới.
Ảnh phát hiện mặt đơn thuần không được coi là lượt kiểm soát thành công.
Khi sao lưu hoặc chuyển máy, chép cả thư mục `backend/data/` (ảnh và SQLite).

Mục **Giám sát cổng** dùng hai webcam được trình duyệt cấp quyền: một camera mặt và một camera biển số. Chọn **Hướng kiểm tra** vào hoặc ra, chọn hai thiết bị khác nhau rồi bấm **Bật hai camera**. Dừng camera trước khi đổi hướng. Bản này thử lần lượt một hướng; chưa vận hành hai làn độc lập đồng thời. Ảnh bằng chứng mới ghép mặt bên trái, biển số bên phải. Cần đảm bảo chỉ một người/xe được thử trong cùng chu kỳ quét; chưa có cơ chế theo dõi nhiều xe hoặc đồng bộ phần cứng.

Muốn triển khai hai làn đồng thời cần bốn camera và mở rộng quản lý luồng/phiên; quyết định hiện tại chưa kết nối barrier vật lý.

## Mô hình và dữ liệu

YOLOv8 và FaceNet được tự tải lần đầu khi sử dụng; model VLM tải bằng `scripts/setup-vlm.*`. Khi chạy bằng Docker, Ollama chạy trên máy host và container gọi qua `host.docker.internal`. Để đạt chỉ tiêu độ chính xác của đề tài trên dữ liệu thực tế, cần huấn luyện model biển số riêng từ dữ liệu đã gán nhãn và đặt tệp trọng số tại `backend/models/license_plate.pt`. Trọng số mô hình và ảnh khuôn mặt không được đưa lên GitHub.

## Chuẩn bị báo cáo tốt nghiệp

Giao diện bảo vệ có bốn mục: Tổng quan, Giám sát cổng, Đối chiếu & lưu lượng và Nhật ký. Công cụ dữ liệu/mô hình vẫn nằm trong backend; không có trang quản trị có phân quyền.

- [Kế hoạch báo cáo, demo và thực nghiệm](docs/KE_HOACH_BAO_VE_DO_AN.md)
- [Kết quả kiểm thử tự động và giới hạn](docs/KET_QUA_KIEM_THU.md)
- [Phiếu ghi kết quả thực tế](docs/MAU_KIEM_THU_THUC_TE.csv)

Các phiếu mẫu chưa có số liệu đo. Chưa thể kết luận độ chính xác nhận diện thực tế từ kiểm thử AI giả lập.

## Xác nhận xe ra và thanh chắn mô phỏng

Không cần IoT để trình diễn quy trình trên web. Khi lối ra đọc được biển số có phiên đang mở nhưng không xác minh được mặt (không thấy mặt hoặc mặt không khớp), hệ thống tạo yêu cầu chờ bảo vệ, lưu ảnh hai camera và tạm dừng quét cổng.

Ngay cạnh camera, bảo vệ xem ảnh lúc vào/ra, nhập tên và lý do, đánh dấu đã kiểm tra trực tiếp, rồi chọn **Xác nhận cho xe ra (mô phỏng)** hoặc **Không cho xe ra**. Đồng ý sẽ đóng đúng phiên và ghi quyết định `manual_approved`, khác với `approved` của AI; từ chối giữ phiên mở. Quét chỉ tiếp tục khi bảo vệ chủ động bấm nút tiếp tục. Yêu cầu chờ được đọc lại sau khi tải lại trang.

Thanh chắn trên web chỉ mô phỏng trạng thái; nút Đóng mô phỏng chỉ đổi hiển thị, không hoàn tác phiên đã đóng. Không có lệnh điều khiển thiết bị thật. Đeo khẩu trang không nhất thiết làm nhận diện thất bại: hệ thống hiện chưa có bộ phát hiện khẩu trang riêng. Nếu không đọc được biển số hoặc không có phiên vào, không cung cấp nút duyệt ra cho một phiên chưa xác định.

Tên bảo vệ đang do người dùng nhập, chưa phải danh tính được xác thực. Bản này phục vụ demo cục bộ, chưa có phân quyền để vận hành tại cổng thật.

## Tìm lại đúng ảnh của lượt xe

Mở **Nhật ký**, tìm theo biển số và/hoặc khoảng thời gian, chuyển trang nếu cần (20 lượt/trang). Bấm bất kỳ dòng nào để xem ảnh của chính mã lượt đó cùng thời gian, hướng và quyết định; không cần tìm tên tệp trong thư mục. **Mở ảnh gốc** mở tệp bằng chứng. Nếu lượt không có ảnh hoặc tệp đã mất, giao diện sẽ báo rõ. Tổng quan chỉ hiển thị 6 lượt gần nhất và có nút vào toàn bộ nhật ký.
