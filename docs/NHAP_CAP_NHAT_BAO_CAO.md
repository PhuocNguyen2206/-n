# Nháp nội dung cập nhật cho quyển báo cáo

Tài liệu này liệt kê những chỗ quyển `Bao_cao_do_an_4_chuong.docx` đang lệch so với mã nguồn hiện tại và gợi ý nội dung thay thế. Đây là **bản nháp tham khảo**: sinh viên tự viết lại bằng lời văn của mình, kiểm tra số liệu với tệp kết quả gốc trước khi đưa vào báo cáo.

## 0. Những chỗ cần sửa (theo thứ tự ưu tiên)

| Vị trí trong báo cáo | Hiện ghi | Cần sửa thành |
|---|---|---|
| Mục 2.3.3 "Dự phòng bằng EasyOCR và chuẩn hóa", Bảng ngưỡng EasyOCR, mục 1.x OCR, tài liệu tham khảo [5] | EasyOCR là tầng dự phòng | Tầng dự phòng là VLM Qwen2.5-VL 3B qua Ollama (mục 1 bên dưới). EasyOCR đã bỏ khỏi `requirements.txt` |
| Mục 4.3 | "22/22 bài kiểm thử API… thư mục dự án chưa có bộ tests tương ứng" | 56/56 bài, chạy lại được bằng một lệnh (mục 3) |
| Mục 4.4 | "Ngưỡng 0,45 chưa được hiệu chỉnh bằng cặp cùng người và khác người" | Đã đánh giá trên LFW 6.000 cặp (mục 2) |
| Mục 3.5.5 | Ủy quyền/mượn xe "không mô tả… như chức năng" | Đã có chức năng ủy quyền lấy xe hộ (mục 4), bảng mới `exit_authorizations` |
| Chương 3 | Có Use Case, thiếu DFD, ERD, sơ đồ tuần tự (đề cương tuần 5 yêu cầu) | Thêm ba sơ đồ ở mục 6 |
| Chương 3/4 | Giao diện 4 mục, tên bảo vệ nhập tay, không phân quyền | 6 mục, đăng nhập, phân quyền admin/bảo vệ (mục 5) |
| Bố cục | Đề cương ghi 5 chương (có Chương 5 Kết luận) | Hỏi GVHD: giữ 4 chương hay tách "Kết luận và hướng phát triển" thành Chương 5 như đề cương |

## 1. Đọc biển số ba tầng: YOLOv8 → chars_best → VLM

**Luồng.** YOLOv8 (`license_plate.pt`, mAP@50 = 0,970) tìm vùng biển số. Mô hình ký tự `chars_best.pt` đọc từng ký tự, sắp theo hàng (biển 2 dòng) rồi ghép chuỗi. VLM Qwen2.5-VL 3B (chạy cục bộ qua Ollama, lượng tử Q4_K_M, khoảng 3,2 GB) chỉ được gọi khi:

1. OCR không ra chuỗi; hoặc
2. chuỗi sai định dạng biển Việt Nam `^\d{2}[A-Z][A-Z0-9]?\d{4,5}$`; hoặc
3. chuỗi đúng định dạng nhưng có ký tự độ tin cậy < 0,5.

Nếu VLM trả biển hợp lệ thì dùng kết quả VLM, ngược lại giữ kết quả OCR. Ollama tắt hoặc chưa cài thì hệ thống chạy bằng OCR, không báo lỗi. Nhật ký lưu cột `plate_source` (`ocr`/`vlm`).

**Kết quả** (tập test 69 ảnh, bỏ 7 ảnh biển bị cắt): OCR 49/69 = 71,0 %; kết hợp 63/69 = **91,3 %**. Trên 66 ảnh biển rõ: 72,7 % → 92,4 %. Thời gian trung vị 144 ms/ảnh; VLM được gọi ở 17/76 ảnh, mỗi lần khoảng 1,7–2 s trên GPU.

