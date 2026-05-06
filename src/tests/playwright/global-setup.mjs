// Runs once before any test. Writes a JSESSIONID cookie to storageState
// so every browser context starts logged in. Env vars are set by `test_ui`
// after it calls the dev seed endpoint.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const STORAGE_PATH = path.join(here, '.auth-state.json');

export default async function globalSetup() {
    const sessionKey = process.env.PLAYWRIGHT_SESSION_KEY;
    const domainId = process.env.PLAYWRIGHT_DOMAIN_ID;
    if (!sessionKey || !domainId) {
        throw new Error(
            'PLAYWRIGHT_SESSION_KEY / PLAYWRIGHT_DOMAIN_ID not set — '
            + 'run via `docker compose exec playwright ./test_ui`.',
        );
    }

    // Cookie name is JSESSIONID (registrar overrides Django's default).
    // secure: false because the dev server speaks plain HTTP.
    const baseUrl = new URL(process.env.PLAYWRIGHT_BASE_URL || 'http://getgov-test:8080');
    const storageState = {
        cookies: [
            {
                name: 'JSESSIONID',
                value: sessionKey,
                domain: baseUrl.hostname,
                path: '/',
                httpOnly: true,
                secure: false,
                sameSite: 'Lax',
                expires: -1,
            },
        ],
        origins: [],
    };
    fs.writeFileSync(STORAGE_PATH, JSON.stringify(storageState, null, 2));
}

export { STORAGE_PATH };
