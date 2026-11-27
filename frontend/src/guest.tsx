import { ChangeEvent, forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { API, errorMessage, formatPlate } from "./api";
import "./guest.css";

type Lane = "face" | "plate";
type DemoResult = {
  faces: Array<{ box: number[]; confidence: number }>;
  plate_boxes: number[][];
  plate_text: string | null; plate_confidence: number | null; plate_source: "ocr" | "vlm" | null;
};
type Send = (photo: HTMLCanvasElement, lane: Lane) => Promise<DemoResult>;
type LaneResult = { busy: true } | { busy: false; data: DemoResult; image: string; seconds: number };
type LaneHandle = {
  start: (deviceId: string) => Promise<boolean>;
  grab: () => HTMLCanvasElement | null;
  recognize: (photo: HTMLCanvasElement) => Promise<void>;
  stop: () => void;
  isRunning: () => boolean;
};
const MAX_SIDE = 1600;
const LANES = {
  face: { step: "01", title: "Camera khuôn mặt", empty: "Đặt camera ngang khuôn mặt, hoặc chọn một ảnh có người" },
  plate: { step: "02", title: "Camera biển số", empty: "Hướng camera vào biển số xe, hoặc chọn một ảnh biển số" },
};

/** Ảnh đã gửi kèm khung khuôn mặt (xanh dương) hoặc khung biển số (xanh lá). */
function annotate(photo: HTMLCanvasElement, data: DemoResult, lane: Lane) {
  const canvas = toCanvas(photo, photo.width, photo.height);
  const context = canvas.getContext("2d")!;
  context.lineWidth = Math.max(2, Math.round(canvas.width / 300));
  context.strokeStyle = lane === "face" ? "#3b82f6" : "#22c55e";
  const boxes = lane === "face" ? data.faces.map(face => face.box) : data.plate_boxes;
  boxes.forEach(([left, top, right, bottom]) => context.strokeRect(left, top, right - left, bottom - top));
  return canvas.toDataURL("image/jpeg", 0.85);
}

/** Vẽ ảnh hoặc khung hình camera lên canvas, thu nhỏ cạnh dài về tối đa MAX_SIDE. */
function toCanvas(source: CanvasImageSource, width: number, height: number) {
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext("2d")!.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas;
}

const cameraError = (error: unknown) => {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError") return "Trình duyệt đang chặn camera. Hãy cho phép quyền Camera rồi thử lại, hoặc bấm Chọn ảnh.";
  if (name === "NotReadableError") return "Không mở được camera. Đóng ứng dụng khác đang dùng camera rồi thử lại.";
  return "Không mở được camera. Bạn vẫn có thể bấm Chọn ảnh.";
};

type LaneProps = { lane: Lane; devices: MediaDeviceInfo[]; deviceId: string; onDevice: (id: string) => void; onOpened: () => void; send: Send; onResult: (result: LaneResult | undefined) => void };

const LanePanel = forwardRef<LaneHandle, LaneProps>(function LanePanel({ lane, devices, deviceId, onDevice, onOpened, send, onResult }, ref) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const release = () => { streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null; };
  const stop = () => { release(); setCameraOn(false); };
  useEffect(() => release, []);

  const start = async (id: string) => {
    setMessage("");
    stop();
    try {
      // Chưa biết thiết bị nào thì ưu tiên camera trước cho khuôn mặt, camera sau cho biển số.
      const video: MediaTrackConstraints = { width: { ideal: 1280 }, height: { ideal: 720 }, ...(id ? { deviceId: { exact: id } } : { facingMode: lane === "face" ? "user" : "environment" }) };
      const stream = await navigator.mediaDevices.getUserMedia({ video, audio: false });
      streamRef.current = stream;
      setCameraOn(true);
      const element = videoRef.current!;
      element.srcObject = stream;
      await element.play();
      onOpened();
      return true;
    } catch (error) {
      stop();
      setMessage(cameraError(error));
      return false;
    }
  };

  const grab = () => {
    const video = videoRef.current;
    return streamRef.current && video?.videoWidth ? toCanvas(video, video.videoWidth, video.videoHeight) : null;
  };

  const recognize = async (photo: HTMLCanvasElement) => {
    setBusy(true); setMessage(""); onResult({ busy: true });
    const started = performance.now();
    try {
      const data = await send(photo, lane);
      onResult({ busy: false, data, image: annotate(photo, data, lane), seconds: (performance.now() - started) / 1000 });
    } catch (error) {
      onResult(undefined);
      setMessage(error instanceof TypeError ? "Mất kết nối tới máy chủ. Vui lòng thử lại." : error instanceof Error ? error.message : "Không nhận diện được ảnh này");
    } finally { setBusy(false); }
  };

  useImperativeHandle(ref, () => ({
    start, grab, recognize, stop,
    isRunning: () => !!streamRef.current?.getVideoTracks().some(track => track.readyState === "live" && !track.muted),
  }));

  const chooseFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    stop();
    try {
      const bitmap = await createImageBitmap(file);
      const photo = toCanvas(bitmap, bitmap.width, bitmap.height);
      bitmap.close();
      await recognize(photo);
    } catch { setMessage("Trình duyệt không đọc được ảnh này. Hãy chọn ảnh JPG hoặc PNG."); }
  };

  const info = LANES[lane];
  return <section className="guest-lane" aria-label={info.title}>
    <h2><span>{info.step}</span>{info.title}</h2>
    {devices.length > 1 && <select aria-label={`Chọn thiết bị cho ${info.title.toLowerCase()}`} value={deviceId} disabled={busy} onChange={event => { onDevice(event.target.value); if (cameraOn) start(event.target.value); }}>
      <option value="">Camera mặc định</option>
      {devices.map((device, index) => <option key={device.deviceId} value={device.deviceId}>{device.label || `Camera ${index + 1}`}</option>)}
    </select>}
    <div className="guest-feed">
      <video ref={videoRef} autoPlay muted playsInline hidden={!cameraOn} />
      {!cameraOn && <p>{info.empty}</p>}
    </div>
    <div className="guest-actions">
      {!cameraOn
        ? <button type="button" disabled={busy} onClick={() => start(deviceId)}>Bật camera</button>
        : <>
          <button type="button" disabled={busy} onClick={() => { const photo = grab(); if (photo) recognize(photo); }}>Chụp</button>
          <button type="button" className="secondary" onClick={stop}>Tắt</button>
        </>}
      <label className="guest-file">Chọn ảnh<input type="file" accept="image/*" disabled={busy} onChange={chooseFile} /></label>
    </div>
    {busy && <p role="status">Đang nhận diện…</p>}
    {message && <p className="form-message error" role="alert">{message}</p>}
  </section>;
});

