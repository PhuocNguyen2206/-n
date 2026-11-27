"""Kiểm thử API cổng xe với AI giả lập.

Mỗi ảnh thử là một khối màu đơn sắc. Màu quyết định ảnh "chứa" ai hoặc biển
số nào, nhờ vậy kiểm tra được trọn luồng vào/ra, bảo vệ duyệt,
đăng nhập và lưu ảnh mà không cần GPU, camera hay model thật. Các bài này
kiểm tra logic quyết định; độ chính xác nhận diện được đo riêng (LFW, tập test
biển số).
"""

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, database
from app import main as main_module
from app.services.face import FaceService

# ---------- AI giả lập ----------

IDENTITY = {name: np.eye(8)[index].tolist() for index, name in enumerate(["an", "binh", "chi", "dung", "lan"])}
COLORS = {
    "an": (220, 40, 40), "binh": (40, 200, 40), "chi": (40, 40, 220), "dung": (220, 220, 40), "lan": (40, 220, 220),
    "an+binh": (160, 60, 200), "noface": (128, 128, 128),
    "59F113860": (250, 250, 250), "51F79512": (10, 10, 10), "30F5204": (250, 140, 0), "43A12345": (0, 120, 250), "noplate": (90, 50, 20),
}
FACES_IN = {"an": ["an"], "binh": ["binh"], "chi": ["chi"], "dung": ["dung"], "lan": ["lan"], "an+binh": ["an", "binh"]}


def image(name: str, size=(64, 48)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, COLORS[name]).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def label_of(image_data: bytes) -> str:
    pixel = np.asarray(Image.open(BytesIO(image_data)).convert("RGB"))[0, 0].astype(int)
    return min(COLORS, key=lambda key: sum((pixel - np.asarray(COLORS[key])) ** 2))


@dataclass
class FakeFace:
    embedding: list[float]
    confidence: float = 0.99


class FakeFaceService:
    similarity = staticmethod(FaceService.similarity)

    def extract_all(self, image_data):
        people = FACES_IN.get(label_of(image_data))
        if not people:
            raise ValueError("Không phát hiện được khuôn mặt rõ trong ảnh")
        return [FakeFace(IDENTITY[person]) for person in people]

    def extract(self, image_data):
        return self.extract_all(image_data)[0]

    def detect(self, image_data):
        return {"width": 64, "height": 48, "faces": [{"box": [0, 0, 10, 10], "confidence": 0.99}] if label_of(image_data) in FACES_IN else []}


@dataclass
class FakeAnalysis:
    plate_text: str | None
    plate_confidence: float | None = 0.9
    plate_source: str | None = "ocr"


class FakeVlm:
    @staticmethod
    def status():
        return {"enabled": False, "available": False, "model": "fake", "host": "-", "message": "giả lập"}


class FakeVisionService:
    vlm = FakeVlm()

    def analyze_image(self, image_data):
        label = label_of(image_data)
        plate = label if label[:2].isdigit() else None
        return FakeAnalysis(plate, 0.9 if plate else None, "ocr" if plate else None)


# ---------- Fixtures ----------

@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main_module, "EVIDENCE_DIRECTORY", tmp_path / "evidence")
    monkeypatch.setattr(main_module, "TRAINING_DIRECTORY", tmp_path / "training")
    monkeypatch.setattr(main_module, "vision_service", FakeVisionService())
    monkeypatch.setattr(main_module, "face_service", FakeFaceService())
    return tmp_path


def login(client: TestClient, username="admin", password="Matkhau#2026") -> None:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text


@pytest.fixture()
def client(env):
    with TestClient(main_module.app) as test_client:
        response = test_client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        assert response.json()["must_change_password"] is True
        response = test_client.post("/api/v1/auth/change-password", json={"current_password": "admin123", "new_password": "Matkhau#2026"})
        assert response.status_code == 200
        yield test_client


def scan(client, face, plate, direction, automatic=False):
    files = [("images", ("face.jpg", image(face), "image/jpeg")), ("images", ("plate.jpg", image(plate), "image/jpeg"))]
    response = client.post("/api/v1/gate/verify", files=files, data={"direction": direction, "paired_cameras": "true", "automatic": str(automatic).lower()})
    assert response.status_code == 200, response.text
    return response.json()


