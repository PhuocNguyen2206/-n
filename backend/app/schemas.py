from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PersonCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    campus_id: str = Field(min_length=3, max_length=30)
    role: Literal["student", "staff", "security"] = "student"
    face_token: str | None = None


class VehicleCreate(BaseModel):
    plate_number: str = Field(min_length=5, max_length=20)
    owner_id: str
    vehicle_type: Literal["motorbike", "car"] = "motorbike"


class RecognitionRequest(BaseModel):
    plate_number: str | None = Field(default=None, max_length=20)
    face_token: str | None = Field(default=None, max_length=128)
    direction: Literal["entry", "exit"] = "entry"
    plate_confidence: float = Field(default=0, ge=0, le=1)
    face_confidence: float = Field(default=0, ge=0, le=1)


class RecognitionResult(BaseModel):
    event_id: str
    review_id: str | None = None
    entry_evidence_url: str | None = None
    entered_at: str | None = None
    evidence_url: str | None = None
    captured_at: str | None = None
    decision: Literal["approved", "manual_review", "manual_approved", "denied"]
    reason: str
    person_name: str | None = None
    plate_number: str | None = None
    face_detected: bool = False
    face_detection_confidence: float | None = None
    face_similarity: float | None = None
    plate_source: Literal["ocr", "vlm"] | None = None
    authorization_id: str | None = None


class ManualGateEventRequest(BaseModel):
    """Một lượt qua cổng không dùng AI nhưng vẫn phải có nhật ký."""

    direction: Literal["entry", "exit"] = "entry"
    exception_type: Literal["pedestrian", "emergency", "camera_failure", "security_override"]
    # Bỏ qua: người xử lý lấy từ tài khoản đăng nhập. Giữ trường để client cũ không lỗi.
    operator_name: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=300)


class ExitReviewResolution(BaseModel):
    action: Literal["approve", "reject"]
    # Bỏ qua: người xử lý lấy từ tài khoản đăng nhập. Giữ trường để client cũ không lỗi.
    operator_name: str | None = Field(default=None, max_length=120)
    reason: str = Field(min_length=3, max_length=300)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value
