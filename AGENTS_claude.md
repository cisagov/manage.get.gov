# AGENTS.md

> Read this file before making changes. It is the shared brief for OpenAI Codex, GitHub Copilot, Cursor, Aider, Windsurf, and every other AGENTS.md-compatible tool. Claude Code reads `CLAUDE.md` in addition to this file.

---

## ⚠️ This is a government system — read first

`manage.get.gov` is operated by the **Cybersecurity and Infrastructure Security Agency (CISA)** within the U.S. Department of Homeland Security. It administers the public `.gov` top-level domain. Mistakes in this codebase can break a federal trust boundary, leak PII of government employees, or take down domain management for real U.S. government organizations.

**When uncertain, stop and ask.** Do not guess. Do not "best-effort" security-sensitive code. Open an issue or leave a clearly-marked `TODO(security):` comment instead.

---

## What This Repo Is

`manage.get.gov` is a Django-based domain name registrar for the U.S. `.gov` top-level domain. It is the public-facing application where U.S.-based government organizations (federal agencies, state and local governments, tribes, territories) request, manage, and renew `.gov` domains. It speaks to a backend **EPP (Extensible Provisioning Protocol)** registry, integrates with **Login.gov** for identity, **Cloudflare** for DNS, and **AWS S3** for document uploads, and is deployed to **cloud.gov** (a Cloud Foundry PaaS for federal agencies). CISA owns and operates it.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ (71.6% of repo), JavaScript (17.7%), HTML (8.6%), SCSS (1.3%) |
| Web framework | Django |
| Frontend | U.S. Web Design System (USWDS), Alpine.js for interactivity, Sass compiled via gulp |
| Auth | Login.gov via OIDC (`djangooidc`) |
| Database | PostgreSQL (RDS, brokered through cloud.gov) |
| State machines | `django-fsm` (see `docs/architecture/decisions/0015-use-django-fs.md`) |
| Feature flags | `django-waffle` ("Waffle flags") |
| External APIs | EPP registry, Cloudflare (DNS), AWS S3 |
| HTTP client / mocking | `httpx` + `respx` |
| Local dev | Docker Compose (services: `app`, `node`, `pa11y`, `owasp`) |
| Deploy target | Cloud Foundry on cloud.gov (app naming: `getgov-<sandbox>`) |
| Tests | Django test runner, pa11y-ci, OWASP ZAP |
| Python deps | Pipfile / Pipfile.lock |
| JS deps | package.json / package-lock.json |
| CI | GitHub Actions (`.github/workflows/`) |

---

## Repository Structure

Only paths AI tools usually touch. Full tree lives in the repo.

