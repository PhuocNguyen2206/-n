import { FormEvent, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./live.css";

type Event = { id: string; occurred_at: string; plate_number: string | null; decision: string; reason: string };
const API = "http://127.0.0.1:8000/api/v1";

function App() {
  const [events, setEvents] = useState<Event[]>([]);
  const [status, setStatus] = useState("Đang kết nối API...");
  const [faceImages, setFaceImages] = useState<File[]>([]);
  const [vehicleImage, setVehicleImage] = useState<File | null>(null);
  const [direction, setDirection] = useState("exit");
  const [gateResult, setGateResult] = useState("");
  const faceVideoRef = useRef<HTMLVideoElement>(null);
  const plateVideoRef = useRef<HTMLVideoElement>(null);
  const faceStreamRef = useRef<MediaStream | null>(null);
  const plateStreamRef = useRef<MediaStream | null>(null);
  const scanningRef = useRef(false);
  const scanTimerRef = useRef<number | null>(null);
  const [liveCameraOn, setLiveCameraOn] = useState(false);
  const [liveScanning, setLiveScanning] = useState(false);
  const [liveResult, setLiveResult] = useState("Sẵn sàng kết nối camera tại làn xe");
  const load = async () => {
    try { const eventResponse = await fetch(`${API}/events`); setEvents(await eventResponse.json()); setStatus("Hệ thống sẵn sàng"); }
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

  const frameFromVideo = (video: HTMLVideoElement, name: string) => new Promise<File>((resolve, reject) => {
    if (!video.videoWidth || !video.videoHeight) { reject(new Error("Camera chưa sẵn sàng")); return; }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => blob ? resolve(new File([blob], name, { type: "image/jpeg" })) : reject(new Error("Không thể lấy khung hình")), "image/jpeg", 0.88);
  });

  const scanLiveFrame = async () => {
    if (scanningRef.current || !faceVideoRef.current || !plateVideoRef.current) return;
    scanningRef.current = true;
    try {
      const [faceFrame, plateFrame] = await Promise.all([frameFromVideo(faceVideoRef.current, "face-camera.jpg"), frameFromVideo(plateVideoRef.current, "plate-camera.jpg")]);
      const form = new FormData(); form.append("images", faceFrame); form.append("images", plateFrame); form.append("direction", direction);
      const response = await fetch(`${API}/gate/verify`, { method: "POST", body: form }); const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Không thể quét camera");
      const label = result.decision === "approved" ? "✓ CHO PHÉP QUA CỔNG" : "✕ GIỮ XE - CẦN KIỂM TRA";
      setLiveResult(`${label}: ${result.reason}${result.plate_number ? ` · ${result.plate_number}` : ""}`); load();
    } catch (error) { setLiveResult(error instanceof Error ? error.message : "Lỗi camera"); }
    finally { scanningRef.current = false; }
  };

  const startLiveCamera = async () => {
    try {
      const faceStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      let plateStream: MediaStream;
      try { plateStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false }); }
      catch { plateStream = faceStream; }
      faceStreamRef.current = faceStream; plateStreamRef.current = plateStream;
      if (faceVideoRef.current) { faceVideoRef.current.srcObject = faceStream; await faceVideoRef.current.play(); }
      if (plateVideoRef.current) { plateVideoRef.current.srcObject = plateStream; await plateVideoRef.current.play(); }
      setLiveCameraOn(true); setLiveResult("Camera đã kết nối. Bấm quét tự động để kiểm soát làn xe.");
    } catch { setLiveResult("Không thể mở camera. Hãy kiểm tra quyền Camera của trình duyệt."); }
  };

  const stopLiveCamera = () => {
    if (scanTimerRef.current) window.clearInterval(scanTimerRef.current);
    scanTimerRef.current = null; setLiveScanning(false);
    [...(faceStreamRef.current?.getTracks() || []), ...(plateStreamRef.current?.getTracks() || [])].forEach(track => track.stop());
    faceStreamRef.current = null; plateStreamRef.current = null; setLiveCameraOn(false); setLiveResult("Đã dừng camera tại làn xe.");
  };

  const toggleLiveScan = () => {
    if (liveScanning) { if (scanTimerRef.current) window.clearInterval(scanTimerRef.current); scanTimerRef.current = null; setLiveScanning(false); setLiveResult("Đã tạm dừng quét tự động."); return; }
    scanLiveFrame(); scanTimerRef.current = window.setInterval(scanLiveFrame, 3000); setLiveScanning(true);
  };

  useEffect(() => () => stopLiveCamera(), []);

  return <main>
    <header><div className="brand"><div className="brand-mark">AI</div><div><p className="eyebrow">CỔNG KIỂM SOÁT THÔNG MINH</p><h1>Nhận diện AI</h1></div></div><span className="status"><i />{status}</span></header>
    <section className="hero"><div><p className="eyebrow">GIÁM SÁT RA VÀO</p><h2>Kiểm tra xe và khuôn mặt<br /><em>trong vài giây.</em></h2><p>Lúc vào, AI lưu biển số và khuôn mặt. Lúc ra, hệ thống đối chiếu với chính lượt xe đó.</p></div><div className="hero-shield">⌁<span>Protected</span></div></section>
    <section className="cards"><article><span className="card-icon blue">◷</span><div><strong>{events.length}</strong><span>Lượt kiểm soát gần đây</span></div></article><article><span className="card-icon green">✓</span><div><strong>{events.filter(e => e.decision === "approved").length}</strong><span>Được cho phép</span></div></article><article><span className="card-icon red">×</span><div><strong>{events.filter(e => e.decision !== "approved").length}</strong><span>Không cho phép</span></div></article></section>
    <section className="lane-console"><div className="lane-head"><div><p className="eyebrow">LIVE GATE CONTROL</p><h2>Làn xe thời gian thực</h2><p>Hai camera đồng bộ: người điều khiển và biển số.</p></div><span className={liveCameraOn ? "live-badge active" : "live-badge"}><i />{liveCameraOn ? "CAMERA ONLINE" : "CAMERA OFFLINE"}</span></div><div className="live-feeds"><article><div className="feed-label">CAM 01 · KHUÔN MẶT</div><video ref={faceVideoRef} autoPlay muted playsInline /><span className="feed-empty">{liveCameraOn ? "Đang nhận hình ảnh" : "Chưa kết nối camera"}</span></article><article><div className="feed-label">CAM 02 · BIỂN SỐ</div><video ref={plateVideoRef} autoPlay muted playsInline /><span className="feed-empty">{liveCameraOn ? "Đang nhận hình ảnh" : "Chưa kết nối camera"}</span></article></div><div className="lane-actions"><label>Hướng làn xe<select value={direction} onChange={e => setDirection(e.target.value)}><option value="entry">Lối vào</option><option value="exit">Lối ra</option></select></label><div className="live-buttons">{!liveCameraOn ? <button type="button" onClick={startLiveCamera}>Bật camera tại làn xe</button> : <><button type="button" onClick={toggleLiveScan}>{liveScanning ? "Tạm dừng quét" : "Bắt đầu quét tự động"}</button><button type="button" className="secondary" onClick={stopLiveCamera}>Dừng camera</button></>}</div></div><p className={`gate-decision ${liveResult.startsWith("✓") ? "allow" : liveResult.startsWith("✕") ? "block" : ""}`}>{liveResult}</p></section>
    <section className="grid"><div>
      <form onSubmit={verifyGate} className="scan-card"><div className="form-title"><span className="form-icon">⌁</span><div><h2>Quét kiểm soát cổng</h2><p>Không cần đăng ký trước: đối chiếu lượt vào và lượt ra của cùng xe.</p></div></div><div className="upload-grid"><label className="upload"><b>◎</b><span>Ảnh khuôn mặt</span><small>{faceImages.length ? `Đã chọn ${faceImages.length} ảnh` : "Chọn 1 hoặc nhiều ảnh rõ mặt"}</small><input type="file" accept="image/*" multiple onChange={e => setFaceImages(Array.from(e.target.files || []))} /></label><label className="upload"><b>▣</b><span>Ảnh xe & biển số</span><small>{vehicleImage?.name || "Chọn ảnh biển số"}</small><input type="file" accept="image/*" onChange={e => setVehicleImage(e.target.files?.[0] || null)} /></label></div><label>Thời điểm quét<select value={direction} onChange={e => setDirection(e.target.value)}><option value="entry">Xe vào cổng</option><option value="exit">Xe ra cổng</option></select></label><button>Quét và kiểm tra <span>→</span></button>{gateResult && <p className="result">{gateResult}</p>}</form>
    </div><section className="events"><div className="events-head"><div><p className="eyebrow">LỊCH SỬ HỆ THỐNG</p><h2>Nhật ký ra vào</h2></div><span>{events.length} lượt</span></div>{events.length === 0 ? <p>Chưa có lượt kiểm soát.</p> : events.map(e => <article key={e.id}><div><b>{e.plate_number || "Không đọc được biển số"}</b><small>{new Date(e.occurred_at).toLocaleString("vi-VN")}</small></div><span className={`tag ${e.decision}`}>{e.decision === "approved" ? "Được phép" : "Từ chối"}</span><p>{e.reason}</p></article>)}</section></section>
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
