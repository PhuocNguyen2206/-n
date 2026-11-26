import { FormEvent, useEffect, useState } from "react";
import { API, apiFetch, errorMessage } from "./api";

export type StaffUser = { username: string; full_name: string; role: "admin" | "guard"; must_change_password: boolean };
type Authorization = {
  id: string; plate_number: string; owner_name: string; borrower_name: string; borrower_code: string; note: string | null;
  created_by: string; created_at: string; valid_until: string; status: "active" | "used" | "expired" | "revoked"; used_event_id: string | null;
};

const statusLabel: Record<Authorization["status"], string> = { active: "Còn hiệu lực", used: "Đã lấy xe", expired: "Hết hiệu lực", revoked: "Đã hủy" };

export function LoginScreen({ onLogin }: { onLogin: (user: StaffUser) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setMessage("");
    try {
      const response = await fetch(`${API}/auth/login`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: username.trim(), password }) });
      if (!response.ok) throw new Error(await errorMessage(response, "Không đăng nhập được"));
      onLogin(await response.json());
    } catch (error) {
      setMessage(error instanceof TypeError ? "Không kết nối được API. Kiểm tra backend ở cổng 8000." : error instanceof Error ? error.message : "Không đăng nhập được");
    } finally { setBusy(false); }
  };
  return <div className="login-screen"><form className="login-card" onSubmit={submit}>
    <div className="brand"><div className="brand-mark">BV</div><div><p className="eyebrow">QUẢN LÝ PHƯƠNG TIỆN</p><h1>Đăng nhập trạm bảo vệ</h1></div></div>
    <p>Chỉ bảo vệ và quản trị viên được xem camera, ảnh bằng chứng và duyệt xe ra.</p>
    <label>Tên đăng nhập<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required maxLength={60} autoFocus /></label>
    <label>Mật khẩu<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required maxLength={200} /></label>
    {message && <p className="form-message error" role="alert">{message}</p>}
    <button type="submit" disabled={busy || !username.trim() || !password}>{busy ? "Đang đăng nhập…" : "Đăng nhập"}</button>
  </form></div>;
}

export function ChangePasswordForm({ onDone }: { onDone: (user: StaffUser) => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (next !== confirm) { setMessage({ text: "Hai lần nhập mật khẩu mới không giống nhau.", ok: false }); return; }
    setBusy(true); setMessage(null);
    try {
      const response = await apiFetch(`${API}/auth/change-password`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: current, new_password: next }) });
      if (!response.ok) throw new Error(await errorMessage(response, "Mật khẩu mới cần ít nhất 8 ký tự."));
      setCurrent(""); setNext(""); setConfirm("");
      setMessage({ text: "Đã đổi mật khẩu.", ok: true });
      onDone(await response.json());
    } catch (error) { setMessage({ text: error instanceof Error ? error.message : "Không đổi được mật khẩu", ok: false }); }
    finally { setBusy(false); }
  };
  return <form className="stack-form" onSubmit={submit}>
    <label>Mật khẩu hiện tại<input type="password" autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)} required /></label>
    <label>Mật khẩu mới <small>(ít nhất 8 ký tự)</small><input type="password" autoComplete="new-password" value={next} onChange={e => setNext(e.target.value)} minLength={8} required /></label>
    <label>Nhập lại mật khẩu mới<input type="password" autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} minLength={8} required /></label>
    {message && <p className={`form-message ${message.ok ? "success" : "error"}`} role="status">{message.text}</p>}
    <button type="submit" disabled={busy}>{busy ? "Đang lưu…" : "Đổi mật khẩu"}</button>
  </form>;
}

