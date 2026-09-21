"""Phát hiện và đối chiếu khuôn mặt bằng FaceNet trên CPU."""

from dataclasses import dataclass

import numpy as np
import torch
from facenet_pytorch import InceptionResnetV1, MTCNN
from PIL import Image


@dataclass
class FaceData:
    embedding: list[float]
    confidence: float


class FaceService:
    def __init__(self) -> None:
        self.device = "cpu"
        self.detector = MTCNN(keep_all=True, device=self.device, min_face_size=40)
        self.encoder = InceptionResnetV1(pretrained="vggface2").eval().to(self.device)

    def extract(self, image_data: bytes) -> FaceData:
        image = Image.open(__import__("io").BytesIO(image_data)).convert("RGB")
        boxes, probabilities = self.detector.detect(image)
        if boxes is None or probabilities is None:
            raise ValueError("Không phát hiện được khuôn mặt rõ trong ảnh")
        index = int(np.argmax(probabilities))
        face = self.detector.extract(image, np.asarray([boxes[index]]), save_path=None)
        if face is None:
            raise ValueError("Không thể trích xuất khuôn mặt")
        with torch.inference_mode():
            vector = self.encoder(face.to(self.device))[0]
        vector = torch.nn.functional.normalize(vector, p=2, dim=0).cpu().numpy()
        return FaceData(vector.astype(float).tolist(), round(float(probabilities[index]), 3))

    @staticmethod
    def similarity(first: list[float], second: list[float]) -> float:
        return round(float(np.dot(np.asarray(first), np.asarray(second))), 3)
