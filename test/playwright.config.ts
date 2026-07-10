import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for FinAlly. Tests run against the Docker container on port 8000
 * (started via docker-compose.test.yml with LLM_MOCK=true).
 * Override the target with BASE_URL.
 */
export default defineConfig({
  testDir: ".",
  testMatch: "e2e.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
