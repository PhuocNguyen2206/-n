"""Đăng nhập cho bảo vệ/quản trị viên bằng cookie phiên (HttpOnly).

Mật khẩu băm PBKDF2-SHA256 (thư viện chuẩn), token phiên chỉ lưu dạng băm
SHA-256 trong SQLite nên lộ tệp cơ sở dữ liệu cũng không dùng lại được phiên.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from . import config
from .database import get_connection

COOKIE_NAME = "gate_session"
_ITERATIONS = 200_000

router = APIRouter(prefix="/api/v1", tags=["auth"])


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), _ITERATIONS).hex()
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def ensure_default_admin() -> None:
    """Tạo tài khoản quản trị đầu tiên; bắt buộc đổi mật khẩu khi đăng nhập."""
    with get_connection() as connection:
        if connection.execute("SELECT 1 FROM staff_accounts LIMIT 1").fetchone():
            return
        connection.execute(
            "INSERT INTO staff_accounts (username, full_name, role, password_hash, must_change_password, created_at) VALUES (?, ?, 'admin', ?, 1, ?)",
            (config.DEFAULT_ADMIN_USERNAME, "Quản trị viên", hash_password(config.DEFAULT_ADMIN_PASSWORD), datetime.now(timezone.utc).isoformat()),
        )


class StaffUser(BaseModel):
    username: str
    full_name: str
    role: Literal["admin", "guard"]
    must_change_password: bool = False


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=config.COOKIE_SECURE,
                        max_age=int(config.SESSION_HOURS * 3600), path="/")


def current_user(request: Request, response: Response) -> StaffUser:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Cần đăng nhập")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT a.username, a.full_name, a.role, a.must_change_password, s.expires_at FROM auth_sessions s JOIN staff_accounts a ON a.username = s.username WHERE s.token_hash = ? AND a.active = 1",
            (_token_hash(token),),
        ).fetchone()
        now = datetime.now(timezone.utc)
        if row is None or datetime.fromisoformat(row["expires_at"]) <= now:
            raise HTTPException(401, "Phiên đăng nhập đã hết hạn")
        # Trạm bảo vệ mở cả ngày, các ca thay nhau ngồi: còn hoạt động thì gia hạn, không tự đăng xuất.
        # Chỉ ghi lại khi đã qua 1/12 thời hạn (mặc định 1 giờ) để không ghi cơ sở dữ liệu ở mọi yêu cầu.
        lifetime = timedelta(hours=config.SESSION_HOURS)
        if datetime.fromisoformat(row["expires_at"]) - now <= lifetime * 11 / 12:
            connection.execute("UPDATE auth_sessions SET expires_at = ? WHERE token_hash = ?",
                               ((now + lifetime).isoformat(), _token_hash(token)))
            _set_session_cookie(response, token)
    return StaffUser(username=row["username"], full_name=row["full_name"], role=row["role"], must_change_password=bool(row["must_change_password"]))


def active_user(user: StaffUser = Depends(current_user)) -> StaffUser:
    """Người dùng đã đăng nhập và đã đổi mật khẩu mặc định."""
    if user.must_change_password:
        raise HTTPException(403, "Hãy đổi mật khẩu mặc định trước khi sử dụng")
    return user


def admin_user(user: StaffUser = Depends(active_user)) -> StaffUser:
    if user.role != "admin":
        raise HTTPException(403, "Chỉ quản trị viên được thực hiện thao tác này")
    return user


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class Registration(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class AccountCreate(Registration):
    role: Literal["admin", "guard"] = "guard"


class AccountRequest(BaseModel):
    username: str
    full_name: str
    created_at: str


@router.post("/auth/login", response_model=StaffUser)
def login(request: LoginRequest, response: Response) -> StaffUser:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM staff_accounts WHERE username = ? AND active = 1", (request.username.strip(),)).fetchone()
        if row is None or not verify_password(request.password, row["password_hash"]):
            # Chỉ người biết đúng mật khẩu đăng ký mới được báo là đang chờ duyệt.
            waiting = connection.execute("SELECT password_hash FROM account_requests WHERE username = ?", (request.username.strip(),)).fetchone()
            if row is None and waiting and verify_password(request.password, waiting["password_hash"]):
                raise HTTPException(403, "Tài khoản đang chờ quản trị viên duyệt")
            raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        connection.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now.isoformat(),))
        connection.execute(
            "INSERT INTO auth_sessions (token_hash, username, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (_token_hash(token), row["username"], now.isoformat(), (now + timedelta(hours=config.SESSION_HOURS)).isoformat()),
        )
    _set_session_cookie(response, token)
    return StaffUser(username=row["username"], full_name=row["full_name"], role=row["role"], must_change_password=bool(row["must_change_password"]))


@router.post("/auth/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with get_connection() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_token_hash(token),))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.get("/auth/me", response_model=StaffUser)
def me(user: StaffUser = Depends(current_user)) -> StaffUser:
    return user


@router.post("/auth/change-password", response_model=StaffUser)
def change_password(request: PasswordChange, user: StaffUser = Depends(current_user)) -> StaffUser:
    if request.new_password == request.current_password:
        raise HTTPException(422, "Mật khẩu mới phải khác mật khẩu cũ")
    with get_connection() as connection:
        row = connection.execute("SELECT password_hash FROM staff_accounts WHERE username = ?", (user.username,)).fetchone()
        if row is None or not verify_password(request.current_password, row["password_hash"]):
            raise HTTPException(401, "Mật khẩu hiện tại không đúng")
        connection.execute("UPDATE staff_accounts SET password_hash = ?, must_change_password = 0 WHERE username = ?",
                           (hash_password(request.new_password), user.username))
    return user.model_copy(update={"must_change_password": False})


@router.get("/accounts", response_model=list[StaffUser])
def list_accounts(_: StaffUser = Depends(admin_user)) -> list[StaffUser]:
    with get_connection() as connection:
        rows = connection.execute("SELECT username, full_name, role, must_change_password FROM staff_accounts WHERE active = 1 ORDER BY role, username").fetchall()
    return [StaffUser(username=row["username"], full_name=row["full_name"], role=row["role"], must_change_password=bool(row["must_change_password"])) for row in rows]


@router.post("/accounts", response_model=StaffUser, status_code=201)
def create_account(request: AccountCreate, _: StaffUser = Depends(admin_user)) -> StaffUser:
    with get_connection() as connection:
        if connection.execute("SELECT 1 FROM staff_accounts WHERE username = ?", (request.username,)).fetchone():
            raise HTTPException(409, "Tên đăng nhập đã tồn tại")
        if connection.execute("SELECT 1 FROM account_requests WHERE lower(username) = lower(?)", (request.username,)).fetchone():
            raise HTTPException(409, "Tên đăng nhập này đang có người đăng ký chờ duyệt")
        connection.execute(
            "INSERT INTO staff_accounts (username, full_name, role, password_hash, must_change_password, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (request.username, request.full_name, request.role, hash_password(request.password), datetime.now(timezone.utc).isoformat()),
        )
    return StaffUser(username=request.username, full_name=request.full_name, role=request.role, must_change_password=True)


@router.delete("/accounts/{username}")
def deactivate_account(username: str, user: StaffUser = Depends(admin_user)) -> dict:
    if username == user.username:
        raise HTTPException(422, "Không thể tự khóa tài khoản đang đăng nhập")
    with get_connection() as connection:
        result = connection.execute("UPDATE staff_accounts SET active = 0 WHERE username = ? AND active = 1", (username,))
        if result.rowcount == 0:
            raise HTTPException(404, "Không tìm thấy tài khoản")
        connection.execute("DELETE FROM auth_sessions WHERE username = ?", (username,))
    return {"status": "ok"}


# ---------- Đăng ký chờ duyệt ----------

@router.get("/auth/register")
def registration_status() -> dict[str, bool]:
    return {"enabled": config.ALLOW_REGISTRATION}


@router.post("/auth/register", status_code=201)
def register(request: Registration) -> dict[str, str]:
    """Người ngoài gửi yêu cầu cấp tài khoản. Không tạo phiên, không có quyền gì cho tới khi được duyệt."""
    if not config.ALLOW_REGISTRATION:
        raise HTTPException(404, "Chức năng đăng ký đang tắt")
    now = datetime.now(timezone.utc)
    with get_connection() as connection:
        # Khóa ghi trước khi kiểm tra: hai người đăng ký cùng lúc không thể lấy trùng tên hoặc vượt giới hạn.
        connection.execute("BEGIN IMMEDIATE")
        pending, recent = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(created_at > ?), 0) FROM account_requests",
            ((now - timedelta(minutes=1)).isoformat(),),
        ).fetchone()
        if pending >= config.MAX_PENDING_REGISTRATIONS or recent >= config.REGISTRATIONS_PER_MINUTE:
            raise HTTPException(429, "Đang có quá nhiều đăng ký. Vui lòng thử lại sau.")
        taken = connection.execute(
            "SELECT 1 FROM staff_accounts WHERE lower(username) = lower(?) UNION ALL SELECT 1 FROM account_requests WHERE lower(username) = lower(?)",
            (request.username, request.username),
        ).fetchone()
        if taken:
            raise HTTPException(409, "Tên đăng nhập đã được dùng. Hãy chọn tên khác.")
        connection.execute(
            "INSERT INTO account_requests (username, full_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (request.username, request.full_name, hash_password(request.password), now.isoformat()),
        )
    return {"status": "pending"}


@router.get("/account-requests", response_model=list[AccountRequest])
def list_account_requests(_: StaffUser = Depends(admin_user)) -> list[AccountRequest]:
    with get_connection() as connection:
        rows = connection.execute("SELECT username, full_name, created_at FROM account_requests ORDER BY created_at").fetchall()
    return [AccountRequest(**dict(row)) for row in rows]


@router.post("/account-requests/{username}/approve", response_model=StaffUser)
def approve_account_request(username: str, _: StaffUser = Depends(admin_user)) -> StaffUser:
    """Duyệt thành tài khoản bảo vệ. Người đăng ký tự đặt mật khẩu nên không bắt đổi lại."""
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM account_requests WHERE username = ?", (username,)).fetchone()
        if row is None:
            raise HTTPException(404, "Yêu cầu không còn tồn tại")
        if connection.execute("SELECT 1 FROM staff_accounts WHERE lower(username) = lower(?)", (username,)).fetchone():
            raise HTTPException(409, "Tên đăng nhập đã có tài khoản. Hãy từ chối yêu cầu này.")
        connection.execute(
            "INSERT INTO staff_accounts (username, full_name, role, password_hash, must_change_password, created_at) VALUES (?, ?, 'guard', ?, 0, ?)",
            (row["username"], row["full_name"], row["password_hash"], datetime.now(timezone.utc).isoformat()),
        )
        connection.execute("DELETE FROM account_requests WHERE username = ?", (username,))
    return StaffUser(username=row["username"], full_name=row["full_name"], role="guard")


@router.delete("/account-requests/{username}")
def reject_account_request(username: str, _: StaffUser = Depends(admin_user)) -> dict:
    with get_connection() as connection:
        if connection.execute("DELETE FROM account_requests WHERE username = ?", (username,)).rowcount == 0:
            raise HTTPException(404, "Yêu cầu không còn tồn tại")
    return {"status": "ok"}
