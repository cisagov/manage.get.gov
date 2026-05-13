# AGENTS.md

> Read this file before making changes. It is the shared brief for OpenAI Codex, GitHub Copilot, Cursor, Aider, Windsurf, and every other AGENTS.md-compatible tool. Claude Code reads `CLAUDE.md` in addition to this file. Pair this with `AI_USAGE_POLICY.md` (governs *how* AI tools may be used) and this file (governs *what* the resulting code must look like).

---

## This is a government system — read first

`manage.get.gov` is operated by the **Cybersecurity and Infrastructure Security Agency (CISA)** within the U.S. Department of Homeland Security. It administers the public `.gov` top-level domain. Mistakes in this codebase can break a federal trust boundary, leak PII of government employees, or take down domain management for real U.S. government organizations.

**When uncertain, stop and ask.** Do not guess. Do not "best-effort" security-sensitive code. Open an issue or leave a clearly-marked `TODO(security):` comment instead.

---

## What This Repo Is

`manage.get.gov` is a Django-based domain name registrar for the U.S. `.gov` top-level domain. It is the public-facing application where U.S.-based government organizations (federal agencies, state and local governments, tribes, territories) request, manage, and renew `.gov` domains. It speaks to a backend **EPP (Extensible Provisioning Protocol)** registry as the system of record, integrates with **Login.gov** for identity, **Cloudflare** for DNS, and **AWS S3/SES** for document uploads and outbound mail, and is deployed to **cloud.gov** (a Cloud Foundry PaaS for federal agencies). CISA owns and operates it.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+, JavaScript, HTML, SCSS |
| Web framework | Django 4.2.x |
| Frontend | U.S. Web Design System (USWDS), HTMX + Alpine.js for dynamic interactions, Sass compiled via gulp |
| Auth | Login.gov via OIDC (`djangooidc`) |
| User model | Custom `registrar.User` (`AUTH_USER_MODEL = "registrar.User"`) |
| Database | PostgreSQL (RDS, brokered through cloud.gov) |
| State machines | `django-fsm` (see `docs/architecture/decisions/0015-use-django-fs.md`) |
| Feature flags | `django-waffle` |
| Audit history | `django-auditlog` |
| External APIs | EPP registry, Cloudflare (DNS), AWS S3, AWS SES |
| HTTP client / mocking | `httpx` + `respx` |
| Local dev | Docker Compose (services: `app`, `db`, `node`, `pa11y`, `owasp`) |
| Deploy target | Cloud Foundry on cloud.gov (app naming: `getgov-<sandbox>`) |
| Backend tests | Django test runner |
| Accessibility | pa11y-ci (automated), ANDI (manual) |
| Static analysis / security | Black, Flake8, Mypy, Bandit |
| Dynamic scan | OWASP ZAP baseline |
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
│   │   ├── test.yaml              # Django tests + pa11y-ci + OWASP ZAP + lint/security
│   │   └── deploy-sandbox.yaml    # Auto-deploys branches matching `initials/*`
│   ├── CODEOWNERS                 # Default reviewers per path
│   └── copilot-instructions.md    # GitHub Copilot custom instructions
├── docs/
│   ├── architecture/decisions/    # ADRs — read before changing load-bearing things
│   ├── developer/README.md        # Canonical local dev guide
│   ├── operations/runbooks/       # On-call procedures (e.g. rotate_application_secrets.md)
│   ├── django-admin/roles.md      # /admin role model
│   ├── product/                   # Product goals
│   └── research/                  # User research artifacts (treat as sensitive — see CONTRIBUTING.md)
├── ops/
│   └── manifests/                 # Cloud Foundry / cloud.gov deploy manifests
├── src/                           # All application code lives here
│   ├── docker-compose.yml         # Local dev orchestration
│   ├── manage.py                  # Django entry point
│   ├── Pipfile / Pipfile.lock     # Python deps (pipenv)
│   ├── package.json               # JS deps (gulp, USWDS)
│   ├── .env-example               # Template for local secrets — copy to .env, never commit .env
│   ├── .pa11yci                   # Accessibility scan URL list — add new pages here
│   ├── api/                       # Internal/API Django app (lightweight; most logic lives in registrar/)
│   ├── djangooidc/                # Login.gov OIDC integration (Django app)
│   ├── epplibwrapper/             # Thin wrapper around the EPP registry client (Django app)
│   ├── requirements.txt           # Pinned Python deps; MUST stay in sync with Pipfile.lock
│   └── registrar/                 # The primary Django app — most product logic lives here
│       ├── config/settings.py     # Django settings, middleware, security headers, logging
│       ├── models/                # ORM models (incl. domain.py — has the available() check)
│       ├── views/                 # View functions and CBVs
│       ├── forms/                 # Django Forms + ModelForms
│       ├── templates/             # Server-rendered HTML (USWDS-based)
│       ├── assets/                # Source CSS, JS, images (compiled into public/)
│       ├── public/                # Compiled/served static assets — DO NOT hand-edit
│       ├── management/commands/   # Custom manage.py commands (e.g. load.py, lint)
│       ├── migrations/            # Django migrations — never edit a merged one
│       ├── fixtures/              # JSON + fixtures_users.py (ADMINS / STAFF / ADDITIONAL_ALLOWED_EMAILS)
│       └── tests/                 # All tests live here, incl. common.py (less_console_noise, MockUserLogin)
├── AI_USAGE_POLICY.md             # Acceptable AI tool use on this repo — read once per onboarding
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

