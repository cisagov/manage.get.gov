# GitHub Copilot — Repository Instructions

> Commit this file to **`.github/copilot-instructions.md`** in the repository root.

These instructions apply to Copilot Chat, inline completions, the Copilot coding agent, and Copilot code review across this repository. They are written to be **self-contained** because Copilot Chat does not automatically read sibling instruction files (`AGENTS.md`, `CLAUDE.md`). For deeper background or per-team policy, see `AGENTS.md` and `AI_USAGE_POLICY.md` at the repo root.

> **This is a CISA / DHS government system** administering the U.S. `.gov` top-level domain. Security mistakes have real-world consequences. When uncertain, stop and ask in the PR or issue.

---

## Project Summary

`manage.get.gov` is a Django-based domain name registrar for the U.S. `.gov` TLD, operated by CISA (DHS). It authenticates users via Login.gov OIDC (custom user model `registrar.User`), talks to an EPP registry as the system of record, manages DNS through Cloudflare, sends mail through AWS SES, stores uploads in AWS S3, and is deployed to cloud.gov (Cloud Foundry). The repo has four Django apps:

- `src/registrar/` — primary; most product logic, models, views, forms, admin, fixtures, tests
- `src/api/` — lightweight internal API
- `src/djangooidc/` — Login.gov OIDC integration
- `src/epplibwrapper/` — thin wrapper around the EPP registry client (`fred-epplib`)

Application code lives under `src/`. Documentation lives under `docs/`.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.10+, JavaScript, SCSS |
| Framework | Django 4.2.x (apps: `registrar`, `api`, `djangooidc`, `epplibwrapper`) |
| Frontend | USWDS 3.x, HTMX + Alpine.js, Sass (gulp) |
| Auth | Login.gov OIDC (`djangooidc`); `AUTH_USER_MODEL = "registrar.User"` |
| Database | PostgreSQL (cloud.gov RDS broker) |
| State machines | `django-fsm` (Domain, DomainRequest) |
| Feature flags | `django-waffle` |
| Audit history | `django-auditlog` |
| Email | AWS SES (via boto3) |
| External APIs | EPP registry, Cloudflare, AWS S3, AWS SES |
| HTTP / mocking | `httpx` + `respx` |
| Asset pipeline | `@uswds/compile` / gulp |
| Local dev | Docker Compose |
| Deploy | Cloud Foundry on cloud.gov |
| Backend tests | Django test runner |
| Quality / static analysis | Black, Flake8, Mypy, Bandit |
| Accessibility | pa11y-ci |
| Dynamic security | OWASP ZAP baseline |

Linter configs: `src/.flake8` (max-line-length=120, migrations excluded), `src/pyproject.toml` (Black, line-length=120; Mypy options), `src/mypy.ini` (Mypy Django plugin), `src/.bandit` (Bandit).

---

## Repository Layout

