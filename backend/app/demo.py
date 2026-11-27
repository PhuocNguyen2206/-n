"""Chế độ "Xem thử" cho khách chưa đăng nhập.

Khách chỉ gửi một ảnh và nhận lại biển số cùng vị trí khuôn mặt. Không tạo phiên,
không ghi cơ sở dữ liệu, không lưu ảnh và không đối chiếu danh tính, nên khách
không chạm được vào dữ liệu thật của cổng.
"""

import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException


class GuestLimiter:
    """Mỗi lúc một lượt khách, và tối đa ``per_minute`` lượt trong 60 giây."""

    def __init__(self, per_minute: int, clock=time.monotonic) -> None:
        self.per_minute = per_minute
        self._clock = clock
        self._times: deque[float] = deque()
        self._busy = threading.Lock()

    @contextmanager
    def slot(self) -> Iterator[None]:
        if not self._busy.acquire(blocking=False):
            raise HTTPException(429, "Đang có người khác thử. Vui lòng thử lại sau vài giây.")
        try:
            now = self._clock()
            while self._times and now - self._times[0] >= 60:
                self._times.popleft()
            if len(self._times) >= self.per_minute:
                raise HTTPException(429, "Đã quá số lượt thử trong một phút. Vui lòng đợi một chút.")
            self._times.append(now)
            yield
        finally:
            self._busy.release()
