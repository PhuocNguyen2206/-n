import { FormEvent, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Event = { id: string; occurred_at: string; plate_number: string | null; decision: string; reason: string };
type Owner = { id: string; full_name: string; campus_id: string; plates: string | null; face_registered: number };
const API = "http://127.0.0.1:8000/api/v1";

function App() {
  const [events, setEvents] = useState<Event[]>([]);
  const [owners, setOwners] = useState<Owner[]>([]);
  const [status, setStatus] = useState("Đang kết nối API...");
  const [faceImages, setFaceImages] = useState<File[]>([]);
  const [vehicleImage, setVehicleImage] = useState<File | null>(null);
  const [direction, setDirection] = useState("exit");
  const [gateResult, setGateResult] = useState("");
  const [name, setName] = useState("");
  const [campusId, setCampusId] = useState("");
  const [plate, setPlate] = useState("");
  const [portrait, setPortrait] = useState<File | null>(null);
  const [registerResult, setRegisterResult] = useState("");
  const load = async () => {
    try { const [eventResponse, ownerResponse] = await Promise.all([fetch(`${API}/events`), fetch(`${API}/people`)]); setEvents(await eventResponse.json()); setOwners(await ownerResponse.json()); setStatus("Hệ thống sẵn sàng"); }
    catch { setStatus("Chưa kết nối API"); }
  };
  useEffect(() => { load(); }, []);

  const verifyGate = async (event: FormEvent) => {
    event.preventDefault(); if (!faceImages.length && !vehicleImage) return;
    setGateResult("Đang quét biển số và khuôn mặt...");
    const form = new FormData(); faceImages.forEach(image => form.append("images", image)); if (vehicleImage) form.append("images", vehicleImage); form.append("direction", direction);
    try {
      const response = await fetch(`${API}/gate/verify`, { method: "POST", body: form }); const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Không thể kiểm tra ảnh");
      const faceStatus = result.face_detected ? ` | Khuôn mặt: đã phát hiện (${result.face_detection_confidence})${result.face_similarity !== null ? `, mức khớp ${result.face_similarity}` : "; chờ biển số để đối chiếu"}` : " | Khuôn mặt: không phát hiện";
      setGateResult(`${result.decision === "approved" ? "✓ ĐƯỢC PHÉP" : "✕ KHÔNG CHO PHÉP"}: ${result.reason}${result.plate_number ? ` | Biển số: ${result.plate_number}` : ""}${faceStatus}`); load();
    } catch (error) { setGateResult(error instanceof Error ? error.message : "Không thể kiểm tra ảnh"); }
  };

  const registerOwner = async (event: FormEvent) => {
    event.preventDefault(); if (!portrait) return;
    setRegisterResult("Đang đăng ký khuôn mặt và phương tiện...");
    try {
      const personResponse = await fetch(`${API}/people`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ full_name: name, campus_id: campusId, role: "student" }) });
      const person = await personResponse.json(); if (!personResponse.ok) throw new Error(person.detail || "Không thể tạo chủ xe");
      const faceForm = new FormData(); faceForm.append("image", portrait);
      const faceResponse = await fetch(`${API}/people/${person.id}/face-enrollment`, { method: "POST", body: faceForm }); const face = await faceResponse.json();
      if (!faceResponse.ok) throw new Error(face.detail || "Không thể đăng ký khuôn mặt");
      const vehicleResponse = await fetch(`${API}/vehicles`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plate_number: plate, owner_id: person.id, vehicle_type: "motorbike" }) });
      const vehicle = await vehicleResponse.json(); if (!vehicleResponse.ok) throw new Error(vehicle.detail || "Không thể đăng ký xe");
      setRegisterResult(`✓ Đã đăng ký ${name}, biển số ${vehicle.plate_number}. Khuôn mặt đã lưu (${face.face_confidence}).`); setName(""); setCampusId(""); setPlate(""); setPortrait(null);
    } catch (error) { setRegisterResult(error instanceof Error ? error.message : "Không thể đăng ký"); }
  };

  return <main>
    <header><div className="brand"><div className="brand-mark">AI</div><div><p className="eyebrow">CỔNG KIỂM SOÁT THÔNG MINH</p><h1>Nhận diện AI</h1></div></div><span className="status"><i />{status}</span></header>
    <section className="hero"><div><p className="eyebrow">GIÁM SÁT RA VÀO</p><h2>Kiểm tra xe và chủ xe<br /><em>trong vài giây.</em></h2><p>Đối chiếu biển số và nhóm người đã cùng vào xe trước khi cho phép qua cổng.</p></div><div className="hero-shield">⌁<span>Protected</span></div></section>
    <section className="cards"><article><span className="card-icon blue">◷</span><div><strong>{events.length}</strong><span>Lượt kiểm soát gần đây</span></div></article><article><span className="card-icon green">✓</span><div><strong>{events.filter(e => e.decision === "approved").length}</strong><span>Được cho phép</span></div></article><article><span className="card-icon red">×</span><div><strong>{events.filter(e => e.decision !== "approved").length}</strong><span>Không cho phép</span></div></article></section>
    <section className="grid"><div>
      <form onSubmit={verifyGate} className="scan-card"><div className="form-title"><span className="form-icon">⌁</span><div><h2>Quét kiểm soát cổng</h2><p>Quét khuôn mặt và biển số để xác thực.</p></div></div><div className="upload-grid"><label className="upload"><b>◎</b><span>Ảnh khuôn mặt</span><small>{faceImages.length ? `Đã chọn ${faceImages.length} người` : "Chọn 1 hoặc nhiều ảnh rõ mặt"}</small><input type="file" accept="image/*" multiple onChange={e => setFaceImages(Array.from(e.target.files || []))} /></label><label className="upload"><b>▣</b><span>Ảnh xe & biển số</span><small>{vehicleImage?.name || "Chọn ảnh biển số"}</small><input type="file" accept="image/*" onChange={e => setVehicleImage(e.target.files?.[0] || null)} /></label></div><label>Thời điểm quét<select value={direction} onChange={e => setDirection(e.target.value)}><option value="entry">Xe vào cổng</option><option value="exit">Xe ra cổng</option></select></label><button>Quét và kiểm tra <span>→</span></button>{gateResult && <p className="result">{gateResult}</p>}</form>
      <form onSubmit={registerOwner} className="manual register-card"><div className="form-title"><span className="form-icon purple">✦</span><div><h2>Đăng ký chủ xe</h2><p>Lưu khuôn mặt và thông tin phương tiện.</p></div></div><label>Họ và tên<input value={name} onChange={e => setName(e.target.value)} placeholder="Nguyễn Văn A" required /></label><label>Mã sinh viên / nhân sự<input value={campusId} onChange={e => setCampusId(e.target.value)} placeholder="SV001" required /></label><label>Biển số xe<input value={plate} onChange={e => setPlate(e.target.value)} placeholder="43-A1 123.45" required /></label><label>Ảnh khuôn mặt rõ<input type="file" accept="image/*" onChange={e => setPortrait(e.target.files?.[0] || null)} required /></label><button>Đăng ký phương tiện <span>→</span></button>{registerResult && <p className="result">{registerResult}</p>}</form>
      <section className="owners"><div className="events-head"><div><p className="eyebrow">DỮ LIỆU ĐÃ LƯU</p><h2>Chủ xe đã đăng ký</h2></div><span>{owners.length} người</span></div>{owners.length === 0 ? <p>Chưa có chủ xe nào được đăng ký.</p> : owners.map(owner => <article key={owner.id}><span className="owner-avatar">{owner.full_name.slice(0, 1).toUpperCase()}</span><div><b>{owner.full_name}</b><small>{owner.campus_id} · {owner.plates || "Chưa có xe"}</small></div><span className={owner.face_registered ? "face-ok" : "face-missing"}>{owner.face_registered ? "Mặt đã lưu" : "Chưa có mặt"}</span></article>)}</section>
    </div><section className="events"><div className="events-head"><div><p className="eyebrow">LỊCH SỬ HỆ THỐNG</p><h2>Nhật ký ra vào</h2></div><span>{events.length} lượt</span></div>{events.length === 0 ? <p>Chưa có lượt kiểm soát.</p> : events.map(e => <article key={e.id}><div><b>{e.plate_number || "Không đọc được biển số"}</b><small>{new Date(e.occurred_at).toLocaleString("vi-VN")}</small></div><span className={`tag ${e.decision}`}>{e.decision === "approved" ? "Được phép" : "Từ chối"}</span><p>{e.reason}</p></article>)}</section></section>
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
