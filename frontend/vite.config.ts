import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

export default defineConfig(({ mode }) => ({
  // Use /static/ in production so index.html points to /static/assets/...
  base: mode === "production" ? "/static/" : "/",

  plugins: [
    react(),
    mode === "development" && componentTagger(),
  ].filter(Boolean),

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },

  // Dev server is only for local development; Azure won’t use this.
  server: {
    host: "::", // or "0.0.0.0"
    port: 8080,
  },

  // (optional) make the build explicit
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
}));
