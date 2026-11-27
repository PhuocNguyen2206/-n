# Chạy thật trong mạng nội bộ của trường

Máy chủ: một máy đặt ở phòng bảo vệ, cắm hai webcam, cài Docker và Ollama (`ollama pull qwen2.5vl:3b`).
Chép `chars_best.pt`, `plate_best.pt`/`license_plate.pt` vào `backend/models/`.

## Cấu hình một lần

```bash
cp deploy/.env.example .env
```

Sửa `.env`: `SITE_ADDRESS` gồm `localhost`, tên máy `<tên>.local` và IP LAN của máy chủ; `DEFAULT_SNI` là IP đó.
Nên đặt IP tĩnh cho máy chủ trên router để địa chỉ không đổi.

Đổi tên máy để có địa chỉ dễ nhớ (macOS): Cài đặt hệ thống → Cài đặt chung → Chia sẻ → Tên máy chủ cục bộ → `baove`.
Khi đó bảo vệ mở `https://baove.local`.

## Bật, tắt, cập nhật

```bash
docker compose -f docker-compose.prod.yml up -d --build   # bật hoặc cập nhật sau khi git pull
docker compose -f docker-compose.prod.yml down            # tắt
docker compose -f docker-compose.prod.yml logs -f api     # xem log
```

Các container tự chạy lại khi máy khởi động (macOS + Colima: chạy `colima start` sau khi bật máy).

## Lưu ý

- Camera trên trình duyệt chỉ chạy qua HTTPS. Caddy tự cấp chứng chỉ nội bộ, nên lần đầu trình duyệt trên máy khác
  báo "kết nối không riêng tư": bấm Nâng cao → Tiếp tục. Muốn hết cảnh báo hẳn, cài chứng chỉ gốc của Caddy
  (`docker compose -f docker-compose.prod.yml cp web:/data/caddy/pki/authorities/local/root.crt .`) vào máy đó.
- Dữ liệu (SQLite, ảnh bằng chứng) nằm ở `backend/data/`: sao lưu thư mục này định kỳ.
- Lần đầu đăng nhập `admin` với mật khẩu `ADMIN_PASSWORD` (mặc định `admin123`), hệ thống bắt đổi mật khẩu.

## Link công khai tạm thời (Cloudflare Tunnel)

Cho người ngoài mạng nội bộ xem thử, không cần tên miền hay mở cổng router:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml up -d
docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml logs tunnel | grep trycloudflare   # lấy link
docker compose -f docker-compose.prod.yml -f docker-compose.tunnel.yml rm -sf tunnel                      # tắt link
```

Link đổi mỗi khi container `tunnel` khởi động lại; máy phải bật và không ngủ. Ai có link đều thấy trang
đăng nhập, nên dùng mật khẩu mạnh và chỉ tạo tài khoản cho người cần.

## Máy chủ Windows

Xem [HUONG_DAN_WINDOWS.md](HUONG_DAN_WINDOWS.md).