export function AuthorizationPanel({ captureFace, cameraOn, onChanged }: { captureFace: () => Promise<File>; cameraOn: boolean; onChanged: () => void }) {
  const [items, setItems] = useState<Authorization[]>([]);
  const [plate, setPlate] = useState("");
  const [owner, setOwner] = useState("");
  const [borrower, setBorrower] = useState("");
  const [code, setCode] = useState("");
  const [hours, setHours] = useState("4");
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const refresh = async () => {
    try {
      const response = await apiFetch(`${API}/authorizations?limit=50`);
      if (response.ok) setItems(await response.json());
    } catch { /* giữ danh sách cũ */ }
  };
  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 15000); return () => window.clearInterval(timer); }, []);
  useEffect(() => { if (!photo) { setPreview(""); return; } const url = URL.createObjectURL(photo); setPreview(url); return () => URL.revokeObjectURL(url); }, [photo]);

  const takePhoto = async () => {
    try { setPhoto(await captureFace()); setMessage(null); }
    catch (error) { setMessage({ text: error instanceof Error ? error.message : "Không chụp được ảnh", ok: false }); }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!photo) { setMessage({ text: "Cần ảnh khuôn mặt rõ của người lấy xe hộ.", ok: false }); return; }
    setBusy(true); setMessage(null);
    const form = new FormData();
    form.append("plate_number", plate); form.append("owner_name", owner); form.append("borrower_name", borrower);
    form.append("borrower_code", code); form.append("valid_hours", hours); form.append("note", note); form.append("face_image", photo);
    try {
      const response = await apiFetch(`${API}/authorizations`, { method: "POST", body: form });
      if (!response.ok) throw new Error(await errorMessage(response, "Hãy kiểm tra lại thông tin ủy quyền."));
      const created: Authorization = await response.json();
      setMessage({ text: `Đã ủy quyền cho ${created.borrower_name} lấy xe ${created.plate_number} đến ${new Date(created.valid_until).toLocaleString("vi-VN")}.`, ok: true });
      setPlate(""); setOwner(""); setBorrower(""); setCode(""); setNote(""); setPhoto(null);
      refresh(); onChanged();
    } catch (error) { setMessage({ text: error instanceof Error ? error.message : "Không lưu được ủy quyền", ok: false }); }
    finally { setBusy(false); }
  };

  const revoke = async (item: Authorization) => {
    if (!window.confirm(`Hủy ủy quyền lấy xe ${item.plate_number} của ${item.borrower_name}?`)) return;
    const response = await apiFetch(`${API}/authorizations/${item.id}/revoke`, { method: "POST" });
    if (!response.ok) setMessage({ text: await errorMessage(response, "Không hủy được ủy quyền"), ok: false });
    refresh();
  };

  return <section className="authorization-panel">
    <div className="access-grid">
      <form className="access-card stack-form" onSubmit={submit}>
        <div><p className="eyebrow">TẠO ỦY QUYỀN</p><h2>Người lấy xe hộ</h2><p>Chỉ dùng cho xe đang ở trong bãi. Bảo vệ xác minh chủ xe (gặp trực tiếp hoặc gọi điện), chụp mặt người lấy hộ. Ủy quyền dùng một lần.</p></div>
        <label>Biển số xe<input value={plate} onChange={e => setPlate(e.target.value)} placeholder="Ví dụ: 59F1-138.60" maxLength={20} required /></label>
        <label>Họ tên chủ xe (người gửi xe)<input value={owner} onChange={e => setOwner(e.target.value)} maxLength={120} required /></label>
        <div className="two-columns"><label>Họ tên người lấy hộ<input value={borrower} onChange={e => setBorrower(e.target.value)} maxLength={120} required /></label>
          <label>MSSV / CCCD người lấy hộ<input value={code} onChange={e => setCode(e.target.value)} maxLength={30} required /></label></div>
        <div className="two-columns"><label>Hiệu lực (giờ)<input type="number" min="0.5" max="24" step="0.5" value={hours} onChange={e => setHours(e.target.value)} required /></label>
          <label>Ghi chú<input value={note} onChange={e => setNote(e.target.value)} maxLength={300} placeholder="Ví dụ: chủ xe gọi điện xác nhận" /></label></div>
        <div className="photo-picker">
          {preview ? <img src={preview} alt="Ảnh khuôn mặt người lấy xe hộ" /> : <span>Chưa có ảnh khuôn mặt</span>}
          <div><label className="file-button">Chọn ảnh từ máy<input type="file" accept="image/*" onChange={e => setPhoto(e.target.files?.[0] || null)} /></label>
            <button type="button" className="secondary" onClick={takePhoto} disabled={!cameraOn} title={cameraOn ? "" : "Bật camera ở mục Giám sát cổng trước"}>Chụp từ camera khuôn mặt</button></div>
        </div>
        {message && <p className={`form-message ${message.ok ? "success" : "error"}`} role="status">{message.text}</p>}
        <button type="submit" disabled={busy}>{busy ? "Đang lưu…" : "Lưu ủy quyền"}</button>
      </form>
      <div className="access-card">
        <div><p className="eyebrow">DANH SÁCH</p><h2>Ủy quyền gần đây</h2></div>
        {items.length === 0 ? <p className="empty-note">Chưa có ủy quyền nào.</p> : <ul className="authorization-list">{items.map(item => <li key={item.id} className={item.status}>
          <div><b>{item.plate_number}</b><span className={`badge ${item.status}`}>{statusLabel[item.status]}</span></div>
          <p>{item.borrower_name} ({item.borrower_code}) lấy hộ {item.owner_name}</p>
          <small>Tạo bởi {item.created_by} · {new Date(item.created_at).toLocaleString("vi-VN")} · hết hạn {new Date(item.valid_until).toLocaleString("vi-VN")}{item.note ? ` · ${item.note}` : ""}</small>
          {item.status === "active" && <button type="button" className="secondary" onClick={() => revoke(item)}>Hủy ủy quyền</button>}
        </li>)}</ul>}
      </div>
    </div>
  </section>;
}

