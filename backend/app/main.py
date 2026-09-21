from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .database import get_connection, initialize_database
from .schemas import (
    AuthorizationCreate,
    PersonCreate,
    RecognitionRequest,
    RecognitionResult,
    VehicleCreate,
)
from .services.vision import VisionService

app = FastAPI(title="Vehicle AI Gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
vision_service: VisionService | None = None


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def get_vision_service() -> VisionService:
    global vision_service
    if vision_service is None:
        vision_service = VisionService()
    return vision_service


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/vision/analyze")
async def analyze_image(image: UploadFile = File(...)) -> dict:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(415, "Chỉ hỗ trợ tệp hình ảnh")
    try:
        analysis = get_vision_service().analyze_image(await image.read())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {
        "model": analysis.model_name,
        "uses_plate_model": analysis.uses_plate_model,
        "detections": [item.__dict__ for item in analysis.detections],
    }


@app.post("/api/v1/people", status_code=201)
def create_person(payload: PersonCreate) -> dict:
    person_id = str(uuid4())
    try:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO people (id, full_name, campus_id, role, face_token) VALUES (?, ?, ?, ?, ?)",
                (person_id, payload.full_name, payload.campus_id, payload.role, payload.face_token),
            )
    except Exception as error:
        raise HTTPException(409, "Mã trường hoặc face token đã tồn tại") from error
    return {"id": person_id, **payload.model_dump()}


@app.post("/api/v1/vehicles", status_code=201)
def create_vehicle(payload: VehicleCreate) -> dict:
    vehicle_id = str(uuid4())
    plate = payload.plate_number.upper().replace(" ", "")
    with get_connection() as connection:
        owner = connection.execute("SELECT id FROM people WHERE id = ?", (payload.owner_id,)).fetchone()
        if not owner:
            raise HTTPException(404, "Không tìm thấy chủ phương tiện")
        try:
            connection.execute(
                "INSERT INTO vehicles (id, plate_number, owner_id, vehicle_type) VALUES (?, ?, ?, ?)",
                (vehicle_id, plate, payload.owner_id, payload.vehicle_type),
            )
        except Exception as error:
            raise HTTPException(409, "Biển số đã tồn tại") from error
    return {"id": vehicle_id, "plate_number": plate, **payload.model_dump(exclude={"plate_number"})}


@app.post("/api/v1/authorizations", status_code=201)
def create_authorization(payload: AuthorizationCreate) -> dict:
    if payload.valid_until <= payload.valid_from:
        raise HTTPException(422, "Thời điểm hết hạn phải sau thời điểm bắt đầu")
    authorization_id = str(uuid4())
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO vehicle_authorizations (id, vehicle_id, borrower_id, valid_from, valid_until, note) VALUES (?, ?, ?, ?, ?, ?)",
            (authorization_id, payload.vehicle_id, payload.borrower_id, payload.valid_from.isoformat(), payload.valid_until.isoformat(), payload.note),
        )
    return {"id": authorization_id, **payload.model_dump()}


@app.post("/api/v1/recognition/process", response_model=RecognitionResult)
def process_recognition(payload: RecognitionRequest) -> RecognitionResult:
    now = datetime.now(timezone.utc)
    plate = payload.plate_number.upper().replace(" ", "") if payload.plate_number else None
    event_id = str(uuid4())
    decision, reason, person_name, person_id = "manual_review", "Không đủ dữ liệu để tự động đối soát", None, None

    with get_connection() as connection:
        person = connection.execute("SELECT * FROM people WHERE face_token = ?", (payload.face_token,)).fetchone() if payload.face_token else None
        vehicle = connection.execute("SELECT * FROM vehicles WHERE plate_number = ? AND active = 1", (plate,)).fetchone() if plate else None
        if not plate or not payload.face_token or payload.plate_confidence < 0.80 or payload.face_confidence < 0.80:
            decision, reason = "manual_review", "Cần bảo vệ kiểm tra do độ tin cậy hoặc dữ liệu nhận diện chưa đủ"
        elif not vehicle:
            decision, reason = "denied", "Không tìm thấy phương tiện đã đăng ký"
        elif not person:
            decision, reason = "denied", "Không nhận diện được người điều khiển"
        else:
            person_id, person_name = person["id"], person["full_name"]
            authorized = vehicle["owner_id"] == person_id or connection.execute(
                "SELECT 1 FROM vehicle_authorizations WHERE vehicle_id = ? AND borrower_id = ? AND valid_from <= ? AND valid_until >= ?",
                (vehicle["id"], person_id, now.isoformat(), now.isoformat()),
            ).fetchone()
            decision, reason = ("approved", "Xác thực chính chủ hoặc ủy quyền hợp lệ") if authorized else ("denied", "Người điều khiển chưa được ủy quyền dùng phương tiện này")
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, plate_number, person_id, decision, reason, plate_confidence, face_confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, now.isoformat(), payload.direction, plate, person_id, decision, reason, payload.plate_confidence, payload.face_confidence),
        )
    return RecognitionResult(event_id=event_id, decision=decision, reason=reason, person_name=person_name, plate_number=plate)


@app.get("/api/v1/events")
def list_events(limit: int = 20) -> list[dict]:
    with get_connection() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM access_events ORDER BY occurred_at DESC LIMIT ?", (min(limit, 100),))]
