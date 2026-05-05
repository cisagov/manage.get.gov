// Playwright config — runs against the live Django app.
// baseURL: container uses `getgov-test` alias; host scripts override.
// PWDEMO=1 + PWDEMO_MS for slow-mo (npm run test:ui-demo).

import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const demoMode = !!process.env.PWDEMO;
const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://getgov-test:8080';

export default defineConfig({
    testDir: './tests/playwright',
    // Serialize in demo mode so slow-mo windows don't overlap.
    fullyParallel: !demoMode,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    reporter: 'list',
    globalSetup: path.join(here, 'tests/playwright/global-setup.mjs'),
    use: {
        baseURL,
        storageState: path.join(here, 'tests/playwright/.auth-state.json'),
        trace: 'retain-on-failure',
        launchOptions: demoMode
            ? { slowMo: parseInt(process.env.PWDEMO_MS || '400', 10) }
            : undefined,
    },
    projects: [
        { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    ],
});
