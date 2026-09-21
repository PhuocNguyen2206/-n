import { FormEvent, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Event = { id: string; occurred_at: string; plate_number: string | null; decision: string; reason: string };
const API = "http://127.0.0.1:8000/api/v1";

function App() {
  const [events, setEvents] = useState<Event[]>([]);
  const [status, setStatus] = useState("Đang kết nối API...");
  const [faceImage, setFaceImage] = useState<File | null>(null);
  const [vehicleImage, setVehicleImage] = useState<File | null>(null);
  const [direction, setDirection] = useState("exit");
  const [gateResult, setGateResult] = useState("");
  const [name, setName] = useState("");
  const [campusId, setCampusId] = useState("");
  const [plate, setPlate] = useState("");
  const [portrait, setPortrait] = useState<File | null>(null);
  const [registerResult, setRegisterResult] = useState("");
  const load = async () => {
    try { const response = await fetch(`${API}/events`); setEvents(await response.json()); setStatus("Hệ thống sẵn sàng"); }
    catch { setStatus("Chưa kết nối API"); }
  };
  useEffect(() => { load(); }, []);

  const verifyGate = async (event: FormEvent) => {
    event.preventDefault(); if (!faceImage && !vehicleImage) return;
    setGateResult("Đang quét biển số và khuôn mặt...");
    const form = new FormData(); [faceImage, vehicleImage].filter((image): image is File => image !== null).forEach(image => form.append("images", image)); form.append("direction", direction);
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
    <header><div><p className="eyebrow">CỔNG KIỂM SOÁT THÔNG MINH</p><h1>Nhận diện AI</h1></div><span className="status">● {status}</span></header>
    <section className="cards"><article><strong>{events.length}</strong><span>Lượt kiểm soát gần đây</span></article><article><strong>{events.filter(e => e.decision === "approved").length}</strong><span>Được cho phép</span></article><article><strong>{events.filter(e => e.decision !== "approved").length}</strong><span>Không cho phép</span></article></section>
    <section className="grid"><div>
      <form onSubmit={verifyGate}><h2>Quét cổng: biển số + khuôn mặt</h2><p>Chụp riêng mặt và biển số (trước/sau) hoặc dùng một ảnh có đủ cả hai. Không khớp sẽ bị từ chối.</p><label>Ảnh khuôn mặt người điều khiển<input type="file" accept="image/*" onChange={e => setFaceImage(e.target.files?.[0] || null)} /></label><label>Ảnh xe và biển số<input type="file" accept="image/*" onChange={e => setVehicleImage(e.target.files?.[0] || null)} /></label><label>Thời điểm quét<select value={direction} onChange={e => setDirection(e.target.value)}><option value="entry">Xe vào</option><option value="exit">Xe ra</option></select></label><button>Kiểm tra cho ra/vào</button>{gateResult && <p className="result">{gateResult}</p>}</form>
      <form onSubmit={registerOwner} className="manual"><h2>Đăng ký chủ xe</h2><label>Họ và tên<input value={name} onChange={e => setName(e.target.value)} required /></label><label>Mã sinh viên/nhân sự<input value={campusId} onChange={e => setCampusId(e.target.value)} required /></label><label>Biển số xe<input value={plate} onChange={e => setPlate(e.target.value)} placeholder="43-A1 123.45" required /></label><label>Ảnh khuôn mặt rõ<input type="file" accept="image/*" onChange={e => setPortrait(e.target.files?.[0] || null)} required /></label><button>Đăng ký khuôn mặt và xe</button>{registerResult && <p className="result">{registerResult}</p>}</form>
    </div><section className="events"><h2>Nhật ký ra vào</h2>{events.length === 0 ? <p>Chưa có lượt kiểm soát.</p> : events.map(e => <article key={e.id}><div><b>{e.plate_number || "Không đọc được biển số"}</b><small>{new Date(e.occurred_at).toLocaleString("vi-VN")}</small></div><span className={`tag ${e.decision}`}>{e.decision}</span><p>{e.reason}</p></article>)}</section></section>
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
