// Mặc định gọi API qua proxy của Vite (cùng nguồn với trang web) để cookie đăng nhập
// hoạt động cả khi mở bằng localhost hay 127.0.0.1. VITE_API_URL chỉ cần khi API ở máy khác.
export const API: string = import.meta.env.VITE_API_URL || "/api/v1";
export const BACKEND = API.startsWith("http") ? new URL(API).origin : "";
export const UNAUTHORIZED_EVENT = "gate-unauthorized";
export const formatPlate = (plate: string) => plate.replace(/^(\d{2}[A-Z][A-Z0-9]?)(\d{3})(\d{2})$/, "$1-$2.$3").replace(/^(\d{2}[A-Z][A-Z0-9]?)(\d{4})$/, "$1-$2");

/** fetch kèm cookie phiên; hết phiên (401) thì báo cho màn hình đăng nhập. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(input, { ...init, credentials: "include" });
  if (response.status === 401) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  return response;
}

export async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return fallback;
  } catch { /* không phải JSON */ }
  return fallback;
}
