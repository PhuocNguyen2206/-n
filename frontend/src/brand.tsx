export const SCHOOL_NAME = "Đại học Kiến trúc Đà Nẵng";

/** Logo trường đặt cạnh tiêu đề ở mọi màn hình. */
export function BrandLogo() {
  return <img className="brand-logo" src="/logo-dau.png" alt={`Logo ${SCHOOL_NAME}`} width={46} height={46} />;
}
