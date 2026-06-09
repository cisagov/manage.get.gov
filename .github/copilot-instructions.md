# Copilot Instructions for manage.get.gov

## Project overview

This repository is the **.gov domain registrar** — the Django web application through which U.S. government organizations request and manage `.gov` domains. It is a Django 5.2 app deployed on Cloud.gov (Cloud Foundry), backed by PostgreSQL, authenticating via Login.gov (OIDC), and communicating with a `.gov` EPP registry (fred-epplib).

All application source code lives under `src/`. Documentation lives under `docs/`.

---

## Repository layout

```
.github/           CI workflows, PR template, CODEOWNERS, copilot instructions
docs/              Developer docs, ADRs, operations runbooks, dev-practices
ops/               Cloud.gov / Cloud Foundry manifests and deploy scripts
src/               All application code (working directory for all commands)
  registrar/       Main Django app — models, views, templates, tests, admin, fixtures
  epplibwrapper/   Thin wrapper around the EPP registry client (fred-epplib)
  djangooidc/      Login.gov OIDC integration
  api/             Lightweight public REST endpoints (available, rdap, reports)
  manage.py        Django management entry point
  docker-compose.yml  Local dev: app (8080) + db (5432) + node + pa11y + owasp
  Dockerfile       Python 3.14 app image
  node.Dockerfile  Node image for USWDS Sass compilation
  Pipfile / Pipfile.lock  Python deps — always keep in sync with requirements.txt
  requirements.txt Pinned Python deps (keep in sync with Pipfile)
  package.json     Node deps: USWDS 3.8.1, pa11y-ci, sass, @uswds/compile
  pyproject.toml   Black (line-length=120) and mypy config
  mypy.ini         mypy Django plugin settings
  .flake8          max-line-length=120, max-complexity=10, migrations excluded
  .pa11yci         URLs scanned by pa11y-ci accessibility tool
  gulpfile.js      USWDS asset compilation tasks
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.14 |
| Framework | Django 5.2 |
| Database | PostgreSQL (psycopg2) |
| Authentication | Login.gov via OIDC (`src/djangooidc/`) |
| State machines | django-fsm on `Domain` and `DomainRequest` |
| Email | AWS SES via boto3 — `send_templated_email()` in `registrar/utility/email.py` |
| DNS hosting | Cloudflare API via `registrar/services/cloudflare_service.py` |
| Frontend | USWDS 3.8.1 + Sass; dynamic interactions via HTMX |
| Asset pipeline | `@uswds/compile` / gulp (compiled by `node` Docker service) |
| Deployment | Cloud.gov (Cloud Foundry), Docker |
| Audit log | django-auditlog — every key model calls `auditlog.register()` in `models/__init__.py` |
| Feature flags | django-waffle — custom `WaffleFlag` model (`WAFFLE_FLAG_MODEL = "registrar.WaffleFlag"`) |

---

## Local development

All work runs inside Docker. The `db` image pulls from Docker Hub on first run.

```bash
cd src
cp .env-example .env     # minimum: set DJANGO_SECRET_KEY=""  (any non-empty value works locally)
docker compose build
docker compose up         # app:8080, db:5432, node watcher
```

On startup, `docker-compose.yml` runs:
1. `python manage.py migrate`
2. `python manage.py createcachetable`
3. `python manage.py load`  — loads all fixtures (users, domains, domain requests, etc.)
4. `python manage.py runserver 0.0.0.0:8080`

The app is at `http://localhost:8080`. The EPP registry and Login.gov OIDC errors in startup logs are **expected** — they do not affect unit tests or most development tasks.

Non-secret env vars are set directly in `docker-compose.yml`. Secrets go in `src/.env` (gitignored). Only two are typically needed locally: `DJANGO_SECRET_KEY` and `DJANGO_SECRET_LOGIN_KEY`.

---

## Running tests

Tests require the `db` container, so either use `exec` against a running stack, or start one first.

```bash
cd src

# Preferred: exec into an already-running app container
docker compose up -d
docker compose exec app ./manage.py test
docker compose exec app ./manage.py test registrar.tests.test_models   # single module
docker compose exec app ./manage.py test registrar.tests.test_admin.DomainRequestAdminTest  # single class

# Without a running db (lint-only scenarios): --no-deps skips db
docker compose run --rm --no-deps app ./manage.py lint

# Full test run as CI does it (parallel):
docker compose run --rm app python manage.py test --parallel --verbosity 2
```

If you see `database "test_app" already exists`, type `yes` to let Django delete and recreate it. For non-interactive runs add `--noinput`.

The EPP `Connection refused` and `RSA key format is not supported` log lines at startup are expected — they do not indicate test failure.

---

## Linting

All four linters run inside Docker. Run them all at once via the `lint` management command:

```bash
cd src
docker compose exec app ./manage.py lint
```

