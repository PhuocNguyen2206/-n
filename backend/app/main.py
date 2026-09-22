import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .database import get_connection, initialize_database
from .schemas import (
    PersonCreate,
    RecognitionRequest,
    RecognitionResult,
    VehicleCreate,
)
from .services.vision import VisionService
from .services.face import FaceService

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
face_service: FaceService | None = None


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def get_vision_service() -> VisionService:
    global vision_service
    if vision_service is None:
        vision_service = VisionService()
    return vision_service


def get_face_service() -> FaceService:
    global face_service
    if face_service is None:
        face_service = FaceService()
    return face_service


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
        "plate_text": analysis.plate_text,
        "plate_confidence": analysis.plate_confidence,
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


@app.get("/api/v1/people")
def list_people() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT p.id, p.full_name, p.campus_id, p.role,
                   CASE WHEN p.face_embedding IS NULL THEN 0 ELSE 1 END AS face_registered,
                   GROUP_CONCAT(v.plate_number, ', ') AS plates
            FROM people p
            LEFT JOIN vehicles v ON v.owner_id = p.id AND v.active = 1
            GROUP BY p.id
            ORDER BY p.full_name
            """
        ).fetchall()
        return [dict(row) for row in rows]


@app.post("/api/v1/people/{person_id}/face-enrollment")
async def enroll_face(person_id: str, image: UploadFile = File(...)) -> dict:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(415, "Chỉ hỗ trợ tệp hình ảnh")
    try:
        face = get_face_service().extract(await image.read())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    with get_connection() as connection:
        person = connection.execute("SELECT id FROM people WHERE id = ?", (person_id,)).fetchone()
        if not person:
            raise HTTPException(404, "Không tìm thấy người đăng ký")
        connection.execute("UPDATE people SET face_embedding = ? WHERE id = ?", (json.dumps(face.embedding), person_id))
    return {"person_id": person_id, "face_confidence": face.confidence}


@app.post("/api/v1/gate/verify", response_model=RecognitionResult)
async def verify_gate_image(
    images: list[UploadFile] = File(...), direction: str = Form("exit")
) -> RecognitionResult:
    if direction not in {"entry", "exit"}:
        raise HTTPException(422, "Hướng di chuyển không hợp lệ")
    plate, plate_confidence, faces = None, 0.0, []
    for image in images:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(415, "Chỉ hỗ trợ tệp hình ảnh")
        image_data = await image.read()
        try:
            analysis = get_vision_service().analyze_image(image_data)
            if not plate and analysis.plate_text:
                plate, plate_confidence = analysis.plate_text, analysis.plate_confidence or 0.0
        except ValueError:
            continue
        try:
            faces.extend(get_face_service().extract_all(image_data))
        except ValueError:
            pass
    event_id = str(uuid4())
    decision, reason, person_id, person_name, score = "denied", "Không đọc được biển số xe", None, None, 0.0
    with get_connection() as connection:
        vehicle = connection.execute("SELECT * FROM vehicles WHERE plate_number = ? AND active = 1", (plate,)).fetchone() if plate else None
        known_people = connection.execute("SELECT * FROM people WHERE face_embedding IS NOT NULL").fetchall()
        matched_people: dict[str, tuple[object, float]] = {}
        for captured_face in faces:
            for candidate in known_people:
                similarity = get_face_service().similarity(captured_face.embedding, json.loads(candidate["face_embedding"]))
                if similarity >= 0.45 and (candidate["id"] not in matched_people or similarity > matched_people[candidate["id"]][1]):
                    matched_people[candidate["id"]] = (candidate, similarity)
        if not faces:
            reason = "Không phát hiện được khuôn mặt rõ trong các ảnh đã chọn"
        elif vehicle:
            owner_match = matched_people.get(vehicle["owner_id"])
            if direction == "entry" and owner_match:
                decision, reason = "approved", "Chủ xe hợp lệ; đã ghi nhận những người cùng vào xe"
                owner, score = owner_match
                person_id, person_name = owner["id"], owner["full_name"]
                session_id = str(uuid4())
                connection.execute(
                    "INSERT INTO vehicle_sessions (id, vehicle_id, entry_event_id, entered_at) VALUES (?, ?, ?, ?)",
                    (session_id, vehicle["id"], event_id, datetime.now(timezone.utc).isoformat()),
                )
                for matched_id in matched_people:
                    connection.execute("INSERT INTO vehicle_session_people (session_id, person_id) VALUES (?, ?)", (session_id, matched_id))
            elif direction == "entry":
                reason = "Lúc xe vào phải nhận diện được khuôn mặt chủ xe"
            else:
                session = connection.execute(
                    "SELECT * FROM vehicle_sessions WHERE vehicle_id = ? AND status = 'open' ORDER BY entered_at DESC LIMIT 1", (vehicle["id"],)
                ).fetchone()
                allowed_ids = {vehicle["owner_id"]}
                if session:
                    allowed_ids = {row["person_id"] for row in connection.execute("SELECT person_id FROM vehicle_session_people WHERE session_id = ?", (session["id"],))}
                valid_matches = [(candidate, similarity) for candidate_id, (candidate, similarity) in matched_people.items() if candidate_id in allowed_ids]
                if valid_matches:
                    matched, score = max(valid_matches, key=lambda item: item[1])
                    decision, reason = "approved", "Người điều khiển đã được ghi nhận cùng xe khi vào cổng"
                    person_id, person_name = matched["id"], matched["full_name"]
                    if session:
                        connection.execute("UPDATE vehicle_sessions SET status = 'closed', exited_at = ? WHERE id = ?", (datetime.now(timezone.utc).isoformat(), session["id"]))
                else:
                    reason = "Khuôn mặt không thuộc nhóm người đã vào cùng phương tiện này"
        elif plate:
            reason = "Không tìm thấy phương tiện đã đăng ký"
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, plate_number, person_id, decision, reason, plate_confidence, face_confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, datetime.now(timezone.utc).isoformat(), direction, plate, person_id, decision, reason, plate_confidence, score),
        )
    return RecognitionResult(
        event_id=event_id, decision=decision, reason=reason, person_name=person_name,
        plate_number=plate, face_detected=bool(faces),
        face_detection_confidence=max((face.confidence for face in faces), default=None),
        face_similarity=score if plate else None,
    )


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


@app.get("/api/v1/vehicles")
def list_vehicles() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT v.*, p.full_name AS owner_name, p.campus_id AS owner_campus_id FROM vehicles v JOIN people p ON p.id = v.owner_id ORDER BY v.plate_number"
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/v1/dashboard/summary")
def dashboard_summary() -> dict:
    with get_connection() as connection:
        totals = connection.execute(
            "SELECT COUNT(*) AS total, SUM(decision = 'approved') AS approved, SUM(decision = 'denied') AS denied FROM access_events"
        ).fetchone()
        registered = connection.execute("SELECT COUNT(*) AS people, (SELECT COUNT(*) FROM vehicles WHERE active = 1) AS vehicles FROM people").fetchone()
        return {
            "events": totals["total"] or 0,
            "approved": totals["approved"] or 0,
            "denied": totals["denied"] or 0,
            "people": registered["people"] or 0,
            "vehicles": registered["vehicles"] or 0,
        }


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
            authorized = vehicle["owner_id"] == person_id
            decision, reason = ("approved", "Xác thực chính chủ hợp lệ") if authorized else ("denied", "Người điều khiển không phải chủ xe đã đăng ký")
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, plate_number, person_id, decision, reason, plate_confidence, face_confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, now.isoformat(), payload.direction, plate, person_id, decision, reason, payload.plate_confidence, payload.face_confidence),
        )
    return RecognitionResult(event_id=event_id, decision=decision, reason=reason, person_name=person_name, plate_number=plate)


@app.get("/api/v1/events")
def list_events(limit: int = 20) -> list[dict]:
    with get_connection() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM access_events ORDER BY occurred_at DESC LIMIT ?", (min(limit, 100),))]