const plateSource = (data: DemoResult) => data.plate_source === "vlm" ? "Đọc bằng VLM Qwen2.5-VL"
  : `Đọc bằng YOLOv8${data.plate_confidence == null ? "" : ` · tin cậy ${Math.round(data.plate_confidence * 100)}%`}`;

/** Ô kết quả chung của hai camera, luôn hiện để khách biết kết quả sẽ nằm ở đâu. */
function ResultBoard({ face, plate }: { face?: LaneResult; plate?: LaneResult }) {
  const faceDone = face && !face.busy ? face : undefined;
  const plateDone = plate && !plate.busy ? plate : undefined;
  const hasFace = !!faceDone?.data.faces.length;
  const hasPlate = !!plateDone?.data.plate_text;
  const [tone, title] = face?.busy || plate?.busy ? ["scan", "Đang nhận diện…"]
    : hasFace && hasPlate ? ["allow", "Đã nhận diện được khuôn mặt và biển số"]
    : hasFace ? ["wait", plateDone ? "Có khuôn mặt, chưa đọc được biển số" : "Có khuôn mặt, còn thiếu ảnh biển số"]
    : hasPlate ? ["wait", faceDone ? "Có biển số, không thấy khuôn mặt" : "Có biển số, còn thiếu ảnh khuôn mặt"]
    : faceDone || plateDone ? ["block", "Chưa nhận diện được, hãy chụp lại"]
    : ["idle", "Chưa có kết quả. Bật camera rồi bấm Chụp, hoặc chọn ảnh."];
  return <section className={`guest-board ${tone}`} aria-label="Kết quả nhận diện" aria-live="polite">
    <div className="guest-board-title"><small>KẾT QUẢ</small><strong>{title}</strong></div>
    <div className="guest-board-items">
      <div className="guest-item">
        {faceDone ? <img src={faceDone.image} alt="Ảnh khuôn mặt vừa nhận diện" /> : <span className="guest-thumb">{face?.busy ? "…" : "Ảnh khuôn mặt"}</span>}
        <div><small>KHUÔN MẶT</small><b>{faceDone ? (hasFace ? `${faceDone.data.faces.length} khuôn mặt` : "Không thấy") : "—"}</b>{faceDone && <span>Xử lý {faceDone.seconds.toFixed(1)} giây</span>}</div>
      </div>
      <div className="guest-item">
        {plateDone ? <img src={plateDone.image} alt="Ảnh biển số vừa nhận diện" /> : <span className="guest-thumb">{plate?.busy ? "…" : "Ảnh biển số"}</span>}
        <div><small>BIỂN SỐ</small><b className="guest-plate">{plateDone ? (hasPlate ? formatPlate(plateDone.data.plate_text!) : "Không đọc được") : "—"}</b>{plateDone && <span>{hasPlate ? `${plateSource(plateDone.data)} · ` : ""}{plateDone.seconds.toFixed(1)} giây</span>}</div>
      </div>
    </div>
  </section>;
}

