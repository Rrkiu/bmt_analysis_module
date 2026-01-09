import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