def events(client):
    return client.get("/api/v1/events/search", params={"limit": 100}).json()["items"]


# ---------- Đăng nhập và phân quyền ----------

def test_protected_endpoints_require_login(env):
    with TestClient(main_module.app) as anonymous:
        assert anonymous.get("/api/v1/health").status_code == 200
        assert anonymous.get("/api/v1/model/status").status_code == 200
        for method, path in [("get", "/api/v1/events"), ("get", "/api/v1/events/search"), ("get", "/api/v1/dashboard/summary"),
                             ("get", "/api/v1/sessions/recent"), ("get", "/api/v1/gate/exit-reviews/pending"),
                             ("get", "/evidence/x_entry.jpg"), ("post", "/api/v1/gate/manual")]:
            assert getattr(anonymous, method)(path).status_code == 401, path
        files = [("images", ("a.jpg", image("an"), "image/jpeg")), ("images", ("b.jpg", image("59F113860"), "image/jpeg"))]
        assert anonymous.post("/api/v1/gate/verify", files=files, data={"direction": "entry", "paired_cameras": "true"}).status_code == 401


def test_default_password_must_be_changed_before_use(env):
    with TestClient(main_module.app) as fresh:
        assert fresh.post("/api/v1/auth/login", json={"username": "admin", "password": "sai"}).status_code == 401
        fresh.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        assert fresh.get("/api/v1/events").status_code == 403
        assert fresh.post("/api/v1/auth/change-password", json={"current_password": "admin123", "new_password": "ngan"}).status_code == 422
        assert fresh.post("/api/v1/auth/change-password", json={"current_password": "sai-mat-khau", "new_password": "Matkhau#2026"}).status_code == 401
        assert fresh.post("/api/v1/auth/change-password", json={"current_password": "admin123", "new_password": "Matkhau#2026"}).status_code == 200
        assert fresh.get("/api/v1/events").status_code == 200


def test_logout_and_guard_role(client):
    created = client.post("/api/v1/accounts", json={"username": "baove1", "full_name": "Lê Bảo Vệ", "password": "BaoVe#2026", "role": "guard"})
    assert created.status_code == 201
    assert client.post("/api/v1/accounts", json={"username": "baove1", "full_name": "Trùng", "password": "BaoVe#2026"}).status_code == 409
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/events").status_code == 401
    login(client, "baove1", "BaoVe#2026")
    client.post("/api/v1/auth/change-password", json={"current_password": "BaoVe#2026", "new_password": "BaoVe#2027"})
    assert client.get("/api/v1/auth/me").json()["role"] == "guard"
    assert client.get("/api/v1/events").status_code == 200
    assert client.post("/api/v1/accounts", json={"username": "x123", "full_name": "Không được", "password": "Khongduoc#1"}).status_code == 403


def test_deactivated_account_loses_session(client):
    client.post("/api/v1/accounts", json={"username": "baove2", "full_name": "Bảo Vệ Hai", "password": "BaoVe#2026"})
    with TestClient(main_module.app) as guard:
        login(guard, "baove2", "BaoVe#2026")
        assert client.delete("/api/v1/accounts/baove2").status_code == 200
        assert guard.get("/api/v1/auth/me").status_code == 401
        assert guard.post("/api/v1/auth/login", json={"username": "baove2", "password": "BaoVe#2026"}).status_code == 401


# ---------- Luồng vào / ra ----------

