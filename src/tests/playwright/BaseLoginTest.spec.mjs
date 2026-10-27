// Playwright tests for DNS records tab order (#4804).
// Run: `docker compose exec playwright ./test_ui` (headless) or
//      `./test_ui --slow` / `--headed` / `--ui` to watch in the VNC viewer.

import { test, expect } from '@playwright/test';

const PAGE_PATH = `/domains/`;
use: {
    storageState: process.env.STORAGE_PATH
}

// Helpers ─────────────────────────────────────────────────────────────────
const submitBtn = (page) =>
    page.locator(`button[name="button"]`);

test.describe('Base Login Test', () => {
    test.beforeEach(async ({ page }) => {
        
        
        await page.goto(PAGE_PATH)
        await expect(submitBtn(page)).toBeVisible();
    });

    test('Base Login Test', async ({ page }) => {
        await page.goto(PAGE_PATH)
    });
});