import { defineConfig, devices } from "@playwright/test";

// The whole platform, started by deploy/compose.production.yaml with fake identity: requirement
// work and the knowledge portal behind one edge (ADR-0099). CI's deployment job runs this after
// the stack is up; nothing is started here.
const platformUrl = process.env.PLATFORM_URL ?? "http://127.0.0.1:8080";

export default defineConfig({
  testDir: "./platform-tests",
  timeout: 120_000,
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: platformUrl,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } },
  ],
});