**Vì sao không dùng VLM cho mọi ảnh.** VLM chậm hơn khoảng 15 lần. Phần lớn biển OCR đọc đúng với độ tin cậy cao, nên chỉ hỏi VLM khi nghi ngờ thì giữ được tốc độ ở cổng.

**Sự cố và cách xử lý.** Với Ollama 0.40.18, một số ảnh làm runner rơi vào trạng thái hỏng: mọi câu trả lời sau đó là chuỗi `888…`. Hệ thống phát hiện ký tự lặp ≥ 12 lần, gỡ model khỏi bộ nhớ (`keep_alive = 0`) rồi đọc lại bằng PNG. Trên 60 lượt đọc liên tiếp: trước khi sửa 32 lượt hỏng, sau khi sửa 0.

**Hạn chế.** Hai biển OCR đọc sai một ký tự nhưng vẫn đúng định dạng (`51H09488` → `51H09468`, `53X74327` → `53X794327`) được gửi cho VLM nhưng VLM cũng không đọc đúng (ảnh có hai biển, ký tự mờ). Biển bị cắt mất phần (7 ảnh) không đọc được.

## 2. Đối chiếu khuôn mặt và ngưỡng 0,45

MTCNN tìm **mọi** khuôn mặt trong khung hình, FaceNet (InceptionResnetV1, VGGFace2) tạo vector 512 chiều đã chuẩn hóa L2. Lúc ra, hệ thống lấy độ giống cosine **lớn nhất** giữa các mặt hiện tại và các mặt đã lưu lúc vào của cùng biển số.

Đánh giá trên LFW (6.000 cặp chuẩn, 10-fold): độ chính xác 98,90 % ± 0,65 %, AUC 0,9989. Tại ngưỡng 0,45: độ chính xác 98,95 %, FAR 0,37 %, FRR 1,73 %; ngưỡng tối ưu theo độ chính xác là 0,43 (FAR 0,50 %). Chọn 0,45 vì để người lạ lấy xe nguy hiểm hơn chủ xe phải chờ bảo vệ. Cách "lấy mọi mặt, chọn độ giống lớn nhất" giảm chặn nhầm từ 7,1 % (chỉ lấy một mặt) xuống 1,7 %. Ngưỡng nay cấu hình được bằng biến `FACE_MATCH_THRESHOLD`.

Hạn chế: LFW không có mũ bảo hiểm, khẩu trang; cần đo lại tại cổng trường.

## 3. Kiểm thử

`pytest` 56 bài (23 bài API nghiệp vụ, 23 bài client VLM, 10 bài luật kết hợp OCR + VLM), khoảng 15 s, không cần GPU. Bài API dùng AI giả lập để kiểm chứng logic quyết định: vào/ra, người lạ, bảo vệ duyệt, ủy quyền, đăng nhập, dữ liệu lỗi, đồng thời, khôi phục sau khởi động lại. Bảng chi tiết: `docs/KET_QUA_KIEM_THU.md`. Có thể đưa nguyên bảng nhóm kịch bản vào mục 4.3.

Chạy thật với mô hình thật: chủ xe ra (độ giống 0,90) được cho phép; người khác (0,04) chờ bảo vệ; người được ủy quyền (0,64) được cho phép; mỗi lượt quét khoảng 0,2 s khi không cần VLM.

## 4. Ủy quyền lấy xe hộ (xe mượn) — đáp ứng "tính mới" trong đề cương

**Bài toán.** Chủ xe A gửi xe rồi nhờ bạn C lấy xe ra. Theo luật "người ra phải khớp người vào", C sẽ bị chặn.

**Giải pháp.** Khi xe đang ở trong bãi, bảo vệ (đã đăng nhập) xác minh với A (gặp trực tiếp/gọi điện), ghi tên A, tên và MSSV/CCCD của C, chụp mặt C. Ủy quyền gắn với **đúng lượt gửi xe** đang mở, có thời hạn (mặc định 4 giờ, tối đa 24 giờ) và **chỉ dùng một lần**. Lúc ra: nếu mặt không khớp người lúc vào, hệ thống so tiếp với các ủy quyền còn hiệu lực của lượt đó; khớp ≥ ngưỡng thì cho phép với lý do "Người được ủy quyền lấy xe: C (MSSV) · Chủ xe: A". Ủy quyền chuyển sang "đã dùng". Chủ xe tự lấy xe thì các ủy quyền chưa dùng hết hiệu lực. Bảo vệ có thể hủy ủy quyền.

