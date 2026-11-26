"""Đọc biển số bằng Vision Language Model (Qwen2.5-VL) chạy local qua Ollama.

VLM chỉ là tầng dự phòng: pipeline YOLOv8 + chars_best vẫn chạy trước, VLM
chỉ được gọi khi kết quả OCR rỗng hoặc sai định dạng biển số Việt Nam
(xem ``VisionService``). Benchmark ngày 25/11/2026 trên 69 ảnh test: OCR
71,0 % -> kết hợp 91,3 % đọc đúng toàn biển.

Chạy như nhau trên Windows, macOS và Linux vì chỉ giao tiếp với Ollama qua
HTTP. Khi Ollama chưa cài, đang tắt hoặc thiếu model, mọi hàm ở đây trả về
``None`` thay vì ném lỗi để cổng vẫn hoạt động bằng OCR.
"""

from __future__ import annotations

import base64
import logging
import os
import re
import threading
import time
from dataclasses import dataclass

import cv2
import httpx
import numpy as np

logger = logging.getLogger(__name__)

# 2 số tỉnh + 1 chữ cái + (1 chữ/số) + 4-5 số. Ví dụ: 59F138151, 51F79512, 50XA5535.
VN_PLATE_PATTERN = re.compile(r"^\d{2}[A-Z][A-Z0-9]?\d{4,5}$")

PROMPT = (
    "This image shows a Vietnamese vehicle license plate. Read every character on the plate exactly. "
    "If it has two lines, read the top line then the bottom line. "
    "Reply with only the plate characters (letters and digits), no explanation."
)


def is_valid_vn_plate(text: str | None) -> bool:
    return bool(text) and bool(VN_PLATE_PATTERN.match(text))


def normalize_plate(text: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


_DEGENERATE_PATTERN = re.compile(r"(.)\1{11,}")


def is_degenerate_output(text: str | None) -> bool:
    """Một ký tự lặp từ 12 lần trở lên: biển số thật không bao giờ như vậy."""
    return bool(text) and bool(_DEGENERATE_PATTERN.search(text))


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


@dataclass
class VlmReading:
    plate: str | None
    raw_text: str
    elapsed_ms: float


class VlmPlateReader:
    """Client nhỏ cho Ollama ``/api/generate``; an toàn khi gọi từ nhiều request."""

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        enabled: bool | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.host = (host or os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
        if not self.host.startswith(("http://", "https://")):
            self.host = f"http://{self.host}"
        self.model = model or os.getenv("VLM_MODEL", "qwen2.5vl:3b")
        self.enabled = _env_flag("VLM_ENABLED", True) if enabled is None else enabled
        self.timeout = timeout if timeout is not None else float(os.getenv("VLM_TIMEOUT", "30"))
        self._client = client or httpx.Client(timeout=self.timeout)
        # Chỉ một lượt VLM cùng lúc: camera gửi khung liên tục, không để dồn hàng đợi.
        self._busy = threading.Lock()
        self._status_lock = threading.Lock()
        self._status: dict | None = None
        self._status_checked_at = 0.0

    # ---------- trạng thái ----------
    def status(self, max_age: float = 30.0) -> dict:
        """Ollama có chạy và đã có model chưa (kết quả được nhớ ``max_age`` giây)."""
        if not self.enabled:
            return {"enabled": False, "available": False, "model": self.model, "host": self.host,
                    "message": "Đã tắt bằng VLM_ENABLED=0"}
        with self._status_lock:
            if self._status is not None and time.monotonic() - self._status_checked_at < max_age:
                return self._status
            try:
                response = self._client.get(f"{self.host}/api/tags", timeout=3)
                response.raise_for_status()
                names = {item.get("name", "") for item in response.json().get("models", [])}
                has_model = self.model in names or f"{self.model}:latest" in names
                message = "Sẵn sàng" if has_model else f"Ollama đang chạy nhưng chưa có model. Chạy: ollama pull {self.model}"
                self._status = {"enabled": True, "available": has_model, "model": self.model, "host": self.host, "message": message}
            except (httpx.HTTPError, ValueError):
                self._status = {"enabled": True, "available": False, "model": self.model, "host": self.host,
                                "message": "Không kết nối được Ollama. Mở ứng dụng Ollama hoặc chạy: ollama serve"}
            self._status_checked_at = time.monotonic()
            return self._status

    def is_available(self) -> bool:
        return bool(self.status().get("available"))

    def _generate(self, image_b64: str) -> str:
        payload = {
            "model": self.model,
            "prompt": PROMPT,
            "images": [image_b64],
            "stream": False,
            "keep_alive": os.getenv("VLM_KEEP_ALIVE", "30m"),
            "options": {"temperature": 0, "num_predict": 24},
        }
        response = self._client.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
        response.raise_for_status()
        return str(response.json().get("response", "")).strip()

    def reset_runner(self) -> None:
        """Gỡ model khỏi bộ nhớ (keep_alive=0); lượt gọi sau Ollama tự nạp lại."""
        try:
            self._client.post(f"{self.host}/api/generate", json={"model": self.model, "keep_alive": 0}, timeout=self.timeout)
        except httpx.HTTPError as error:
            logger.warning("Không gỡ được model VLM: %s", error)

    # ---------- đọc biển ----------
    def read_plate(self, image: np.ndarray, wait: bool = False) -> VlmReading | None:
        """Đọc biển số trong ảnh BGR. Trả ``None`` nếu VLM không dùng được hoặc đang bận."""
        if image is None or image.size == 0 or not self.is_available():
            return None
        if not self._busy.acquire(blocking=wait):
            return None
        try:
            # Ảnh lớn không giúp VLM đọc tốt hơn nhưng làm chậm; giới hạn cạnh dài 1024px.
            height, width = image.shape[:2]
            scale = 1024 / max(height, width)
            if scale < 1:
                image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            started = time.perf_counter()
            raw_text = ""
            # Một số ảnh làm runner của Ollama rơi vào trạng thái hỏng: từ đó mọi
            # câu trả lời đều là "8888..." cho tới khi model được nạp lại. Phát hiện
            # chuỗi lặp bất thường, gỡ model khỏi bộ nhớ rồi thử lại bằng PNG.
            for extension, params in ((".jpg", [cv2.IMWRITE_JPEG_QUALITY, 92]), (".png", [])):
                ok, buffer = cv2.imencode(extension, image, params)
                if not ok:
                    continue
                raw_text = self._generate(base64.b64encode(buffer.tobytes()).decode("ascii"))
                if not is_degenerate_output(raw_text):
                    break
                logger.warning("VLM trả chuỗi lặp bất thường (%r); nạp lại model", raw_text[:30])
                self.reset_runner()
            elapsed_ms = (time.perf_counter() - started) * 1000
            if is_degenerate_output(raw_text):
                return VlmReading(None, raw_text, round(elapsed_ms, 1))
            plate = normalize_plate(raw_text)
            return VlmReading(plate if is_valid_vn_plate(plate) else None, raw_text, round(elapsed_ms, 1))
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("VLM không đọc được biển số: %s", error)
            with self._status_lock:
                self._status = None  # kiểm tra lại kết nối ở lần sau
            return None
        finally:
            self._busy.release()
