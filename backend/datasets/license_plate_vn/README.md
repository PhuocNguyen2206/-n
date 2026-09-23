# Dataset biển số Việt Nam (YOLO format)

Đặt ảnh và nhãn theo cấu trúc sau:

```text
images/train/xe_001.jpg
labels/train/xe_001.txt
images/val/xe_101.jpg
labels/val/xe_101.txt
images/test/xe_151.jpg
labels/test/xe_151.txt
```

Mỗi dòng trong tệp nhãn là một biển số:

```text
0 x_center y_center width height
```

Tất cả tọa độ chuẩn hóa từ 0 đến 1, lớp `0` là `license_plate`.

Khuyến nghị cho demo: tối thiểu 100 ảnh đã gán nhãn, có xe máy/ô tô, góc chéo, ảnh sáng/tối, ảnh mờ nhẹ và biển số ở các khoảng cách khác nhau.