Or individually:

```bash
docker compose exec app flake8 . --count --show-source --statistics
docker compose exec app black --check .
docker compose exec app mypy .
docker compose exec app bandit -r .
```

| Linter | Config |
|---|---|
| flake8 | `src/.flake8` — max-line-length=120, max-complexity=10, migrations excluded |
| black | `src/pyproject.toml` — line-length=120 |
| mypy | `src/mypy.ini` — Django plugin, strict_optional=True, ignore_missing_imports=True |
| bandit | `src/.bandit` — security scanning |

CI fails if any linter reports an error. Always lint before committing.

---

## Making database migrations

After any model change:

```bash
docker compose exec app ./manage.py makemigrations
docker compose exec app ./manage.py migrate
```

Verify CI won't complain:
```bash
docker compose run app ./manage.py makemigrations --check
```

Migrations live in `src/registrar/migrations/` and are auto-generated. Do not edit them manually. **PR titles that include a migration must be suffixed with ` - MIGRATION`.**

---

## Models (`src/registrar/models/`)

Every model extends `TimeStampedModel` (provides `created_at`, `updated_at`). All key models are registered with django-auditlog in `models/__init__.py`.

### Domain (`domain.py`)

Uses `django-fsm`. The `state` FSMField has these values:
- `UNKNOWN` — initial state, not yet in the EPP registry
- `DNS_NEEDED` — registered in EPP but no nameservers
- `READY` — nameservers set, active on the internet
- `ON_HOLD` — manually suspended by registrar staff
- `DELETED` — removed from the EPP registry

Transition methods: `activate_hold()`, `remove_hold()`, `expunge()`, `set_nameservers()`. **Never set `domain.state` directly — always call the transition method.**

`Domain.available(domain)` calls the EPP registry. Locally it will always fail with `Connection refused`. Work around this by temporarily making the method `return True` for local testing.

Domain properties (nameservers, expiration_date, etc.) are **lazily loaded** from the EPP registry on first access.

### DomainRequest (`domain_request.py`)

Uses `django-fsm`. The `status` FSMField has these values:
- `STARTED` → `SUBMITTED` → `IN_REVIEW` → `APPROVED`
- `IN_REVIEW` → `IN_REVIEW_OMB` (federal executive branch requests via OMB)
- `IN_REVIEW` / `APPROVED` → `ACTION_NEEDED`, `REJECTED`, `INELIGIBLE`
- Any active state → `WITHDRAWN`

Transition methods: `submit()`, `in_review()`, `in_review_omb()`, `action_needed()`, `approve()`, `reject()`, `reject_with_prejudice()`, `withdraw()`. Approving a request creates a `Domain`, `DomainInformation`, and `UserDomainRole` in one transaction.

### Other key models

| Model | Purpose |
|---|---|
| `DomainInformation` | Detailed org/contact info attached to an approved domain |
| `Portfolio` | Groups domains under an organization; enforced by `multiple_portfolios` waffle flag |
| `User` | Extends `AbstractUser`; `username` is the Login.gov UUID |
| `UserDomainRole` | RBAC join: user ↔ domain with role=`MANAGER` |
| `UserPortfolioPermission` | RBAC join: user ↔ portfolio with roles/permissions |
| `UserGroup` | Three Django groups: `cisa_analysts_group`, `omb_analysts_group`, `full_access_group` |
| `WaffleFlag` | Extends `AbstractUserFlag` — the model backing all waffle feature flags |
| `AllowedEmail` | Email allowlist used in non-production environments |
| `DnsRecord`, `DnsZone`, `DnsAccount` | DNS hosting models under `models/dns/` |

---

## Access control

### User roles

Three permission groups (defined in `UserGroup`):
- **`cisa_analysts_group`** — has `analyst_access_permission`; limited read/write in admin
- **`omb_analysts_group`** — can transition requests to `IN_REVIEW_OMB`
- **`full_access_group`** — has `full_access_permission`; full admin access

