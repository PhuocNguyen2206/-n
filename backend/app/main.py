import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image

from . import config
from .auth import StaffUser, active_user, ensure_default_admin
from .auth import router as auth_router
from .database import get_connection, initialize_database
from .demo import GuestLimiter
from .schemas import ExitReviewResolution, ManualGateEventRequest, RecognitionResult
from .services.face import FaceService
from .services.face_quality import UNCLEAR_REASON, clear_faces
from .services.vision import VisionService
from .services.vlm import VlmPlateReader

@asynccontextmanager
async def lifespan(_: FastAPI):
    EVIDENCE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    TRAINING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    initialize_database()
    ensure_default_admin()
    yield


app = FastAPI(title="Vehicle AI Gateway", version="0.2.0", lifespan=lifespan)
EVIDENCE_DIRECTORY = config.data_directory() / "evidence"
TRAINING_DIRECTORY = config.data_directory() / "training_samples"
MODELS_DIRECTORY = config.BACKEND_DIRECTORY / "models"
_extra_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        *_extra_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
vision_service: VisionService | None = None
vlm_status_reader = VlmPlateReader()  # dùng cho /model/status khi chưa nạp VisionService
face_service: FaceService | None = None
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]+$")
guest_limiter = GuestLimiter(config.GUEST_DEMO_PER_MINUTE)


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


# Quét tự động ở lối ra: trong khoảng này sau khi xe được cho ra, khung hình lặp của xe đó không ghi nhật ký.
EXIT_REPEAT_WINDOW_SECONDS = 60
CROWDED_REASON = "Có hai xe cùng trong khung: mời từng xe tiến vào"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def evidence_url(path: str | None) -> str | None:
    return f"/evidence/{path}" if path else None


