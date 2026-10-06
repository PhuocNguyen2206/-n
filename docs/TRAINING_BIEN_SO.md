# Training model nhận diện biển số

## Tài nguyên đã chuẩn bị

- RTX 3050 8GB: dùng `--device 0` và `--batch 8`.
- YOLOv8n có sẵn: `backend/yolov8n.pt`.
- Dataset chuẩn YOLO: `backend/datasets/license_plate_vn/`.
- LabelImg đã được cài trong môi trường dự án để vẽ khung biển số.
- Kiểm tra nhãn: `backend/training/verify_dataset.py`.
- Training + đánh giá + tự chép best model: `backend/training/train_license_plate.py`.
- Web sẽ tự đọc Precision, Recall và mAP@50 từ `backend/data/model_metrics.json` sau khi train.

## Chuẩn bị data

1. Thu ảnh/video được phép sử dụng từ camera: biển số rõ, nhiều góc, ngày/đêm và có xe máy/ô tô. Chép trực tiếp mọi tệp vào `backend/datasets/raw_media/`.
2. Chạy bước chuẩn bị để trích một khung hình mỗi 2 giây video và tự gợi ý nhãn bằng `plate_best.pt`:

```powershell
& ".\backend\.venv\Scripts\python.exe" ".\backend\training\prepare_media_dataset.py"
```

Có thể lấy khung dày hơn bằng cách thêm `--video-step 1`.

3. Mở LabelImg cho từng thư mục ảnh, chọn định dạng **YOLO**, rồi kiểm tra/chỉnh khung cho mỗi vùng biển số. Tên lớp duy nhất là `license_plate` (id `0`).

```powershell
& ".\backend\.venv\Scripts\labelImg.exe" ".\backend\datasets\license_plate_vn\images\train" ".\backend\datasets\license_plate_vn\labels\train"
```

4. Lặp lại cho `val` và `test`. Ảnh và tệp `.txt` nhãn phải cùng tên.
5. Script đã tự chia xấp xỉ: train 70%, val 20%, test 10%.
6. Đặt ảnh và tệp `.txt` cùng tên theo cấu trúc trong `backend/datasets/license_plate_vn/README.md`.

## Chạy trước khi train

Tại thư mục gốc dự án:

```powershell
& ".\backend\.venv\Scripts\python.exe" ".\backend\training\verify_dataset.py"
```

## Train

Môi trường hiện tại chạy được ngay bằng CPU. Lệnh dưới đây dùng `--device cpu` để bảo đảm không lỗi khi chưa có PyTorch CUDA:

```powershell
& ".\backend\.venv\Scripts\python.exe" ".\backend\training\train_license_plate.py" --epochs 60 --imgsz 640 --batch 4 --device cpu
```

## Dùng GPU RTX 3050 (tuỳ chọn)

Máy có RTX 3050 8 GB, nhưng PyTorch CUDA chưa cài được vì ổ C hiện chỉ còn khoảng 1.2 GB trống cho quá trình tải/cài. Khi đã giải phóng thêm dung lượng ổ C hoặc cấu hình vùng tạm sang ổ D ổn định, thay `torch` CPU bằng bản CUDA; sau đó mới dùng lệnh này:

```powershell
& ".\backend\.venv\Scripts\python.exe" ".\backend\training\train_license_plate.py" --epochs 60 --imgsz 640 --batch 8 --device 0
```

Khi thành công, model sẽ được đặt tại `backend/models/license_plate.pt`. Hãy khởi động lại API để dự án dùng model mới.

## Lưu ý

- Nếu bị tràn VRAM, giảm `--batch` xuống 4.
- Không đưa ảnh khuôn mặt nhận dạng cá nhân vào dataset nếu chưa có sự đồng ý phù hợp.
- Không báo cáo Precision/Recall/mAP khi chưa chạy tập test; web đang để trống các chỉ số này cho đến khi train thật.
