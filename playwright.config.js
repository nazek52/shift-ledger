import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8014",
    viewport: { width: 1440, height: 1100 },
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `${process.env.PYTHON || "python"} scripts/browser_server.py`,
    url: "http://127.0.0.1:8014/health",
    reuseExistingServer: false,
  },
  reporter: "list",
});
