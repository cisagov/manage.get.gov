# AGENTS.md

## What This Repo Is

This repository contains the Django-based `.gov` registrar operated by CISA/dotgov for U.S.-based government organizations to request, manage, and operate `.gov` domains. This is a government or sensitive-data system. Security mistakes have real-world consequences. When uncertain, stop and ask.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Django 4.2.x |
| Database | PostgreSQL via `DATABASE_URL` |
| Auth | Login.gov / OpenID Connect via `djangooidc` |
| Frontend | Django templates, JavaScript, Sass, USWDS 3.x |
| Accessibility | pa11y-ci, ANDI for manual checks |
| Security scanning | Bandit, OWASP ZAP baseline scan |
| Quality | Black, Flake8, Mypy, Django tests |
| Feature flags | django-waffle |
| Audit/history | django-auditlog |
| Deployment | Docker Compose locally; Cloud.gov manifests under `ops/` |
| External integrations | EPP registry, AWS SES/S3, Cloudflare/DNS vendor APIs |

## Repository Structure

```text
.
├── README.md                         # Project overview and top-level repo context
├── CONTRIBUTING.md                   # Branch naming, project practices, commit exclusions
├── docs/
│   ├── developer/README.md           # Local setup, testing, assets, security/a11y scans
│   ├── operations/                   # Operations runbooks and deployment references
│   ├── architecture/decisions/       # ADRs; check before changing architecture
│   ├── product/                      # Product goals and context
│   └── research/                     # Research artifacts; avoid adding PII
├── ops/
│   └── manifests/                    # Cloud.gov deployment manifests
└── src/
    ├── manage.py                     # Django management entry point
    ├── Pipfile / Pipfile.lock        # Python dependencies
    ├── package.json                  # USWDS/Sass/JS tooling
    ├── docker-compose.yml            # Local app/db/node/pa11y/owasp services
    ├── .env-example                  # Local env var template
    ├── registrar/
    │   ├── config/settings.py        # Django settings, auth, security, logging
    │   ├── models/                   # Domain, request, user, DNS, portfolio models
    │   ├── views/                    # Django views
    │   ├── forms/                    # Django forms
    │   ├── templates/                # Django templates
    │   ├── assets/                   # Source assets: Sass, JS, images
    │   ├── public/                   # Compiled/static deployment assets
    │   ├── management/commands/      # Custom manage.py commands, including lint/load
    │   └── tests/                    # Test utilities and test cases
    └── api/                          # Internal/API Django app
```

## Development Environment

Use Docker Compose from `src/`.

```bash
cd src
cp ./.env-example .env
docker compose build
docker compose up
```

The local app runs at:

```text
http://localhost:8080
```

Run detached and follow logs:

```bash
cd src
docker compose up -d
docker compose logs -f
```

Run a shell inside the app container:

```bash
cd src
docker compose exec app bash
```

Compile/copy frontend assets when needed:

```bash
cd src
docker compose run node npm install
docker compose run node npx gulp compile
docker compose run node npx gulp copyAssets
```

During normal `docker compose up`, the `node` service watches `registrar/assets` and recompiles USWDS/Sass assets.

Secrets belong in `src/.env` or Cloud.gov user-provided services. Do not commit `.env`.

## Testing

Primary CI-equivalent checks:

```bash
cd src
docker compose run --rm app python manage.py test --parallel
docker compose run --rm app ./manage.py makemigrations --dry-run --verbosity 3
docker compose run --rm app ./manage.py makemigrations --check
```

Lint/security/type checks:

```bash
cd src
docker compose run --rm --no-deps app flake8 .
docker compose run --rm --no-deps app black --check .
docker compose run --rm --no-deps app mypy .
docker compose run --rm --no-deps app bandit -q -r .
```

Repository helper command:

```bash
cd src
docker compose exec app ./manage.py lint
```

Accessibility scan:

```bash
cd src
docker compose run pa11y npm run pa11y-ci
```

OWASP ZAP baseline scan:

```bash
cd src
docker compose run owasp
```

Testing notes:

- Django tests are the source of truth for backend behavior.
- Use existing test helpers in `registrar.tests.common` when testing authenticated paths.
- `MockUserLogin` may be inserted for local pa11y/ZAP scanning only; remove it after testing.
- External DNS vendor APIs use `httpx` and `respx` boundaries. Prefer service-level mocks over live vendor calls in tests.
- Do not weaken auth, CSRF, CSP, or security middleware to make tests pass.

## Database & Migrations

Create migrations after model changes:

```bash
cd src
docker compose exec app python manage.py makemigrations
```

Apply migrations locally:

```bash
cd src
docker compose exec app python manage.py migrate
```

CI checks that migrations are complete:

```bash
cd src
docker compose run app ./manage.py makemigrations --dry-run --verbosity 3
docker compose run app ./manage.py makemigrations --check
```

Local Docker startup runs:

```bash
python manage.py migrate
python manage.py createcachetable
python manage.py load
```

Deployment constraint:

- Cloud.gov deploys must run Django migrations as a Cloud.gov task after push, not by ad hoc manual database edits.
- Never edit production data directly without an approved runbook.
- Treat migrations as backwards-compatible unless a release plan explicitly coordinates downtime/data migration.
- Keep data migrations idempotent and safe to rerun where practical.