# Run all services (app, db, node asset watcher, etc.)
docker compose up                # foreground, logs to terminal
docker compose up -d             # detached
docker compose logs -f           # tail logs when detached
docker compose down              # stop everything

# Local secrets
cp ./.env-example .env           # then fill in values from `cf env getgov-<your-sandbox>`
```

Application URL: **http://localhost:8080**

**Branch convention drives deploys.** Branches named `<initials>/<issue#>-<topic>` (e.g. `dg/4321-fix-dns-form`) are auto-deployed to a per-developer cloud.gov sandbox by `.github/workflows/deploy-sandbox.yaml` as soon as a PR exists. Do not push secrets, hardcoded tokens, or PII to such branches — they become reachable on the public internet.

Frontend asset rebuild (only when the `node` watcher isn't running):

```bash
cd src
docker compose run node npm install
docker compose run node npx gulp compile
docker compose run node npx gulp copyAssets
```

### Environments

| Name | Description |
| --- | --- |
| `stable` | Production |
| `staging` | Pre-production staging |
| `development` | Integration / dev environment |
| `getgov-<initials>` | Per-developer Cloud Foundry sandbox (auto-deployed from `<initials>/*` branches) |

Cloud Foundry manifests live in `ops/manifests/`. Non-prod environments use an email allowlist (`AllowedEmail` model in `src/registrar/models/allowed_email.py`) — outbound mail to addresses not on the allowlist is dropped in sandboxes. Add an entry via fixtures or `/admin` if you need delivery to test.

### OIDC clock-skew gotcha

If you see `ERROR [djangooidc.oidc:243] Issued in the future`, the host clock has drifted relative to Login.gov. Resync NTP (`sudo sntp -sS time.nist.gov` on macOS). Do not change the OIDC validator.

---

## Testing

Tests must pass locally before opening a PR. CI re-runs them.

```bash
# Django test suite (inside the running app container)
docker compose exec app ./manage.py test

# Same, parallel
docker compose run --rm app python manage.py test --parallel

# Surface DeprecationWarnings
docker compose exec app python -Wa ./manage.py test

# Run a single test module / class / method
docker compose exec app ./manage.py test registrar.tests.test_views
docker compose exec app ./manage.py test registrar.tests.test_views.DomainRequestViewTest.test_submit

# Migration completeness (CI runs both)
docker compose run --rm app ./manage.py makemigrations --dry-run --verbosity 3
docker compose run --rm app ./manage.py makemigrations --check

# Lint / format / type-check / static security
docker compose exec app ./manage.py lint
docker compose run --rm --no-deps app black --check .
docker compose run --rm --no-deps app flake8 .
docker compose run --rm --no-deps app mypy .
docker compose run --rm --no-deps app bandit -q -r .

# Accessibility (pa11y-ci) — add any new public URL to src/.pa11yci first
docker compose run pa11y npm run pa11y-ci

# Security scan (OWASP ZAP baseline)
docker compose run owasp
```

**Test conventions:**
- Tests live under `src/registrar/tests/`. Django test runner is the source of truth — do not depend on pytest-only features.
- Use `less_console_noise()` (or `@less_console_noise_decorator`) from `registrar.tests.common` to silence expected error logs. Do not delete the underlying log calls.
- To test behind login, temporarily add `"registrar.tests.common.MockUserLogin"` to `MIDDLEWARE` in `settings.py`. **Remove it before committing.**
- Mock external HTTP with `respx` against `httpx`. For Cloudflare specifically, set `DNS_MOCK_EXTERNAL_APIS=True` in `.env` to route through the built-in `MockCloudflareService`. Test domains: `exists.gov` for an existing zone, names starting with `error-400` / `error-403` / `error*` to force error responses.
- Tests must not hit the real EPP registry, real Cloudflare, real Login.gov, real S3, or real SES.

---

## Database & Migrations

```bash
# Generate a new migration after changing a model
docker compose exec app ./manage.py makemigrations

# Apply migrations locally
docker compose exec app ./manage.py migrate

# Load fixtures (also runs automatically on container start, alongside migrate and createcachetable)
docker compose exec app ./manage.py load
```

**Migration rules:**
- One logical change per migration. Name them descriptively. Rename Django's auto-named `0123_auto_*` files before merging.
- Once a migration is merged to `main`, treat it as immutable. Write a follow-up migration instead of editing it.
- Data migrations must be **reversible** (`RunPython(forwards, reverse=...)`) unless reversal is genuinely impossible — document why in the migration docstring. Keep them idempotent where practical so a rerun is safe.
- Schema changes touching production must consider zero-downtime: avoid renaming non-empty columns or dropping columns in the same deploy as code that reads them. Stage the rollout across two PRs when needed.
- Deployed migrations run as a **cloud.gov task** after the push, not by hand on the database. Never edit production data directly outside an approved runbook.
- After a migration affecting fixtures, also update `src/registrar/fixtures/`.

---

## Architecture Principles

These are load-bearing decisions. Read the relevant ADR in `docs/architecture/decisions/` before challenging any of them.

1. **Four Django apps; product logic lives in `registrar`.** The repo contains `registrar/` (primary — domain requests, domains, users, portfolios, admin), `api/` (lightweight internal API), `djangooidc/` (Login.gov OIDC integration), and `epplibwrapper/` (thin wrapper around the EPP registry client). Do not introduce a fifth app to "organize" `registrar/` business logic — use modules inside `registrar/` instead.
2. **State transitions go through `django-fsm`.** Domain requests and domains have explicit FSM states. Mutate status only via `@transition`-decorated methods (e.g. `domain_request.submit()`), never by direct attribute assignment. (ADR-0015)
3. **EPP is the system of record for registry data.** When local DB and EPP disagree, EPP wins. Reads should reconcile, not assume.
4. **Login.gov is the only identity provider.** No local password auth, no social login, no API keys for human users. `AUTH_USER_MODEL = "registrar.User"` stays.
5. **Login-required by default.** `LoginRequiredMiddleware` and `RestrictAccessMiddleware` enforce that routes need authentication unless explicitly opted out. Do not add public routes without an explicit reason, tests, and security review.
6. **Authorization is server-authoritative.** Analyst, admin, portfolio, requester, and domain-manager checks must run on the server. Templates, HTMX endpoints, and Alpine.js are presentation only — authorization happens before the view returns.
7. **`django-auditlog` covers audit-sensitive models.** Keep new audit-sensitive model changes covered by `auditlog` registration and by tests.
8. **USWDS first, custom CSS second.** Reach for a USWDS component before writing new CSS. Custom classes use BEM and live in `registrar/assets/sass/_theme/_uswds-theme-custom-styles.scss`. Preserve CSP nonce patterns and Django template autoescaping. Dynamic interactions use HTMX (`hx-get` / `hx-post` / `hx-target`) for partials and Alpine.js for client-side UX polish.
9. **Feature-flag risky changes with Waffle.** New flows roll out behind a `Waffle flag` so they can be killed without a redeploy.
10. **External services live behind service boundaries.** EPP, Cloudflare/DNS, AWS S3/SES, and Login.gov calls are wrapped so they can be mocked in tests. Views do not call those clients directly.
11. **Synthetic data only.** No PII in logs, fixtures, or test data. `igorville.gov`, `exists.gov`, and the like are the canonical test domains.
12. **The `/admin` site is for staff, not the public.** Access is gated on UUIDs added to `ADMINS` or `STAFF` in `src/registrar/fixtures/fixtures_users.py`. Never widen these lists in a PR you didn't write.
13. **Use `transaction.atomic()` for multi-step writes** that must succeed or fail together (e.g., a domain status transition that also writes audit rows or external state).
14. **Models extend `TimeStampedModel`** (from `src/registrar/models/utility/time_stamped_model.py`), which provides `created_at` and `updated_at` automatically. New models should inherit from it rather than reinventing the timestamps.

---

## Security Requirements

This is a government system handling sensitive data. The following are **hard rules**. They apply identically to human-written and AI-generated code.

Contributors — and any AI tool used by a contributor — must never:

- Commit hardcoded credentials, tokens, API keys, EPP passwords, OIDC client secrets, Cloudflare keys, AWS keys, or Django `SECRET_KEY`s. Use environment variables loaded from `.env` (local) or `cf env getgov-*` (deployed).
- Commit a real `.env`, real session cookies, real JWTs, real production database dumps, real certificates, real private keys, or anything pulled from `getgov-stable` or any other production-equivalent environment.
- Bypass `@login_required`, `@permission_required`, `UserPassesTestMixin`, analyst/admin role checks, portfolio permissions, or domain-manager checks. If a view is gated, it stays gated.
- Remove or weaken `LoginRequiredMiddleware`, `RestrictAccessMiddleware`, CSRF middleware, CSP middleware, the `auditlog` middleware, or any other Django security middleware.
- Disable CSRF protection, `SECURE_*` settings, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, the CSP, or HSTS to make something "work locally."
- Add broad CSP exceptions (`unsafe-inline`, `unsafe-eval`, wildcard external origins) without security review. Do not remove CSP nonce or template autoescape patterns to solve a frontend bug.
- Use raw SQL with string interpolation, `%` formatting, or f-strings. Use the Django ORM, or `cursor.execute(sql, params)` with parameter binding.
- Pass `shell=True` to `subprocess.run`, `subprocess.Popen`, or `os.system`. Pass a list of arguments.
- Call `eval()`, `exec()`, `pickle.loads()`, `yaml.load()` (use `yaml.safe_load`), or `marshal.loads()` on any input that could come from a user, an HTTP request, an uploaded file, or an external API.
- Log email addresses, full names, phone numbers, mailing addresses, SSNs, EINs, UUIDs of users, session IDs, OIDC tokens, EPP credentials, or full request/response bodies. Use the structured logging fields that already redact.
- Expand the scope of a Login.gov token, an EPP credential, a Cloudflare API key, or an AWS IAM role. Minimum-privilege only.
- Reproduce content from `docs/research/` or anything tagged as user research in commit messages, PR descriptions, code comments, templates, or AI-tool conversations. That material is excluded from the repo by policy (see `CONTRIBUTING.md`).
- Commit vendor or procurement details, compliance documentation containing IP addresses, or generated local reports (e.g., ZAP HTML output) unless explicitly requested.
- Auto-fill or auto-submit forms with real personal data when generating examples or tests.
- Make tests depend on live EPP, Cloudflare/DNS, AWS, or Login.gov calls.

**When uncertain about a security implication, stop and ask the issue's assignee or the `@cisagov/dotgov` team through your standard channel before writing code.** See `AI_USAGE_POLICY.md` for the rules that govern AI-tool use itself.

---

## Pull Request Guidelines

- **Branch name:** `<initials>/<issue#>-<short-description>` — e.g. `dg/4321-fix-dns-form`. Enforced socially; triggers sandbox auto-deploy.
- **One issue per PR.** Link the issue in the description (`Closes #4321`).
- **CI must be green** before requesting review: Django tests, lint, Black, Flake8, Mypy, Bandit, pa11y-ci, OWASP ZAP.
- **Add or update tests** for every behavior change. New view → new test. New model field → fixture + serializer/form test. Security-sensitive changes require Bandit clean and, where applicable, an OWASP ZAP check.
- **Run the full test suite locally**, not just the file you changed. State machine transitions cross modules.
- **Update `src/.pa11yci`** when adding a new public URL.
- **Update the relevant ADR or write a new one** when changing architecture (state machine, auth flow, registry interface, middleware ordering).
- **Migrations:** keep them small, reversible, and named.
- **Two merge rules, don't conflate them:**
  - **Bringing `main` into your feature branch:** merge, don't rebase (per `docs/developer/README.md` — history preservation is intentional).
  - **Landing a PR on `main`:** squash-and-merge (current team practice — recent commits land as `#issue: Title (#PR)`).
- **PR title format:** `#issue_number: Descriptive name ideally matching ticket name - [sandbox]`. Append `- MIGRATION` (preceded by a space) to the title when the PR includes a migration.
- **Dependency PRs must keep `src/requirements.txt` in sync with `Pipfile.lock`.** The PR checklist enforces this; CI will not.
- **CODEOWNERS will be auto-requested** as reviewers based on paths touched.
- **No force-pushes to `main`.** Ever.
- **No new production dependencies** without explicit justification and review.
- **AI-assisted PRs follow the same review bar** as fully human-authored PRs. See `AI_USAGE_POLICY.md` §7 for disclosure rules.

---

## What NOT To Do

Anti-patterns observed in this codebase. Do not reintroduce them.

- Editing files in `registrar/public/` directly. Edit `registrar/assets/` and let gulp recompile.
- Adding a second Django app to organize code. Use modules inside `registrar/`.
- Mutating `domain_request.status = "approved"` directly. Use the FSM transition method.
- Putting business-critical status transition logic only in templates or client-side JavaScript.
- Adding new login paths or auth backends. Login.gov OIDC is the only one.
- Calling Cloudflare, EPP, S3, or SES from a view directly. Go through the service layer; mock it in tests via `respx` or `DNS_MOCK_EXTERNAL_APIS`.
- Hardcoding a feature on by changing code in a view. Use a Waffle flag instead.
- Returning `True` from `Domain.available()` to "make local testing work" and forgetting to revert. This is documented in `docs/developer/README.md` as a local-only debugging trick — never commit it.
- Leaving `"registrar.tests.common.MockUserLogin"` in `MIDDLEWARE` after testing.
- Adding your own UUID to `ADMINS` in `fixtures_users.py` for production. That list is shared dev-only state.
- Committing screenshots, exports, or fixtures that contain real applicant data.
- Force-adding images outside `registrar/assets/img/registrar/` (the `.gitignore` rule for `/img/` exists for a reason).
- Using `print()` for debugging in committed code. Use `logger`.
- Weakening admin, analyst, portfolio, or domain-manager permissions to simplify a UI flow.
- Combining unrelated refactors with a feature or security change in one PR.

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
| Cloud.gov deploy manifests | `ops/manifests/` |
| Local orchestration | `src/docker-compose.yml` |
| Env var template | `src/.env-example` |
| Python deps | `src/Pipfile`, `src/Pipfile.lock` |
| JS deps | `src/package.json`, `src/package-lock.json` |
| Accessibility scan config | `src/.pa11yci` |
| Django entry point | `src/manage.py` |
| Django settings/security/auth | `src/registrar/config/settings.py` |
| Primary Django app | `src/registrar/` |
| Internal API app | `src/api/` |
| Domain model (incl. `available()`) | `src/registrar/models/domain.py` |
| `/admin` user fixtures | `src/registrar/fixtures/fixtures_users.py` |
| Fixture loader command | `src/registrar/management/commands/load.py` |
| Test helpers | `src/registrar/tests/common.py` |
| CI test workflow | `.github/workflows/test.yaml` |
| Sandbox deploy workflow | `.github/workflows/deploy-sandbox.yaml` |
| Code owners | `.github/CODEOWNERS` |
| Contribution policy | `CONTRIBUTING.md` |
| AI tool acceptable use | `AI_USAGE_POLICY.md` |
