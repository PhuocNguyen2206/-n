import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import get_connection, initialize_database
from .schemas import RecognitionResult
from .services.vision import VisionService
from .services.face import FaceService

app = FastAPI(title="Vehicle AI Gateway", version="0.1.0")
EVIDENCE_DIRECTORY = Path("data/evidence")
EVIDENCE_DIRECTORY.mkdir(parents=True, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=str(EVIDENCE_DIRECTORY)), name="evidence")
TRAINING_DIRECTORY = Path("data/training_samples")
TRAINING_DIRECTORY.mkdir(parents=True, exist_ok=True)
app.mount("/training-data", StaticFiles(directory=str(TRAINING_DIRECTORY)), name="training-data")
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


def save_evidence(event_id: str, direction: str, image_data: bytes) -> str:
    """Lưu ảnh bằng chứng cục bộ, tách biệt với dữ liệu nhúng khuôn mặt."""
    filename = f"{event_id}_{direction}.jpg"
    (EVIDENCE_DIRECTORY / filename).write_bytes(image_data)
    return filename


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
    images: list[UploadFile] = File(...), direction: str = Form("exit"), automatic: bool = Form(False)
) -> RecognitionResult:
    if direction not in {"entry", "exit"}:
        raise HTTPException(422, "Hướng di chuyển không hợp lệ")
    plate, plate_confidence, faces, frames = None, 0.0, [], []
    for image in images:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(415, "Chỉ hỗ trợ tệp hình ảnh")
        image_data = await image.read()
        frames.append(image_data)
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
    evidence_path = None
    with get_connection() as connection:
        # Camera tự động gửi nhiều khung hình. Khi khung chưa đủ dữ liệu, chỉ
        # báo trạng thái chờ thay vì ghi hàng loạt lỗi vào nhật ký bảo vệ.
        if automatic and (not plate or not faces):
            waiting_reason = "Đang chờ biển số xe rõ" if not plate else "Đang chờ khuôn mặt rõ"
            return RecognitionResult(
                event_id="live-preview", decision="manual_review", reason=waiting_reason,
                plate_number=plate, face_detected=bool(faces),
                face_detection_confidence=max((face.confidence for face in faces), default=None),
            )
        if not faces:
            reason = "Không phát hiện được khuôn mặt rõ trong các ảnh đã chọn"
        elif plate and direction == "entry":
            existing = connection.execute("SELECT id FROM gate_sessions WHERE plate_number = ? AND status = 'open' ORDER BY entered_at DESC LIMIT 1", (plate,)).fetchone()
            decision, reason = "approved", ("Xe đã có lượt vào đang mở; bỏ qua khung hình lặp" if existing else "Đã ghi nhận xe và khuôn mặt tại thời điểm vào")
            if automatic and existing:
                return RecognitionResult(
                    event_id=existing["id"], decision="approved", reason=reason, plate_number=plate,
                    face_detected=True, face_detection_confidence=max(face.confidence for face in faces),
                )
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
        if plate and faces and frames:
            evidence_path = save_evidence(event_id, direction, frames[0])
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, plate_number, person_id, decision, reason, plate_confidence, face_confidence, evidence_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, datetime.now(timezone.utc).isoformat(), direction, plate, None, decision, reason, plate_confidence, score, evidence_path),
        )
        if plate and faces and direction == "entry" and decision == "approved" and not existing:
            session_id = str(uuid4())
            connection.execute("INSERT INTO gate_sessions (id, plate_number, entry_event_id, entered_at, entry_evidence_path) VALUES (?, ?, ?, ?, ?)", (session_id, plate, event_id, datetime.now(timezone.utc).isoformat(), evidence_path))
            connection.executemany("INSERT INTO gate_session_faces (session_id, embedding, confidence) VALUES (?, ?, ?)", [(session_id, json.dumps(face.embedding), face.confidence) for face in faces])
        if plate and direction == "exit" and decision == "approved" and session:
            connection.execute("UPDATE gate_sessions SET status = 'closed', exited_at = ?, exit_event_id = ?, exit_evidence_path = ? WHERE id = ?", (datetime.now(timezone.utc).isoformat(), event_id, evidence_path, session["id"]))
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
        rows = connection.execute("SELECT * FROM access_events ORDER BY occurred_at DESC LIMIT ?", (min(limit, 100),)).fetchall()
        events = []
        for row in rows:
            event = dict(row)
            event["evidence_url"] = f"/evidence/{event['evidence_path']}" if event["evidence_path"] else None
            events.append(event)
        return events


