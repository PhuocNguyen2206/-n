# Máy chủ Windows (máy bàn luôn bật)

Máy Windows chạy bản thật và link công khai; Mac chỉ để sửa code (push lên GitHub, máy Windows pull về).
Chỉ dùng **một** máy làm máy chủ vì mỗi máy có dữ liệu riêng trong `backend\data`.

## Cài một lần

1. Cài **Docker Desktop** (chọn WSL 2). Trong Settings → General bật *Start Docker Desktop when you sign in*.
2. Cài **Ollama**, mở PowerShell chạy: `ollama pull qwen2.5vl:3b` (khoảng 3,2 GB).
3. Lấy code mới nhất trong thư mục dự án: `git pull` (chưa có thì `git clone https://github.com/PhuocNguyen2206/-n.git`).
4. Đảm bảo `backend\models\` có `chars_best.pt` và `license_plate.pt` hoặc `plate_best.pt`.
5. **Điện**: Settings → System → Power & battery → Screen and sleep: *Sleep = Never* khi cắm điện.
   **Windows Update**: Settings → Windows Update → *Pause updates* (tối đa 5 tuần) để máy không tự khởi động lại.
6. **Tường lửa** (chỉ cần nếu máy khác trong mạng LAN vào bằng IP): lần đầu Windows hỏi quyền mạng cho Docker,
   chọn *Private networks* → Allow. Link công khai trycloudflare không cần bước này.

## Bật hệ thống

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-win.ps1
```

Script kiểm tra Docker, model, Ollama; lần đầu tạo file `.env` ở thư mục gốc với IP LAN của máy; build và bật
API, giao diện (Caddy, HTTPS) và Cloudflare Tunnel; cuối cùng in ra:

- `https://<IP LAN>`: trong mạng nội bộ (lần đầu trình duyệt cảnh báo chứng chỉ: Nâng cao → Tiếp tục).
- `https://....trycloudflare.com`: **link công khai**, gửi cho mọi người.

Lần build đầu mất khoảng 5–15 phút (tải torch). Các container tự chạy lại khi máy khởi động, nhưng **link công khai
đổi sau mỗi lần khởi động lại**: chạy lại script để xem link mới.

### File `.env` (script tự tạo; không đưa lên git)

```
SITE_ADDRESS=localhost, 192.168.1.50   # các địa chỉ mở trong mạng nội bộ: localhost + IP LAN của máy Windows
DEFAULT_SNI=192.168.1.50               # IP LAN đó (trình duyệt không gửi tên khi vào bằng IP)
```

Giá trị trên Mac không dùng được cho máy này. IP đổi thì sửa hai dòng rồi chạy lại script. Nên đặt IP tĩnh trên router.

## Việc hằng ngày

| Việc | Lệnh (PowerShell, trong thư mục dự án) |
|---|---|
| Xem lại link công khai | `docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml logs tunnel \| Select-String trycloudflare` |
| Cập nhật code | `git pull` rồi chạy lại `scripts\deploy-win.ps1` |
| Tắt link công khai (giữ hệ thống nội bộ) | `docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml rm -sf tunnel` |
| Tắt toàn bộ | `docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml down` |
| Xem log API | `docker compose -f docker-compose.prod.yml logs -f api` |
| Sao lưu dữ liệu | chép cả thư mục `backend\data` sang ổ khác (nên tắt hệ thống trước khi chép) |

## Link cố định (nếu cần)

1. Mua một tên miền rẻ, chuyển DNS về tài khoản Cloudflare miễn phí.
2. Cloudflare Zero Trust → Networks → Tunnels → tạo tunnel, trỏ `baove.<tên miền>` tới `http://web:8080`, lấy token.
3. Trong `docker-compose.tunnel.yml` đổi `command` thành `tunnel --no-autoupdate run --token <TOKEN>` (giữ token ngoài git, ví dụ đặt trong `.env`).
