import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  server: {
    host: '0.0.0.0',  // WSL에서 Windows 브라우저 접속 허용
    port: 5173,
    proxy: {
      // /api/xxx → 백엔드 /api/xxx  (rewrite 없이 그대로 전달)
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
      // 이미지/영상 정적파일
      "/storage": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
});

