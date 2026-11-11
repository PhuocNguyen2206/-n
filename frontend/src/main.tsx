import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./operations.css";

type Event = { id: string; occurred_at: string; direction: string; plate_number: string | null; decision: string; reason: string; evidence_url?: string | null };
type GateSession = { id: string; plate_number: string; entered_at: string; exited_at?: string | null; status: string; entry_decision?: string | null; exit_decision?: string | null; exit_reason?: string | null; entry_evidence_url?: string | null; exit_evidence_url?: string | null };
type ExitReview = { review_id: string; plate_number: string; reason: string; evidence_url: string | null; entry_evidence_url: string | null; captured_at: string; entered_at: string };
type CameraDevice = { deviceId: string; label: string };
const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";
const BACKEND = new URL(API).origin;

function App() {
  const [events, setEvents] = useState<Event[]>([]);
  const [sessions, setSessions] = useState<GateSession[]>([]);
  const [status, setStatus] = useState("Đang kết nối API...");
  const [activeView, setActiveView] = useState<"overview" | "monitor" | "analysis" | "history">("overview");
  const [historyPlate, setHistoryPlate] = useState("");
  const [historyPage, setHistoryPage] = useState(0);
  const [historyData, setHistoryData] = useState<{items: Event[]; total: number}>({items: [], total: 0});
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [photoError, setPhotoError] = useState(false);
  const evidenceDialog = useRef<HTMLDialogElement>(null);
  const [historyStart, setHistoryStart] = useState("");
  const [historyEnd, setHistoryEnd] = useState("");
  const [currentTime, setCurrentTime] = useState(() => new Date());
  const faceVideoRef = useRef<HTMLVideoElement>(null);
  const faceOverlayRef = useRef<HTMLCanvasElement>(null);
  const plateVideoRef = useRef<HTMLVideoElement>(null);
  const faceStreamRef = useRef<MediaStream | null>(null);
  const plateStreamRef = useRef<MediaStream | null>(null);
  const scanningRef = useRef(false);
  const reviewRef = useRef<ExitReview | null>(null);
  const [pendingReview, setPendingReview] = useState<ExitReview | null>(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewMessage, setReviewMessage] = useState("");
  const [operatorName, setOperatorName] = useState("");
  const [reviewReason, setReviewReason] = useState("");
  const [checkedEvidence, setCheckedEvidence] = useState(false);
  const [barrierState, setBarrierState] = useState<"held" | "auto_open" | "manual_open">("held");
  const scanTimerRef = useRef<number | null>(null);
  const faceTimerRef = useRef<number | null>(null);
  const faceScanningRef = useRef(false);
  const [liveCameraOn, setLiveCameraOn] = useState(false);
  const [cameraStarting, setCameraStarting] = useState(false);
  const [direction, setDirection] = useState<"entry" | "exit">("entry");
  const [liveScanning, setLiveScanning] = useState(false);
  const [faceScanning, setFaceScanning] = useState(false);
  const [faceResult, setFaceResult] = useState("Chưa bắt đầu quét khuôn mặt.");
  const [entrySnapshot, setEntrySnapshot] = useState("");
  const [exitSnapshot, setExitSnapshot] = useState("");
  const [captureDetails, setCaptureDetails] = useState({ entry: "", exit: "" });
  const [liveResult, setLiveResult] = useState("Sẵn sàng kết nối camera tại làn xe");
  const [cameraDevices, setCameraDevices] = useState<CameraDevice[]>([]);
  const [faceDeviceId, setFaceDeviceId] = useState("");
  const [plateDeviceId, setPlateDeviceId] = useState("");
  const load = async () => {
    try {
      const responses = await Promise.all([fetch(`${API}/events`), fetch(`${API}/sessions/recent`), fetch(`${API}/gate/exit-reviews/pending`)]);
      if (!responses.every(response => response.ok)) throw new Error("API unavailable");
      const [eventData, sessionData, reviewData] = await Promise.all(responses.map(response => response.json()));
      if (!reviewRef.current && reviewData[0]) {
        reviewRef.current = reviewData[0]; setPendingReview(reviewData[0]); setBarrierState("held"); setDirection("exit");
        setLiveResult(`… CHỜ BẢO VỆ · ${reviewData[0].plate_number} · ${reviewData[0].reason}`);
        if (scanTimerRef.current) window.clearInterval(scanTimerRef.current);
        scanTimerRef.current = null; setLiveScanning(false);
      }
      setEvents(eventData); setSessions(sessionData); setStatus("Hệ thống sẵn sàng");
    } catch { setStatus("Chưa kết nối API"); }
  };
  useEffect(() => {
    load();
    const refreshTimer = window.setInterval(load, 10000);
    const clockTimer = window.setInterval(() => setCurrentTime(new Date()), 1000);
    return () => { window.clearInterval(refreshTimer); window.clearInterval(clockTimer); };
  }, []);

  useEffect(() => {
    if (activeView !== "history") return;
    const controller = new AbortController();
    setHistoryBusy(true); setHistoryError("");
    const timer = window.setTimeout(async () => {
      try {
        if (historyStart && historyEnd && historyStart > historyEnd) throw new Error("Thời gian bắt đầu phải trước thời gian kết thúc.");
        const query = new URLSearchParams({plate: historyPlate, limit: "20", offset: String(historyPage * 20)});
        if (historyStart) query.set("start", new Date(historyStart).toISOString());
        if (historyEnd) query.set("end", new Date(historyEnd).toISOString());
        const response = await fetch(`${API}/events/search?${query}`, {signal: controller.signal});
        if (!response.ok) throw new Error("Không tải được lịch sử. Kiểm tra API rồi bấm tải lại.");
        const result = await response.json();
        if (!controller.signal.aborted) setHistoryData(result);
      } catch (error) {
        if (!controller.signal.aborted) setHistoryError(error instanceof Error ? error.message : "Không tải được lịch sử.");
      } finally { if (!controller.signal.aborted) setHistoryBusy(false); }
    }, 250);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [activeView, historyPlate, historyStart, historyEnd, historyPage, historyRefresh]);

  useEffect(() => {
    if (selectedEvent) { setPhotoError(false); evidenceDialog.current?.showModal(); }
  }, [selectedEvent]);

  const refreshCameraDevices = async () => {
    try {
      const devices = (await navigator.mediaDevices.enumerateDevices())
        .filter(device => device.kind === "videoinput")
        .map((device, index) => ({ deviceId: device.deviceId, label: device.label || `Camera ${index + 1}` }));
      setCameraDevices(devices);
      if (!faceDeviceId && devices[0]) setFaceDeviceId(devices[0].deviceId);
      if (!plateDeviceId && devices[1]) setPlateDeviceId(devices[1].deviceId);
      setLiveResult(devices.length ? "Đã tìm thấy camera. Chọn một webcam khuôn mặt và một webcam biển số." : "Chưa tìm thấy camera. Kiểm tra kết nối webcam rồi tìm lại.");
    } catch { setLiveResult("Không thể đọc danh sách camera. Hãy cho phép quyền Camera rồi thử lại."); }
  };

  const frameFromVideo = (video: HTMLVideoElement, name: string) => new Promise<File>((resolve, reject) => {
    if (!video.videoWidth || !video.videoHeight) { reject(new Error("Camera chưa sẵn sàng")); return; }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => blob ? resolve(new File([blob], name, { type: "image/jpeg" })) : reject(new Error("Không thể lấy khung hình")), "image/jpeg", 0.88);
  });

  const scanLiveFrame = async () => {
    if (reviewRef.current || scanningRef.current || !faceVideoRef.current || !plateVideoRef.current) return;
    scanningRef.current = true;
    setBarrierState("held");
    try {
      const [faceFrame, plateFrame] = await Promise.all([frameFromVideo(faceVideoRef.current, "face-camera.jpg"), frameFromVideo(plateVideoRef.current, "plate-camera.jpg")]);
      const form = new FormData();
      form.append("images", faceFrame); form.append("images", plateFrame);
      form.append("direction", direction); form.append("automatic", "true"); form.append("paired_cameras", "true");
      const response = await fetch(`${API}/gate/verify`, { method: "POST", body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Không thể quét camera");
      if (result.review_id) {
        reviewRef.current = result; setPendingReview(result); setCheckedEvidence(false); setReviewMessage("");
        if (scanTimerRef.current) window.clearInterval(scanTimerRef.current);
        scanTimerRef.current = null; setLiveScanning(false);
      }
      if (result.decision === "approved") setBarrierState("auto_open");
      if (result.decision === "approved" && result.evidence_url) {
        const url = `${BACKEND}${result.evidence_url}`;
        if (direction === "entry") setEntrySnapshot(url); else setExitSnapshot(url);

        setCaptureDetails(previous => ({ ...previous, [direction]: `${result.plate_number || ""} · ${new Date(result.captured_at).toLocaleString("vi-VN")}` }));
      }
      const decision = result.decision === "approved" ? "✓ CHO PHÉP" : result.decision === "manual_review" ? "… ĐANG CHỜ" : "✕ TỪ CHỐI";
      setLiveResult(`${decision} · ${direction === "entry" ? "Lối vào" : "Lối ra"} — ${result.reason}${result.plate_number ? ` · ${result.plate_number}` : ""}`);
      load();
    } catch (error) { setLiveResult(error instanceof Error ? error.message : "Lỗi camera"); }
    finally { scanningRef.current = false; }
  };

  const resolveReview = async (action: "approve" | "reject") => {
    if (!pendingReview || reviewBusy) return;
    setReviewBusy(true); setReviewMessage("");
    try {
      const response = await fetch(`${API}/gate/exit-reviews/${pendingReview.review_id}/resolve`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action, operator_name: operatorName.trim(), reason: reviewReason.trim()})});
      const result = await response.json();
      if (!response.ok) {
        if (response.status === 409 || response.status === 404) { reviewRef.current = null; setPendingReview(null); await load(); setLiveResult("Yêu cầu không còn hiệu lực. Kiểm tra nhật ký và quét lại."); }
        throw new Error(typeof result.detail === "string" ? result.detail : "Hãy kiểm tra tên người xử lý và lý do.");
      }
      if (action === "approve") {
        setBarrierState("manual_open");
        if (result.evidence_url) setExitSnapshot(`${BACKEND}${result.evidence_url}`);

        setCaptureDetails(previous => ({...previous, exit: `${result.plate_number} · Bảo vệ xác nhận · ${new Date(result.captured_at).toLocaleString("vi-VN")}`}));
      } else setBarrierState("held");
      setLiveResult(action === "approve" ? `✓ BẢO VỆ XÁC NHẬN · ${result.plate_number} · Mở thanh chắn mô phỏng` : `✕ BẢO VỆ TỪ CHỐI · ${result.plate_number} · Giữ thanh chắn mô phỏng`);
      reviewRef.current = null; setPendingReview(null); setReviewReason(""); setCheckedEvidence(false);
      await load();
    } catch (error) { setReviewMessage(error instanceof Error ? error.message : "Không lưu được xác nhận. Thanh chắn mô phỏng vẫn giữ."); }
    finally { setReviewBusy(false); }
  };

  const drawFaceBoxes = (video: HTMLVideoElement | null, canvas: HTMLCanvasElement | null, result: { width: number; height: number; faces: Array<{ box: number[]; confidence: number }> }) => {
    if (!video || !canvas || !result.width || !result.height) return;
    canvas.width = video.clientWidth; canvas.height = video.clientHeight;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    const scale = Math.min(canvas.width / result.width, canvas.height / result.height);
    const offsetX = (canvas.width - result.width * scale) / 2;
    const offsetY = (canvas.height - result.height * scale) / 2;
    result.faces.forEach(({ box, confidence }) => {
      const [left, top, right, bottom] = box;
      const x = offsetX + left * scale, y = offsetY + top * scale, width = (right - left) * scale, height = (bottom - top) * scale;
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
      return result.faces.length > 0;
    } catch { return false; }
  };

  const scanFaceOnly = async () => {
    if (faceScanningRef.current) return;
    faceScanningRef.current = true;
    try {
      const detected = await scanOneLaneFace("entry", faceVideoRef.current, faceOverlayRef.current);
      setFaceResult(detected ? "✓ Đã phát hiện khuôn mặt ở camera khuôn mặt." : "Chưa thấy khuôn mặt rõ. Hãy nhìn thẳng vào camera khuôn mặt và tăng ánh sáng.");
    } finally { faceScanningRef.current = false; }
  };

  const startLiveCamera = async () => {
    if (cameraStarting || liveCameraOn) return;
    setCameraStarting(true);
    try {
      const devices = cameraDevices.length ? cameraDevices : (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === "videoinput").map((device, index) => ({ deviceId: device.deviceId, label: device.label || `Camera ${index + 1}` }));
      if (devices.length < 2) throw new Error("Cần kết nối hai webcam riêng: khuôn mặt và biển số.");
      setCameraDevices(devices);
      const selectedFace = faceDeviceId || devices[0].deviceId;
      const selectedPlate = plateDeviceId || devices[1].deviceId;
      if (selectedPlate === selectedFace) throw new Error("Hãy chọn hai webcam khác nhau cho khuôn mặt và biển số.");
      setFaceDeviceId(selectedFace); setPlateDeviceId(selectedPlate);
      const faceStream = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: selectedFace }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      faceStreamRef.current = faceStream;
      const plateStream = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: selectedPlate }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      plateStreamRef.current = plateStream;
      if (faceVideoRef.current) { faceVideoRef.current.srcObject = faceStream; await faceVideoRef.current.play(); }
      if (plateVideoRef.current) { plateVideoRef.current.srcObject = plateStream; await plateVideoRef.current.play(); }
      setLiveCameraOn(true);
      scanFaceOnly(); faceTimerRef.current = window.setInterval(scanFaceOnly, 900); setFaceScanning(true);
      if (!reviewRef.current) { scanLiveFrame(); scanTimerRef.current = window.setInterval(scanLiveFrame, 3000); setLiveScanning(true); }
      setLiveResult("Chế độ tự động đang hoạt động: AI liên tục quét mặt, biển số và kiểm tra cổng.");
    } catch (error) {
      stopLiveCamera();
      setLiveResult(error instanceof Error ? error.message : "Không thể mở camera. Hãy kiểm tra quyền Camera của trình duyệt.");
    } finally { setCameraStarting(false); }
  };

  const stopLiveCamera = () => {
    if (scanTimerRef.current) window.clearInterval(scanTimerRef.current);
    if (faceTimerRef.current) window.clearInterval(faceTimerRef.current);
    scanTimerRef.current = null; faceTimerRef.current = null; setLiveScanning(false); setFaceScanning(false);
    [...(faceStreamRef.current?.getTracks() || []), ...(plateStreamRef.current?.getTracks() || [])].forEach(track => track.stop());
    faceStreamRef.current = null; plateStreamRef.current = null; setLiveCameraOn(false); setLiveResult("Đã dừng camera tại làn xe.");
  };

  const toggleLiveScan = () => {
    if (reviewRef.current) { setLiveResult("Cần xử lý yêu cầu bảo vệ trước khi tiếp tục quét."); return; }
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

  useEffect(() => () => stopLiveCamera(), []);

  const displayedEvents = activeView === "history" ? historyData.items : events.slice(0, 6);
  const decisionLabel = (decision: string) => ({approved: "Cho phép (AI)", manual_approved: "Bảo vệ cho ra", manual_review: "Chờ bảo vệ", denied: "Từ chối"}[decision] || decision);
  const startOfToday = new Date(currentTime);
  startOfToday.setHours(0, 0, 0, 0);
  const todayEvents = events.filter(event => new Date(event.occurred_at).getTime() >= startOfToday.getTime());
  const hourlyTraffic = Array.from({ length: 24 }, (_, hour) => todayEvents.filter(event => new Date(event.occurred_at).getHours() === hour).length);
  const trafficPeak = Math.max(...hourlyTraffic, 0);
  const latestComparison = sessions.find(session => session.exited_at) || sessions[0];


  return <main className={`view-${activeView}`}>
    <header><div className="brand"><div className="brand-mark">BV</div><div><p className="eyebrow">QUẢN LÝ PHƯƠNG TIỆN</p><h1>Trạm bảo vệ</h1></div></div><span className={`status ${status === "Hệ thống sẵn sàng" ? "connected" : "disconnected"}`}><i />{status}</span></header>
    <nav className="app-nav" aria-label="Chức năng hệ thống"><button aria-current={activeView === "overview" ? "page" : undefined} className={activeView === "overview" ? "active" : ""} onClick={() => setActiveView("overview")}>Tổng quan</button><button aria-current={activeView === "monitor" ? "page" : undefined} className={activeView === "monitor" ? "active" : ""} onClick={() => setActiveView("monitor")}>Giám sát cổng</button><button aria-current={activeView === "analysis" ? "page" : undefined} className={activeView === "analysis" ? "active" : ""} onClick={() => setActiveView("analysis")}>Đối chiếu & lưu lượng</button><button aria-current={activeView === "history" ? "page" : undefined} className={activeView === "history" ? "active" : ""} onClick={() => setActiveView("history")}>Nhật ký</button></nav>
    <div className="page-heading"><div><p className="eyebrow">CỔNG TRƯỜNG / VẬN HÀNH</p><h2>{{ overview: "Tổng quan ca trực", monitor: "Giám sát cổng", analysis: "Đối chiếu & lưu lượng", history: "Nhật ký ra vào" }[activeView]}</h2><p>{{ overview: "Theo dõi lượt xe và tình trạng kết nối trong ngày.", monitor: "Hai camera riêng cho khuôn mặt và biển số; thử từng hướng vào hoặc ra.", analysis: "Tra cứu bằng chứng và phân bố lượt kiểm soát theo giờ.", history: "Tra cứu thời gian, biển số và kết quả kiểm soát." }[activeView]}</p></div><time>{currentTime.toLocaleDateString("vi-VN")}<strong>{currentTime.toLocaleTimeString("vi-VN", {hour: "2-digit", minute: "2-digit"})}</strong></time></div>
    <section className="cards"><article><span className="card-icon blue">◷</span><div><strong>{todayEvents.length}</strong><span>Lượt kiểm soát hôm nay</span></div></article><article><span className="card-icon green">✓</span><div><strong>{todayEvents.filter(e => e.decision === "approved" || e.decision === "manual_approved").length}</strong><span>Được cho phép hôm nay</span></div></article><article><span className="card-icon red">×</span><div><strong>{todayEvents.filter(e => e.decision === "denied").length}</strong><span>Không cho phép hôm nay</span></div></article></section><section className="overview-peak"><article className="overview-command"><div className="overview-kicker"><span><i /> TÌNH TRẠNG THIẾT BỊ</span><time>{currentTime.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time></div><h2>Hệ thống đang <em>{liveCameraOn ? "giám sát trực tiếp" : "chờ kết nối camera"}.</em></h2><p>{liveCameraOn ? "Hai camera đang cung cấp ảnh mặt và biển số cho hướng kiểm tra đã chọn." : "Mở mục Giám sát cổng để kết nối camera và bắt đầu quét tự động."}</p><div className="system-pulse"><span><i className={liveCameraOn ? "ok" : ""} />Camera</span><span><i className={faceScanning ? "ok" : ""} />Nhận diện mặt</span><span><i className={liveScanning ? "ok" : ""} />Quét biển số</span><span><i className={status === "Hệ thống sẵn sàng" ? "ok" : ""} />API</span></div></article></section>
    <section className="lane-console">
      <div className="lane-head"><div><h2>Camera trực tiếp & ảnh quét</h2></div><span className={liveCameraOn ? "live-badge active" : "live-badge"}><i />{liveCameraOn ? "HAI CAMERA ĐÃ BẬT" : "CHƯA KẾT NỐI"}</span></div>
      <div className="monitor-toolbar"><label>Hướng kiểm tra<select disabled={liveCameraOn || cameraStarting || scanningRef.current || !!pendingReview} value={direction} onChange={e => { setDirection(e.target.value as "entry" | "exit"); setLiveResult("Đã đổi hướng kiểm tra. Bật camera để bắt đầu."); }}><option value="entry">Lối vào — ghi nhận xe</option><option value="exit">Lối ra — đối chiếu xe</option></select></label>      <div className="live-buttons monitor-buttons"><button type="button" className="secondary" disabled={liveCameraOn || cameraStarting} onClick={refreshCameraDevices}>Tìm camera</button>{!liveCameraOn ? <button disabled={cameraStarting || scanningRef.current} type="button" onClick={startLiveCamera}>{cameraStarting ? "Đang mở hai camera…" : "Bật hai camera"}</button> : <><button type="button" onClick={toggleFaceScan}>{faceScanning ? "Tạm dừng quét mặt" : "Tiếp tục quét mặt"}</button><button type="button" onClick={toggleLiveScan}>{liveScanning ? "Tạm dừng quét cổng" : "Tiếp tục quét cổng"}</button><button type="button" className="secondary" onClick={stopLiveCamera}>Dừng camera</button></>}</div></div>
      <details className="camera-settings"><summary>Chọn thiết bị camera <span>Dừng camera trước khi đổi hướng hoặc thiết bị</span></summary><div className="lane-actions"><label>Camera khuôn mặt<select disabled={liveCameraOn || cameraStarting} value={faceDeviceId} onChange={e => setFaceDeviceId(e.target.value)}><option value="">Chọn webcam khuôn mặt</option>{cameraDevices.map(camera => <option key={camera.deviceId} value={camera.deviceId}>{camera.label}</option>)}</select></label>
        <label>Camera biển số<select disabled={liveCameraOn || cameraStarting} value={plateDeviceId} onChange={e => setPlateDeviceId(e.target.value)}><option value="">Chọn webcam biển số</option>{cameraDevices.map(camera => <option key={camera.deviceId} value={camera.deviceId}>{camera.label}</option>)}</select></label>
</div></details>
      <div className="scan-workspace"><div className="camera-preview">
      <div className="gate-lanes">
        <section className="lane-group"><header><span>01</span><div><p className="eyebrow">THU NHẬN KHUÔN MẶT</p><h3>Camera khuôn mặt</h3></div><b>{liveCameraOn ? "Đã kết nối" : "Chưa kết nối"}</b></header><article className="live-tile"><video ref={faceVideoRef} autoPlay muted playsInline /><canvas className="face-overlay" ref={faceOverlayRef} />{!liveCameraOn && <span className="feed-empty">Đặt camera ngang mặt người lái</span>}<div className="feed-label">KHUÔN MẶT · {direction === "entry" ? "LỐI VÀO" : "LỐI RA"}</div></article></section>
        <section className="lane-group"><header><span>02</span><div><p className="eyebrow">THU NHẬN BIỂN SỐ</p><h3>Camera biển số</h3></div><b>{liveCameraOn ? "Đã kết nối" : "Chưa kết nối"}</b></header><article className="live-tile"><video ref={plateVideoRef} autoPlay muted playsInline />{!liveCameraOn && <span className="feed-empty">Hướng camera vào biển số xe</span>}<div className="feed-label">BIỂN SỐ · {direction === "entry" ? "LỐI VÀO" : "LỐI RA"}</div></article></section>
      </div>
      <p className="face-feedback">{faceResult}</p></div>
      <aside className={`scan-receipt ${pendingReview ? "has-review" : ""}`} aria-label="Ảnh quét đã lưu">
        <div className={`barrier-simulation ${barrierState === "held" ? "held" : "opened"}`}><div><small>THANH CHẮN · MÔ PHỎNG</small><strong>{barrierState === "held" ? "ĐANG GIỮ" : barrierState === "manual_open" ? "MỞ — BẢO VỆ XÁC NHẬN" : "MỞ — AI CHO PHÉP"}</strong></div><span className="simulated-arm" aria-hidden="true" />{barrierState !== "held" && <button type="button" className="secondary" onClick={() => setBarrierState("held")}>Đóng mô phỏng</button>}<p>Chỉ hiển thị trên web · Không kết nối thiết bị IoT</p></div>
        {pendingReview && <section className="exit-review" aria-label="Bảo vệ xác nhận xe ra"><h3>Cần bảo vệ kiểm tra · {pendingReview.plate_number}</h3><p>{pendingReview.reason}</p><div className="review-evidence">{([{label: "Lúc vào", url: pendingReview.entry_evidence_url}, {label: "Lúc quét ra", url: pendingReview.evidence_url}]).map(item => <div key={item.label}><b>{item.label}</b>{item.url ? <a href={`${BACKEND}${item.url}`} target="_blank" rel="noreferrer"><img src={`${BACKEND}${item.url}`} alt={`Ảnh mặt và biển số ${item.label}`} /></a> : <p>Không có ảnh</p>}</div>)}</div><small>Vào: {new Date(pendingReview.entered_at).toLocaleString("vi-VN")} · Quét ra: {new Date(pendingReview.captured_at).toLocaleString("vi-VN")}</small><label>Người xử lý<input value={operatorName} onChange={e => setOperatorName(e.target.value)} maxLength={120} disabled={reviewBusy} placeholder="Nhập tên bảo vệ" /></label><label>Lý do xác nhận<input value={reviewReason} onChange={e => setReviewReason(e.target.value)} maxLength={300} disabled={reviewBusy} placeholder="Ví dụ: đeo khẩu trang, đã kiểm tra trực tiếp" /></label><label className="review-check"><input type="checkbox" checked={checkedEvidence} onChange={e => setCheckedEvidence(e.target.checked)} disabled={reviewBusy} />Tôi đã kiểm tra người, xe và ảnh đối chiếu.</label><div className="review-buttons"><button type="button" disabled={reviewBusy || !checkedEvidence || operatorName.trim().length < 2 || reviewReason.trim().length < 3} onClick={() => resolveReview("approve")}>{reviewBusy ? "Đang lưu…" : "Xác nhận cho xe ra (mô phỏng)"}</button><button type="button" className="secondary" disabled={reviewBusy || operatorName.trim().length < 2 || reviewReason.trim().length < 3} onClick={() => resolveReview("reject")}>Không cho xe ra</button></div>{reviewMessage && <p role="alert">{reviewMessage}</p>}<small>Quét cổng đã tạm dừng. Xử lý xong rồi bấm tiếp tục quét.</small></section>}
        <div className="receipt-heading"><div><p className="eyebrow">ẢNH QUÉT ĐÃ LƯU</p><h3>Ảnh quét {direction === "entry" ? "lối vào" : "lối ra"}</h3></div></div>
        <div className="lane-receipts single-lane">{[direction].map(lane => {
          const photo = lane === "entry" ? entrySnapshot : exitSnapshot;
          return <section className={`lane-receipt ${lane} ${direction === lane ? "selected-lane" : ""}`} key={lane} aria-label={`Ảnh quét ${lane === "entry" ? "lối vào" : "lối ra"}`}>
            <header><h4>{lane === "entry" ? "↘ LỐI VÀO" : "↗ LỐI RA"}</h4><span>Lượt gần nhất</span></header>
            {photo ? <><a className="receipt-photo" href={photo} target="_blank" rel="noreferrer"><img src={photo} alt={`Ảnh khuôn mặt và biển số ${lane === "entry" ? "lúc vào" : "lúc ra"}`} /><span>Xem ảnh lớn ↗</span></a><div className="receipt-meta"><strong>✓ Đã lưu</strong><p>{captureDetails[lane]}</p></div></> : <div className="receipt-empty"><span>Chưa có ảnh {lane === "entry" ? "lối vào" : "lối ra"}</span><p>Ảnh hiện tại ô này sau khi lượt xe được cho phép.</p></div>}
          </section>;
        })}</div>
        <p className="lane-receipts-note">Chỉ hiển thị ảnh của hướng đang chọn. Xem cả ảnh vào và ra tại Đối chiếu & lưu lượng.</p>
        <div className={`gate-decision receipt-decision ${liveResult.startsWith("✓") ? "allow" : liveResult.startsWith("✕") ? "block" : ""}`} role="status"><small>TRẠNG THÁI HIỆN TẠI</small><p>{liveResult}</p></div>
      </aside></div>
    </section>
    <section className="showcase-grid"><article className="traffic-panel"><div><p className="eyebrow">LƯU LƯỢNG HÔM NAY</p><h2>Biểu đồ lượt xe theo giờ</h2></div><div className="traffic-chart">{hourlyTraffic.map((count, hour) => <div className="hour-bar" key={hour} title={`${hour}:00 — ${count} lượt`}><span style={{ height: `${count / (trafficPeak || 1) * 100}%` }} /><small>{hour % 3 === 0 ? `${hour}h` : ""}</small></div>)}</div><p className="traffic-caption">Đỉnh lưu lượng: <b>{trafficPeak} lượt/giờ</b> · Tổng hôm nay: <b>{todayEvents.length} lượt</b></p></article></section><section className="comparison-panel"><div className="comparison-head"><div><p className="eyebrow">ĐỐI CHIẾU BẰNG CHỨNG</p><h2>So sánh lượt xe vào và ra</h2></div>{latestComparison && <span className={latestComparison.exited_at ? "comparison-badge done" : "comparison-badge"}>{latestComparison.exited_at ? "ĐÃ ĐỐI CHIẾU" : "ĐANG Ở TRONG BÃI"}</span>}</div>{latestComparison ? <div className="comparison-content"><div className="proof-card"><b>01 · LÚC VÀO</b>{latestComparison.entry_evidence_url ? <img src={`${BACKEND}${latestComparison.entry_evidence_url}`} alt="Ảnh lúc xe vào" /> : <span>Chưa có ảnh bằng chứng</span>}<small>{new Date(latestComparison.entered_at).toLocaleString("vi-VN")}</small></div><div className="comparison-result"><strong>{latestComparison.plate_number}</strong><span>{latestComparison.exited_at ? (latestComparison.exit_decision === "manual_approved" ? "Bảo vệ đã kiểm tra và xác nhận cho xe ra" : "AI đã đối chiếu lượt vào và ra") : "Đang chờ lượt xe ra để xác minh"}</span><b className={latestComparison.exit_decision === "approved" ? "match" : "waiting"}>{latestComparison.exit_decision === "manual_approved" ? "✓ BẢO VỆ XÁC NHẬN" : latestComparison.exit_decision === "approved" ? "✓ KHUÔN MẶT KHỚP" : "… CHỜ ĐỐI CHIẾU"}</b></div><div className="proof-card"><b>02 · LÚC RA</b>{latestComparison.exit_evidence_url ? <img src={`${BACKEND}${latestComparison.exit_evidence_url}`} alt="Ảnh lúc xe ra" /> : <span>Chưa có ảnh bằng chứng</span>}<small>{latestComparison.exited_at ? new Date(latestComparison.exited_at).toLocaleString("vi-VN") : "Chưa có thời gian ra"}</small></div></div> : <div className="comparison-empty">Chưa có lượt xe hoàn chỉnh để đối chiếu. Khi AI ghi nhận xe vào và ra cùng biển số, ảnh bằng chứng sẽ hiện ở đây.</div>}</section><section className="history-panel">
      <div className="history-head"><div><p className="eyebrow">LỊCH SỬ HỆ THỐNG</p><h2>Nhật ký kiểm soát</h2><p>Bấm vào một lượt để xem đúng ảnh và chi tiết lúc quét.</p></div><div className="history-total"><strong>{activeView === "history" ? historyData.total : events.length}</strong><span>{activeView === "history" ? "lượt phù hợp" : "lượt gần đây"}</span></div></div>
      <div className="history-filter"><label>Tìm biển số<input value={historyPlate} onChange={e => { setHistoryPlate(e.target.value); setHistoryPage(0); }} placeholder="Ví dụ: 43A123456" maxLength={30} /></label><label>Từ thời gian<input type="datetime-local" value={historyStart} onChange={e => { setHistoryStart(e.target.value); setHistoryPage(0); }} /></label><label>Đến thời gian<input type="datetime-local" value={historyEnd} onChange={e => { setHistoryEnd(e.target.value); setHistoryPage(0); }} /></label><button type="button" onClick={() => { setHistoryPlate(""); setHistoryStart(""); setHistoryEnd(""); setHistoryPage(0); }}>Xóa lọc</button><button type="button" onClick={() => setHistoryRefresh(value => value + 1)}>Tải lại</button></div>
      {activeView === "history" && historyBusy ? <p className="history-empty" role="status">Đang tải lịch sử…</p> : activeView === "history" && historyError ? <p className="history-empty" role="alert">{historyError}</p> : displayedEvents.length === 0 ? <div className="history-empty"><b>Chưa có lượt phù hợp</b><span>Thử tìm biển số khác hoặc thay đổi khoảng thời gian.</span></div> : <div className="history-table"><div className="history-columns"><span>Thời gian</span><span>Làn xe</span><span>Biển số</span><span>Kết quả</span><span>Ảnh & ghi chú</span></div>{displayedEvents.map(event => <button type="button" className="history-row event-detail-button" key={event.id} onClick={() => setSelectedEvent(event)} aria-label={`Xem lượt ${event.plate_number || "không biển số"} ${event.direction === "entry" ? "vào" : "ra"} lúc ${new Date(event.occurred_at).toLocaleString("vi-VN")}`}><time>{new Date(event.occurred_at).toLocaleString("vi-VN")}</time><span className={`direction ${event.direction}`}>{event.direction === "entry" ? "↘ Vào" : "↗ Ra"}</span><b>{event.plate_number || "Không có biển số"}</b><span className={`history-status ${event.decision}`}>{decisionLabel(event.decision)}</span><span className="history-note">{event.evidence_url ? <img src={`${BACKEND}${event.evidence_url}`} alt="Ảnh của lượt này" loading="lazy" /> : <small>Không có ảnh</small>}<span>{event.reason}<small className="view-event-hint">Xem chi tiết ↗</small></span></span></button>)}</div>}
      {activeView === "history" ? <div className="history-pagination"><span>{historyData.total ? `${historyPage * 20 + 1}–${Math.min((historyPage + 1) * 20, historyData.total)} / ${historyData.total} lượt` : "0 lượt"}</span><button type="button" className="secondary" disabled={historyBusy || historyPage === 0} onClick={() => setHistoryPage(page => page - 1)}>Trang trước</button><button type="button" className="secondary" disabled={historyBusy || (historyPage + 1) * 20 >= historyData.total} onClick={() => setHistoryPage(page => page + 1)}>Trang sau</button></div> : <button type="button" className="secondary all-history-button" onClick={() => setActiveView("history")}>Tra cứu toàn bộ nhật ký →</button>}
    </section>
    {selectedEvent && <dialog ref={evidenceDialog} className="evidence-dialog" aria-labelledby="event-detail-title" onCancel={() => setSelectedEvent(null)} onClick={e => { if (e.target === e.currentTarget) setSelectedEvent(null); }}><div className="event-detail"><header><div><p className="eyebrow">CHI TIẾT LƯỢT QUÉT</p><h2 id="event-detail-title">{selectedEvent.plate_number || "Không có biển số"} · {selectedEvent.direction === "entry" ? "Lối vào" : "Lối ra"}</h2></div><button type="button" className="secondary" autoFocus onClick={() => setSelectedEvent(null)}>Đóng ✕</button></header><p className="event-time">{new Date(selectedEvent.occurred_at).toLocaleString("vi-VN")} · <b>{decisionLabel(selectedEvent.decision)}</b></p>{selectedEvent.evidence_url && !photoError ? <img className="event-evidence-photo" src={`${BACKEND}${selectedEvent.evidence_url}`} alt={`Ảnh bằng chứng của lượt ${selectedEvent.id}`} onError={() => setPhotoError(true)} /> : <div className="event-no-photo">{photoError ? "Không tải được ảnh bằng chứng. Tệp có thể đã bị di chuyển hoặc xóa." : "Lượt này không có ảnh bằng chứng được lưu."}</div>}<p className="event-reason">{selectedEvent.reason}</p><footer><small>Mã lượt: {selectedEvent.id}</small>{selectedEvent.evidence_url && !photoError && <a href={`${BACKEND}${selectedEvent.evidence_url}`} target="_blank" rel="noreferrer">Mở ảnh gốc ↗</a>}</footer></div></dialog>}


  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
