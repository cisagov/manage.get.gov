# E2E Regression Tests

Browser-level regression tests for manage.get.gov using [Playwright](https://playwright.dev/python/).

## Why Playwright?

- Real Chromium browser — tests what actual users see, including CSS, JS, and navigation
- Built-in auto-wait (no `time.sleep()` hacks)
- Works alongside Django's test suite without modifying it

## Auth bypass

Login.gov (OIDC) requires 2FA and cannot be automated locally. We use a **dev-only auto-login URL**
(`/dev-auto-login/`) that:

- Creates or reuses a test Django user for the requested persona
- Logs them in via Django's session auth
- Redirects to the target page

**Safety guarantees:**
- The view returns 404 unless `settings.ALLOW_AUTO_LOGIN = True`
- `ALLOW_AUTO_LOGIN` is forced to `False` if `IS_PRODUCTION = False`
- This protects it from being turned on in production, however, it also allows us to use the `ALLOW_AUTO_LOGIN` to gate some sandboxes from using this as well. For instance, if we don't want staging or product using e2e testing and messing with UAT testing items, we can turn `ALLOW_AUTO_LOGIN` off in that env. Meanwhile, IS_PRODUCTION will always remain false in any non prod env and shouldn't be altered.

## Setup

### 1. Start the app

```bash
cd src
docker compose up -d
```

### 2. Install Python test dependencies (on your laptop, outside Docker)

```bash
cd e2e
pip install -r requirements.txt
playwright install chromium
```

## Running the tests

### Run the entire suite

```bash
cd e2e
pytest -v
```

### Run a single file

```bash
pytest test_profile_page.py -v
```

### Watch mode (visible browser)

```bash
pytest -v --headed
```

### Slow motion (useful for debugging)

```bash
pytest -v --headed --slowmo 1000
```

## Output

- **Videos** — `e2e/videos/<test_name>.webm`, one per test, recorded regardless of pass/fail
- **Screenshots** — `e2e/screenshots/FAILED_<test_name>.png`, saved only on failure

## Test files

| File | Personas | Scenarios |
|---|---|---|
| `test_profile_page.py` | generic | Profile page loads, no OIDC redirect, accessibility scan, form save |
| `test_legacy_user.py` | legacy_user_1 | Full legacy experience: home, domain management, profile, domain request |
| `test_portfolio_user_basic.py` | portfolio_user_2 | Home, manage domain, org access blocked, profile |
| `test_portfolio_user_requester.py` | portfolio_user_requester_3 | Home, create domain request |
| `test_org_admin.py` | org_admin_4 | Home, org page, member management |
| `test_multi_portfolio.py` | multi_portfolio_admin_7 | Portfolio selector, switch portfolios, /your-organizations/ |
| `test_mixed_permissions.py` | mixed_permissions_6 | Org experience, legacy domain access |
| `test_navigation_footer.py` | portfolio_user_2, legacy_user_1, multi_portfolio_admin_7 | Header and footer link consistency |
| `test_permission_ui.py` | portfolio_user_2, portfolio_user_requester_3, org_admin_4 | Role-based control visibility |
| `test_session_management.py` | portfolio_user_requester_3, multi_portfolio_admin_7 | Session persistence, portfolio switch |
| `test_error_handling.py` | legacy_user_1, portfolio_user_2 | 403 errors, read-only org page, unauthenticated access |
| `test_django_admin.py` | django_admin_analyst_8 | Domain request workflow, search, filters, collapsible fieldsets |


