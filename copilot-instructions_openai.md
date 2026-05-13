# GitHub Copilot Instructions

## Project Summary

This repository contains CISA’s Django-based `.gov` registrar for U.S. government domain requests and management. It integrates with Login.gov/OIDC, PostgreSQL, Cloud.gov, an EPP registry, AWS services, USWDS frontend assets, and DNS vendor APIs. This is a government or sensitive-data system. Security mistakes have real-world consequences. When uncertain, stop and ask.

## Tech Stack

| Area | Technology |
|---|---|
| Backend | Python, Django 4.2.x |
| Database | PostgreSQL, Django ORM/migrations |
| Auth | Login.gov/OpenID Connect via `djangooidc` |
| Frontend | Django templates, JavaScript, Sass, USWDS |
| Local dev | Docker Compose |
| Deployment | Cloud.gov manifests under `ops/` |
| Feature flags | django-waffle |
| Audit | django-auditlog |
| Quality/security | Django tests, Black, Flake8, Mypy, Bandit, pa11y-ci, OWASP ZAP |

## Coding Guidelines

### General

- Work from `src/` for app commands.
- Follow existing patterns in nearby files before introducing new patterns.
- Keep changes small, scoped, and test-backed.
- Do not add production dependencies without clear justification.
- Prefer readability and explicit domain logic over clever abstractions.

### Python/Django

- Use Django ORM for database access.
- Use parameterized queries if raw SQL is unavoidable.
- Keep business rules in models, forms, services, or management commands, not only in templates/client-side code.
- Use transactions for multi-step writes that must be atomic.
- Preserve django-fsm transition patterns for stateful domain/request workflows.
- Preserve the custom `registrar.User` model.
- Add migrations for model changes.

### Security

Copilot must never:

- Hardcode credentials, tokens, API keys, private keys, registry credentials, DNS credentials, AWS credentials, or Login.gov secrets.
- Bypass authentication or authorization checks.
- Bypass analyst/admin checks, portfolio permissions, requester checks, or domain-manager checks.
- Use SQL string interpolation.
- Use `shell=True` in subprocess calls.
- Log PII such as email, SSN, phone, national ID, addresses, requester details, or sensitive domain-management data.
- Use `eval()` or `exec()` with user-supplied input.
- Expand API token scopes beyond the minimum required.
- Remove or weaken CSRF, CSP, secure cookies, HSTS, LoginRequiredMiddleware, RestrictAccessMiddleware, audit logging, or Django security middleware.
- Commit `.env`, real certs, private keys, Cloud.gov env dumps, research PII, procurement details, or compliance docs with IP addresses.
- Make tests depend on live EPP, Cloudflare/DNS, AWS, or Login.gov calls.

### Tests and validation

Common commands:

```bash
cd src
docker compose run --rm app python manage.py test --parallel
docker compose run --rm app ./manage.py makemigrations --dry-run --verbosity 3
docker compose run --rm app ./manage.py makemigrations --check
docker compose run --rm --no-deps app black --check .
docker compose run --rm --no-deps app flake8 .
docker compose run --rm --no-deps app mypy .
docker compose run --rm --no-deps app bandit -q -r .
docker compose run pa11y npm run pa11y-ci
docker compose run owasp
```

Use targeted tests for focused changes, but keep CI-equivalent commands in mind before PR handoff.

### Frontend

- Use USWDS patterns and existing template conventions.
- Use BEM for custom CSS classes.
- Preserve Django template autoescaping and CSP nonce patterns.
- Do not add broad CSP exceptions.
- For new user-facing pages, consider pa11y coverage in `src/.pa11yci`.
- Compile/copy assets through the existing Node/Gulp workflow.

## Project Structure

```text
.
├── README.md                         # Top-level project overview
├── CONTRIBUTING.md                   # Branch and contribution rules
├── docs/
│   ├── developer/README.md           # Local setup, tests, scans, assets
│   ├── operations/                   # Ops runbooks
│   └── architecture/decisions/       # ADRs
├── ops/manifests/                    # Cloud.gov manifests
├── .github/workflows/                # CI/CD workflows
└── src/
    ├── manage.py                     # Django CLI
    ├── docker-compose.yml            # Local app/db/node/pa11y/owasp
    ├── Pipfile                       # Python deps
    ├── package.json                  # USWDS/Sass/JS tooling
    ├── registrar/
    │   ├── config/settings.py        # Settings, auth, middleware, security
    │   ├── models/                   # Domain/request/user/DNS/portfolio models
    │   ├── views/                    # Django views
    │   ├── forms/                    # Forms and validation
    │   ├── templates/                # Django templates
    │   ├── assets/                   # Source frontend assets
    │   ├── management/commands/      # Custom commands
    │   └── tests/                    # Tests and helpers
    └── api/                          # API Django app
```

## Architectural Constraints

- Login is required by default; do not create public routes without explicit reason and tests.
- Auth is Login.gov/OIDC; do not replace or bypass it.
- Domain, request, DNS, registry, portfolio, and permission behavior must remain server-authoritative.
- External integrations must remain behind service boundaries and be mockable.
- Use Waffle flags for staged/risky feature rollout.
- Preserve audit logging and security middleware.
- Follow ADRs before changing foundational architecture.
- Prefer merge from `main`; this repo explicitly values merge context over a purely linear history.
- Branches should follow `your_initials/issue_number-description`.