Tại sao gắn với lượt gửi xe thay vì với biển số: ủy quyền không bị dùng lại cho những lần gửi xe sau, giảm rủi ro "ủy quyền vĩnh viễn".

## 5. Đăng nhập và phân quyền

- Hai vai trò: **quản trị viên** (tạo/khóa tài khoản) và **bảo vệ**. Lần đầu tạo `admin`, bắt buộc đổi mật khẩu.
- Mật khẩu băm PBKDF2-SHA256 200.000 vòng, có salt. Phiên đăng nhập là cookie HttpOnly, SameSite=Lax, 12 giờ; trong cơ sở dữ liệu chỉ lưu SHA-256 của token.
- Mọi API nghiệp vụ và ảnh bằng chứng (có khuôn mặt — dữ liệu cá nhân) yêu cầu đăng nhập. Chỉ `/health` và `/model/status` công khai.
- Người duyệt xe ra, ghi ngoại lệ, tạo ủy quyền được ghi theo tài khoản (`operator_username`), không còn nhập tên tay.
- Ảnh tải lên giới hạn 10 MB, kiểm tra giải mã trước khi lưu.

## 6. Sơ đồ bổ sung cho Chương 3

Các sơ đồ viết bằng Mermaid; dán vào https://mermaid.live để xuất ảnh PNG/SVG rồi chèn vào Word.

### 6.1 DFD mức ngữ cảnh

```mermaid
flowchart LR
  NL[Người điều khiển xe] -- "khuôn mặt, biển số (qua 2 camera)" --> HT((Hệ thống quản lý<br/>phương tiện))
  BV[Bảo vệ] -- "đăng nhập, duyệt xe ra, ủy quyền, tra cứu" --> HT
  HT -- "quyết định cho phép / chờ / từ chối, ảnh bằng chứng" --> BV
  QT[Quản trị viên] -- "tạo / khóa tài khoản" --> HT
  HT -- "ảnh biển số nghi ngờ" --> VLM[Ollama - Qwen2.5-VL]
  VLM -- "chuỗi biển số" --> HT
```

### 6.2 DFD mức 1

```mermaid
flowchart TB
  CAM[Camera mặt + biển số] --> P1[1. Đọc biển số<br/>YOLOv8 + chars_best + VLM]
  CAM --> P2[2. Trích đặc trưng mặt<br/>MTCNN + FaceNet]
  P1 --> P3[3. Ra quyết định vào/ra]
  P2 --> P3
  P3 <--> D1[(gate_sessions<br/>gate_session_faces)]
  P3 <--> D2[(exit_authorizations)]
  P3 --> D3[(access_events)]
  P3 --> D4[(Ảnh bằng chứng)]
  P3 -- "không khớp / không thấy mặt" --> P4[4. Bảo vệ xác nhận]
  P4 <--> D5[(exit_reviews)]
  P4 --> D3
  BV[Bảo vệ] --> P5[5. Ủy quyền lấy xe hộ]
  P5 --> D2
  BV --> P6[6. Tra cứu nhật ký, thống kê]
  D3 --> P6
  D4 --> P6
  BV --> P7[7. Đăng nhập]
  P7 <--> D6[(staff_accounts<br/>auth_sessions)]
```

### 6.3 ERD (các bảng đang dùng)

