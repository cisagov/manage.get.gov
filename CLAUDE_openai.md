# CLAUDE.md

This file guides Claude Code when working in this repository. Read `AGENTS.md` for full project, architecture, security, and workflow details.

## Quick Reference

```bash
cd src
cp ./.env-example .env
docker compose build
docker compose up
docker compose logs -f
docker compose exec app python manage.py makemigrations
docker compose exec app python manage.py migrate
docker compose run --rm app python manage.py test --parallel
docker compose run --rm --no-deps app black --check . && docker compose run --rm --no-deps app flake8 . && docker compose run --rm --no-deps app mypy . && docker compose run --rm --no-deps app bandit -q -r .
docker compose run pa11y npm run pa11y-ci
docker compose run owasp
```

## Project Context

This is CISA’s Django-based `.gov` registrar for U.S. government domain requests and domain management. It uses PostgreSQL, Login.gov/OIDC, Cloud.gov, USWDS, django-waffle feature flags, django-auditlog, EPP registry integration, AWS services, and DNS vendor APIs. This is a government or sensitive-data system. Security mistakes have real-world consequences. When uncertain, stop and ask.

For complete repo rules, use `AGENTS.md` as the authoritative shared instruction file.

## How Claude Should Work

Before changing code:

- Inspect the existing pattern in the nearest model, view, form, service, template, test, or management command.
- Check `docs/architecture/decisions/` before changing foundational architecture.
- Identify whether the change touches authentication, authorization, domain status, registry, DNS, email, S3, audit logging, migrations, or PII.
- For risky changes, explain the planned approach before editing.

During changes:

- Make the smallest coherent change that satisfies the ticket.
- Preserve service boundaries for EPP registry, DNS vendor APIs, AWS, and Login.gov.
- Keep auth and permission checks server-side.
- Use Django ORM or parameterized SQL only.
- Add or update tests with the behavior change.
- For UI changes, follow existing Django template, USWDS, Sass, and BEM conventions.
- Do not permanently alter settings for local-only test shortcuts.

After changes:

- Run targeted tests first, then broader checks when appropriate.
- For model changes, run `makemigrations` and migration completeness checks.
- For frontend changes, verify asset compilation and affected pages.
- For authenticated/a11y flows, use approved test helpers and pa11y as appropriate.
- Summarize what changed, what was tested, and any residual risk.

## Security — Claude Must Never

- Never hardcode credentials, tokens, API keys, private keys, registry credentials, DNS credentials, AWS credentials, or Login.gov secrets.
- Never bypass authentication, authorization, admin/analyst checks, portfolio permissions, or domain-manager checks.
- Never remove or weaken LoginRequiredMiddleware, RestrictAccessMiddleware, CSRF middleware, CSP middleware, auditlog middleware, or Django security middleware.
- Never use SQL string interpolation; use Django ORM or parameterized queries only.
- Never use `shell=True` in subprocess calls.
- Never log PII such as email, SSN, phone, national ID, requester details, addresses, or sensitive domain-management data.
- Never use `eval()` or `exec()` with user-supplied input.
- Never expand API token scopes beyond the minimum required.
- Never commit `.env`, real certs, private keys, Cloud.gov environment dumps, research PII, procurement details, or compliance docs containing IP addresses.
- Never make tests depend on live Cloudflare/DNS/EPP/AWS/Login.gov calls.
- Never add broad CSP exceptions or disable TLS/secure-cookie/CSRF behavior to make a change easier.

## Framework-Specific Patterns

Django:

- Keep business rules in models/services/forms, not only in templates or JavaScript.
- Preserve `AUTH_USER_MODEL = "registrar.User"`.
- Use class-based or function-based view patterns already present in the touched area.
- Use `transaction.atomic()` for multi-step writes that must succeed or fail together.
- Keep status transitions consistent with django-fsm patterns.
- Use django-waffle for staged or incomplete features.
- Keep audit-sensitive model changes covered by tests.

Auth and permissions:

- Login is required by default.
- OIDC/Login.gov is the primary auth path.
- Do not add public routes without explicit approval and tests.
- Check analyst, admin, portfolio, requester, and domain-manager authorization at the server.

Database:

- Create migrations for model changes.
- Do not hand-edit migration history without a clear reason.
- Keep data migrations safe, scoped, and repeatable where practical.
- Avoid raw SQL; if unavoidable, parameterize and test it.

External services:

- Keep EPP registry, DNS vendor, AWS SES/S3, and Login.gov interactions behind service boundaries.
- Use `httpx`/`respx` mocking patterns for DNS vendor API tests.
- Use environment variables or Cloud.gov services for secrets.
- `DNS_MOCK_EXTERNAL_APIS=True` is local/test behavior only.

Frontend:

- Use USWDS components and existing Sass structure.
- Use BEM for custom CSS classes.
- Keep templates accessible and compatible with pa11y checks.
- Preserve CSP nonce patterns and Django autoescaping.
- Add new pa11y URLs to `src/.pa11yci` when new pages need scanning.

## Compacting Instructions

When compacting or resuming, preserve:

- This is a CISA `.gov` registrar; treat as government/sensitive-data software.
- Commands are run from `src/` through Docker Compose.
- Core checks: Django tests, migration completeness, Black, Flake8, Mypy, Bandit, pa11y, OWASP ZAP when relevant.
- Auth is Login.gov/OIDC and login-required by default.
- Never weaken auth, permissions, CSRF, CSP, HSTS, secure cookies, audit logging, or access restrictions.
- Never hardcode secrets or log PII.
- Use Django ORM/parameterized SQL only.
- Keep external integrations behind services and mocked in tests.
- Follow USWDS/BEM for frontend work.
- Prefer merge from `main` over rebase.
- Branch pattern: `initials/issue_number-description`.
