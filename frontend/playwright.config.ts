import { defineConfig, devices } from "@playwright/test";

// Assumes the backend (http://localhost:8000) and the Vite dev server
// (http://localhost:5173) are already running, with an admin account created.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    {
      name: "mobile",
      use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 800 } },
    },
  ],
});
