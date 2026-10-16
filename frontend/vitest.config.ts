import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  define: { "import.meta.env.VITE_API_BASE": JSON.stringify("http://localhost/api") },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    // Not pool: "vmThreads": it would cut the ~40% of the run spent creating
    // jsdom environments, but its VM context lacks WritableStream (breaking
    // msw) and makes window.top/location non-configurable (breaking the spies
    // in AuthProvider.test.tsx and ErrorBoundary.test.tsx).
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    coverage: {
      provider: "v8",
      reporter: ["text-summary", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/api/schema.d.ts", "src/main.tsx"],
      // Measured 2026-10-15 (`npm run test:coverage`): 82.85 / 76.19 / 74.55 / 85.91.
      // Floors sit just below so a real drop fails CI. Raise them as coverage
      // improves; never lower them.
      thresholds: { statements: 82, branches: 75, functions: 73, lines: 85 },
    },
  },
});
