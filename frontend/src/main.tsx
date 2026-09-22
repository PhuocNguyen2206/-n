import { FormEvent, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./live.css";
import "./face.css";
import "./lanes.css";
import "./evidence.css";

type Event = { id: string; occurred_at: string; plate_number: string | null; decision: string; reason: string; evidence_url?: string | null };
type CameraDevice = { deviceId: string; label: string };
const API = "http://127.0.0.1:8000/api/v1";

function App() {
  const [events, setEvents] = useState<Event[]>([]);
  const [status, setStatus] = useState("Đang kết nối API...");
  const [faceImages, setFaceImages] = useState<File[]>([]);
  const [vehicleImage, setVehicleImage] = useState<File | null>(null);
  const [direction, setDirection] = useState("exit");
  const [gateResult, setGateResult] = useState("");
  const faceVideoRef = useRef<HTMLVideoElement>(null);
  const faceOverlayRef = useRef<HTMLCanvasElement>(null);
  const exitOverlayRef = useRef<HTMLCanvasElement>(null);
  const plateVideoRef = useRef<HTMLVideoElement>(null);
  const faceStreamRef = useRef<MediaStream | null>(null);
  const plateStreamRef = useRef<MediaStream | null>(null);
  const scanningRef = useRef(false);
  const scanTimerRef = useRef<number | null>(null);
  const faceTimerRef = useRef<number | null>(null);
  const faceScanningRef = useRef(false);
  const snapshotUrlRef = useRef({ entry: "", exit: "" });
  const lastSnapshotAtRef = useRef({ entry: 0, exit: 0 });
  const [liveCameraOn, setLiveCameraOn] = useState(false);
  const [liveScanning, setLiveScanning] = useState(false);
  const [faceScanning, setFaceScanning] = useState(false);
  const [faceResult, setFaceResult] = useState("Chưa bắt đầu quét khuôn mặt.");
  const [entrySnapshot, setEntrySnapshot] = useState("");
  const [exitSnapshot, setExitSnapshot] = useState("");
  const [liveResult, setLiveResult] = useState("Sẵn sàng kết nối camera tại làn xe");
  const [cameraDevices, setCameraDevices] = useState<CameraDevice[]>([]);
  const [faceDeviceId, setFaceDeviceId] = useState("");
  const [plateDeviceId, setPlateDeviceId] = useState("");
  const load = async () => {
    try { const eventResponse = await fetch(`${API}/events`); setEvents(await eventResponse.json()); setStatus("Hệ thống sẵn sàng"); }
    catch { setStatus("Chưa kết nối API"); }
  };
  useEffect(() => { load(); }, []);

  const refreshCameraDevices = async () => {
    try {
      const devices = (await navigator.mediaDevices.enumerateDevices())
        .filter(device => device.kind === "videoinput")
        .map((device, index) => ({ deviceId: device.deviceId, label: device.label || `Camera ${index + 1}` }));
      setCameraDevices(devices);
      if (!faceDeviceId && devices[0]) setFaceDeviceId(devices[0].deviceId);
      if (!plateDeviceId && devices[0]) setPlateDeviceId(devices[0].deviceId);
      setLiveResult(devices.length ? "Đã tìm thấy camera. Chọn DroidCam cho làn cần dùng." : "Chưa tìm thấy camera. Hãy mở DroidCam Client rồi tải lại danh sách.");
    } catch { setLiveResult("Không thể đọc danh sách camera. Hãy cho phép quyền Camera rồi thử lại."); }
  };

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
      const form = new FormData(); form.append("images", faceFrame); form.append("images", plateFrame); form.append("direction", direction); form.append("automatic", "true");
      const response = await fetch(`${API}/gate/verify`, { method: "POST", body: form }); const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Không thể quét camera");
      const label = result.decision === "approved" ? "✓ CHO PHÉP QUA CỔNG" : result.decision === "manual_review" ? "… ĐANG QUÉT TỰ ĐỘNG" : "✕ GIỮ XE - CẦN KIỂM TRA";
      setLiveResult(`${label}: ${result.reason}${result.plate_number ? ` · ${result.plate_number}` : ""}`); load();
    } catch (error) { setLiveResult(error instanceof Error ? error.message : "Lỗi camera"); }
    finally { scanningRef.current = false; }
  };

  const drawFaceBoxes = (video: HTMLVideoElement | null, canvas: HTMLCanvasElement | null, result: { width: number; height: number; faces: Array<{ box: number[]; confidence: number }> }) => {
    if (!video || !canvas || !result.width || !result.height) return;
    canvas.width = video.clientWidth; canvas.height = video.clientHeight;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    const scaleX = canvas.width / result.width, scaleY = canvas.height / result.height;
    result.faces.forEach(({ box, confidence }) => {
      const [left, top, right, bottom] = box;
      const x = left * scaleX, y = top * scaleY, width = (right - left) * scaleX, height = (bottom - top) * scaleY;
      context.strokeStyle = "#4ade80"; context.lineWidth = 3; context.strokeRect(x, y, width, height);
      context.fillStyle = "#16a34acc"; context.fillRect(x, Math.max(0, y - 23), 142, 21);
      context.fillStyle = "#ffffff"; context.font = "bold 12px system-ui"; context.fillText(`KHUÔN MẶT ${Math.round(confidence * 100)}%`, x + 6, Math.max(15, y - 8));
    });
  };

  const scanOneLaneFace = async (lane: "entry" | "exit", video: HTMLVideoElement | null, canvas: HTMLCanvasElement | null) => {
    if (!video) return false;
    try {
      const frame = await frameFromVideo(video, `${lane}-face-live.jpg`);
      const form = new FormData(); form.append("image", frame);
      const response = await fetch(`${API}/face/analyze`, { method: "POST", body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Không thể quét khuôn mặt");
      drawFaceBoxes(video, canvas, result);
      if (result.faces.length && Date.now() - lastSnapshotAtRef.current[lane] > 2500) {
        if (snapshotUrlRef.current[lane]) URL.revokeObjectURL(snapshotUrlRef.current[lane]);
        const url = URL.createObjectURL(frame); snapshotUrlRef.current[lane] = url; lastSnapshotAtRef.current[lane] = Date.now();
        if (lane === "entry") setEntrySnapshot(url); else setExitSnapshot(url);
      }
      return result.faces.length > 0;
    } catch { return false; }
  };

  const scanFaceOnly = async () => {
    if (faceScanningRef.current) return;
    faceScanningRef.current = true;
    try {
      const [entryDetected, exitDetected] = await Promise.all([
        scanOneLaneFace("entry", faceVideoRef.current, faceOverlayRef.current),
        scanOneLaneFace("exit", plateVideoRef.current, exitOverlayRef.current),
      ]);
      setFaceResult(entryDetected || exitDetected ? `✓ Đã phát hiện khuôn mặt: lối vào ${entryDetected ? "sẵn sàng" : "đang chờ"}, lối ra ${exitDetected ? "sẵn sàng" : "đang chờ"}.` : "Chưa thấy khuôn mặt rõ ở hai lối. Hãy nhìn thẳng vào camera và tăng ánh sáng.");
    } finally { faceScanningRef.current = false; }
  };

  const startLiveCamera = async () => {
    try {
      const devices = cameraDevices.length ? cameraDevices : (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === "videoinput").map((device, index) => ({ deviceId: device.deviceId, label: device.label || `Camera ${index + 1}` }));
      if (!devices.length) throw new Error("Không tìm thấy camera");
      setCameraDevices(devices);
      const selectedFace = faceDeviceId || devices[0].deviceId;
      const selectedPlate = plateDeviceId || selectedFace;
      const faceStream = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: selectedFace }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      let plateStream: MediaStream;
      if (selectedPlate === selectedFace) plateStream = faceStream;
      else plateStream = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: selectedPlate }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      faceStreamRef.current = faceStream; plateStreamRef.current = plateStream;
      if (faceVideoRef.current) { faceVideoRef.current.srcObject = faceStream; await faceVideoRef.current.play(); }
      if (plateVideoRef.current) { plateVideoRef.current.srcObject = plateStream; await plateVideoRef.current.play(); }
      setLiveCameraOn(true);
      scanFaceOnly(); faceTimerRef.current = window.setInterval(scanFaceOnly, 900); setFaceScanning(true);
      scanLiveFrame(); scanTimerRef.current = window.setInterval(scanLiveFrame, 3000); setLiveScanning(true);
      setLiveResult("Chế độ tự động đang hoạt động: AI liên tục quét mặt, biển số và kiểm tra cổng.");
    } catch (error) { setLiveResult(error instanceof Error ? error.message : "Không thể mở camera. Hãy kiểm tra quyền Camera của trình duyệt."); }
  };

  const stopLiveCamera = () => {
    if (scanTimerRef.current) window.clearInterval(scanTimerRef.current);
    if (faceTimerRef.current) window.clearInterval(faceTimerRef.current);
    scanTimerRef.current = null; faceTimerRef.current = null; setLiveScanning(false); setFaceScanning(false);
    [...(faceStreamRef.current?.getTracks() || []), ...(plateStreamRef.current?.getTracks() || [])].forEach(track => track.stop());
    Object.values(snapshotUrlRef.current).filter(Boolean).forEach(URL.revokeObjectURL);
    snapshotUrlRef.current = { entry: "", exit: "" }; setEntrySnapshot(""); setExitSnapshot(""); faceStreamRef.current = null; plateStreamRef.current = null; setLiveCameraOn(false); setLiveResult("Đã dừng camera tại làn xe.");
  };

  const toggleLiveScan = () => {
    if (liveScanning) { if (scanTimerRef.current) window.clearInterval(scanTimerRef.current); scanTimerRef.current = null; setLiveScanning(false); setLiveResult("Đã tạm dừng quét tự động."); return; }
    scanLiveFrame(); scanTimerRef.current = window.setInterval(scanLiveFrame, 3000); setLiveScanning(true);
  };

  const toggleFaceScan = () => {
    if (faceScanning) {
      if (faceTimerRef.current) window.clearInterval(faceTimerRef.current);
      faceTimerRef.current = null; setFaceScanning(false); setFaceResult("Đã tạm dừng quét khuôn mặt."); return;
    }
    scanFaceOnly(); faceTimerRef.current = window.setInterval(scanFaceOnly, 900); setFaceScanning(true);
  };

  useEffect(() => {
    // Sau lần cấp quyền đầu tiên, làn xe tự khởi động lại khi mở trang.
    const startAutomatically = async () => { await startLiveCamera(); };
    startAutomatically();
  }, []);

  useEffect(() => () => stopLiveCamera(), []);

  return <main>
    <header><div className="brand"><div className="brand-mark">AI</div><div><p className="eyebrow">CỔNG KIỂM SOÁT THÔNG MINH</p><h1>Nhận diện AI</h1></div></div><span className="status"><i />{status}</span></header>
    <section className="hero"><div><p className="eyebrow">GIÁM SÁT RA VÀO</p><h2>Kiểm tra xe và khuôn mặt<br /><em>trong vài giây.</em></h2><p>Lúc vào, AI lưu biển số và khuôn mặt. Lúc ra, hệ thống đối chiếu với chính lượt xe đó.</p></div><div className="hero-shield">⌁<span>Protected</span></div></section>
    <section className="cards"><article><span className="card-icon blue">◷</span><div><strong>{events.length}</strong><span>Lượt kiểm soát gần đây</span></div></article><article><span className="card-icon green">✓</span><div><strong>{events.filter(e => e.decision === "approved").length}</strong><span>Được cho phép</span></div></article><article><span className="card-icon red">×</span><div><strong>{events.filter(e => e.decision !== "approved").length}</strong><span>Không cho phép</span></div></article></section>
    <section className="lane-console"><div className="lane-head"><div><p className="eyebrow">AUTOMATED PARKING CONSOLE</p><h2>Giám sát lối vào và lối ra</h2><p>Mỗi làn có camera quét và ảnh kết quả riêng.</p></div><span className={liveCameraOn ? "live-badge active" : "live-badge"}><i />{liveCameraOn ? "AUTOMATION ACTIVE" : "CAMERA OFFLINE"}</span></div><div className="gate-lanes"><section className="lane-group entry-lane"><header><span>01</span><div><p className="eyebrow">ENTRY GATE</p><h3>Làn xe vào</h3></div><b>ĐANG GIÁM SÁT</b></header><div className="lane-cards"><article className="live-tile"><div className="feed-label">CAMERA VÀO · LIVE</div><video ref={faceVideoRef} autoPlay muted playsInline /><canvas className="face-overlay" ref={faceOverlayRef} /><span className="feed-empty">{liveCameraOn ? "Đang nhận hình ảnh" : "Đang tự kết nối camera"}</span></article><article className="capture-tile">{entrySnapshot ? <img src={entrySnapshot} alt="Ảnh khuôn mặt tại lối vào" /> : <div className="capture-empty">⌁<span>Chờ ảnh nhận diện<br />lối vào</span></div>}<div className="capture-label">ẢNH QUÉT · LỐI VÀO</div></article></div></section><section className="lane-group exit-lane"><header><span>02</span><div><p className="eyebrow">EXIT GATE</p><h3>Làn xe ra</h3></div><b>ĐANG GIÁM SÁT</b></header><div className="lane-cards"><article className="live-tile"><div className="feed-label">CAMERA RA · LIVE</div><video ref={plateVideoRef} autoPlay muted playsInline /><canvas className="face-overlay" ref={exitOverlayRef} /><span className="feed-empty">{liveCameraOn ? "Đang nhận hình ảnh" : "Đang tự kết nối camera"}</span></article><article className="capture-tile">{exitSnapshot ? <img src={exitSnapshot} alt="Ảnh khuôn mặt tại lối ra" /> : <div className="capture-empty">⌁<span>Chờ ảnh nhận diện<br />lối ra</span></div>}<div className="capture-label">ẢNH QUÉT · LỐI RA</div></article></div></section></div><div className="lane-actions"><label>Camera lối vào<select value={faceDeviceId} onChange={e => setFaceDeviceId(e.target.value)}><option value="">Chọn camera</option>{cameraDevices.map(camera => <option key={camera.deviceId} value={camera.deviceId}>{camera.label}</option>)}</select></label><label>Camera lối ra<select value={plateDeviceId} onChange={e => setPlateDeviceId(e.target.value)}><option value="">Dùng cùng camera lối vào</option>{cameraDevices.map(camera => <option key={camera.deviceId} value={camera.deviceId}>{camera.label}</option>)}</select></label><label>Hướng kiểm tra<select value={direction} onChange={e => setDirection(e.target.value)}><option value="entry">Lối vào</option><option value="exit">Lối ra</option></select></label><div className="live-buttons"><button type="button" className="secondary" onClick={refreshCameraDevices}>Đổi camera</button>{!liveCameraOn ? <button type="button" onClick={startLiveCamera}>Khởi động lại làn tự động</button> : <><button type="button" className="face-scan-button" onClick={toggleFaceScan}>{faceScanning ? "Tạm dừng quét mặt" : "Tiếp tục quét mặt"}</button><button type="button" onClick={toggleLiveScan}>{liveScanning ? "Tạm dừng quét cổng" : "Tiếp tục quét cổng"}</button><button type="button" className="secondary" onClick={stopLiveCamera}>Dừng camera</button></>}</div></div><p className={`gate-decision ${faceResult.startsWith("✓") ? "allow" : ""}`}>{faceResult}</p><p className={`gate-decision ${liveResult.startsWith("✓") ? "allow" : liveResult.startsWith("✕") ? "block" : ""}`}>{liveResult}</p></section>
    <section className="grid"><div>
      <form onSubmit={verifyGate} className="scan-card"><div className="form-title"><span className="form-icon">⌁</span><div><h2>Quét kiểm soát cổng</h2><p>Không cần đăng ký trước: đối chiếu lượt vào và lượt ra của cùng xe.</p></div></div><div className="upload-grid"><label className="upload"><b>◎</b><span>Ảnh khuôn mặt</span><small>{faceImages.length ? `Đã chọn ${faceImages.length} ảnh` : "Chọn 1 hoặc nhiều ảnh rõ mặt"}</small><input type="file" accept="image/*" multiple onChange={e => setFaceImages(Array.from(e.target.files || []))} /></label><label className="upload"><b>▣</b><span>Ảnh xe & biển số</span><small>{vehicleImage?.name || "Chọn ảnh biển số"}</small><input type="file" accept="image/*" onChange={e => setVehicleImage(e.target.files?.[0] || null)} /></label></div><label>Thời điểm quét<select value={direction} onChange={e => setDirection(e.target.value)}><option value="entry">Xe vào cổng</option><option value="exit">Xe ra cổng</option></select></label><button>Quét và kiểm tra <span>→</span></button>{gateResult && <p className="result">{gateResult}</p>}</form>
    </div><section className="events"><div className="events-head"><div><p className="eyebrow">LỊCH SỬ HỆ THỐNG</p><h2>Nhật ký ra vào</h2></div><span>{events.length} lượt</span></div>{events.length === 0 ? <p>Chưa có lượt kiểm soát.</p> : events.map(e => <article key={e.id}><div><b>{e.plate_number || "Không đọc được biển số"}</b><small>{new Date(e.occurred_at).toLocaleString("vi-VN")}</small></div><span className={`tag ${e.decision}`}>{e.decision === "approved" ? "Được phép" : "Từ chối"}</span><p>{e.evidence_url && <img className="event-evidence" src={`http://127.0.0.1:8000${e.evidence_url}`} alt="Ảnh bằng chứng" />}{e.reason}</p></article>)}</section></section>
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
