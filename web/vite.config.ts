import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// /api goes to the NBA service (`uvicorn api.app:app --port 8000`); without it the UI falls back to public/data.
const api = { "/api": process.env.MAINGAU_API ?? "http://localhost:8000" };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: api },
  preview: { proxy: api },
});