```mermaid
erDiagram
  gate_sessions ||--|{ gate_session_faces : "lưu mặt lúc vào"
  gate_sessions ||--o{ exit_reviews : "yêu cầu bảo vệ"
  gate_sessions ||--o{ exit_authorizations : "ủy quyền lấy hộ"
  access_events ||--o| gate_sessions : "entry_event_id / exit_event_id"
  access_events ||--o| exit_reviews : "event_id"
  exit_authorizations |o--o| access_events : "used_event_id"
  staff_accounts ||--o{ auth_sessions : "phiên đăng nhập"
  staff_accounts ||--o{ access_events : "operator_username"
  gate_sessions { text id PK
    text plate_number
    text entry_event_id
    text entered_at
    text exited_at
    text status "open / closed"
    text entry_evidence_path
    text exit_evidence_path }
  gate_session_faces { text session_id FK
    text embedding "vector 512 chiều (JSON)"
    real confidence }
  access_events { text id PK
    text occurred_at
    text direction "entry / exit"
    text plate_number
    text decision "approved / manual_approved / manual_review / denied"
    text reason
    real plate_confidence
    real face_confidence
    text plate_source "ocr / vlm"
    text evidence_path
    text authorization_id
    text operator_username }
  exit_reviews { text id PK
    text session_id FK
    text event_id FK
    text status "pending / approved / rejected" }
  exit_authorizations { text id PK
    text session_id FK
    text plate_number
    text owner_name
    text borrower_name
    text borrower_code
    text embedding
    text valid_until
    text status "active / used / expired / revoked" }
  staff_accounts { text username PK
    text full_name
    text role "admin / guard"
    text password_hash
    int must_change_password }
  auth_sessions { text token_hash PK
    text username FK
    text expires_at }
```

Các bảng `people`, `vehicles`, `vehicle_authorizations`, `vehicle_sessions`, `vehicle_session_people` còn trong lược đồ từ thiết kế ban đầu (đăng ký xe trước) nhưng không được dùng; có thể nêu ở mục "hướng phát triển: tích hợp hệ thống sinh viên".

### 6.4 Sơ đồ tuần tự — xe ra

```mermaid
sequenceDiagram
  participant C as Camera (trình duyệt)
  participant A as API FastAPI
  participant V as YOLOv8 + chars_best
  participant L as VLM (Ollama)
  participant F as MTCNN + FaceNet
  participant D as SQLite
  C->>A: POST /gate/verify (ảnh mặt, ảnh biển, hướng = ra)
  A->>V: đọc biển số
  alt OCR rỗng / sai định dạng / kém tin cậy
    V->>L: ảnh biển số
    L-->>V: chuỗi biển số
  end
  V-->>A: biển số
  A->>F: trích mọi khuôn mặt
  F-->>A: các vector 512 chiều
  A->>D: tìm phiên mở theo biển số
  alt độ giống với người lúc vào ≥ 0,45
    A->>D: ghi sự kiện approved, đóng phiên
    A-->>C: CHO PHÉP
  else khớp người được ủy quyền ≥ 0,45
    A->>D: ghi approved + authorization_id, đóng phiên, ủy quyền = used
    A-->>C: CHO PHÉP (người được ủy quyền)
  else không khớp hoặc không thấy mặt
    A->>D: ghi manual_review, tạo exit_review, lưu ảnh
    A-->>C: CHỜ BẢO VỆ (tạm dừng quét)
  else không có phiên mở
    A->>D: ghi denied
    A-->>C: TỪ CHỐI
  end
```

## 7. Hướng phát triển (gợi ý cho chương kết luận)

- Thu thập ảnh thật tại cổng trường (có sự đồng ý) để đo lại cả biển số và khuôn mặt; thử mũ bảo hiểm, khẩu trang, ban đêm.
- Tích hợp danh sách sinh viên/xe đăng ký để chủ xe tự tạo ủy quyền trên cổng thông tin sinh viên thay vì qua bảo vệ.
- Điều khiển thanh chắn thật (IoT), chạy hai làn đồng thời, triển khai HTTPS.
- Thử ArcFace (đã có so sánh trong `02_Ket_qua_so_sanh_model`) hoặc tinh chỉnh ngưỡng theo dữ liệu thật.