def normalize_plate_input(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


async def read_image_upload(image: UploadFile) -> bytes:
    """Đọc ảnh tải lên với giới hạn dung lượng; chặn tệp không phải ảnh."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(415, "Chỉ hỗ trợ tệp hình ảnh")
    limit = int(config.MAX_UPLOAD_MB * 1024 * 1024)
    data = await image.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Ảnh vượt quá {config.MAX_UPLOAD_MB:g} MB")
    if not data:
        raise HTTPException(422, "Ảnh rỗng")
    return data


def ensure_decodable(image_data: bytes) -> None:
    try:
        with Image.open(BytesIO(image_data)) as decoded:
            decoded.verify()
    except (OSError, ValueError) as error:
        raise HTTPException(422, "Ảnh không hợp lệ hoặc không đọc được") from error


def save_evidence(event_id: str, direction: str, frames: list[bytes]) -> str:
    """Store one JPEG; paired inputs keep face (left) and plate (right)."""
    filename = f"{event_id}_{direction}.jpg"
    EVIDENCE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    if len(frames) == 1:
        with Image.open(BytesIO(frames[0])) as image:
            image.convert("RGB").save(EVIDENCE_DIRECTORY / filename, format="JPEG", quality=90)
    else:
        images = []
        for frame in frames:
            with Image.open(BytesIO(frame)) as image:
                tile = image.convert("RGB")
                tile.thumbnail((1280, 720))
                images.append(tile)
        evidence = Image.new("RGB", (sum(image.width for image in images), max(image.height for image in images)), "black")
        offset = 0
        for image in images:
            evidence.paste(image, (offset, 0))
            offset += image.width
        evidence.save(EVIDENCE_DIRECTORY / filename, format="JPEG", quality=90)
    return filename


def _serve_file(directory: Path, filename: str) -> FileResponse:
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(404, "Không tìm thấy tệp")
    path = directory / filename
    if not path.is_file():
        raise HTTPException(404, "Không tìm thấy tệp")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/evidence/{filename}")
def get_evidence(filename: str, _: StaffUser = Depends(active_user)) -> FileResponse:
    """Ảnh bằng chứng có khuôn mặt: chỉ người đã đăng nhập mới xem được."""
    return _serve_file(EVIDENCE_DIRECTORY, filename)


@app.get("/training-data/{filename}")
def get_training_image(filename: str, _: StaffUser = Depends(active_user)) -> FileResponse:
    return _serve_file(TRAINING_DIRECTORY, filename)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/vision/analyze")
async def analyze_image(image: UploadFile = File(...), _: StaffUser = Depends(active_user)) -> dict:
    image_data = await read_image_upload(image)
    try:
        # Chạy trong threadpool: lượt gọi VLM (~1-2 s) không được chặn các request khác.
        analysis = await run_in_threadpool(get_vision_service().analyze_image, image_data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {
        "model": analysis.model_name,
        "uses_plate_model": analysis.uses_plate_model,
        "detections": [item.__dict__ for item in analysis.detections],
        "plate_text": analysis.plate_text,
        "plate_confidence": analysis.plate_confidence,
        "plate_source": analysis.plate_source,
        "ocr_text": analysis.ocr_text,
        "ocr_min_confidence": analysis.ocr_min_confidence,
        "vlm_text": analysis.vlm_text,
        "vlm_ms": analysis.vlm_ms,
    }


@app.post("/api/v1/face/analyze")
async def analyze_face(image: UploadFile = File(...), _: StaffUser = Depends(active_user)) -> dict:
    """Chế độ demo: chỉ phát hiện khuôn mặt, không lưu và không đối chiếu danh tính."""
    image_data = await read_image_upload(image)
    try:
        return await run_in_threadpool(get_face_service().detect, image_data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/v1/demo/status")
def demo_status() -> dict[str, bool]:
    return {"enabled": config.GUEST_DEMO}


@app.post("/api/v1/demo/analyze")
async def demo_analyze(image: UploadFile = File(...), lane: Literal["face", "plate"] | None = Form(None)) -> dict:
    """Khách thử nhận diện một ảnh: không cần đăng nhập, không lưu, không đối chiếu danh tính.

    ``lane`` cho biết ảnh đến từ camera nào để chỉ chạy đúng phần nhận diện đó; bỏ trống thì chạy cả hai.
    """
    if not config.GUEST_DEMO:
        raise HTTPException(404, "Chế độ xem thử đang tắt")
    image_data = await read_image_upload(image)
    ensure_decodable(image_data)
    with Image.open(BytesIO(image_data)) as header:
        width, height = header.size
    if width * height > config.GUEST_DEMO_MAX_PIXELS:
        raise HTTPException(413, "Ảnh có kích thước quá lớn")
    faces: list = []
    analysis = None
    with guest_limiter.slot():
        try:
            if lane != "plate":
                faces = (await run_in_threadpool(get_face_service().detect, image_data))["faces"]
            if lane != "face":
                analysis = await run_in_threadpool(get_vision_service().analyze_image, image_data)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    return {
        "width": width,
        "height": height,
        "faces": faces,
        "plate_boxes": [item.box for item in analysis.detections] if analysis and analysis.uses_plate_model else [],
        "plate_text": analysis.plate_text if analysis else None,
        "plate_confidence": analysis.plate_confidence if analysis else None,
        "plate_source": analysis.plate_source if analysis else None,
    }


@app.post("/api/v1/gate/manual", response_model=RecognitionResult)
def record_manual_gate_event(request: ManualGateEventRequest, user: StaffUser = Depends(active_user)) -> RecognitionResult:
    """Ghi nhận ngoại lệ khi cổng không áp dụng quét AI.

    Đây không phải là "bỏ qua" kiểm soát: bảo vệ đã đăng nhập vẫn phải chọn lý
    do và để lại ghi chú để truy vết trong nhật ký.
    """
    exception_labels = {
        "pedestrian": "Người đi bộ (không thuộc phạm vi kiểm soát xe)",
        "emergency": "Xe ưu tiên hoặc tình huống khẩn cấp",
        "camera_failure": "Camera hoặc kết nối AI gặp sự cố",
        "security_override": "Bảo vệ xác nhận thủ công",
    }
    event_id = str(uuid4())
    note = request.note.strip() if request.note and request.note.strip() else "Không có ghi chú thêm"
    reason = f"[XỬ LÝ THỦ CÔNG] {exception_labels[request.exception_type]} · Bảo vệ: {user.full_name} ({user.username}) · {note}"
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, decision, reason, operator_username) VALUES (?, ?, ?, 'manual_review', ?, ?)",
            (event_id, now_iso(), request.direction, reason, user.username),
        )
    return RecognitionResult(event_id=event_id, decision="manual_review", reason=reason)


def prepare_exit_review(connection, plate: str, reason: str, frames: list[bytes], score: float | None, operator: str) -> RecognitionResult | None:
    """A review belongs to one open session, with immutable scan evidence."""
    session = connection.execute("SELECT * FROM gate_sessions WHERE plate_number = ? AND status = 'open' ORDER BY entered_at DESC LIMIT 1", (plate,)).fetchone()
    if session is None:
        return None
    pending = connection.execute("SELECT r.id AS review_id, e.* FROM exit_reviews r JOIN access_events e ON e.id = r.event_id WHERE r.session_id = ? AND r.status = 'pending' LIMIT 1", (session["id"],)).fetchone()
    if pending:
        event_id, review_id, evidence_path, occurred_at = pending["id"], pending["review_id"], pending["evidence_path"], pending["occurred_at"]
        reason, score = pending["reason"], pending["face_confidence"]
    else:
        event_id, review_id = str(uuid4()), str(uuid4())
        occurred_at = now_iso()
        evidence_path = save_evidence(event_id, "exit", frames)
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, plate_number, decision, reason, face_confidence, evidence_path, operator_username) VALUES (?, ?, 'exit', ?, 'manual_review', ?, ?, ?, ?)",
            (event_id, occurred_at, plate, reason, score, evidence_path, operator),
        )
        connection.execute("INSERT INTO exit_reviews (id, session_id, event_id) VALUES (?, ?, ?)", (review_id, session["id"], event_id))
    return RecognitionResult(event_id=event_id, review_id=review_id, decision="manual_review", reason=reason, plate_number=plate,
        evidence_url=evidence_url(evidence_path), captured_at=occurred_at, face_similarity=score,
        entry_evidence_url=evidence_url(session["entry_evidence_path"]), entered_at=session["entered_at"])


@app.get("/api/v1/gate/exit-reviews/pending")
def pending_exit_reviews(_: StaffUser = Depends(active_user)) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute("SELECT r.id AS review_id, e.id AS event_id, e.plate_number, e.reason, e.evidence_path, e.face_confidence AS face_similarity, e.occurred_at AS captured_at, s.entry_evidence_path, s.entered_at FROM exit_reviews r JOIN access_events e ON e.id = r.event_id JOIN gate_sessions s ON s.id = r.session_id WHERE r.status = 'pending' AND s.status = 'open' ORDER BY e.occurred_at DESC LIMIT 20").fetchall()
        return [dict(row) | {"evidence_url": evidence_url(row["evidence_path"]), "entry_evidence_url": evidence_url(row["entry_evidence_path"])} for row in rows]


@app.post("/api/v1/gate/exit-reviews/{review_id}/resolve", response_model=RecognitionResult)
def resolve_exit_review(review_id: str, request: ExitReviewResolution, user: StaffUser = Depends(active_user)) -> RecognitionResult:
    with get_connection() as connection:
        # Serialise approvals; a second click/client cannot close a different session.
        connection.execute("BEGIN IMMEDIATE")
        review = connection.execute("SELECT r.status AS review_status, r.session_id, e.*, s.status AS session_status FROM exit_reviews r JOIN access_events e ON e.id = r.event_id JOIN gate_sessions s ON s.id = r.session_id WHERE r.id = ?", (review_id,)).fetchone()
        if review is None:
            raise HTTPException(404, "Không tìm thấy yêu cầu xác nhận")
        if review["review_status"] != "pending" or review["session_status"] != "open":
            raise HTTPException(409, "Yêu cầu đã xử lý hoặc phiên xe đã đóng; hãy quét lại")
        event_id, now = str(uuid4()), now_iso()
        approved = request.action == "approve"
        decision = "manual_approved" if approved else "denied"
        note = f" · Lý do: {request.reason}" if request.reason else ""
        reason = f"[BẢO VỆ XÁC NHẬN] {'Cho xe ra' if approved else 'Không cho xe ra'} · Người xử lý: {user.full_name} ({user.username}){note} · AI: {review['reason']}"
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, plate_number, decision, reason, face_confidence, evidence_path, operator_username) VALUES (?, ?, 'exit', ?, ?, ?, ?, ?, ?)",
            (event_id, now, review["plate_number"], decision, reason, review["face_confidence"], review["evidence_path"], user.username),
        )
        connection.execute("UPDATE exit_reviews SET status = ? WHERE id = ?", ("approved" if approved else "rejected", review_id))
        if approved:
            connection.execute("UPDATE gate_sessions SET status = 'closed', exited_at = ?, exit_event_id = ?, exit_evidence_path = ? WHERE id = ? AND status = 'open'", (now, event_id, review["evidence_path"], review["session_id"]))
        return RecognitionResult(event_id=event_id, decision=decision, reason=reason, plate_number=review["plate_number"], evidence_url=evidence_url(review["evidence_path"]), captured_at=review["occurred_at"])


@app.post("/api/v1/gate/entry/manual-approve", response_model=RecognitionResult)
async def approve_entry_by_guard(
    images: list[UploadFile] = File(...), expected_plate: str = Form(..., max_length=30), user: StaffUser = Depends(active_user),
) -> RecognitionResult:
    """Bảo vệ đồng ý cho xe vào khi khuôn mặt không nhận diện rõ (áo mưa, đồ che nắng kín người).

    Biển số vẫn bắt buộc do hệ thống đọc từ chính ảnh gửi lên; bảo vệ không gõ tay.
    ``expected_plate`` là biển đang hiện trên màn hình lúc bấm, chỉ dùng để chặn
    trường hợp xe khác đã vào khung hình. Phiên xe được mở nhưng không lưu đặc trưng khuôn mặt, nên lúc ra xe này luôn
    được chuyển cho bảo vệ đối chiếu ảnh. Ảnh lúc bấm nút và tài khoản được ghi lại.
    """
    if len(images) != 2:
        raise HTTPException(422, "Cần hai ảnh theo thứ tự: khuôn mặt, biển số")
    frames = []
    for image in images:
        image_data = await read_image_upload(image)
        ensure_decodable(image_data)
        frames.append(image_data)
    try:
        analysis = await run_in_threadpool(get_vision_service().analyze_image, frames[1])
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if getattr(analysis, "crowded", False):
        raise HTTPException(409, CROWDED_REASON)
    plate_number = analysis.plate_text
    if not plate_number:
        raise HTTPException(422, "Chưa đọc được biển số. Đưa biển vào rõ trong khung rồi bấm lại.")
    if plate_number != normalize_plate_input(expected_plate):
        raise HTTPException(409, f"Biển số trong khung hiện là {plate_number}. Kiểm tra lại xe rồi bấm lại.")
    event_id, captured_at = str(uuid4()), now_iso()
    reason = f"[BẢO VỆ XÁC NHẬN] Cho xe vào khi khuôn mặt không nhận diện rõ · Người xử lý: {user.full_name} ({user.username})"
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM gate_sessions WHERE plate_number = ? AND status = 'open'", (plate_number,)).fetchone():
            raise HTTPException(409, "Xe này đã có lượt vào đang mở")
        evidence_path = save_evidence(event_id, "entry", frames)
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, plate_number, decision, reason, plate_confidence, evidence_path, plate_source, operator_username) VALUES (?, ?, 'entry', ?, 'manual_approved', ?, ?, ?, ?, ?)",
            (event_id, captured_at, plate_number, reason, analysis.plate_confidence, evidence_path, analysis.plate_source, user.username),
        )
        connection.execute("INSERT INTO gate_sessions (id, plate_number, entry_event_id, entered_at, entry_evidence_path) VALUES (?, ?, ?, ?, ?)", (str(uuid4()), plate_number, event_id, captured_at, evidence_path))
    return RecognitionResult(event_id=event_id, decision="manual_approved", reason=reason, plate_number=plate_number, plate_source=analysis.plate_source,
                             evidence_url=evidence_url(evidence_path), captured_at=captured_at)


def entry_face_score(connection, session, faces) -> float:
    """Độ giống lớn nhất giữa mọi mặt lúc ra và mọi mặt đã lưu lúc vào của phiên."""
    face_service_instance = get_face_service()
    entry_faces = connection.execute("SELECT embedding FROM gate_session_faces WHERE session_id = ?", (session["id"],)).fetchall()
    return max((face_service_instance.similarity(current.embedding, json.loads(saved["embedding"])) for current in faces for saved in entry_faces), default=0.0)


@app.post("/api/v1/gate/verify", response_model=RecognitionResult)
async def verify_gate_image(
    images: list[UploadFile] = File(...), direction: str = Form("exit"), automatic: bool = Form(False),
    paired_cameras: bool = Form(False), previous_plate: str | None = Form(None, max_length=30), user: StaffUser = Depends(active_user),
) -> RecognitionResult:
    if direction not in {"entry", "exit"}:
        raise HTTPException(422, "Hướng di chuyển không hợp lệ")
    if paired_cameras and len(images) != 2:
        raise HTTPException(422, "Cần hai ảnh theo thứ tự: khuôn mặt, biển số")
    if len(images) > 4:
        raise HTTPException(422, "Tối đa 4 ảnh cho một lượt quét")
    plate, plate_confidence, plate_source, faces, frames = None, None, None, [], []
    for image in images:
        image_data = await read_image_upload(image)
        # Decode every input before analysing or saving, including a dedicated face frame.
        ensure_decodable(image_data)
        frames.append(image_data)
    face_frames: list[tuple[bytes, list]] = []
    crowded = False
    for index, image_data in enumerate(frames):
        if not paired_cameras or index == 1:
            try:
                analysis = await run_in_threadpool(get_vision_service().analyze_image, image_data)
                crowded = crowded or getattr(analysis, "crowded", False)
                if not plate and analysis.plate_text:
                    plate, plate_confidence = analysis.plate_text, analysis.plate_confidence  # None khi VLM đọc: VLM không trả độ tin cậy
                    plate_source = analysis.plate_source
            except ValueError:
                pass
        if not paired_cameras or index == 0:
            try:
                face_frames.append((image_data, await run_in_threadpool(get_face_service().extract_all, image_data)))
            except ValueError:
                pass
    if crowded:
        return RecognitionResult(event_id="live-preview", decision="manual_review", reason=CROWDED_REASON, stage="crowded")
    # Quét tự động gửi kèm biển đọc ở khung trước: phải đọc ra cùng một biển hai lần liền mới quyết định.
    if automatic and previous_plate is not None and plate and normalize_plate_input(previous_plate) != plate:
        return RecognitionResult(event_id="live-preview", decision="manual_review", reason="Đang xác nhận biển số, giữ xe đứng yên",
                                 plate_number=plate, stage="confirm_plate")
    # Có biển số mới có thể cho xe qua, nên chỉ khi đó mới tốn công kiểm tra mặt có bị che không.
    face_unclear = False
    for image_data, found in face_frames:
        usable = await run_in_threadpool(clear_faces, image_data, found, getattr(get_vision_service(), "vlm", None)) if plate else found
        faces.extend(usable)
        face_unclear = face_unclear or not usable
    face_unclear = face_unclear and not faces
    face_confidence = max((face.confidence for face in faces), default=None)
    event_id = str(uuid4())
    decision, reason, score = "denied", "Không đọc được biển số xe", None
    evidence_path, session = None, None
    captured_at = now_iso()
    with get_connection() as connection:
        # Khóa ghi ngay từ đầu: hai khung hình đến cùng lúc không thể tạo hai phiên
        # cho cùng một biển số hoặc đóng cùng một phiên hai lần.
        connection.execute("BEGIN IMMEDIATE")
        # Camera tự động gửi nhiều khung hình. Khi khung chưa đủ dữ liệu, chỉ
        # báo trạng thái chờ thay vì ghi hàng loạt lỗi vào nhật ký bảo vệ.
        if direction == "exit" and plate and not faces:
            problem = "Khuôn mặt bị che hoặc chưa rõ" if face_unclear else "Không xác minh được khuôn mặt"
            review = prepare_exit_review(connection, plate, f"{problem}; cần bảo vệ kiểm tra trực tiếp", frames, None, user.username)
            if review:
                return review
        if automatic and (not plate or not faces):
            waiting_decision = "manual_review"
            waiting_reason = "Đang chờ biển số xe rõ" if not plate else UNCLEAR_REASON if face_unclear else "Đang chờ khuôn mặt rõ"
            if direction == "entry" and plate and connection.execute("SELECT 1 FROM gate_sessions WHERE plate_number = ? AND status = 'open'", (plate,)).fetchone():
                waiting_decision, waiting_reason = "approved", "Xe này đã được ghi nhận vào; chờ xe đi qua"
            return RecognitionResult(
                event_id="live-preview", decision=waiting_decision, reason=waiting_reason,
                plate_number=plate, face_detected=bool(faces), face_detection_confidence=face_confidence,
            )
        if not faces:
            reason = UNCLEAR_REASON if face_unclear else "Không phát hiện được khuôn mặt rõ trong các ảnh đã chọn" if plate else "Không đọc được biển số xe và không thấy khuôn mặt rõ"
        elif plate and direction == "entry":
            existing = connection.execute("SELECT id, entry_event_id FROM gate_sessions WHERE plate_number = ? AND status = 'open' ORDER BY entered_at DESC LIMIT 1", (plate,)).fetchone()
            if existing:
                # Khung hình lặp của xe đã vào: không ghi thêm nhật ký, không tạo phiên mới.
                return RecognitionResult(
                    event_id=existing["entry_event_id"], decision="approved", reason="Xe đã có lượt vào đang mở; bỏ qua khung hình lặp",
                    plate_number=plate, face_detected=True, face_detection_confidence=face_confidence, plate_source=plate_source,
                )
            decision, reason = "approved", "Đã ghi nhận xe và khuôn mặt tại thời điểm vào"
        elif plate:
            session = connection.execute("SELECT * FROM gate_sessions WHERE plate_number = ? AND status = 'open' ORDER BY entered_at DESC LIMIT 1", (plate,)).fetchone()
            recent_exit = None if session or not automatic else connection.execute(
                "SELECT exit_event_id, exited_at FROM gate_sessions WHERE plate_number = ? AND status = 'closed' AND julianday(exited_at) >= julianday(?) ORDER BY exited_at DESC LIMIT 1",
                (plate, (datetime.now(timezone.utc) - timedelta(seconds=EXIT_REPEAT_WINDOW_SECONDS)).isoformat()),
            ).fetchone()
            if recent_exit:
                # Xe vừa được cho ra còn đứng trước camera: như lượt vào lặp, không ghi thêm "Từ chối".
                return RecognitionResult(
                    event_id=recent_exit["exit_event_id"], decision="approved", reason="Xe vừa được cho ra; bỏ qua khung hình lặp",
                    plate_number=plate, face_detected=True, face_detection_confidence=face_confidence, plate_source=plate_source,
                )
            if not session:
                reason = "Không có lượt vào đang mở của biển số này"
            else:
                score = entry_face_score(connection, session, faces)
                if score >= config.FACE_MATCH_THRESHOLD:
                    decision, reason = "approved", "Khuôn mặt khớp với người đã vào cùng xe"
                elif connection.execute("SELECT 1 FROM gate_session_faces WHERE session_id = ?", (session["id"],)).fetchone():
                    reason = "Khuôn mặt hiện tại không khớp lượt xe lúc vào"
                else:
                    score, reason = None, "Lượt vào do bảo vệ duyệt, không có khuôn mặt để đối chiếu; cần bảo vệ kiểm tra"
        if direction == "exit" and plate and decision == "denied":
            review = prepare_exit_review(connection, plate, reason, frames, score, user.username)
            if review:
                return review
        if plate and faces and frames:
            evidence_path = save_evidence(event_id, direction, frames)
        connection.execute(
            "INSERT INTO access_events (id, occurred_at, direction, plate_number, person_id, decision, reason, plate_confidence, face_confidence, evidence_path, plate_source, operator_username) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, captured_at, direction, plate, None, decision, reason, plate_confidence, score, evidence_path,
             plate_source if plate else None, user.username),
        )
        if plate and faces and direction == "entry" and decision == "approved":
            session_id = str(uuid4())
            connection.execute("INSERT INTO gate_sessions (id, plate_number, entry_event_id, entered_at, entry_evidence_path) VALUES (?, ?, ?, ?, ?)", (session_id, plate, event_id, captured_at, evidence_path))
            connection.executemany("INSERT INTO gate_session_faces (session_id, embedding, confidence) VALUES (?, ?, ?)", [(session_id, json.dumps(face.embedding), face.confidence) for face in faces])
        if plate and direction == "exit" and decision == "approved" and session:
            connection.execute("UPDATE gate_sessions SET status = 'closed', exited_at = ?, exit_event_id = ?, exit_evidence_path = ? WHERE id = ?", (captured_at, event_id, evidence_path, session["id"]))
    return RecognitionResult(
        event_id=event_id, decision=decision, reason=reason,
        plate_number=plate, face_detected=bool(faces),
        evidence_url=evidence_url(evidence_path),
        captured_at=captured_at if evidence_path else None,
        face_detection_confidence=face_confidence,
        face_similarity=score if plate else None,
        plate_source=plate_source if plate else None,
    )


# ---------- Thống kê và nhật ký ----------

@app.get("/api/v1/dashboard/summary")
def dashboard_summary(since: datetime | None = None, _: StaffUser = Depends(active_user)) -> dict:
    """Đếm theo quyết định. ``approved`` gồm cả lượt bảo vệ duyệt; ``pending`` là lượt chờ bảo vệ."""
    if since is not None and since.utcoffset() is None:
        raise HTTPException(422, "Thời gian phải có múi giờ")
    where, values = ("WHERE julianday(occurred_at) >= julianday(?)", [since.astimezone(timezone.utc).isoformat()]) if since else ("", [])
    with get_connection() as connection:
        totals = connection.execute(
            f"SELECT COUNT(*) AS total, SUM(decision = 'approved') AS ai_approved, SUM(decision = 'manual_approved') AS manual_approved, "
            f"SUM(decision = 'denied') AS denied, SUM(decision = 'manual_review') AS pending "
            f"FROM access_events {where}", values,
        ).fetchone()
        open_sessions = connection.execute("SELECT COUNT(*) FROM gate_sessions WHERE status = 'open'").fetchone()[0]
    ai_approved, manual_approved = totals["ai_approved"] or 0, totals["manual_approved"] or 0
    return {
        "events": totals["total"] or 0,
        "approved": ai_approved + manual_approved,
        "ai_approved": ai_approved,
        "manual_approved": manual_approved,
        "denied": totals["denied"] or 0,
        "pending": totals["pending"] or 0,
        "open_sessions": open_sessions,
    }


@app.get("/api/v1/events/search")
def search_events(
    plate: str = Query("", max_length=30),
    start: datetime | None = None, end: datetime | None = None,
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    _: StaffUser = Depends(active_user),
) -> dict:
    for value in (start, end):
        if value is not None and value.utcoffset() is None:
            raise HTTPException(422, "Thời gian phải có múi giờ")
    if start and end and start > end:
        raise HTTPException(422, "Thời gian bắt đầu phải trước thời gian kết thúc")
    conditions, values = [], []
    normalized = normalize_plate_input(plate)
    if normalized:
        conditions.append("instr(UPPER(REPLACE(REPLACE(REPLACE(COALESCE(plate_number, ''), '-', ''), '.', ''), ' ', '')), ?) > 0")
        values.append(normalized)
    if start:
        conditions.append("julianday(occurred_at) >= julianday(?)")
        values.append(start.astimezone(timezone.utc).isoformat())
    if end:
        conditions.append("julianday(occurred_at) <= julianday(?)")
        values.append(end.astimezone(timezone.utc).isoformat())
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with get_connection() as connection:
        total = connection.execute("SELECT COUNT(*) FROM access_events" + where, values).fetchone()[0]
        rows = connection.execute("SELECT * FROM access_events" + where + " ORDER BY occurred_at DESC, id DESC LIMIT ? OFFSET ?", [*values, limit, offset]).fetchall()
        items = [dict(row) | {"evidence_url": evidence_url(row["evidence_path"])} for row in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/api/v1/events")
def list_events(limit: int = Query(20, ge=1, le=500), since: datetime | None = None, _: StaffUser = Depends(active_user)) -> list[dict]:
    if since is not None and since.utcoffset() is None:
        raise HTTPException(422, "Thời gian phải có múi giờ")
    where, values = ("WHERE julianday(occurred_at) >= julianday(?)", [since.astimezone(timezone.utc).isoformat()]) if since else ("", [])
    with get_connection() as connection:
        rows = connection.execute(f"SELECT * FROM access_events {where} ORDER BY occurred_at DESC LIMIT ?", [*values, limit]).fetchall()
        return [dict(row) | {"evidence_url": evidence_url(row["evidence_path"])} for row in rows]


@app.get("/api/v1/sessions/recent")
def recent_gate_sessions(limit: int = Query(6, ge=1, le=20), _: StaffUser = Depends(active_user)) -> list[dict]:
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
            (limit,),
        ).fetchall()
        return [dict(row) | {"entry_evidence_url": evidence_url(row["entry_evidence_path"]), "exit_evidence_url": evidence_url(row["exit_evidence_path"])} for row in rows]


# ---------- Dữ liệu huấn luyện ----------

@app.get("/api/v1/dataset/samples")
def list_training_samples(limit: int = Query(60, ge=1, le=100), _: StaffUser = Depends(active_user)) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM training_samples ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "image_url": f"/training-data/{row['image_path']}"} for row in rows]


@app.post("/api/v1/dataset/samples")
async def add_training_sample(image: UploadFile = File(...), plate_label: str = Form("", max_length=20), _: StaffUser = Depends(active_user)) -> dict:
    image_data = await read_image_upload(image)
    ensure_decodable(image_data)
    suffix = Path(image.filename or "sample.jpg").suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    sample_id = str(uuid4())
    filename = f"{sample_id}{suffix}"
    TRAINING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (TRAINING_DIRECTORY / filename).write_bytes(image_data)
    cleaned_label = normalize_plate_input(plate_label)
    now = now_iso()
    status = "labeled" if cleaned_label else "unlabeled"
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO training_samples (id, image_path, plate_label, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (sample_id, filename, cleaned_label or None, status, now, now),
        )
    return {"id": sample_id, "image_url": f"/training-data/{filename}", "plate_label": cleaned_label or None, "status": status}


@app.patch("/api/v1/dataset/samples/{sample_id}")
async def label_training_sample(sample_id: str, plate_label: str = Form(..., max_length=20), _: StaffUser = Depends(active_user)) -> dict:
    cleaned_label = normalize_plate_input(plate_label)
    if not cleaned_label:
        raise HTTPException(422, "Hãy nhập biển số để gán nhãn")
    with get_connection() as connection:
        result = connection.execute(
            "UPDATE training_samples SET plate_label = ?, status = 'labeled', updated_at = ? WHERE id = ?",
            (cleaned_label, now_iso(), sample_id),
        )
        if result.rowcount == 0:
            raise HTTPException(404, "Không tìm thấy ảnh dữ liệu")
    return {"id": sample_id, "plate_label": cleaned_label, "status": "labeled"}


@app.get("/api/v1/model/status")
def model_status() -> dict:
    """Trạng thái mô hình; công khai để kiểm tra nhanh sau khi cài đặt (không chứa dữ liệu cá nhân)."""
    with get_connection() as connection:
        dataset = connection.execute(
            "SELECT COUNT(*) AS total, SUM(status = 'labeled') AS labeled FROM training_samples"
        ).fetchone()
    detector_model = MODELS_DIRECTORY / "plate_best.pt"
    character_model = MODELS_DIRECTORY / "chars_best.pt"
    trained_model = MODELS_DIRECTORY / "license_plate.pt"
    custom_model = detector_model.is_file() or trained_model.is_file()
    if trained_model.is_file() and character_model.is_file():
        model_name = "license_plate.pt + chars_best.pt (detector đã train)"
    elif trained_model.is_file():
        model_name = "license_plate.pt (detector đã train)"
    elif detector_model.is_file() and character_model.is_file():
        model_name = "plate_best.pt + chars_best.pt (đọc biển số 2 tầng)"
    else:
        model_name = "yolov8n.pt (mô hình tổng quát)"
    vlm_status = get_vision_service().vlm.status() if vision_service is not None else vlm_status_reader.status()
    if vlm_status["available"]:
        model_name = f"{model_name} + {vlm_status['model']} (VLM dự phòng)"
    metrics_path = config.data_directory() / "model_metrics.json"
    try:
        evaluation = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        evaluation = {}
    return {
        "model_name": model_name,
        "custom_plate_model": custom_model,
        "dataset_total": dataset["total"] or 0,
        "dataset_labeled": dataset["labeled"] or 0,
        "evaluation": {
            "precision": evaluation.get("precision"),
            "recall": evaluation.get("recall"),
            "map50": evaluation.get("map50"),
        },
        "face_match_threshold": config.FACE_MATCH_THRESHOLD,
        "ocr_min_char_confidence": config.OCR_MIN_CHAR_CONFIDENCE,
        "vlm": vlm_status,
    }
