// Playwright tests for DNS records tab order (#4804).
// Run: `docker compose exec playwright ./test_ui` (headless) or
//      `./test_ui --slow` / `--headed` / `--ui` to watch in the VNC viewer.

import { test, expect } from '@playwright/test';

const DOMAIN_ID = process.env.PLAYWRIGHT_DOMAIN_ID;
const RECORD_IDS = (process.env.PLAYWRIGHT_RECORD_IDS || '').split(',').filter(Boolean);
const [RECORD_A, RECORD_B] = RECORD_IDS;
const PAGE_PATH = `/domain/${DOMAIN_ID}/dns/records`;

// Helpers ─────────────────────────────────────────────────────────────────
const editBtn = (page, id) =>
    page.locator(`button[data-action="edit"][data-record-id="${id}"]`);
const cancelBtn = (page, id) =>
    page.locator(`button[data-action="form-cancel"][data-record-id="${id}"]`);
const formDelete = (page, id) =>
    page.locator(`a[data-action="form-delete"][data-record-id="${id}"]`);
const kebab = (page, id) =>
    page.locator(`button[aria-controls="more-actions-dnsrecord-${id}"]`);
const formField = (page, id, fieldName) =>
    page.locator(`#id_edit_${id}_${fieldName}`);

test.describe('DNS records tab order (#4804)', () => {
    test.beforeAll(() => {
        // Friendly failure if the suite was launched without the seed step
        // (e.g. someone ran `npx playwright test` directly).
        if (!DOMAIN_ID || RECORD_IDS.length < 2) {
            throw new Error(
                'PLAYWRIGHT_DOMAIN_ID / PLAYWRIGHT_RECORD_IDS missing — '
                + 'run via `docker compose exec playwright ./test_ui`.',
            );
        }
    });

    test.beforeEach(async ({ page }) => {
        await page.goto(PAGE_PATH);
        // Wait until Alpine + the bundle are ready before any keyboard input.
        await page.waitForFunction(() => Boolean(window.Alpine));
        await expect(editBtn(page, RECORD_A)).toBeVisible();
    });

    test('Tab from Edit (form closed) lands on More Actions', async ({ page }) => {
        await editBtn(page, RECORD_A).focus();
        await page.keyboard.press('Tab');
        await expect(kebab(page, RECORD_A)).toBeFocused();
    });

    test('clicking Edit moves focus to first form input', async ({ page }) => {
        await editBtn(page, RECORD_A).click();
        await expect(formField(page, RECORD_A, 'name')).toBeFocused();
    });

    test('Tab walks the open form: Name → Content → TTL → Comment → Cancel → Save → Delete → kebab', async ({ page }) => {
        await editBtn(page, RECORD_A).click();
        await expect(formField(page, RECORD_A, 'name')).toBeFocused();

        const stops = [
            formField(page, RECORD_A, 'content'),
            formField(page, RECORD_A, 'ttl'),
            formField(page, RECORD_A, 'comment'),
            cancelBtn(page, RECORD_A),
            page.locator(`#dnsrecord-edit-form-${RECORD_A} button[type="submit"]`),
            formDelete(page, RECORD_A),
            kebab(page, RECORD_A),
        ];

        for (const stop of stops) {
            await page.keyboard.press('Tab');
            await expect(stop).toBeFocused();
        }
    });

    test('Shift+Tab walks the open form in reverse: kebab → Delete → Save → Cancel → Comment → TTL → Content → Name → Edit', async ({ page }) => {
        await editBtn(page, RECORD_A).click();
        await expect(formField(page, RECORD_A, 'name')).toBeFocused();
        // Reach kebab the way a real user would: 7 forward Tabs from Name.
        for (let i = 0; i < 7; i++) await page.keyboard.press('Tab');
        await expect(kebab(page, RECORD_A)).toBeFocused();

        const reverseStops = [
            formDelete(page, RECORD_A),
            page.locator(`#dnsrecord-edit-form-${RECORD_A} button[type="submit"]`),
            cancelBtn(page, RECORD_A),
            formField(page, RECORD_A, 'comment'),
            formField(page, RECORD_A, 'ttl'),
            formField(page, RECORD_A, 'content'),
            formField(page, RECORD_A, 'name'),
            editBtn(page, RECORD_A),
        ];

        for (const stop of reverseStops) {
            await page.keyboard.press('Shift+Tab');
            await expect(stop).toBeFocused();
        }
    });

    test('Tab from kebab (form open) skips back into the form and lands on next record\'s Edit', async ({ page }) => {
        await editBtn(page, RECORD_A).click();
        await expect(formField(page, RECORD_A, 'name')).toBeFocused();
        await kebab(page, RECORD_A).focus();
        await page.keyboard.press('Tab');
        await expect(editBtn(page, RECORD_B)).toBeFocused();
    });

    test('Shift+Tab from kebab (form open) lands on form Delete (not Edit)', async ({ page }) => {
        await editBtn(page, RECORD_A).click();
        await expect(formField(page, RECORD_A, 'name')).toBeFocused();
        await kebab(page, RECORD_A).focus();
        await page.keyboard.press('Shift+Tab');
        await expect(formDelete(page, RECORD_A)).toBeFocused();
    });

    test('Shift+Tab from first form input lands on Edit', async ({ page }) => {
        await editBtn(page, RECORD_A).click();
        await expect(formField(page, RECORD_A, 'name')).toBeFocused();
        await page.keyboard.press('Shift+Tab');
        await expect(editBtn(page, RECORD_A)).toBeFocused();
    });

    test('clicking Cancel returns focus to the same row\'s Edit', async ({ page }) => {
        await editBtn(page, RECORD_A).click();
        await expect(formField(page, RECORD_A, 'name')).toBeFocused();
        await cancelBtn(page, RECORD_A).click();
        await expect(editBtn(page, RECORD_A)).toBeFocused();
    });

    test('Cancel + Tab from Edit lands on More Actions (regression)', async ({ page }) => {
        await editBtn(page, RECORD_A).click();
        await expect(formField(page, RECORD_A, 'name')).toBeFocused();
        await cancelBtn(page, RECORD_A).click();
        await expect(editBtn(page, RECORD_A)).toBeFocused();
        await page.keyboard.press('Tab');
        await expect(kebab(page, RECORD_A)).toBeFocused();
    });
});
