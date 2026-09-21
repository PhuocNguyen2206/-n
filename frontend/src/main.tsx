import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Event = { id: string; occurred_at: string; plate_number: string | null; decision: string; reason: string };
const API = "http://localhost:8000/api/v1";

function App() {
  const [events, setEvents] = useState<Event[]>([]);
  const [status, setStatus] = useState("Đang kết nối API...");
  const [plate, setPlate] = useState("");
  const [face, setFace] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [visionResult, setVisionResult] = useState("");
  const load = async () => {
    try { const response = await fetch(`${API}/events`); setEvents(await response.json()); setStatus("Hệ thống sẵn sàng"); }
    catch { setStatus("Chưa kết nối API"); }
  };
  useEffect(() => { load(); }, []);
  const check = async (event: React.FormEvent) => {
    event.preventDefault();
    const response = await fetch(`${API}/recognition/process`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plate_number: plate, face_token: face, plate_confidence: 0.95, face_confidence: 0.95 }) });
    const result = await response.json(); alert(`${result.decision}: ${result.reason}`); load();
  };
  const analyzeImage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!image) return;
    const formData = new FormData(); formData.append("image", image);
    try {
      const response = await fetch(`${API}/vision/analyze`, { method: "POST", body: formData });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Không thể phân tích ảnh");
      const found = result.detections.map((item: { label: string; confidence: number }) => `${item.label} (${item.confidence})`).join(", ");
      setVisionResult(`${result.model}: ${found || "chưa phát hiện đối tượng"}${result.uses_plate_model ? "" : ". Cần thêm model biển số riêng để nhận diện biển số."}`);
    } catch (error) { setVisionResult(error instanceof Error ? error.message : "Không thể phân tích ảnh"); }
  };
  return <main>
    <header><div><p className="eyebrow">CỔNG KIỂM SOÁT THÔNG MINH</p><h1>Nhận diện AI</h1></div><span className="status">● {status}</span></header>
    <section className="cards"><article><strong>{events.length}</strong><span>Lượt kiểm soát gần đây</span></article><article><strong>{events.filter(e => e.decision === "approved").length}</strong><span>Được cho phép</span></article><article><strong>{events.filter(e => e.decision !== "approved").length}</strong><span>Cần xử lý</span></article></section>
    <section className="grid"><div><form onSubmit={analyzeImage}><h2>Phân tích ảnh YOLOv8</h2><label>Ảnh từ camera<input type="file" accept="image/*" onChange={e => setImage(e.target.files?.[0] || null)} required /></label><button>Phân tích ảnh</button>{visionResult && <p>{visionResult}</p>}</form><form onSubmit={check} className="manual"><h2>Kiểm tra thủ công</h2><label>Biển số xe<input value={plate} onChange={e => setPlate(e.target.value)} placeholder="43-A1 123.45" required /></label><label>Face token<input value={face} onChange={e => setFace(e.target.value)} placeholder="Mã từ ArcFace" required /></label><button>Đối soát phương tiện</button></form></div>
      <section className="events"><h2>Nhật ký ra vào</h2>{events.length === 0 ? <p>Chưa có lượt kiểm soát.</p> : events.map(e => <article key={e.id}><div><b>{e.plate_number || "Không đọc được biển số"}</b><small>{new Date(e.occurred_at).toLocaleString("vi-VN")}</small></div><span className={`tag ${e.decision}`}>{e.decision}</span><p>{e.reason}</p></article>)}</section></section>
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
