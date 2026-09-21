from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PersonCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    campus_id: str = Field(min_length=3, max_length=30)
    role: Literal["student", "staff", "security"] = "student"
    face_token: str | None = None


class VehicleCreate(BaseModel):
    plate_number: str = Field(min_length=5, max_length=20)
    owner_id: str
    vehicle_type: Literal["motorbike", "car"] = "motorbike"


class AuthorizationCreate(BaseModel):
    vehicle_id: str
    borrower_id: str
    valid_from: datetime
    valid_until: datetime
    note: str | None = Field(default=None, max_length=300)


class RecognitionRequest(BaseModel):
    plate_number: str | None = Field(default=None, max_length=20)
    face_token: str | None = Field(default=None, max_length=128)
    direction: Literal["entry", "exit"] = "entry"
    plate_confidence: float = Field(default=0, ge=0, le=1)
    face_confidence: float = Field(default=0, ge=0, le=1)


class RecognitionResult(BaseModel):
    event_id: str
    decision: Literal["approved", "manual_review", "denied"]
    reason: str
    person_name: str | None = None
    plate_number: str | None = None