```
.
├── .github/
│   ├── workflows/
│   │   ├── test.yaml              # Runs Django tests + pa11y-ci + OWASP ZAP
│   │   └── deploy-sandbox.yaml    # Auto-deploys branches matching `initials/*`
│   ├── CODEOWNERS                 # Default reviewers per path
│   └── copilot-instructions.md    # GitHub Copilot custom instructions
├── docs/
│   ├── architecture/decisions/    # ADRs — read before changing load-bearing things
│   ├── developer/README.md        # Canonical local dev guide
│   ├── operations/runbooks/       # On-call procedures (e.g. rotate_application_secrets.md)
│   ├── django-admin/roles.md      # /admin role model
│   ├── product/                   # Product goals
│   └── research/                  # User research artifacts (treat as sensitive)
├── ops/                           # Cloud Foundry / deploy scripts
├── src/                           # All application code lives here
│   ├── docker-compose.yml         # Local dev orchestration
│   ├── manage.py                  # Django entry point
│   ├── Pipfile / Pipfile.lock     # Python deps (pipenv)
│   ├── package.json               # JS deps (gulp, USWDS)
│   ├── .env-example               # Template for local secrets — copy to .env, never commit .env
│   ├── .pa11yci                   # Accessibility scan URL list — add new pages here
│   └── registrar/                 # The Django app (there is only one)
│       ├── models/                # ORM models (incl. domain.py — has the available() check)
│       ├── views/                 # View functions and CBVs
│       ├── forms/                 # Django Forms + ModelForms
│       ├── templates/             # Server-rendered HTML (USWDS-based)
│       ├── assets/                # Source CSS, JS, images (compiled into public/)
│       ├── public/                # Compiled/served static assets — DO NOT hand-edit
│       ├── management/commands/   # Custom manage.py commands (e.g. load.py)
│       ├── migrations/            # Django migrations — never edit a merged one
│       ├── fixtures/              # JSON + fixtures_users.py (ADMINS / STAFF / ADDITIONAL_ALLOWED_EMAILS)
│       └── tests/                 # All tests live here, incl. common.py (less_console_noise, MockUserLogin)
├── CONTRIBUTING.md
└── README.md
```

---

## Development Environment

The entire stack runs in Docker. There is no supported host-Python workflow.

```bash
# One-time prereq: Docker Desktop (or equivalent)
# https://docs.docker.com/get-docker/

# Initial build (also after Pipfile or package.json changes)
cd src
docker compose build

# Run all services (app, node asset watcher, etc.)
docker compose up                # foreground, logs to terminal
docker compose up -d             # detached
docker compose logs -f           # tail logs when detached
docker compose down              # stop everything

# Local secrets
cp ./.env-example .env           # then fill in values from `cf env getgov-<your-sandbox>`
```

Application URL: **http://localhost:8080**

**Branch convention drives deploys.** Branches named `<initials>/<issue#>-<topic>` (e.g. `dg/4321-fix-dns-form`) are auto-deployed to a per-developer cloud.gov sandbox by `.github/workflows/deploy-sandbox.yaml` as soon as a PR exists. Do not push secrets, hardcoded tokens, or PII to such branches — they become reachable on the public internet.

---

## Testing

Tests must pass locally before opening a PR. CI re-runs them.

```bash
# Django test suite (inside the running app container)
docker compose exec app ./manage.py test

# Same, but surface DeprecationWarnings
docker compose exec app python -Wa ./manage.py test

# Run a single test module / class / method
docker compose exec app ./manage.py test registrar.tests.test_views
docker compose exec app ./manage.py test registrar.tests.test_views.DomainRequestViewTest.test_submit

# Linters
docker compose exec app ./manage.py lint

# Accessibility (pa11y-ci) — add any new public URL to src/.pa11yci first
docker compose run pa11y npm run pa11y-ci

# Security scan (OWASP ZAP)
docker compose run owasp
```

**Test conventions:**
- Tests live under `src/registrar/tests/`.
- Use the `less_console_noise` context manager (or `@less_console_noise_decorator`) from `registrar.tests.common` to silence expected error logs. Do not delete those logs at the source.
- To test behind login, temporarily add `"registrar.tests.common.MockUserLogin"` to `MIDDLEWARE` in `settings.py`. **Remove it before committing.**
- Mock external HTTP: use `respx` against `httpx`. For Cloudflare specifically, set `DNS_MOCK_EXTERNAL_APIS=True` in `.env` to route through the built-in `MockCloudflareService`. Special test domains: `exists.gov` for an existing zone, names starting with `error-400` / `error-403` / `error*` to force error responses.
- Never write tests that hit the real EPP registry, real Cloudflare, real Login.gov, or real S3.

---

## Database & Migrations

```bash
# Generate a new migration after changing a model
docker compose exec app ./manage.py makemigrations

# Apply migrations locally
docker compose exec app ./manage.py migrate

# Load fixtures (also runs automatically on container start)
docker compose exec app ./manage.py load
```

**Migration rules:**
- One logical change per migration. Name them descriptively (Django's auto-name is usually fine; rename if it's just `0123_auto_*`).
- **Never edit a migration that has already been merged to `main`.** Add a follow-up migration instead.
- Data migrations must be **reversible** (`RunPython(forwards, reverse=...)`) unless reversal is genuinely impossible — document why in the migration docstring.
- Schema changes touching production must consider zero-downtime: avoid renaming non-empty columns or dropping columns in the same deploy as code that reads them. Stage the rollout across two PRs when needed.
- After a migration affecting fixtures, also update `src/registrar/fixtures/`.

---

## Architecture Principles

These are load-bearing decisions. Read the relevant ADR in `docs/architecture/decisions/` before challenging any of them.

1. **Single Django app.** All domain logic lives in `registrar/`. Do not introduce a second app to "organize" things; use modules within `registrar/` instead.
2. **State transitions go through `django-fsm`.** Domain requests and domains have explicit FSM states. Do not mutate status fields directly — use the `@transition`-decorated methods. (ADR-0015)
3. **EPP is the system of record for registry data.** When local DB and EPP disagree, EPP wins. Reads should reconcile, not assume.
4. **Login.gov is the only identity provider.** No local password auth, no social login, no API keys for human users.
5. **USWDS first, custom CSS second.** Reach for a USWDS component before writing new CSS. Custom classes use BEM and live in `registrar/assets/sass/_theme/_uswds-theme-custom-styles.scss`.
6. **Feature-flag risky changes with Waffle.** New flows roll out behind a `Waffle flag` so they can be killed without a redeploy.
7. **No PII in logs, fixtures, or test data.** Use synthetic data. `igorville.gov`, `exists.gov`, and the like are the canonical test domains.
8. **The `/admin` site is for staff, not the public.** Access is gated on UUIDs added to `ADMINS` or `STAFF` in `src/registrar/fixtures/fixtures_users.py`. Never widen these lists in a PR you didn't write.

---

## Security Requirements

This is a government system handling sensitive data. The following are **hard rules**.

**Claude / Copilot / Codex / any AI tool must never:**

- Commit hardcoded credentials, tokens, API keys, EPP passwords, OIDC secrets, Cloudflare keys, or AWS keys. Use environment variables loaded from `.env` (local) or `cf env getgov-*` (deployed).
- Commit a real `.env` file, real session cookies, real JWTs, real production database dumps, or anything pulled from `getgov-stable`.
- Bypass `@login_required`, `@permission_required`, or `UserPassesTestMixin`. If a view is gated, it stays gated.
- Disable CSRF protection, `SECURE_*` settings, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, the CSP, or HSTS to make something "work locally."
- Use raw SQL with string interpolation or f-strings. Use the Django ORM, or `cursor.execute(sql, params)` with parameter binding. **No exceptions.**
- Pass `shell=True` to `subprocess.run`, `subprocess.Popen`, or `os.system`. Pass a list of arguments.
- Call `eval()`, `exec()`, `pickle.loads()`, `yaml.load()` (use `yaml.safe_load`), or `marshal.loads()` on any input that could come from a user, an HTTP request, an uploaded file, or an external API.
- Log email addresses, full names, phone numbers, mailing addresses, SSNs, EINs, UUIDs of users, session IDs, OIDC tokens, EPP passwords, or full request/response bodies. Use the structured logging fields that already redact.
- Expand the scope of a Login.gov token, an EPP credential, a Cloudflare API key, or an AWS IAM role. Minimum-privilege only.
- Reproduce content from `docs/research/` or anything tagged as user research in commit messages, PR descriptions, code comments, or templates. That material is excluded from the repo by policy (see `CONTRIBUTING.md`).
- Auto-fill or auto-submit forms with real personal data when generating examples or tests.

**When uncertain about a security implication, stop and ask the issue's assignee or post in `#getgov-dev` before writing code.**

---

## Pull Request Guidelines

- **Branch name:** `<initials>/<issue#>-<short-description>` — e.g. `dg/4321-fix-dns-form`. This is enforced socially and triggers sandbox auto-deploy.
- **One issue per PR.** Link the issue in the description (`Closes #4321`).
- **CI must be green** before requesting review: Django tests, lint, pa11y-ci, OWASP ZAP.
- **Add or update tests** for every behavior change. New view → new test. New model field → fixture + serializer test.
- **Run the full test suite locally**, not just the file you changed. State machine transitions cross modules.
- **Update `src/.pa11yci`** when adding a new public URL.
- **Update the relevant ADR or write a new one** when changing architecture (state machine, auth flow, registry interface).
- **Migrations:** keep them small, reversible, and named.
- **Merge, don't rebase.** History preservation is intentional (per `docs/developer/README.md`).
- **CODEOWNERS will be auto-requested** as reviewers based on paths touched.
- **No force-pushes to `main`.** Ever.

---

## What NOT To Do

Anti-patterns observed in this codebase. Do not reintroduce them.

- ❌ Editing files in `registrar/public/` directly. Edit `registrar/assets/` and let gulp recompile.
- ❌ Adding a second Django app to organize code. Use modules inside `registrar/`.
- ❌ Mutating `domain_request.status = "approved"` directly. Use the FSM transition method.
- ❌ Adding new login paths or auth backends. Login.gov OIDC is the only one.
- ❌ Calling Cloudflare, EPP, or S3 from a view directly. Go through the service layer; mock it in tests via `respx` or `DNS_MOCK_EXTERNAL_APIS`.
- ❌ Hardcoding a feature on by changing code in a view. Use a Waffle flag instead.
- ❌ Returning `True` from `Domain.available()` to "make local testing work" and forgetting to revert. This is documented in `docs/developer/README.md` as a local-only debugging trick — never commit it.
- ❌ Leaving `"registrar.tests.common.MockUserLogin"` in `MIDDLEWARE` after testing.
- ❌ Adding your own UUID to `ADMINS` in `fixtures_users.py` for production. That list is shared dev-only state.
- ❌ Committing screenshots, exports, or fixtures that contain real applicant data.
- ❌ Force-adding images outside `registrar/assets/img/registrar/` (the `.gitignore` rule for `/img/` exists for a reason).
- ❌ Using `print()` for debugging in committed code. Use `logger`.

---

## Key File References

| Purpose | Path |
|---|---|
| Local dev guide (canonical) | `docs/developer/README.md` |
| Architectural Decision Records | `docs/architecture/decisions/` |
| FSM ADR | `docs/architecture/decisions/0015-use-django-fs.md` |
| Operations runbooks | `docs/operations/runbooks/` |
| Secrets rotation runbook | `docs/operations/runbooks/rotate_application_secrets.md` |
| `/admin` role model | `docs/django-admin/roles.md` |
| Local orchestration | `src/docker-compose.yml` |
| Env var template | `src/.env-example` |
| Python deps | `src/Pipfile`, `src/Pipfile.lock` |
| JS deps | `src/package.json`, `src/package-lock.json` |
| Accessibility scan config | `src/.pa11yci` |
| Django entry point | `src/manage.py` |
| The Django app | `src/registrar/` |
| Domain model (incl. `available()`) | `src/registrar/models/domain.py` |
| `/admin` user fixtures | `src/registrar/fixtures/fixtures_users.py` |
| Fixture loader command | `src/registrar/management/commands/load.py` |
| Test helpers | `src/registrar/tests/common.py` |
| CI test workflow | `.github/workflows/test.yaml` |
| Sandbox deploy workflow | `.github/workflows/deploy-sandbox.yaml` |
| Code owners | `.github/CODEOWNERS` |
| Contribution policy | `CONTRIBUTING.md` |
