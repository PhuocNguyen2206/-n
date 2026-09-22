"""Phát hiện và đối chiếu khuôn mặt bằng FaceNet trên CPU."""

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import torch
from facenet_pytorch import InceptionResnetV1, MTCNN
from PIL import Image, UnidentifiedImageError


@dataclass
class FaceData:
    embedding: list[float]
    confidence: float


class FaceService:
    def __init__(self) -> None:
        self.device = "cpu"
        self.detector = MTCNN(keep_all=True, device=self.device, min_face_size=40)
        self.encoder = InceptionResnetV1(pretrained="vggface2").eval().to(self.device)

    @staticmethod
    def _open_image(image_data: bytes) -> Image.Image:
        try:
            return Image.open(BytesIO(image_data)).convert("RGB")
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("Tệp tải lên không phải ảnh hợp lệ") from error

    def extract_all(self, image_data: bytes) -> list[FaceData]:
        """Trích xuất mọi khuôn mặt rõ trong một khung hình camera.

        Việc này cho phép ghi nhận cả người lái và người ngồi cùng xe khi họ
        cùng xuất hiện ở làn vào. Hàm ``extract`` bên dưới vẫn giữ lại cho
        thao tác đăng ký chỉ cần một khuôn mặt tốt nhất.
        """
        image = self._open_image(image_data)
        boxes, probabilities = self.detector.detect(image)
        if boxes is None or probabilities is None:
            raise ValueError("Không phát hiện được khuôn mặt rõ trong ảnh")
        results: list[FaceData] = []
        for index, probability in sorted(enumerate(probabilities), key=lambda item: float(item[1]), reverse=True):
            if probability is None or np.isnan(probability):
                continue
            face = self.detector.extract(image, np.asarray([boxes[index]]), save_path=None)
            if face is None:
                continue
            with torch.inference_mode():
                vector = self.encoder(face.to(self.device))[0]
            vector = torch.nn.functional.normalize(vector, p=2, dim=0).cpu().numpy()
            results.append(FaceData(vector.astype(float).tolist(), round(float(probability), 3)))
        if not results:
            raise ValueError("Không thể trích xuất khuôn mặt")
        return results

    def detect(self, image_data: bytes) -> dict:
        """Phát hiện nhanh vị trí khuôn mặt để vẽ trực tiếp trên giao diện."""
        image = self._open_image(image_data)
        boxes, probabilities = self.detector.detect(image)
        faces = []
        if boxes is not None and probabilities is not None:
            for box, confidence in zip(boxes, probabilities):
                if confidence is None or np.isnan(confidence):
                    continue
                left, top, right, bottom = [max(0, round(float(value), 1)) for value in box]
                faces.append({"box": [left, top, right, bottom], "confidence": round(float(confidence), 3)})
        return {"width": image.width, "height": image.height, "faces": faces}

    def extract(self, image_data: bytes) -> FaceData:
        return max(self.extract_all(image_data), key=lambda item: item.confidence)

    @staticmethod
    def similarity(first: list[float], second: list[float]) -> float:
        return round(float(np.dot(np.asarray(first), np.asarray(second))), 3)
