import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // During development the React app runs on :5173 and forwards /api to
    // FastAPI on :8000, so the browser still sees one origin (cookies and the
    // CSRF check behave exactly as in production, where FastAPI serves both).
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
