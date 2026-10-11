# Kết quả huấn luyện model biển số Việt Nam

Model YOLOv8 được huấn luyện 20 epoch với 2.814 ảnh train và đánh giá trên 159 ảnh validation.

| Chỉ số | Kết quả |
| --- | ---: |
| Precision | 93.0% |
| Recall | 98.8% |
| mAP@50 | 97.0% |

## Ý nghĩa biểu đồ

- `01_Tien_trinh_huan_luyen.png`: loss và các chỉ số được cải thiện qua từng epoch.
- `02_Ma_tran_nham_lan.png`: mức độ model phát hiện đúng biển số trên tập validation.
- `03_Duong_cong_Precision_Recall.png`: cân bằng giữa độ chính xác và độ bao phủ.
- `04_Duong_cong_F1.png`: ngưỡng nhận diện có hiệu quả cân bằng nhất.

Các tệp trọng số model, dataset và ảnh camera không được đưa lên Git để tránh repository quá nặng và bảo vệ dữ liệu thực tế.