export function AccountsPanel({ user }: { user: StaffUser }) {
  const [accounts, setAccounts] = useState<StaffUser[]>([]);
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"guard" | "admin">("guard");
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const isAdmin = user.role === "admin";
  const refresh = async () => {
    if (!isAdmin) return;
    const response = await apiFetch(`${API}/accounts`);
    if (response.ok) setAccounts(await response.json());
  };
  useEffect(() => { refresh(); }, [isAdmin]);
  const create = async (event: FormEvent) => {
    event.preventDefault(); setMessage(null);
    const response = await apiFetch(`${API}/accounts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: username.trim(), full_name: fullName, password, role }) });
    if (!response.ok) { setMessage({ text: await errorMessage(response, "Tên đăng nhập 3–60 ký tự (chữ, số, . _ -), mật khẩu ít nhất 8 ký tự."), ok: false }); return; }
    setMessage({ text: `Đã tạo tài khoản ${username.trim()}. Người dùng sẽ phải đổi mật khẩu khi đăng nhập lần đầu.`, ok: true });
    setUsername(""); setFullName(""); setPassword(""); refresh();
  };
  const deactivate = async (account: StaffUser) => {
    if (!window.confirm(`Khóa tài khoản ${account.username}? Người này sẽ bị đăng xuất ngay.`)) return;
    const response = await apiFetch(`${API}/accounts/${encodeURIComponent(account.username)}`, { method: "DELETE" });
    if (!response.ok) setMessage({ text: await errorMessage(response, "Không khóa được tài khoản"), ok: false });
    refresh();
  };
  return <section className="accounts-panel"><div className="access-grid">
    <div className="access-card"><div><p className="eyebrow">TÀI KHOẢN CỦA BẠN</p><h2>{user.full_name}</h2><p>Tên đăng nhập <b>{user.username}</b> · {user.role === "admin" ? "Quản trị viên" : "Bảo vệ"}</p></div><ChangePasswordForm onDone={() => undefined} /></div>
    {isAdmin ? <div className="access-card">
      <div><p className="eyebrow">QUẢN LÝ BẢO VỆ</p><h2>Tài khoản đang hoạt động</h2></div>
      <ul className="account-list">{accounts.map(account => <li key={account.username}><div><b>{account.full_name}</b><small>{account.username} · {account.role === "admin" ? "Quản trị" : "Bảo vệ"}{account.must_change_password ? " · chưa đổi mật khẩu" : ""}</small></div>{account.username !== user.username && <button type="button" className="secondary" onClick={() => deactivate(account)}>Khóa</button>}</li>)}</ul>
      <form className="stack-form" onSubmit={create}>
        <h3>Thêm tài khoản</h3>
        <div className="two-columns"><label>Tên đăng nhập<input value={username} onChange={e => setUsername(e.target.value)} pattern="[a-zA-Z0-9_.\-]{3,60}" required /></label>
          <label>Họ tên<input value={fullName} onChange={e => setFullName(e.target.value)} minLength={2} maxLength={120} required /></label></div>
        <div className="two-columns"><label>Mật khẩu tạm<input type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} minLength={8} required /></label>
          <label>Vai trò<select value={role} onChange={e => setRole(e.target.value as "guard" | "admin")}><option value="guard">Bảo vệ</option><option value="admin">Quản trị viên</option></select></label></div>
        {message && <p className={`form-message ${message.ok ? "success" : "error"}`} role="status">{message.text}</p>}
        <button type="submit">Tạo tài khoản</button>
      </form>
    </div> : <div className="access-card"><p className="empty-note">Liên hệ quản trị viên để thêm hoặc khóa tài khoản bảo vệ.</p></div>}
  </div></section>;
}
