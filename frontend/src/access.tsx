import { FormEvent, useEffect, useState } from "react";
import { API, apiFetch, errorMessage } from "./api";

export type StaffUser = { username: string; full_name: string; role: "admin" | "guard"; must_change_password: boolean };
export function LoginScreen({ onLogin, onGuest }: { onLogin: (user: StaffUser) => void; onGuest?: () => void }) {
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
    {onGuest && <div className="guest-entry"><p>Chưa có tài khoản? Thử nhận diện biển số và khuôn mặt, không cần đăng ký.</p><button type="button" className="secondary" onClick={onGuest}>Xem thử</button></div>}
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