`is_staff` (Django's flag) gates access to `/admin`. Superusers are not used — `full_access_permission` is the top permission level.

### `@grant_access` decorator (`registrar/decorators.py`)

All views use this decorator instead of Django's built-in `@login_required`. Pass one or more permission constants:

```python
from registrar.decorators import grant_access, IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN

@grant_access(IS_DOMAIN_MANAGER, IS_STAFF_MANAGING_DOMAIN)
class DomainNameserversView(DomainFormBaseView):
    ...
```

Key constants: `IS_STAFF`, `IS_CISA_ANALYST`, `IS_OMB_ANALYST`, `IS_FULL_ACCESS`, `IS_DOMAIN_MANAGER`, `IS_DOMAIN_REQUEST_REQUESTER`, `IS_PORTFOLIO_MEMBER`, `HAS_PORTFOLIO_DOMAINS_ANY_PERM`, `HAS_PORTFOLIO_MEMBERS_EDIT`, and more. See `decorators.py` for the full list.

URL-level permission requirements are documented in `registrar/permissions.py` (`URL_PERMISSIONS` dict).

---

## EPP registry integration (`src/epplibwrapper/`)

Wraps `fred-epplib`. The singleton `CLIENT` is imported as `registry` in most callers:

```python
from epplibwrapper import CLIENT as registry, commands, RegistryError
```

All registry calls must be wrapped in `try/except RegistryError`. In local dev the registry is unavailable; this causes only log warnings, not application failures.

---

## Services (`src/registrar/services/`)

Business logic that spans multiple models lives here, not in views or models:

- `invitation_service.py` — creates/validates portfolio invitations and domain invitations
- `dns_host_service.py` — orchestrates DNS hosting operations
- `cloudflare_service.py` — Cloudflare API client for DNS hosting
- `mock_cloudflare_service.py` — test double for Cloudflare (enabled via `DNS_MOCK_EXTERNAL_APIS=True`)

---

## Feature flags (waffle)

Feature flags are checked with `flag_is_active(request, flag_name)` (when a request is available) or `flag_is_active_for_user(user, flag_name)` (no request). Both are in `registrar/utility/waffle.py`.

Active flags in the codebase:

| Flag name | Controls |
|---|---|
| `multiple_portfolios` | Allows users to belong to more than one Portfolio |
| `dns_hosting` | DNS hosting via Cloudflare (gated on `@waffle_flag("dns_hosting")`) |
| `domain_deletion` | Self-service domain deletion flow |
| `user_portfolio_permission_invitations` | Portfolio invitation workflow |
| `disable_email_sending` | Suppresses all outbound email |

Flags are managed via Django Admin (`/admin/registrar/waffleflag/`).

---

## Views (`src/registrar/views/`)

- Class-based views extend `DomainBaseView` or `DomainFormBaseView` for domain pages; `TemplateView` for general pages.
- **HTMX** is used for the DNS records UI (`DomainDNSRecordsView`): form submissions and updates use `hx-post`, `hx-target`, and `HX-TRIGGER` response headers.
- JSON views (`domains_json.py`, `domain_requests_json.py`, `portfolio_members_json.py`, etc.) power DataTables in the UI.
- `DomainRequestWizard` is a multi-step wizard using session storage; steps are defined as `Step` enum values in `registrar/utility/enums.py`.

### DB query timeouts

Long-running admin list views use `pg_timeouts` from `registrar/utility/db_timeouts.py`:

```python
from registrar.utility.db_timeouts import pg_timeouts

with pg_timeouts(statement_ms=5000):
    queryset = Domain.objects.filter(...)
```

---

## Admin interface (`src/registrar/admin.py`)

The admin is ~6000 lines and heavily customized. Key base classes:
- `AuditedAdmin` — base for all admin classes; logs changes
- `ListHeaderAdmin(AuditedAdmin, OrderableFieldsMixin)` — adds sortable list headers
- `ImportExportRegistrarModelAdmin(ImportExportModelAdmin)` — adds CSV import/export

Key admin classes: `DomainAdmin`, `DomainRequestAdmin` (most complex — handles FSM transitions and status emails), `MyUserAdmin`, `PortfolioAdmin`, `DomainInformationAdmin`.

To get access to `/admin`:
1. Log in via Login.gov (even on localhost, use the identity sandbox)
2. Note your UUID from the "not authorized" error message
3. Add your UUID to `ADMINS` (for `full_access_group`) or `STAFF` (for `cisa_analysts_group`) in `src/registrar/fixtures/fixtures_users.py`
4. Run `docker compose exec app ./manage.py load` to reload fixtures

---

## Templates and frontend

Templates use Django's template language with USWDS 3.8.1 components.

- `base.html` / `dashboard_base.html` — layout templates
- `domain_base.html` / `portfolio_base.html` — section-specific base templates
- Email templates live in `templates/emails/` as `.txt` files; subjects are separate `_subject.txt` files
- USWDS Sass lives in `registrar/assets/_theme/`; compiled output goes to `registrar/public/`
- Custom images go in `registrar/assets/img/registrar/` — **must be force-added to git** (`git add --force`) because `/img/` is in `.gitignore`
- The `node` Docker service auto-recompiles on asset changes. Run `npx gulp compile` manually if needed.
- CSS class naming follows BEM convention (aligned with USWDS)

---

## Writing tests

All test files are in `src/registrar/tests/`. Use `src/registrar/tests/common.py` for shared helpers:

| Helper | Purpose |
|---|---|
| `less_console_noise()` | Context manager — suppresses expected Django error output |
| `less_console_noise_decorator` | Decorator version of the above |
| `MockEppLib(TestCase)` | TestCase base class that mocks all EPP registry calls — use for any test touching `Domain` |
| `MockSESClient(Mock)` | Mock for AWS SES — use for any test that triggers email sending |
| `completed_domain_request(**kwargs)` | Factory that creates a fully-populated `DomainRequest` fixture |
| `create_superuser(**kwargs)` | Creates a user with `full_access_permission` |
| `create_user(**kwargs)` | Creates a basic user |
| `mock_user()` | Returns a simple `User` object |
| `MockUserLogin` | Middleware — bypasses Login.gov; add to `settings.MIDDLEWARE` for accessibility/security scans only, **never commit** |

Most domain-related tests inherit from `MockEppLib` to avoid real registry calls.

---

## Branch and PR conventions

- **Branch naming**: `initials/issue-number-description` (e.g., `ab/1234-fix-footer`). The `initials/` prefix triggers auto-deploy to a personal Cloud.gov sandbox when a PR exists.
- **Merge strategy**: Merge commits to main. Never rebase main.
- **PR title format**: `#issue_number: Descriptive name - [sandbox]`
  - Append ` - MIGRATION` if the PR contains a migration file.
- **PR size**: Keep PRs small and focused. Designer approval required for user-facing changes.

---

## Dependency management

When adding or updating Python packages:
1. Update `Pipfile`
2. Run `pipenv lock`
3. **Also update `requirements.txt`** — both files must stay in sync. The PR checklist requires this.

---

## Accessibility

Accessibility is a first-class requirement for this government application.

- New pages **must** be added to `src/.pa11yci` to be included in automated accessibility scanning
- Run pa11y locally: `docker compose run pa11y npm run pa11y-ci`
- All UI changes must pass the [accessibility checklist](../docs/dev-practices/code_review.md) (ANDI/WAVE, keyboard nav, NVDA/VoiceOver)
- Use the [ANDI browser extension](https://www.ssa.gov/accessibility/andi/help/install.html) for in-browser testing (disable CSP extension required)

---

## CI workflows (`.github/workflows/`)

Main workflow: `test.yaml` — runs on push/PR to `main`.

| Job | What it does |
|---|---|
| `python-linting` | flake8, black, mypy, bandit inside Docker |
| `python-test` | Django tests with `--parallel --verbosity 2` inside Docker |
| `django-migrations-complete` | `makemigrations --check` to ensure no unmade migrations |
| `pa11y-scan` | Injects `MockUserLogin` middleware, starts the stack, runs pa11y-ci |

Other workflows: `deploy-sandbox.yaml` (auto-deploy on personal branches), `deploy-stable.yaml`, `deploy-staging.yaml`, `migrate.yaml`, `reset-db.yaml`, `security-check.yaml` (OWASP ZAP).

**All CI jobs build the Docker image.** Changes to `Dockerfile` or `Pipfile.lock` affect every job.

---

## Environments

| Name | Description |
|---|---|
| `stable` | Production |
| `staging` | Pre-production |
| `development` | Integration/CI |
| `<initials>` sandbox | Per-developer, auto-deployed from personal branches |

Non-production environments enforce an email allowlist (`AllowedEmail` model). Add addresses via Django Admin or fixtures before expecting emails to be delivered.

---

## Common pitfalls and workarounds

| Situation | Action |
|---|---|
| `Domain.available()` fails locally with connection error | Temporarily change the method body to `return True` for manual local testing |
| EPP `Connection refused` / OIDC `RSA key format` errors in logs | Expected in local dev — not failures, just missing external service config |
| `database "test_app" already exists` prompt when running tests | Type `yes`; or pass `--noinput` for non-interactive runs |
| Stale test DB causes second error after accepting cleanup | Run `docker compose down` then re-start the stack cleanly |
| `db Pulling` hangs when running `docker compose run --rm app ...` | Use `--no-deps` to skip pulling the db image if it's not needed: `docker compose run --rm --no-deps app ./manage.py lint` |
| CSS changes not reflected | Wait for `node` watcher, or run `npx gulp compile` manually |
| Custom image not tracked by git | `git add --force <path>` (the `/img/` directory is gitignored) |
| Login time `Issued in the future` error | Re-sync system clock: `sudo sntp -sS time.nist.gov` |
| Can't access `/admin` | Add Login.gov UUID to `ADMINS` or `STAFF` in `fixtures_users.py`, then `./manage.py load` |
| Email not delivered in sandbox | Add address to `AllowedEmail` via Django Admin |

---

## Secrets

Never commit secrets. Only two are needed for most local tasks:

```
DJANGO_SECRET_KEY=""           # any non-empty string works locally
DJANGO_SECRET_LOGIN_KEY=""     # base64-encoded private key; required only for Login.gov auth flows
```

Put them in `src/.env` (copy from `src/.env-example`). AWS SES, S3, registry, and DNS credentials are optional for unit testing and most development work.
