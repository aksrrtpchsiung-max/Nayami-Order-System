import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const rootEnvDir = resolve(__dirname, "..");
  const env = loadEnv(mode, rootEnvDir, "");
  const frontendHost = env.FRONTEND_HOST || "127.0.0.1";
  const frontendPort = Number(env.FRONTEND_PORT || "5173");
  const backendHost = env.BACKEND_HOST || "127.0.0.1";
  const backendPort = env.BACKEND_PORT || "5000";
  const backendProxyTarget = env.VITE_BACKEND_PROXY_TARGET || `http://${backendHost}:${backendPort}`;

  return {
    envDir: rootEnvDir,
    plugins: [react()],
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/test/setup.ts"
    },
    server: {
      host: frontendHost,
      port: frontendPort,
      proxy: {
        "/api": {
          target: backendProxyTarget,
          changeOrigin: true
        }
      }
    }
  };
});