@app.get("/api/v1/sessions/recent")
def recent_gate_sessions(limit: int = 6) -> list[dict]:
    """Dữ liệu đối chiếu trực quan giữa bằng chứng lúc vào và lúc ra."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT gate_sessions.*, entry_event.decision AS entry_decision,
                   exit_event.decision AS exit_decision, exit_event.reason AS exit_reason
            FROM gate_sessions
            LEFT JOIN access_events AS entry_event ON entry_event.id = gate_sessions.entry_event_id
            LEFT JOIN access_events AS exit_event ON exit_event.id = gate_sessions.exit_event_id
            ORDER BY COALESCE(gate_sessions.exited_at, gate_sessions.entered_at) DESC
            LIMIT ?
            """,
            (min(limit, 20),),
        ).fetchall()
        sessions = []
        for row in rows:
            session = dict(row)
            session["entry_evidence_url"] = f"/evidence/{session['entry_evidence_path']}" if session["entry_evidence_path"] else None
            session["exit_evidence_url"] = f"/evidence/{session['exit_evidence_path']}" if session["exit_evidence_path"] else None
            sessions.append(session)
        return sessions


@app.get("/api/v1/dataset/samples")
def list_training_samples(limit: int = 60) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM training_samples ORDER BY created_at DESC LIMIT ?", (min(limit, 100),)
        ).fetchall()
        return [{**dict(row), "image_url": f"/training-data/{row['image_path']}"} for row in rows]


@app.post("/api/v1/dataset/samples")
async def add_training_sample(image: UploadFile = File(...), plate_label: str = Form("")) -> dict:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(415, "Chỉ hỗ trợ tệp hình ảnh")
    suffix = Path(image.filename or "sample.jpg").suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    sample_id = str(uuid4())
    filename = f"{sample_id}{suffix}"
    (TRAINING_DIRECTORY / filename).write_bytes(await image.read())
    cleaned_label = plate_label.strip().upper()
    now = datetime.now(timezone.utc).isoformat()
    status = "labeled" if cleaned_label else "unlabeled"
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO training_samples (id, image_path, plate_label, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (sample_id, filename, cleaned_label or None, status, now, now),
        )
    return {"id": sample_id, "image_url": f"/training-data/{filename}", "plate_label": cleaned_label or None, "status": status}


@app.patch("/api/v1/dataset/samples/{sample_id}")
async def label_training_sample(sample_id: str, plate_label: str = Form(...)) -> dict:
    cleaned_label = plate_label.strip().upper()
    if not cleaned_label:
        raise HTTPException(422, "Hãy nhập biển số để gán nhãn")
    with get_connection() as connection:
        result = connection.execute(
            "UPDATE training_samples SET plate_label = ?, status = 'labeled', updated_at = ? WHERE id = ?",
            (cleaned_label, datetime.now(timezone.utc).isoformat(), sample_id),
        )
        if result.rowcount == 0:
            raise HTTPException(404, "Không tìm thấy ảnh dữ liệu")
    return {"id": sample_id, "plate_label": cleaned_label, "status": "labeled"}


@app.get("/api/v1/model/status")
def model_status() -> dict:
    with get_connection() as connection:
        dataset = connection.execute(
            "SELECT COUNT(*) AS total, SUM(status = 'labeled') AS labeled FROM training_samples"
        ).fetchone()
        latest_event = connection.execute(
            "SELECT plate_confidence, face_confidence, occurred_at FROM access_events ORDER BY occurred_at DESC LIMIT 1"
        ).fetchone()
    custom_model = Path("models/license_plate.pt").is_file()
    return {
        "model_name": "license_plate.pt" if custom_model else "yolov8n.pt (mô hình tổng quát)",
        "custom_plate_model": custom_model,
        "dataset_total": dataset["total"] or 0,
        "dataset_labeled": dataset["labeled"] or 0,
        "evaluation": {"precision": None, "recall": None, "map50": None},
        "latest_confidence": dict(latest_event) if latest_event else None,
    }
