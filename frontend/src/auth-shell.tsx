import { ReactNode, useEffect, useState } from "react";
import { SCHOOL_NAME } from "./brand";
import "./auth-shell.css";

// Ảnh trường, đặt trong frontend/public/truong/. Thêm ảnh: chép tệp vào đó rồi thêm một dòng.
// Ảnh phủ kín khung; "focus" là điểm giữ lại khi phải cắt bớt mép. "whole": giữ trọn ảnh (tranh vẽ).
const PHOTOS: Array<{ src: string; alt: string; focus?: string; whole?: boolean }> = [
  { src: "/truong/cong-truong.jpg", alt: `Cổng ${SCHOOL_NAME}`, focus: "72% 60%" },
  { src: "/truong/toa-nha-co-hoa.jpg", alt: `Tòa nhà chính ${SCHOOL_NAME}`, focus: "45% 35%" },
  { src: "/truong/tot-nghiep.jpg", alt: "Sinh viên trong lễ tốt nghiệp", focus: "50% 45%" },
  { src: "/truong/ky-hoa-cong-truong.jpg", alt: "Ký họa cổng trường", whole: true },
];
const SLIDE_MS = 6000;

/** Dải đầu trang màu xanh của các màn trước khi đăng nhập. */
export function AuthHeader() {
  return <header className="auth-header">
    <img src="/logo-dau.png" alt="" width={62} height={62} />
    <div><b>{SCHOOL_NAME}</b><span>Đồ án tốt nghiệp · Hệ thống kiểm soát xe ra vào</span></div>
  </header>;
}

/** Trình chiếu ảnh: ảnh mới hiện dần đè lên ảnh cũ và phóng nhẹ, không nháy nền. */
function Slides() {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = window.setTimeout(() => setIndex((index + 1) % PHOTOS.length), SLIDE_MS);
    return () => window.clearTimeout(timer);
  }, [index]);
  const step = (by: number) => setIndex((index + by + PHOTOS.length) % PHOTOS.length);
  return <div className="auth-visual">
    {PHOTOS.map((photo, i) => <figure key={photo.src} className={`auth-slide${i === index ? " active" : ""}${photo.whole ? " whole" : ""}`} aria-hidden={i !== index} style={{ ["--photo" as string]: `url("${photo.src}")` }}>
      <img src={photo.src} alt={photo.alt} style={{ objectPosition: photo.focus }} />
    </figure>)}
    <button type="button" className="auth-arrow previous" aria-label="Ảnh trước" onClick={() => step(-1)}>‹</button>
    <button type="button" className="auth-arrow next" aria-label="Ảnh sau" onClick={() => step(1)}>›</button>
    <div className="auth-dots">{PHOTOS.map((photo, i) => <button type="button" key={photo.src} className={i === index ? "active" : ""} aria-label={`Ảnh ${i + 1}`} aria-current={i === index} onClick={() => setIndex(i)} />)}</div>
  </div>;
}

/** Khung chung: ảnh bên trái, ô đăng nhập bên phải. "tall": form dài, cần nhường chỗ sớm hơn trên màn thấp. */
export function AuthShell({ children, tall }: { children: ReactNode; tall?: boolean }) {
  return <div className="auth-page">
    <AuthHeader />
    <div className="auth-body">
      <Slides />
      <div className={tall ? "auth-panel tall" : "auth-panel"}>
        <img className="auth-banner" src="/truong/chao-mung.jpg" alt={`Chào mừng đến Trường ${SCHOOL_NAME}`} />
        <div className="auth-panel-main">
          <img className="auth-panel-logo" src="/logo-dau.png" alt={`Logo ${SCHOOL_NAME}`} />
          {children}
        </div>
        <footer className="auth-footer">Sản phẩm đồ án tốt nghiệp của sinh viên {SCHOOL_NAME}</footer>
      </div>
    </div>
  </div>;
}
