# CLAUDE.md

> Loaded by Claude Code at the start of every session. Pair this with `AGENTS.md` (the shared brief for all AI tools and contributors) and `AI_USAGE_POLICY.md` (what AI tools may and may not be used for on this repo). Keep this file tight — facts that should hold every session, not a wiki.

---

## Quick Reference

```bash
# Bring the stack up (services: app, db, node, pa11y, owasp)
cd src && cp ./.env-example .env && docker compose build && docker compose up -d
docker compose logs -f

# Run the Django test suite
docker compose exec app ./manage.py test
# Parallel
docker compose run --rm app python manage.py test --parallel

# Migration completeness checks (match CI)
docker compose run --rm app ./manage.py makemigrations --dry-run --verbosity 3
docker compose run --rm app ./manage.py makemigrations --check

# Lint / format / type-check / static security (match CI)
docker compose exec app ./manage.py lint
docker compose run --rm --no-deps app black --check .
docker compose run --rm --no-deps app flake8 .
docker compose run --rm --no-deps app mypy .
docker compose run --rm --no-deps app bandit -q -r .

# Make and apply a migration
docker compose exec app ./manage.py makemigrations
docker compose exec app ./manage.py migrate

# Accessibility + dynamic security scan (match CI)
docker compose run pa11y npm run pa11y-ci
docker compose run owasp

# Read deployed sandbox secrets (you need the cf CLI logged in)
cf env getgov-<your-sandbox>
```

App URL when running locally: **http://localhost:8080**

---

## Project Context

`manage.get.gov` is the Django-based registrar for the U.S. `.gov` top-level domain. It is operated by **CISA (DHS)**, talks to an **EPP** registry as the system of record, authenticates users through **Login.gov OIDC** (custom user model `registrar.User`), manages DNS through **Cloudflare**, sends mail through **AWS SES**, stores uploads in **AWS S3**, and is deployed to **cloud.gov** (Cloud Foundry). State machines run on `django-fsm`, audit history on `django-auditlog`, feature flags on `django-waffle`. The repo has four Django apps: `src/registrar/` (primary — product logic lives here), `src/api/` (lightweight internal API), `src/djangooidc/` (Login.gov OIDC integration), and `src/epplibwrapper/` (EPP registry client wrapper). Full tech stack, file map, security rules, and PR conventions live in `AGENTS.md` at the repo root. Read it once per session if you haven't already.

**This is a government system. Security mistakes have real-world consequences. When uncertain, stop and ask.**

`AI_USAGE_POLICY.md` is the binding policy that governs *how* Claude Code may be used on this repository. Read it before sharing any repo context that isn't already public.

---

## How Claude Should Work

**Before changing code:**
- Confirm which Django module owns the behavior (`models/`, `views/`, `forms/`, `services/`, `templates/`, `management/commands/`, `tests/`).
- Inspect the nearest existing pattern. Follow it rather than introducing a new one.
- Check `docs/architecture/decisions/` before changing anything foundational (state machine, auth flow, registry interface, middleware ordering).
- For anything touching domain state, locate the relevant `@transition` on the model — that is the only legal way to change state.
- For anything touching auth, authorization, registry, DNS, email, S3, audit logging, migrations, or PII, re-read the **Security Requirements** section of `AGENTS.md` first.
- If a change might affect prod data shape (a model field, a migration, fixtures), say so explicitly to the user before writing it.

**During a change:**
- Make the smallest coherent change that satisfies the ticket.
- Stay inside `src/registrar/` for product logic. Do not add a second Django app to organize code.
- Never edit files in `src/registrar/public/` — those are compiled artifacts. Edit `src/registrar/assets/` and let the `node` service rebuild.
- Preserve service boundaries for EPP, Cloudflare/DNS, AWS S3/SES, and Login.gov. Views do not call those clients directly.
- Use the Django ORM. Parameterized raw SQL only when the ORM genuinely cannot express it.
- Use `transaction.atomic()` for multi-step writes that must succeed or fail together.
- Use `logger.<level>(...)`, never `print()`. Never log PII (emails, names, phone numbers, addresses, real user UUIDs, OIDC tokens, EPP credentials, session IDs, full request/response bodies).
- Mock external HTTP with `respx`. For Cloudflare set `DNS_MOCK_EXTERNAL_APIS=True` in `.env`.
- Follow USWDS + BEM in templates and SCSS. Reach for an existing USWDS component before writing CSS. Preserve CSP nonce patterns and Django autoescape.
- Feature-flag risky behavior with django-waffle so it can be killed without a redeploy.
- Keep server-side authorization in place: analyst, admin, portfolio, requester, and domain-manager checks run on the server, not in templates, HTMX endpoints, or Alpine.js.