```
.github/
  workflows/test.yaml            # CI: lint, tests, migration check, pa11y-ci
  workflows/deploy-sandbox.yaml  # Auto-deploys `<initials>/*` branches to cloud.gov
  CODEOWNERS                     # Path-based default reviewers
  copilot-instructions.md        # This file
docs/
  architecture/decisions/        # ADRs — required reading before architectural changes
  developer/README.md            # Canonical local dev guide
  developer/ai-tool-setup.md     # IDE setup for Copilot / Claude Code / Codex
  dev-practices/                 # Code review and accessibility standards
  operations/runbooks/           # On-call procedures
ops/manifests/                   # Cloud Foundry / cloud.gov deploy manifests
src/
  manage.py                      # Django entry point
  docker-compose.yml             # Local orchestration (app, db, node, pa11y, owasp)
  .env-example                   # Local secrets template — copy to .env, never commit .env
  .pa11yci                       # Accessibility scan URL list — add new pages here
  .flake8 / pyproject.toml / mypy.ini / .bandit   # Linter configs
  Pipfile, Pipfile.lock          # Python deps (pipenv)
  requirements.txt               # Pinned Python deps — MUST stay in sync with Pipfile.lock
  package.json                   # JS deps (gulp, USWDS, pa11y-ci, sass)
  api/                           # Internal API app
  djangooidc/                    # Login.gov OIDC integration app
  epplibwrapper/                 # EPP registry client wrapper app
  registrar/                     # Primary Django app
    config/settings.py           # Django settings, middleware, security headers, logging
    models/                      # Domain, DomainRequest, User, Portfolio, AllowedEmail, etc.
    models/utility/time_stamped_model.py  # Base class — all models inherit
    views/                       # Class- and function-based views (HTMX-aware)
    forms/                       # Django Forms / ModelForms
    templates/                   # USWDS-based server-rendered templates
    assets/                      # Source CSS, JS, images — compiled into public/
    public/                      # Compiled static assets — DO NOT hand-edit
    management/commands/         # Custom manage.py commands (load, lint, etc.)
    migrations/                  # Django migrations — immutable once merged
    fixtures/                    # JSON + fixtures_users.py (ADMINS / STAFF)
    tests/common.py              # Shared test helpers (less_console_noise, MockUserLogin)
AI_USAGE_POLICY.md               # Acceptable AI tool use on this repo
```

---

## Local Development

The entire stack runs in Docker. There is no supported host-Python workflow.

```bash
cd src
cp ./.env-example .env       # then fill in values from `cf env getgov-<your-sandbox>`
docker compose build
docker compose up            # foreground (or -d for detached, then `docker compose logs -f`)
```

App URL: **http://localhost:8080**

On startup, the `app` container automatically runs:

1. `python manage.py migrate`
2. `python manage.py createcachetable`
3. `python manage.py load` (loads all fixtures)
4. `runserver 0.0.0.0:8080`

The `node` service watches `registrar/assets/` and recompiles USWDS / Sass automatically. If you need to compile manually:

```bash
docker compose run node npm install
docker compose run node npx gulp compile
docker compose run node npx gulp copyAssets
```

**Branch naming auto-deploys.** Branches named `<initials>/<issue#>-<topic>` (e.g. `dg/4321-fix-dns-form`) deploy to a per-developer cloud.gov sandbox as soon as a PR exists. Do not push secrets, hardcoded tokens, or PII to such a branch — the sandbox is reachable on the public internet.

---

## Environments

| Name | Description |
| --- | --- |
| `stable` | Production |
| `staging` | Pre-production staging |
| `development` | Integration / dev environment |
| `getgov-<initials>` | Per-developer Cloud Foundry sandbox (auto-deployed from `<initials>/*` branches) |

Cloud Foundry manifests live in `ops/manifests/`. Non-prod environments use an email allowlist (`AllowedEmail` model). Outbound mail to addresses not on the allowlist is dropped — add an entry via fixtures or `/admin` if you need delivery in a sandbox.

---

## Coding Guidelines

### General

- Run app commands from `src/` through Docker Compose.
- Follow patterns in nearby files before introducing new ones.
- Keep changes small, scoped, and test-backed. Do not combine unrelated refactors with a feature or security change.
- Do not add new production dependencies without clear justification and human review.
- Prefer readable, explicit domain logic over clever abstractions.

### Python / Django

- Target Python 3.10+ and modern Django idioms. Use type hints on new public functions and methods (Mypy runs in CI).
- Stay inside the primary `registrar` app for product logic. The `api`, `djangooidc`, and `epplibwrapper` apps are scoped — do not move `registrar` business logic into them.
- New models extend `TimeStampedModel` (from `src/registrar/models/utility/time_stamped_model.py`) for automatic `created_at` / `updated_at`.
- Use the Django ORM. If you must drop to raw SQL, use `cursor.execute(sql, params)` with parameter binding — never f-strings, `%` formatting, or string concatenation into a SQL string.
- Keep business rules in models, forms, services, or management commands. Templates and client-side JavaScript are not authoritative.
- Use `transaction.atomic()` for multi-step writes that must succeed or fail together (FSM transition + audit row, etc.).
- Change domain or domain-request state through the `django-fsm` `@transition` method on the model, never by direct attribute assignment. Example: call `domain_request.submit()` rather than `domain_request.status = "submitted"`.
- Preserve `AUTH_USER_MODEL = "registrar.User"`. Do not introduce alternative user models or auth backends.
- Use `logger.<level>(...)` for diagnostics. Never `print()`. Never log PII (email, name, phone, address, real user UUID, OIDC token, EPP credential, session ID, full request body).
- Use Waffle flags for risky new behavior so it can be disabled without a redeploy.
- For settings that vary by environment, read from `os.environ` (validated in `settings.py`); never hardcode.
- Use `subprocess.run([...], shell=False)` — never `shell=True`.
- Never call `eval()`, `exec()`, `pickle.loads`, `yaml.load` (use `yaml.safe_load`), or `marshal.loads` on data that could originate from a request, an upload, or an external API.
- Register audit-sensitive models with `django-auditlog` and cover them in tests.

### Security (hard rules)

These rules apply identically to human-written and AI-generated code.

- **No hardcoded credentials, tokens, API keys, EPP passwords, OIDC secrets, Cloudflare keys, AWS keys, or Django `SECRET_KEY`s.** Pull from env vars (`.env` locally, `cf env getgov-*` in cloud.gov).
- **No real `.env`, real session cookies, real JWTs, real certificates, real private keys, or anything pulled from `getgov-stable`** in commits or PRs.
- **No bypassing of authentication or authorization.** `@login_required`, `@permission_required`, `UserPassesTestMixin`, analyst / admin role checks, portfolio permissions, and domain-manager checks all stay enforced.
- **No removing or weakening** of `LoginRequiredMiddleware`, `RestrictAccessMiddleware`, CSRF middleware, CSP middleware, `auditlog` middleware, or Django security middleware.
- **No disabling** of CSRF, CSP, HSTS, `SECURE_*` settings, or secure cookie flags to make something work locally.
- **No broad CSP exceptions** (`unsafe-inline`, `unsafe-eval`, wildcard external origins). Preserve CSP nonce and template autoescape patterns.
- **No expansion** of Login.gov, EPP, Cloudflare, or AWS credential scope beyond what the task requires.
- **No PII** in logs, fixtures, tests, commit messages, PR descriptions, or code comments. Use `igorville.gov` / `exists.gov` as test data.
- **No real production data** in screenshots, fixtures, or anywhere in the repo. Per `CONTRIBUTING.md`: vendor info, PII, user research, compliance docs containing IPs, and secrets of any kind are never committed.
- **No live external calls in tests.** Mocks only for EPP, Cloudflare / DNS, AWS, and Login.gov.

### Tests

- Place new tests under `src/registrar/tests/`.
- Use the Django test runner — no pytest-only features.
- Use `less_console_noise()` (or `@less_console_noise_decorator`) from `registrar.tests.common` to silence expected error output rather than deleting log calls.
- `MockUserLogin` middleware is a **temporary local-only** auth shim for pa11y / OWASP scans — never leave it in committed `MIDDLEWARE`.
- Mock external services with `respx` against `httpx`. For Cloudflare-touching tests set `DNS_MOCK_EXTERNAL_APIS=True` and use the sentinel domains (`exists.gov`, names starting with `error-400`, `error-403`, `error*`).
- Add or update tests for every behavior change. New view → new test. New model field → fixture + test coverage. New FSM state → transition tests.

### Common commands

```bash
cd src

# Tests
docker compose exec app ./manage.py test
docker compose run --rm app python manage.py test --parallel
docker compose exec app python -Wa ./manage.py test         # surface deprecation warnings
docker compose exec app ./manage.py test registrar.tests.test_views   # single module

# Migration completeness (CI runs both)
docker compose run --rm app ./manage.py makemigrations --dry-run --verbosity 3
docker compose run --rm app ./manage.py makemigrations --check

# Lint / format / type-check / static security
docker compose exec app ./manage.py lint
docker compose run --rm --no-deps app black --check .
docker compose run --rm --no-deps app flake8 .
docker compose run --rm --no-deps app mypy .
docker compose run --rm --no-deps app bandit -q -r .

# Accessibility / dynamic security
docker compose run pa11y npm run pa11y-ci
docker compose run owasp
```

CI (`.github/workflows/test.yaml`) runs four jobs: `python-linting`, `python-test`, `django-migrations-complete`, `pa11y-scan`. All build the Docker image, so changes to `Dockerfile` or `Pipfile.lock` affect every job.

### Frontend (USWDS / HTMX / Alpine.js / SCSS)

- Use a USWDS component before writing custom CSS. Custom classes follow BEM naming. Custom CSS lives in `src/registrar/assets/sass/_theme/_uswds-theme-custom-styles.scss`.
- Edit source files under `src/registrar/assets/`. Never edit `src/registrar/public/` directly — those are compiled outputs the `node` Docker service regenerates.
- Custom images go in `src/registrar/assets/img/registrar/`; the `/img/` `.gitignore` rule means they need `git add --force`.
- When adding a new public URL, append it to `src/.pa11yci` so the accessibility scan covers it.
- Keep validation server-side. HTMX is for dynamic partials (`hx-get`, `hx-post`, `hx-target`, `hx-trigger`) and Alpine.js is for UX polish — neither enforces rules.
- Preserve Django template autoescape and CSP nonces.

---

## Database & Migrations

```bash
# After changing a model
docker compose exec app ./manage.py makemigrations
docker compose exec app ./manage.py migrate
```

Rules:

- One logical change per migration. Rename Django's auto-named `0123_auto_*` files before merging.
- **Migrations are immutable once merged to `main`.** Write a follow-up migration; never edit a merged one.
- Data migrations are reversible (`RunPython(forwards, reverse=...)`) unless reversal is genuinely impossible — document why in the migration docstring. Keep them idempotent where practical.
- **Deployed migrations run as a cloud.gov task** after the push, not by hand. Never edit production data outside an approved runbook.
- **PR titles for any PR including a migration must append `- MIGRATION`** (preceded by a space) to the title — e.g. `#4321: Add expiration field to Domain - [dg] - MIGRATION`.
- After a migration affecting fixtures, also update `src/registrar/fixtures/`.

---

## External Services

- **EPP registry** — wrap calls in the service layer (`src/epplibwrapper/`). Interactions must be wrapped in `try / except RegistryError`. Tests mock the registry; never hit the real one. For local development the registry is not available — to bypass the availability check temporarily, set `Domain.available()` to `return True` (a documented local-only debugging trick — never commit it).
- **Cloudflare / DNS** — `httpx` + `respx`. Set `DNS_MOCK_EXTERNAL_APIS=True` in `.env` to route through `MockCloudflareService`. This flag is local / test only; never enable in production. Test domains: `exists.gov`, names starting with `error-400` / `error-403` / `error*`.
- **AWS S3 / SES** — brokered through cloud.gov; secrets via `cf env getgov-*`. Mock in tests.
- **Login.gov OIDC** — via `djangooidc`. If you see `ERROR [djangooidc.oidc:243] Issued in the future`, the host clock has drifted — resync NTP (`sudo sntp -sS time.nist.gov` on macOS); do not change the OIDC validator.

---

## Architectural Constraints

Hard rules. Do not suggest changes that violate these.

1. **Four Django apps: `registrar`, `api`, `djangooidc`, `epplibwrapper`.** Product logic lives in `registrar`. Do not introduce additional apps for `registrar` business logic — use modules inside `registrar/`.
2. **`django-fsm` owns state transitions.** Use `@transition`-decorated methods on the model (`domain_request.submit()`). Never `obj.status = "approved"`.
3. **EPP is the system of record** for registry data. On conflict, EPP wins.
4. **Login.gov OIDC is the only auth.** No local password auth, social login, or API keys for human users. `AUTH_USER_MODEL = "registrar.User"` stays.
5. **Login-required by default.** `LoginRequiredMiddleware` + `RestrictAccessMiddleware`. New public routes need an explicit reason, tests, and review.
6. **Authorization is server-authoritative.** Analyst, admin, portfolio, requester, and domain-manager checks run on the server, not in templates, HTMX endpoints, or Alpine.js.
7. **`django-auditlog` covers audit-sensitive models.** Keep registration and test coverage in sync.
8. **All models extend `TimeStampedModel`** for automatic `created_at` / `updated_at`.
9. **USWDS first.** Reach for an existing USWDS component before writing custom CSS or new components.
10. **Feature-flag risky changes with Waffle.** Code paths that aren't ready for everyone live behind a Waffle flag.
11. **Source assets live in `registrar/assets/`; compiled assets in `registrar/public/` are output only.**
12. **Migrations are immutable once merged.** Write a follow-up migration; never edit one on `main`. Deployed migrations run as a cloud.gov task.
13. **External services live behind service boundaries.** EPP, Cloudflare, AWS S3 / SES, and Login.gov calls are wrapped so they can be mocked in tests.
14. **Branches named `<initials>/<issue#>-<topic>` auto-deploy to a public cloud.gov sandbox** — never push secrets, real PII, or production data to such a branch.
15. **Two merge rules:** when bringing `main` into your feature branch, merge (don't rebase) per `docs/developer/README.md`. When landing a PR on `main`, squash-and-merge (current team practice).
16. **PR title format:** `#issue: Descriptive name - [sandbox]`. Append `- MIGRATION` (preceded by a space) when the PR includes a migration. Dependency PRs must update `src/requirements.txt` alongside `Pipfile.lock`.

---

## Common Errors and Workarounds

| Error | Workaround |
| --- | --- |
| `Issued in the future` (OIDC login fails) | Host clock has drifted. Resync NTP: `sudo sntp -sS time.nist.gov`. Do not change the OIDC validator. |
| Domain availability check fails locally | Temporarily set `Domain.available()` to `return True`. Local-only — never commit. |
| CSS changes not reflected | Wait for the `node` watcher, or run `docker compose run node npx gulp compile`. |
| Image not tracked by git | Use `git add --force <img-file>` (the `/img/` rule in `.gitignore` is intentional). |
| Tests print error noise that is not failures | Wrap the test code in `less_console_noise()` (context manager) or use `@less_console_noise_decorator`. |
| Can't access `/admin` locally or in your sandbox | Add your Login.gov UUID to `ADMINS` or `STAFF` in `src/registrar/fixtures/fixtures_users.py` and reload fixtures. |
| Email not sending in a sandbox | Add the destination address to the `AllowedEmail` model (fixtures or `/admin`). |

---

## What NOT To Do

Anti-patterns. Do not reintroduce them.

- Editing files in `src/registrar/public/` directly. Edit `src/registrar/assets/` and let gulp recompile.
- Mutating `domain_request.status = "approved"` directly. Use the FSM transition method.
- Putting business-critical status-transition logic only in templates or client-side JavaScript.
- Adding new login paths or auth backends. Login.gov OIDC is the only one.
- Calling Cloudflare, EPP, S3, or SES from a view directly. Go through the service layer; mock in tests.
- Hardcoding a feature on by changing code in a view. Use a Waffle flag.
- Returning `True` from `Domain.available()` to "make local testing work" and forgetting to revert.
- Leaving `"registrar.tests.common.MockUserLogin"` in `MIDDLEWARE` after testing.
- Adding your own UUID to `ADMINS` in `fixtures_users.py` for production. That list is shared dev-only state.
- Committing screenshots, exports, or fixtures that contain real applicant data.
- Using `print()` for debugging in committed code. Use `logger`.
- Weakening admin, analyst, portfolio, or domain-manager permissions to simplify a UI flow.
- Combining unrelated refactors with a feature or security change in one PR.

---

## Pull Request Expectations

- Branch name: `<initials>/<issue#>-<short-description>`.
- One issue per PR; link with `Closes #<issue>`.
- PR title format: `#issue: Descriptive name ideally matching ticket name - [sandbox]`. Append `- MIGRATION` (with leading space) when the PR includes a migration.
- CI must be green: Django tests, migration checks, Black, Flake8, Mypy, Bandit, `./manage.py lint`, pa11y-ci, OWASP ZAP.
- Add or update tests for behavior changes. New view → new test. New model field → fixture + test.
- Update `src/.pa11yci` when adding a new public URL.
- Update or write an ADR when changing architecture (state machine, auth flow, registry interface, middleware ordering).
- Dependency PRs must keep `src/requirements.txt` in sync with `Pipfile.lock`.
- Respect CODEOWNERS and request reviewers for touched areas.
- No force-pushes to `main`. Ever.
- AI-assisted PRs follow the same review bar and disclosure rules as human-authored PRs — see `AI_USAGE_POLICY.md` §7.

---

## Key Files

| Purpose | Path |
| --- | --- |
| Local dev guide | `docs/developer/README.md` |
| ADRs | `docs/architecture/decisions/` |
| FSM ADR | `docs/architecture/decisions/0015-use-django-fs.md` |
| Operations runbooks | `docs/operations/runbooks/` |
| Cloud.gov manifests | `ops/manifests/` |
| Local orchestration | `src/docker-compose.yml` |
| Env var template | `src/.env-example` |
| Django entry point | `src/manage.py` |
| Django settings | `src/registrar/config/settings.py` |
| Domain model | `src/registrar/models/domain.py` |
| Base model | `src/registrar/models/utility/time_stamped_model.py` |
| Email allowlist model | `src/registrar/models/allowed_email.py` |
| `/admin` user fixtures | `src/registrar/fixtures/fixtures_users.py` |
| Test helpers | `src/registrar/tests/common.py` |
| CI test workflow | `.github/workflows/test.yaml` |
| AI tool acceptable use | `AI_USAGE_POLICY.md` |
