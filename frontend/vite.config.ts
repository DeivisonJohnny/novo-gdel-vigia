import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const visao = process.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
const backend = process.env.VITE_AUTH_URL || "http://127.0.0.1:3000";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      "^/api/(auth|usuarios)": { target: backend, changeOrigin: false },
      "/api": { target: visao, changeOrigin: false },
    },
  },
  build: { chunkSizeWarningLimit: 900 },
});