export function GuestScreen({ onBack }: { onBack: () => void }) {
  const faceRef = useRef<LaneHandle>(null);
  const plateRef = useRef<LaneHandle>(null);
  const queueRef = useRef<Promise<unknown>>(Promise.resolve());
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [faceDevice, setFaceDevice] = useState("");
  const [plateDevice, setPlateDevice] = useState("");
  const [starting, setStarting] = useState(false);
  const [note, setNote] = useState("");
  const [results, setResults] = useState<Partial<Record<Lane, LaneResult>>>({});
  const boardRef = useRef<HTMLDivElement>(null);
  const showResult = (lane: Lane) => (result: LaneResult | undefined) => {
    setResults(previous => ({ ...previous, [lane]: result }));
    // Trên màn hình nhỏ ô kết quả có thể đã cuộn khuất: đưa nó vào tầm nhìn khi bắt đầu nhận diện.
    if (result?.busy) boardRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };

  const listCameras = async () => {
    const found = (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === "videoinput" && device.deviceId);
    setDevices(found);
    return found;
  };

  // Máy chủ chỉ nhận mỗi lúc một ảnh của khách, nên hai ô gửi lần lượt.
  const send: Send = (photo, lane) => {
    const task = async (): Promise<DemoResult> => {
      const blob = await new Promise<Blob | null>(resolve => photo.toBlob(resolve, "image/jpeg", 0.92));
      if (!blob) throw new Error("Không đọc được ảnh");
      const form = new FormData();
      form.append("image", blob, `${lane}.jpg`);
      form.append("lane", lane);
      const response = await fetch(`${API}/demo/analyze`, { method: "POST", body: form });
      if (!response.ok) throw new Error(await errorMessage(response, "Không nhận diện được ảnh này"));
      return response.json();
    };
    const run = queueRef.current.then(task, task);
    queueRef.current = run.catch(() => undefined);
    return run;
  };

  const startBoth = async () => {
    setStarting(true); setNote("");
    try {
      // Trình duyệt chỉ trả tên thiết bị sau khi được phép dùng camera: xin quyền trước rồi mới liệt kê.
      const probe = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      probe.getTracks().forEach(track => track.stop());
      const found = await listCameras();
      const known = (id: string) => found.some(device => device.deviceId === id);
      const labelled = (pattern: RegExp) => found.find(device => pattern.test(device.label))?.deviceId;
      const face = known(faceDevice) ? faceDevice : labelled(/front|trước/i) || found[0]?.deviceId || "";
      const plate = known(plateDevice) ? plateDevice : labelled(/back|rear|sau/i) || found.find(device => device.deviceId !== face)?.deviceId || face;
      setFaceDevice(face); setPlateDevice(plate);
      await faceRef.current!.start(face);
      await plateRef.current!.start(plate);
      await new Promise(resolve => window.setTimeout(resolve, 800));
      if (found.length < 2) setNote("Máy này chỉ có một camera nên hai ô dùng chung. Đưa khuôn mặt vào rồi bấm Chụp ở ô 01, đưa biển số vào rồi bấm Chụp ở ô 02.");
      else if (!faceRef.current!.isRunning()) { faceRef.current!.stop(); setNote("Thiết bị này chỉ mở được một camera mỗi lúc (thường gặp trên điện thoại). Hãy bật và chụp lần lượt từng ô."); }
    } catch (error) { setNote(cameraError(error)); }
    finally { setStarting(false); }
  };

  const captureBoth = () => {
    // Lấy khung hình của cả hai camera cùng một lúc rồi mới gửi đi.
    const frames = [faceRef, plateRef].map(lane => ({ lane: lane.current!, photo: lane.current!.grab() }));
    if (frames.every(frame => !frame.photo)) { setNote("Chưa có camera nào đang bật. Bấm Bật hai camera trước."); return; }
    setNote("");
    frames.forEach(frame => { if (frame.photo) frame.lane.recognize(frame.photo); });
  };

  const stopBoth = () => { faceRef.current?.stop(); plateRef.current?.stop(); setNote(""); };

  return <div className="guest-screen"><div className="guest-card">
    <header>
      <div className="brand"><div className="brand-mark">BV</div><div><p className="eyebrow">XEM THỬ</p><h1>Hệ thống quét camera</h1></div></div>
      <button type="button" className="secondary" onClick={onBack}>Đăng nhập</button>
    </header>
    <p>Hệ thống dùng hai camera: một cho <b>khuôn mặt</b>, một cho <b>biển số xe</b>. Ảnh chỉ dùng để nhận diện ngay lúc đó: hệ thống không lưu và không đối chiếu danh tính.</p>
    <div className="guest-actions">
      <button type="button" disabled={starting} onClick={startBoth}>{starting ? "Đang mở camera…" : "Bật hai camera"}</button>
      <button type="button" disabled={starting} onClick={captureBoth}>Chụp cả hai</button>
      <button type="button" className="secondary" disabled={starting} onClick={stopBoth}>Tắt camera</button>
    </div>
    {note && <p className="guest-note" role="status">{note}</p>}
    <div ref={boardRef}><ResultBoard face={results.face} plate={results.plate} /></div>
    <div className="guest-lanes">
      <LanePanel ref={faceRef} lane="face" devices={devices} deviceId={faceDevice} onDevice={setFaceDevice} onOpened={listCameras} send={send} onResult={showResult("face")} />
      <LanePanel ref={plateRef} lane="plate" devices={devices} deviceId={plateDevice} onDevice={setPlateDevice} onOpened={listCameras} send={send} onResult={showResult("plate")} />
    </div>
  </div></div>;
}
