const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

const modules = path.resolve(__dirname, '../../assets/src/js/getgov');
const alpine = fs.readFileSync(require.resolve('@alpinejs/csp/dist/cdn.min.js'), 'utf8');

async function openForm(page, initialType) {
    const types = ['', 'A', 'AAAA', 'CNAME', 'MX', 'PTR', 'TXT'];
    const options = types.map((type, index) =>
        `<option value="${type}" ${index === initialType ? 'selected' : ''}>${type || '- Select -'}</option>`
    ).join('');
    // Mirror the add form's Alpine directives; the application modules are loaded unchanged.
    const html = `<div x-data="{showFormId: 0, recordType: ${initialType}, openComments: []}">
        <div id="dnsrecords-form-container">
            <button id="add-dnsrecord-button">Add record</button>
            <form id="form-container">
                <select id="id_type" x-on:change="recordType = $event.target.selectedIndex">${options}</select>
                <template x-if="recordType !== 6 && recordType !== 4">
                    <div><input id="id_name"><input id="id_content"></div>
                </template>
                <template x-if="recordType === 4">
                    <div><input id="id_name"><input id="id_content"><input id="id_priority"></div>
                </template>
                <template x-if="recordType === 6">
                    <div><input id="id_name"><textarea id="id_content"></textarea></div>
                </template>
                <textarea id="id_comment"></textarea>
                <div id="dnsrecords-form-container-comment--status"></div>
            </form>
        </div>
        <button id="dns-record-type-modal-trigger">Open modal</button>
        <button id="cancel-add-dnsrecord-confirm">Cancel add</button>
        <button id="confirm-delete-record-button">Delete</button>
        <div class="usa-modal-overlay" id="domain-dns-record-type-switcher" hidden>
            <button class="js-confirm-button-dns-record-switcher">Discard changes</button>
            <button data-close-modal>Go back</button>
        </div>
    </div>`;

    await page.route('http://dns-regression.test/**', route => {
        const name = new URL(route.request().url()).pathname.slice(1);
        if (!name) return route.fulfill({ contentType: 'text/html', body: html });
        const file = path.join(modules, name.endsWith('.js') ? name : `${name}.js`);
        return route.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(file, 'utf8') });
    });
    await page.goto('http://dns-regression.test/');
    await page.addScriptTag({ content: alpine });
    await page.evaluate(async () => {
        const modal = document.getElementById('domain-dns-record-type-switcher');
        document.getElementById('dns-record-type-modal-trigger').onclick = () => { modal.hidden = false; };
        modal.querySelector('[data-close-modal]').onclick = () => { modal.hidden = true; };
        modal.onkeydown = event => { if (event.key === 'Escape') modal.hidden = true; };
        const { initDNSRecordCancelModal } = await import('/domain-dns-record-content.js');
        initDNSRecordCancelModal();
    });
    await expect(page.locator('#id_content')).toBeVisible();
}

for (const [from, to, key] of [[1, 'MX', 'm'], [4, 'A', 'a'], [6, 'MX', 'm'], [4, 'TXT', 't']]) {
    test(`preserves unsaved fields when switching from type ${from} to ${to}`, async ({ page }) => {
        await openForm(page, from);
        await page.locator('#id_content').fill('unsaved.example.org');
        // Keyboard input produces a trusted change event, as required by the application.
        await page.locator('#id_type').press(key);
        await expect(page.locator('.usa-modal-overlay')).toBeVisible();
        await expect(page.locator('#id_content')).toHaveValue('unsaved.example.org');
        await expect(page.locator('#id_type')).toHaveValue(from === 4 ? 'MX' : from === 6 ? 'TXT' : 'A');
        await page.getByRole('button', { name: 'Go back', exact: true }).click();
        await expect(page.locator('.usa-modal-overlay')).toBeHidden();
        await expect(page.locator('#id_content')).toHaveValue('unsaved.example.org');
    });
}

test('only discards MX fields after confirmation', async ({ page }) => {
    await openForm(page, 4);
    await page.locator('#id_priority').fill('10');
    await page.locator('#id_type').press('a');
    await expect(page.locator('.usa-modal-overlay')).toBeVisible();
    await page.getByRole('button', { name: 'Discard changes', exact: true }).click();
    await expect(page.locator('#id_type')).toHaveValue('A');
    await expect(page.locator('#id_priority')).toHaveCount(0);
    await expect(page.locator('#id_content')).toHaveValue('');
});

test('allows switching a blank form without confirmation', async ({ page }) => {
    await openForm(page, 1);
    await page.locator('#id_type').press('m');
    await expect(page.locator('#id_priority')).toBeVisible();
    await expect(page.locator('.usa-modal-overlay')).toBeHidden();
});

test('Escape preserves the original record type and entered values', async ({ page }) => {
    await openForm(page, 4);
    await page.locator('#id_content').fill('mail.example.org');
    await page.locator('#id_type').press('a');
    await expect(page.locator('.usa-modal-overlay')).toBeVisible();
    await page.getByRole('button', { name: 'Go back', exact: true }).press('Escape');
    await expect(page.locator('.usa-modal-overlay')).toBeHidden();
    await expect(page.locator('#id_type')).toHaveValue('MX');
    await expect(page.locator('#id_content')).toHaveValue('mail.example.org');
});

test('programmatic type updates still reach Alpine without opening the modal', async ({ page }) => {
    await openForm(page, 1);
    await page.locator('#id_type').evaluate(select => {
        select.value = 'MX';
        select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await expect(page.locator('#id_priority')).toBeVisible();
    await expect(page.locator('.usa-modal-overlay')).toBeHidden();
});
