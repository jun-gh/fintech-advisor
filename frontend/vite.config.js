import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // Load shared single root .env (expose only VITE_* and non-secret APP_NAME)
  const env = loadEnv(mode, "..", ["VITE_", "APP_NAME"]);

  return {
    plugins: [react()],
    envDir: "..",
    define: {
      __APP_NAME__: JSON.stringify(env.APP_NAME || "FintechDemo"),
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
