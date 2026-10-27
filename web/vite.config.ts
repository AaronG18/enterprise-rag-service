import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Python server serves web/dist at the site root, so absolute asset paths are correct.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
  server: {
    port: 5174,
    proxy: {
      "/api": "http://127.0.0.1:8124",
    },
  },
});
