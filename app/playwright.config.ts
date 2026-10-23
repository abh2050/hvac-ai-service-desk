import { defineConfig } from '@playwright/test';

// End-to-end tests against the hosted Amplify app (Gate 5). Credentials come from SSM through
// scripts/e2e.sh and live only in environment variables.
export default defineConfig({
  testDir: './e2e',
  timeout: 15 * 60 * 1000,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: '../reports/gate-5-e2e/playwright-report.json' }]],
  use: {
    baseURL: process.env.APP_URL ?? 'https://main.du00v4uwlekbh.amplifyapp.com',
    viewport: { width: 1920, height: 1080 },
    // Recording mode (E2E_VIDEO=1) captures full 1080p footage for the brag video, with a short pause
    // between actions so the screen reads clearly. Test runs without it go at full speed.
    video: process.env.E2E_VIDEO === '1' ? { mode: 'on', size: { width: 1920, height: 1080 } } : 'off',
    launchOptions: { slowMo: process.env.E2E_VIDEO === '1' ? 400 : 0 },
    trace: 'retain-on-failure',
  },
  outputDir: '../reports/gate-5-e2e/artifacts',
});