def test_entry_then_owner_exit_closes_session_with_two_photos(client):
    entry = scan(client, "an", "59F113860", "entry")
    assert entry["decision"] == "approved" and entry["plate_number"] == "59F113860" and entry["evidence_url"].endswith("_entry.jpg")
    exit_ = scan(client, "an", "59F113860", "exit")
    assert exit_["decision"] == "approved" and exit_["face_similarity"] == pytest.approx(1.0)
    session = client.get("/api/v1/sessions/recent").json()[0]
    assert session["status"] == "closed" and session["entry_evidence_url"] == entry["evidence_url"] and session["exit_evidence_url"] == exit_["evidence_url"]
    photo = client.get(exit_["evidence_url"])
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    # Ảnh ghép: mặt bên trái, biển số bên phải.
    pixels = np.asarray(Image.open(BytesIO(photo.content)).convert("RGB")).astype(int)
    assert np.abs(pixels[5, 5] - COLORS["an"]).max() < 25 and np.abs(pixels[5, -5] - COLORS["59F113860"]).max() < 25
    # Ra lần nữa: phiên đã đóng nên bị từ chối.
    again = scan(client, "an", "59F113860", "exit")
    assert again["decision"] == "denied" and "Không có lượt vào" in again["reason"]


def test_repeated_entry_frames_do_not_duplicate_log_or_session(client):
    scan(client, "an", "59F113860", "entry")
    for automatic in (True, False):
        repeat = scan(client, "an", "59F113860", "entry", automatic=automatic)
        assert repeat["decision"] == "approved" and "lặp" in repeat["reason"]
    assert len(events(client)) == 1
    assert sum(session["status"] == "open" for session in client.get("/api/v1/sessions/recent").json()) == 1


def test_passenger_can_take_bike_out(client):
    scan(client, "an+binh", "51F79512", "entry")
    assert scan(client, "binh", "51F79512", "exit")["decision"] == "approved"


def test_stranger_exit_goes_to_guard_review(client):
    scan(client, "an", "59F113860", "entry")
    review = scan(client, "dung", "59F113860", "exit")
    assert review["decision"] == "manual_review" and review["review_id"] and review["face_similarity"] == pytest.approx(0.0)
    assert review["entry_evidence_url"] and review["evidence_url"]
    pending = client.get("/api/v1/gate/exit-reviews/pending").json()
    assert [item["review_id"] for item in pending] == [review["review_id"]]
    # Quét lại cùng xe khi đang chờ: dùng lại đúng yêu cầu, không tạo yêu cầu mới.
    assert scan(client, "dung", "59F113860", "exit")["review_id"] == review["review_id"]
    assert client.get("/api/v1/sessions/recent").json()[0]["status"] == "open"


def test_guard_approve_records_logged_in_operator(client):
    scan(client, "an", "59F113860", "entry")
    review = scan(client, "noface", "59F113860", "exit")
    assert review["decision"] == "manual_review" and "khuôn mặt" in review["reason"]
    too_long = client.post(f"/api/v1/gate/exit-reviews/{review['review_id']}/resolve", json={"action": "approve", "reason": "x" * 301})
    assert too_long.status_code == 422
    approved = client.post(f"/api/v1/gate/exit-reviews/{review['review_id']}/resolve",
                           json={"action": "approve", "operator_name": "Tên giả", "reason": "Đã kiểm tra thẻ sinh viên"})
    assert approved.status_code == 200 and approved.json()["decision"] == "manual_approved"
    assert "Quản trị viên (admin)" in approved.json()["reason"] and "Tên giả" not in approved.json()["reason"]
    assert events(client)[0]["operator_username"] == "admin"
    assert client.get("/api/v1/sessions/recent").json()[0]["status"] == "closed"
    again = client.post(f"/api/v1/gate/exit-reviews/{review['review_id']}/resolve", json={"action": "approve", "reason": "Bấm lại lần hai"})
    assert again.status_code == 409
    assert client.post("/api/v1/gate/exit-reviews/khong-ton-tai/resolve", json={"action": "reject", "reason": "Không có"}).status_code == 404


def test_guard_resolves_with_one_click_without_reason(client):
    scan(client, "an", "59F113860", "entry")
    review = scan(client, "dung", "59F113860", "exit")
    approved = client.post(f"/api/v1/gate/exit-reviews/{review['review_id']}/resolve", json={"action": "approve"})
    assert approved.status_code == 200 and approved.json()["decision"] == "manual_approved"
    reason = approved.json()["reason"]
    assert "Quản trị viên (admin)" in reason and "Lý do" not in reason and "AI:" in reason
    assert client.get("/api/v1/sessions/recent").json()[0]["status"] == "closed"


