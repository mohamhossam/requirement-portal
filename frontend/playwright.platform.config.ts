import { defineConfig, devices } from "@playwright/test";

// Both portals, each started from its own manifest with fake identity and joined on the peer
// network (ADR-0104): requirement work's edge at PLATFORM_URL, the knowledge portal's at
// KNOWLEDGE_URL (platform-tests/platform.spec.ts reads it). CI's deployment job runs this after
// both are up; nothing is started here.
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