## Architecture Principles

- Keep domain logic centralized in models/services instead of duplicating workflow rules in templates or views.
- Preserve the Login.gov/OIDC authentication model and login-required-by-default posture.
- Preserve the opt-out access restriction model: routes should require authentication unless explicitly exempted.
- Preserve Django security middleware, CSRF settings, CSP configuration, HSTS behavior, and audit logging.
- Use django-waffle flags for incomplete, risky, or staged feature rollout.
- Use Django ORM and parameterized queries; avoid raw SQL unless necessary and reviewed.
- Keep EPP registry, DNS vendor, AWS, and other external integrations behind service boundaries that can be mocked.
- Keep local mock behavior explicit through environment variables such as `DNS_MOCK_EXTERNAL_APIS`; do not make production accidentally use mocks.
- Follow ADRs in `docs/architecture/decisions/` before changing foundational patterns.
- Use USWDS and existing BEM-style custom class conventions for UI changes.
- Add pa11y coverage for new pages or routes that should be accessibility-scanned.

## Security Requirements

Must never:

- Hardcode credentials, tokens, API keys, private keys, registry credentials, DNS credentials, AWS credentials, or Login.gov secrets. Use environment variables or Cloud.gov services.
- Commit `.env`, real certificates, private keys, production service credentials, exported Cloud.gov environment output, or vendor procurement details.
- Bypass authentication, authorization, analyst/admin role checks, portfolio permissions, or domain-manager checks.
- Remove or weaken LoginRequiredMiddleware, RestrictAccessMiddleware, CSRF middleware, CSP middleware, auditlog middleware, or security middleware.
- Add unauthenticated endpoints unless there is a documented product/security reason and tests.
- Use SQL string interpolation. Use Django ORM or parameterized queries only.
- Use `shell=True` in subprocess calls.
- Log PII such as email, SSN, phone numbers, national IDs, domain requester details, addresses, or sensitive registry/DNS data.
- Use `eval()` or `exec()` with user-supplied input.
- Expand API token scopes beyond the minimum required.
- Store or expose research participant data, scheduling details, compliance docs with IP addresses, or user feedback containing PII.
- Make live Cloudflare/DNS/EPP/AWS calls from tests.
- Disable TLS, HSTS, secure cookies, or CSRF protections outside explicit local test-only settings.
- Add broad CSP exceptions such as unrestricted `unsafe-inline`, `unsafe-eval`, or wildcard external origins without security review.

## Pull Request Guidelines

- Branch naming: use `your_initials/issue_number-description`, for example `dg/1234-update-dns-record-flow`.
- Prefer merge from `main` over rebase; this repo values history preservation and merge context.
- Before PR or handoff, run the narrowest relevant tests plus the CI-equivalent checks for touched areas.
- For backend/model changes, run Django tests and migration checks.
- For UI/template changes, run relevant Django tests and pa11y when a page/flow changes.
- For security-sensitive changes, run Bandit and consider OWASP ZAP.
- For Sass/USWDS changes, confirm assets compile and check affected pages visually.
- Keep PRs scoped. Do not combine unrelated refactors with feature/security changes.
- Document behavior changes in the PR description and link the issue.
- Do not add new production dependencies without explicit justification and review.
- Respect CODEOWNERS and request reviewers for touched areas.

## What NOT To Do

- Do not make request approval, DNS setup, registry calls, or domain state transitions happen in multiple unrelated places.
- Do not put business-critical status transition logic only in templates or client-side JavaScript.
- Do not bypass service layers for Cloudflare/DNS, EPP registry, AWS S3/SES, or Login.gov integrations.
- Do not rely on live vendor APIs for local development or tests when mocks exist.
- Do not edit `settings.py` to permanently insert test-only middleware like `MockUserLogin`.
- Do not remove CSP nonces or autoescape protections to solve frontend issues.
- Do not introduce raw SQL for convenience.
- Do not commit generated local reports such as ZAP reports unless explicitly requested.
- Do not add images under ignored asset paths without intentionally force-adding required deployable assets.
- Do not weaken admin, analyst, portfolio, or domain-manager permissions to simplify UI flows.

## Key File References

| Purpose | Path |
|---|---|
| Project overview | `README.md` |
| Contribution rules | `CONTRIBUTING.md` |
| Developer setup and tests | `docs/developer/README.md` |
| Architecture decisions | `docs/architecture/decisions/` |
| Operations docs | `docs/operations/` |
| Cloud.gov manifests | `ops/manifests/` |
| Django settings/security/auth | `src/registrar/config/settings.py` |
| Local Docker environment | `src/docker-compose.yml` |
| Python dependencies | `src/Pipfile`, `src/Pipfile.lock` |
| Frontend tooling | `src/package.json`, `src/gulpfile.js` |
| Django entrypoint | `src/manage.py` |
| App models | `src/registrar/models/` |
| App views | `src/registrar/views/` |
| App forms | `src/registrar/forms/` |
| Templates | `src/registrar/templates/` |
| Static source assets | `src/registrar/assets/` |
| Management commands | `src/registrar/management/commands/` |
| Tests | `src/registrar/tests/` |
| CI workflows | `.github/workflows/` |