def test_guard_reject_keeps_session_open_and_old_review_cannot_close_new_session(client):
    scan(client, "an", "59F113860", "entry")
    review = scan(client, "dung", "59F113860", "exit")
    rejected = client.post(f"/api/v1/gate/exit-reviews/{review['review_id']}/resolve", json={"action": "reject", "reason": "Không có giấy tờ"})
    assert rejected.json()["decision"] == "denied"
    assert client.get("/api/v1/sessions/recent").json()[0]["status"] == "open"
    # Chủ xe ra đúng: phiên đóng; yêu cầu cũ (đã xử lý) không còn dùng được.
    assert scan(client, "an", "59F113860", "exit")["decision"] == "approved"
    scan(client, "an", "59F113860", "entry")
    assert client.post(f"/api/v1/gate/exit-reviews/{review['review_id']}/resolve", json={"action": "approve", "reason": "Thử dùng lại"}).status_code == 409
    assert client.get("/api/v1/sessions/recent").json()[0]["status"] == "open"


def test_exit_without_entry_is_denied_and_logged(client):
    result = scan(client, "an", "43A12345", "exit")
    assert result["decision"] == "denied" and "Không có lượt vào" in result["reason"] and result["evidence_url"]


def test_missing_plate_or_face(client):
    assert scan(client, "an", "noplate", "entry", automatic=True)["event_id"] == "live-preview"
    assert scan(client, "noface", "59F113860", "entry", automatic=True)["reason"] == "Đang chờ khuôn mặt rõ"
    assert events(client) == []
    manual = scan(client, "noface", "59F113860", "entry")
    assert manual["decision"] == "denied" and manual["evidence_url"] is None
    both = scan(client, "noface", "noplate", "entry")
    assert both["decision"] == "denied" and "biển số" in both["reason"]


def test_concurrent_entries_create_one_session(client):
    results = []
    threads = [threading.Thread(target=lambda: results.append(scan(client, "an", "30F5204", "entry"))) for _ in range(4)]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    assert all(result["decision"] == "approved" for result in results)
    sessions = [session for session in client.get("/api/v1/sessions/recent").json() if session["plate_number"] == "30F5204"]
    assert len(sessions) == 1 and len(events(client)) == 1


# ---------- Dữ liệu đầu vào không hợp lệ ----------

def test_invalid_uploads(client, monkeypatch):
    def post(files, direction="entry", paired="true"):
        return client.post("/api/v1/gate/verify", files=files, data={"direction": direction, "paired_cameras": paired})
    good = ("images", ("b.jpg", image("59F113860"), "image/jpeg"))
    assert post([("images", ("a.txt", b"hello", "text/plain")), good]).status_code == 415
    assert post([("images", ("a.jpg", b"\xff\xd8garbage", "image/jpeg")), good]).status_code == 422
    assert post([good]).status_code == 422
    assert post([("images", ("a.jpg", image("an"), "image/jpeg")), good], direction="sideways").status_code == 422
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0.001)
    assert post([("images", ("a.jpg", image("an", size=(400, 300)), "image/jpeg")), good]).status_code == 413
    assert client.post("/api/v1/dataset/samples", files={"image": ("big.jpg", image("an", size=(400, 300)), "image/jpeg")}).status_code == 413
    assert events(client) == [] and not list((main_module.EVIDENCE_DIRECTORY).glob("*.jpg"))


def test_evidence_path_traversal_blocked(client):
    for path in ["/evidence/..%2Ftest.db", "/evidence/%2E%2E%5Ctest.db", "/training-data/..%2F..%2Fapp%2Fmain.py"]:
        assert client.get(path).status_code == 404


# ---------- Thống kê, nhật ký, khôi phục ----------

