import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { contentSecurityPolicy } from "./contentSecurityPolicy.ts";
import { runtimeConfig } from "./runtimeConfig.ts";

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
  // The web image's build: the deployment's values are filled in when its
  // container starts (deploy/web/render-index.sh), not baked in here.
  const runtime = env.WEB_RUNTIME_CONFIG === "true";
  return {
    plugins: [
      react(),
      tailwindcss(),
      contentSecurityPolicy({
        apiBase: env.VITE_API_BASE,
        identityOrigins: env.CSP_IDENTITY_ORIGINS,
        runtimeIdentityOrigins: runtime,
      }),
      runtimeConfig(runtime),
    ],
    server: { proxy: apiProxy },
    preview: { proxy: apiProxy },
  };
});
