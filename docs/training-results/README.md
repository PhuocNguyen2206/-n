# Kết quả huấn luyện model biển số Việt Nam

Model YOLOv8 được huấn luyện 20 epoch với 2.814 ảnh train và đánh giá trên 159 ảnh validation.

| Chỉ số | Kết quả |
| --- | ---: |
| Precision | 93.0% |
| Recall | 98.8% |
| mAP@50 | 97.0% |

## Ý nghĩa của 5 ảnh kết quả

1. **`01_Tien_trinh_huan_luyen.png` — Tiến trình model học qua 20 epoch**  
   Thể hiện các chỉ số và lỗi (loss) thay đổi qua từng vòng học. Đường biểu đồ ổn định dần cho thấy model đã học được đặc điểm biển số.

2. **`02_Ma_tran_nham_lan.png` — Model nhận diện đúng/sai biển số**  
   Thể hiện số lượng biển số model phát hiện đúng và các trường hợp bị nhầm/bỏ sót trên tập validation.

3. **`03_Duong_cong_Precision_Recall.png` — Độ chính xác khi thay đổi ngưỡng nhận diện**  
   Cho thấy sự cân bằng giữa việc nhận diện đúng biển số và việc không bỏ sót biển số khi thay đổi ngưỡng tin cậy.

4. **`04_Duong_cong_F1.png` — Ngưỡng nhận diện tốt nhất của model**  
   Cho biết ngưỡng tin cậy có điểm F1 cao nhất, tức cân bằng tốt nhất giữa Precision và Recall.

5. **`05_Ket_qua_model_du_doan.png` — Kết quả model dự đoán biển số**  
   Ảnh thực tế từ tập kiểm tra, trong đó khung bao quanh biển số là kết quả model YOLOv8 đã dự đoán.

Các tệp trọng số model, dataset và ảnh camera không được đưa lên Git để tránh repository quá nặng và bảo vệ dữ liệu thực tế.