def test_summary_counts_every_decision(client):
    scan(client, "an", "59F113860", "entry")                      # approved
    scan(client, "dung", "59F113860", "exit")                     # manual_review
    review = client.get("/api/v1/gate/exit-reviews/pending").json()[0]
    client.post(f"/api/v1/gate/exit-reviews/{review['review_id']}/resolve", json={"action": "approve", "reason": "Đã kiểm tra"})  # manual_approved
    scan(client, "an", "43A12345", "exit")                        # denied
    client.post("/api/v1/gate/manual", json={"direction": "entry", "exception_type": "emergency", "note": "Xe cứu thương"})  # manual_review
    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["events"] == 5 == summary["approved"] + summary["denied"] + summary["pending"]
    assert (summary["ai_approved"], summary["manual_approved"], summary["denied"], summary["pending"]) == (1, 1, 1, 2)
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert client.get("/api/v1/dashboard/summary", params={"since": future}).json()["events"] == 0
    assert client.get("/api/v1/dashboard/summary", params={"since": "2026-01-01T00:00:00"}).status_code == 422
    manual = events(client)[0]
    assert manual["operator_username"] == "admin" and "Quản trị viên" in manual["reason"]


def test_search_pagination_and_filters(client):
    plates = ["59F113860", "51F79512", "30F5204"]
    for index in range(45):
        scan(client, "an", plates[index % 3], "exit")  # chưa vào: mỗi lượt là một sự kiện từ chối có ảnh
    seen = []
    for page in range(3):
        result = client.get("/api/v1/events/search", params={"limit": 20, "offset": page * 20}).json()
        assert result["total"] == 45
        seen += [item["id"] for item in result["items"]]
    assert len(seen) == len(set(seen)) == 45
    assert client.get("/api/v1/events/search", params={"plate": "59-f1 138.60"}).json()["total"] == 15
    now = datetime.now(timezone(timedelta(hours=7)))
    window = {"start": (now - timedelta(minutes=5)).isoformat(), "end": (now + timedelta(minutes=5)).isoformat()}
    assert client.get("/api/v1/events/search", params=window).json()["total"] == 45
    assert client.get("/api/v1/events/search", params={"start": "2026-11-01T00:00:00"}).status_code == 422
    assert client.get("/api/v1/events/search", params={"start": window["end"], "end": window["start"]}).status_code == 422
    assert client.get("/api/v1/events/search", params={"limit": 0}).status_code == 422
    first = client.get("/api/v1/events/search", params={"limit": 1}).json()["items"][0]
    assert client.get(first["evidence_url"]).status_code == 200
    today = client.get("/api/v1/events", params={"since": (now - timedelta(hours=1)).isoformat(), "limit": 500}).json()
    assert len(today) == 45


def test_data_survives_restart(client):
    scan(client, "an", "59F113860", "entry")
    review = scan(client, "dung", "59F113860", "exit")
    with TestClient(main_module.app) as restarted:
        login(restarted)
        assert restarted.get("/api/v1/gate/exit-reviews/pending").json()[0]["review_id"] == review["review_id"]
        assert restarted.get(review["evidence_url"]).status_code == 200
        assert restarted.get("/api/v1/dashboard/summary").json()["open_sessions"] == 1


def test_vlm_plate_keeps_unknown_confidence(client, monkeypatch):
    """VLM không trả độ tin cậy: nhật ký phải ghi NULL, không ghi 0,0 như thể OCR chắc chắn sai."""
    monkeypatch.setattr(FakeVisionService, "analyze_image",
                        lambda self, data: FakeAnalysis(label_of(data), None, "vlm") if label_of(data)[:2].isdigit() else FakeAnalysis(None, None, None))
    assert scan(client, "an", "59F113860", "entry")["plate_source"] == "vlm"
    recorded = events(client)[0]
    assert (recorded["plate_source"], recorded["plate_confidence"]) == ("vlm", None)


def test_automatic_exit_repeat_after_release_is_not_logged(client):
    scan(client, "an", "59F113860", "entry")
    exited = scan(client, "an", "59F113860", "exit")
    assert exited["decision"] == "approved"
    count = len(events(client))
    repeat = scan(client, "an", "59F113860", "exit", automatic=True)
    assert (repeat["event_id"], repeat["decision"]) == (exited["event_id"], "approved")
    assert len(events(client)) == count
    # Quét thủ công và biển chưa từng vào vẫn ghi "Từ chối" như trước.
    assert scan(client, "an", "59F113860", "exit")["decision"] == "denied"
    assert scan(client, "an", "43A12345", "exit", automatic=True)["decision"] == "denied"
    assert len(events(client)) == count + 2