**After a change:**
- Run `docker compose exec app ./manage.py test` for the affected package, then the full suite if anything touches models, auth, the FSM, or shared services.
- Run `docker compose exec app ./manage.py lint` plus Black / Flake8 / Mypy / Bandit for security-sensitive areas.
- For model changes, run `makemigrations` and the migration-check commands above.
- For frontend changes, verify assets compile and walk the affected pages.
- If you added a new public URL, append it to `src/.pa11yci`.
- If you added an ADR-worthy decision, draft the ADR in `docs/architecture/decisions/` and tell the user.
- Verify the diff does not leave `"registrar.tests.common.MockUserLogin"` in `MIDDLEWARE`, does not leave `Domain.available()` returning `True`, and does not add a UUID to `ADMINS`/`STAFF` permanently.
- Verify the diff has no `.env`, no secrets, no fixtures with real user data, no screenshots from `getgov-stable`, no ZAP reports.
- Summarize what changed, what was tested, and any residual risk.

---

## Security — Claude Must Never

These are hard rules. They apply even if the user asks for the opposite. If asked, explain and refuse.

- Commit hardcoded credentials, tokens, API keys, EPP passwords, OIDC client secrets, Cloudflare keys, AWS keys, or Django `SECRET_KEY`s. Use env vars from `.env` locally and `cf env getgov-*` in the cloud.
- Commit a real `.env`, real session cookies, real JWTs, real certificates, real private keys, or anything pulled from a production-equivalent sandbox (`getgov-stable`).
- Bypass `@login_required`, `@permission_required`, `UserPassesTestMixin`, analyst/admin checks, portfolio permissions, or domain-manager checks. If a view is gated, it stays gated.
- Remove or weaken `LoginRequiredMiddleware`, `RestrictAccessMiddleware`, CSRF middleware, CSP middleware, `auditlog` middleware, or Django security middleware.
- Disable CSRF, `SECURE_*` settings, the CSP, HSTS, or secure cookie flags to "make local work."
- Add broad CSP exceptions (`unsafe-inline`, `unsafe-eval`, wildcard origins) without security review.
- Build SQL by string interpolation, `%` formatting, or f-strings. ORM, or `cursor.execute(sql, params)`.
- Call `subprocess` with `shell=True`. Pass an argv list.
- Call `eval()`, `exec()`, `pickle.loads`, `yaml.load` (use `yaml.safe_load`), or `marshal.loads` on data sourced from a request, an upload, or any external API.
- Log email, full name, phone, address, SSN, EIN, real user UUIDs, OIDC tokens, EPP credentials, or full request/response bodies.
- Broaden the scope of a Login.gov, EPP, Cloudflare, or AWS credential. Minimum privilege.
- Reproduce content from `docs/research/` or anything that looks like user-research notes in code, comments, commits, or PR descriptions.
- Use real applicant data in fixtures, screenshots, or tests. Use `igorville.gov`, `exists.gov`, and the documented test patterns.
- Add a non-Login.gov authentication path.
- Make a test depend on a live EPP, Cloudflare/DNS, AWS, or Login.gov call.

---

## Framework-Specific Patterns

**Django app layout:** four apps — `registrar` (primary, product logic), `api` (lightweight internal API), `djangooidc` (Login.gov OIDC), `epplibwrapper` (EPP registry client). Do not create additional apps for `registrar` business logic — use modules inside `registrar/`. `AUTH_USER_MODEL = "registrar.User"` is fixed.

**Models:** new models extend `TimeStampedModel` (from `src/registrar/models/utility/time_stamped_model.py`) for automatic `created_at` / `updated_at`.

