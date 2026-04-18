import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@textflow/shared-types": path.resolve(__dirname, "../../packages/shared-types/src/index.ts")
    }
  },
  server: {
    port: 1420,
    strictPort: true
  }
});
