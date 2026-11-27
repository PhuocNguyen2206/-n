FROM python:3.12-slim
WORKDIR /app
# OpenCV (opencv-python, ultralytics cần) phải có libGL và glib trong image slim.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# labelImg là công cụ gắn nhãn có giao diện (PyQt5, không có bản Linux ARM): server không cần.
RUN grep -vi '^labelimg' requirements.txt > /tmp/requirements.docker.txt \
    && pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /tmp/requirements.docker.txt
COPY app ./app
# Tải sẵn trọng số YOLO dự phòng và FaceNet để máy chạy thật không cần internet.
RUN mkdir -p /app/data /app/models && python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" \
    && python -c "from facenet_pytorch import InceptionResnetV1; InceptionResnetV1(pretrained='vggface2')"
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
