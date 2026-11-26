import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API chạy ở cổng 8000; trình duyệt chỉ nói chuyện với Vite nên cookie đăng nhập là cùng nguồn.
// Docker đặt VITE_PROXY_TARGET=http://api:8000.
const target = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target, changeOrigin: true },
      "/evidence": { target, changeOrigin: true },
      "/training-data": { target, changeOrigin: true },
    },
  },
});
