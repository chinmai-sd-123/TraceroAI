import { defineConfig } from "@playwright/test";

// One smoke test of the production build: the public pages render, and the
// dashboard says so plainly when its API is down (instead of showing zeros).
// CI runs it against `next start` with an API address where nothing listens.

const PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    // Locally, use the installed Chrome; CI installs Playwright's Chromium.
    channel: process.env.CI ? undefined : "chrome",
  },
  webServer: {
    command: `npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      TRACEROAI_API_URL: "http://127.0.0.1:9", // nothing listens here
      NEXT_TELEMETRY_DISABLED: "1",
    },
  },
});
