# Playwright UI tests

End-to-end browser tests that drive a real Chromium against the running
Django app. Currently scoped to the DNS records tab-order behavior
(issue [#4804](https://github.com/cisagov/manage.get.gov/issues/4804)).

No host setup needed beyond `docker compose up` — Node, Chromium,
Xvfb, and the noVNC viewer all live inside the `playwright` service.

## Run

Same cadence as `./manage.py test`. With everything else in compose
already up:

```sh
docker compose exec playwright ./test_ui                     # headless
docker compose exec playwright ./test_ui --grep "Tab walks"  # filter
docker compose exec playwright ./test_ui --slow              # watch in slow-mo
docker compose exec playwright ./test_ui --headed            # watch normal speed
docker compose exec playwright ./test_ui --ui                # Playwright UI
docker compose exec playwright ./test_ui --debug             # step-through inspector
```

`--slow` is shorthand for `--headed --workers=1` plus slow-mo (default
1.2s between actions; override with `PWDEMO_MS=2000`).

## Watching tests run

Open this URL once in any browser tab (bookmark it):

[`http://localhost:7900/vnc.html?autoconnect=1&resize=scale`](http://localhost:7900/vnc.html?autoconnect=1&resize=scale)

The VNC stream is live continuously. Once the tab is open, any test
you run with `--slow`/`--headed`/`--ui`/`--debug` shows up in that
tab automatically — no need to re-open.

### Auto-open the viewer

If you don't want to keep the tab open, prefix `open` to the command:

```sh
open "http://localhost:7900/vnc.html?autoconnect=1&resize=scale" ; \
  docker compose exec playwright ./test_ui --slow
```

Or drop the prefix into a shell alias once and forget it:

```sh
# add to ~/.zshrc or ~/.bashrc
alias pw='open "http://localhost:7900/vnc.html?autoconnect=1&resize=scale";'
# then run tests like:
pw docker compose exec playwright ./test_ui --slow
```

Or use the bundled wrapper:

```sh
./scripts/test-ui.sh --slow
```

The wrapper takes the same flags as `./test_ui` and skips the
auto-open for headless runs.

## How it works

The `playwright` service is a long-running container alongside `app`
and `db`. On startup it boots an Xvfb virtual display, a window
manager, x11vnc, and websockify+noVNC, with port 7900 exposed for the
viewer.

When you `exec ./test_ui`, that script:

1. Waits for Django at `http://getgov-test:8080/health/`.
2. Hits the dev seed endpoint at `/api/v1/dev/playwright-seed` — that
   makes sure a known test user exists, that they own a domain with
   ≥ 2 DNS records, that the `dns_hosting` waffle flag is on, and
   creates a fresh login session in the database.
3. Runs `playwright test` with whatever flags you passed. A
   `globalSetup` step turns the session key into a `JSESSIONID` cookie
   so every test starts logged in.

The dev seed endpoint is only registered when `IS_PRODUCTION` is
False; production builds don't expose it.

### Why the URL is `getgov-test:8080`, not `app:8080`

Google owns the `.app` top-level domain and added it to Chrome's HSTS
preload list — Chrome refuses plain HTTP on any `.app` hostname. Our
service is named `app`. The playwright service aliases `app` to
`getgov-test` (and `getgov-test` is in `ALLOWED_HOSTS` for dev) to
sidestep it.

## What's tested

[`dns-tab-order.spec.mjs`](dns-tab-order.spec.mjs) covers the
acceptance criteria from #4804:

* Tab from Edit (form closed) → "More options" kebab.
* Click Edit → focus jumps to the form's first input.
* Tab through an open form: Name → Content → TTL → Comment → Cancel →
  Save → Delete → kebab.
* Shift+Tab walks the same sequence in reverse.
* Tab from kebab (form open) → next record's Edit.
* Shift+Tab from kebab (form open) → form Delete.
* Click Cancel → focus returns to Edit on the same row.
* Cancel + Tab from Edit → kebab. (Regression for the bug where focus
  was stranded inside the now-hidden form row.)

## When to update

* Template selectors changed → update
  [`dns-tab-order.spec.mjs`](dns-tab-order.spec.mjs). The selectors
  there match the ones the focus-routing JS uses
  (`registrar/assets/src/js/getgov/domain-dns-record-content.js`).
* Seed data needs to change → update
  [`registrar/management/commands/seed_playwright_session.py`](../../registrar/management/commands/seed_playwright_session.py).

## Files

* [`tests/playwright/dns-tab-order.spec.mjs`](dns-tab-order.spec.mjs)
  — the test suite.
* [`tests/playwright/global-setup.mjs`](global-setup.mjs) — turns the
  session key into a `JSESSIONID` cookie before tests start.
* [`playwright.config.mjs`](../../playwright.config.mjs) — Playwright
  config (baseURL, storageState, slow-mo wiring).
* [`playwright.Dockerfile`](../../playwright.Dockerfile) — image for
  the `playwright` service (node base + VNC + noVNC).
* [`scripts/playwright-vnc.sh`](../../scripts/playwright-vnc.sh) —
  long-running command for the service: starts Xvfb + VNC and idles.
* [`test_ui`](../../test_ui) — script you exec into the container to
  run the suite (handles `--slow`, seeds, runs `playwright test`).
* [`scripts/test-ui.sh`](../../scripts/test-ui.sh) — host-side
  wrapper that auto-opens the viewer URL.
* [`registrar/management/commands/seed_playwright_session.py`](../../registrar/management/commands/seed_playwright_session.py)
  — Django command that creates the test user/domain/records and a
  login session.
* [`registrar/views/dev_playwright.py`](../../registrar/views/dev_playwright.py)
  — dev-only HTTP endpoint that calls the seed command.