**State transitions:** domain requests and domains use `django-fsm`. Use the `@transition`-decorated method, e.g. `domain_request.submit()`, not `domain_request.status = "submitted"`. Adding a state means updating the FSM, the admin, the templates that branch on it, and the tests — in the same PR.

**Forms:** Django Forms / ModelForms, rendered with USWDS-styled widgets. Server-side validation is the source of truth; HTMX handles dynamic partials and Alpine.js handles client-side UX polish.

**Templates:** server-rendered Django templates using USWDS components. Custom CSS lives in `registrar/assets/sass/_theme/_uswds-theme-custom-styles.scss` and uses BEM naming. Preserve CSP nonces and template autoescape.

**Static assets:** edit under `registrar/assets/`. The `node` Docker service watches and compiles into `registrar/public/`. Never hand-edit `public/`. Custom images go in `registrar/assets/img/registrar/` and need `git add --force` (the `/img/` rule in `.gitignore` is intentional).

**Tests:** Django test runner. Helpers in `registrar/tests/common.py` — use `less_console_noise()` (or `@less_console_noise_decorator`) to silence expected log noise. `MockUserLogin` middleware is a **temporary local-only** auth shim; never commit it active. Use `transaction.atomic()` for tests that need multi-step write-or-rollback semantics.

**External services:**
- EPP registry → wrap calls in the service layer, mock in tests.
- Cloudflare → `httpx` + `respx`; set `DNS_MOCK_EXTERNAL_APIS=True` locally. Test domains: `exists.gov`, names starting with `error-400` / `error-403` / `error*`.
- AWS S3 / SES → brokered through cloud.gov; secrets via `cf env`. Mock in tests.

**Feature flags:** django-waffle. Create the flag in `/admin` → `Waffle flags`. The `disable_email_sending` flag is the canonical kill switch for outbound mail in non-prod.

**Audit log:** `django-auditlog`. Register audit-sensitive models and keep coverage in tests.

**Migrations:** Django migrations. One change per file. Reversible (`RunPython(fwd, reverse)`). Never edit a merged migration — write a follow-up. Deployed migrations run as a cloud.gov task after push.

**Login.gov / OIDC:** identity via `djangooidc`. If you see `ERROR [djangooidc.oidc:243] Issued in the future`, the host clock has drifted — resync NTP, do not change the validator.

---

## Compacting Instructions

When `/compact` runs, the following must survive into the next context window:

1. This is a CISA/DHS government system administering the `.gov` TLD. Security rules are non-negotiable. When uncertain, ask.
2. Four Django apps: `src/registrar/` (primary), `src/api/`, `src/djangooidc/`, `src/epplibwrapper/`. Do not add a fifth for `registrar` business logic.
3. State changes go through `django-fsm` `@transition` methods, not direct attribute assignment.
4. Auth is Login.gov OIDC only. `AUTH_USER_MODEL = "registrar.User"`. Login-required is the default; `LoginRequiredMiddleware` and `RestrictAccessMiddleware` enforce it.
5. Server-side authorization is mandatory (analyst, admin, portfolio, requester, domain-manager).
6. No PII in logs, fixtures, tests, commits, or PRs. Use `igorville.gov` / `exists.gov` test data.
7. No hardcoded secrets. Local: `.env`. Cloud: `cf env getgov-*`.
8. Branch convention `<initials>/<issue#>-<topic>` auto-deploys to a public sandbox — never push secrets to such a branch.
9. `MockUserLogin` middleware and `Domain.available() = True` are local-only hacks — never commit them.
10. Edit `src/registrar/assets/`, not `src/registrar/public/`. Compiled assets are output, not source.
11. Core checks before PR: Django tests, migration completeness, Black, Flake8, Mypy, Bandit, `./manage.py lint`, pa11y, OWASP ZAP when relevant.
12. Two merge rules: when bringing `main` into a feature branch, merge (don't rebase). When landing a PR on `main`, squash-and-merge. PR title gets `- MIGRATION` appended (with a leading space) if the PR has a migration.
13. AI tool use is governed by `AI_USAGE_POLICY.md` at the repo root.
14. Full conventions, file map, and PR rules live in `AGENTS.md`. Re-read on compact.
