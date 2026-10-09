import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const localPython = path.resolve(import.meta.dirname, "..", ".venv", "Scripts", "python.exe");
const smokePython = process.env.SMOKE_PYTHON ?? (process.platform === "win32" ? localPython : "python");
const apiPort = process.env.SMOKE_API_PORT ?? "8000";
const uiPort = process.env.SMOKE_UI_PORT ?? "4173";
const apiUrl = `http://127.0.0.1:${apiPort}`;
const uiUrl = `http://127.0.0.1:${uiPort}`;

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: uiUrl,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } },
    },
    {
      name: "responsive-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 740, height: 1000 } },
    },
  ],
  webServer: [
    {
      command:
        `"${smokePython}" -m uvicorn smb_requirement_agent.interfaces.api.main:app --host 127.0.0.1 --port ${apiPort}`,
      cwd: path.resolve(import.meta.dirname, ".."),
      url: `${apiUrl}/health`,
      reuseExistingServer: !process.env.CI,
      env: { ...process.env, PROVIDER_RATE_LIMIT_PER_MINUTE: "0", LLM_PROVIDER: "fake", PERSISTENCE_PROVIDER: "memory", IDENTITY_PROVIDER: "fake", ATTACHMENT_SCAN_MODE: "offline" },
      timeout: 120_000,
    },
    {
      command: `npm run preview -- --host 127.0.0.1 --port ${uiPort}`,
      cwd: import.meta.dirname,
      url: uiUrl,
      reuseExistingServer: !process.env.CI,
      env: { ...process.env, SMOKE_API_PORT: apiPort },
      timeout: 120_000,
    },
  ],
});
