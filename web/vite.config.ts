import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// `npm run dev` proxies /api to `python -m sim serve`. Point it elsewhere with
// SIM_API, e.g. SIM_API=http://127.0.0.1:8001 npm run dev
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    proxy: { "/api": process.env.SIM_API ?? "http://127.0.0.1:8000" },
  },
  test: {
    environment: "node",
  },
});
