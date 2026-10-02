import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  define: { "import.meta.env.VITE_API_BASE": JSON.stringify("http://localhost/api") },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    coverage: {
      provider: "v8",
      reporter: ["text-summary", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/api/schema.d.ts", "src/main.tsx"],
      // Measured 2026-09-29 (`npm run test:coverage`): 80.56 / 73.7 / 71.24 / 83.56.
      // Floors sit just below so a real drop fails CI. Raise them as coverage
      // improves; never lower them.
      thresholds: { statements: 80, branches: 73, functions: 70, lines: 83 },
    },
  },
});
