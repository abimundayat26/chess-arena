import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:3000",
    headless: true,
    channel: "chromium",
  },
  webServer: [
    {
      command: "uv run uvicorn backend.app:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/docs",
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: false,
      timeout: 30000,
    },
  ],
})
