import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { contentSecurityPolicy } from "./contentSecurityPolicy.ts";

const apiPort = process.env.SMOKE_API_PORT ?? "8000";

const apiProxy = {
  "/api": {
    target: `http://127.0.0.1:${apiPort}`,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ""),
  },
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [
      react(),
      tailwindcss(),
      contentSecurityPolicy({
        apiBase: env.VITE_API_BASE,
        identityOrigins: env.CSP_IDENTITY_ORIGINS,
      }),
    ],
    server: { proxy: apiProxy },
    preview: { proxy: apiProxy },
  };
});
