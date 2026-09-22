import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .database import get_connection, initialize_database
from .schemas import RecognitionResult
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


@app.post("/api/v1/face/analyze")
async def analyze_face(image: UploadFile = File(...)) -> dict:
    """Chế độ demo: chỉ phát hiện khuôn mặt, không lưu và không đối chiếu danh tính."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(415, "Chỉ hỗ trợ tệp hình ảnh")
    try:
        return get_face_service().detect(await image.read())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


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
    decision, reason, score = "denied", "Không đọc được biển số xe", 0.0
    with get_connection() as connection:
        if not faces:
            reason = "Không phát hiện được khuôn mặt rõ trong các ảnh đã chọn"
        elif plate and direction == "entry":
            existing = connection.execute("SELECT id FROM gate_sessions WHERE plate_number = ? AND status = 'open' ORDER BY entered_at DESC LIMIT 1", (plate,)).fetchone()
            decision, reason = "approved", ("Xe đã có lượt vào đang mở; bỏ qua khung hình lặp" if existing else "Đã ghi nhận xe và khuôn mặt tại thời điểm vào")
        elif plate:
            session = connection.execute("SELECT * FROM gate_sessions WHERE plate_number = ? AND status = 'open' ORDER BY entered_at DESC LIMIT 1", (plate,)).fetchone()
            if not session:
                reason = "Không có lượt vào đang mở của biển số này"
            else:
                entry_faces = connection.execute("SELECT embedding FROM gate_session_faces WHERE session_id = ?", (session["id"],)).fetchall()
                similarities = [get_face_service().similarity(current.embedding, json.loads(saved["embedding"])) for current in faces for saved in entry_faces]
                score = max(similarities, default=0.0)
                if score >= 0.45:
                    decision, reason = "approved", "Khuôn mặt khớp với người đã vào cùng xe"
                else:
                    reason = "Khuôn mặt hiện tại không khớp lượt xe lúc vào"
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, plate_number, person_id, decision, reason, plate_confidence, face_confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, datetime.now(timezone.utc).isoformat(), direction, plate, None, decision, reason, plate_confidence, score),
        )
        if plate and faces and direction == "entry" and decision == "approved" and not existing:
            session_id = str(uuid4())
            connection.execute("INSERT INTO gate_sessions (id, plate_number, entry_event_id, entered_at) VALUES (?, ?, ?, ?)", (session_id, plate, event_id, datetime.now(timezone.utc).isoformat()))
            connection.executemany("INSERT INTO gate_session_faces (session_id, embedding, confidence) VALUES (?, ?, ?)", [(session_id, json.dumps(face.embedding), face.confidence) for face in faces])
        if plate and direction == "exit" and decision == "approved" and session:
            connection.execute("UPDATE gate_sessions SET status = 'closed', exited_at = ? WHERE id = ?", (datetime.now(timezone.utc).isoformat(), session["id"]))
    return RecognitionResult(
        event_id=event_id, decision=decision, reason=reason,
        plate_number=plate, face_detected=bool(faces),
        face_detection_confidence=max((face.confidence for face in faces), default=None),
        face_similarity=score if plate else None,
    )


@app.get("/api/v1/dashboard/summary")
def dashboard_summary() -> dict:
    with get_connection() as connection:
        totals = connection.execute(
            "SELECT COUNT(*) AS total, SUM(decision = 'approved') AS approved, SUM(decision = 'denied') AS denied FROM access_events"
        ).fetchone()
        return {
            "events": totals["total"] or 0,
            "approved": totals["approved"] or 0,
            "denied": totals["denied"] or 0,
        }


@app.get("/api/v1/events")
def list_events(limit: int = 20) -> list[dict]:
    with get_connection() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM access_events ORDER BY occurred_at DESC LIMIT ?", (min(limit, 100),))]
