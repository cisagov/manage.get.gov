// Playwright tests for DNS records tab order (#4804).
// Run: `docker compose exec playwright ./test_ui` (headless) or
//      `./test_ui --slow` / `--headed` / `--ui` to watch in the VNC viewer.

import { test, expect } from '@playwright/test';

const DOMAIN_ID = process.env.PLAYWRIGHT_DOMAIN_ID;
const RECORD_IDS = (process.env.PLAYWRIGHT_RECORD_IDS || '').split(',').filter(Boolean);
const SESSION_ID = process.env.PLAYWRIGHT_SESSION_KEY
const [RECORD_A, RECORD_B] = RECORD_IDS;
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
        const state = await page.context().storageState()
        console.log(JSON.stringify(state, null, 2))
        // Wait until Alpine + the bundle are ready before any keyboard input.
        await expect(submitBtn(page)).toBeVisible();
    });

    test('Base Login Test', async ({ page }) => {

        page.on('request', async (request) => {
            if (request.url().startsWith('http://getgov-test:8080')) {
                const headers = await request.allHeaders();


                console.log({
                    url: request.url(),
                    sendsJESSIONID: /(?:^|;\s*)JSESSIONID=/.test(
                        headers.cookie ?? ''
                    ),

                });
            }
        });

        page.on('response', response => {
            const status = response.status();

            if (status >= 300 && status < 400) {
                console.log({
                    status,
                    from: response.url(),
                    location: response.headers()['location'],
                });
            }
        })
        await page.goto(PAGE_PATH)
    });
});