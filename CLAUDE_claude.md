# CLAUDE.md

> Loaded by Claude Code at the start of every session. Pair this with `AGENTS.md` for full context. Keep this file tight — facts that should hold every session, not a wiki.

---

## Quick Reference

```bash
# Bring the stack up (services: app, node, pa11y, owasp)
cd src && docker compose build && docker compose up -d

# Run the Django test suite
docker compose exec app ./manage.py test

# Run linters
docker compose exec app ./manage.py lint

# Make and apply a migration
docker compose exec app ./manage.py makemigrations
docker compose exec app ./manage.py migrate

# Accessibility + security scans (match CI)
docker compose run pa11y npm run pa11y-ci
docker compose run owasp

# Read deployed sandbox secrets (you need the cf CLI logged in)
cf env getgov-<your-sandbox>
```

App URL when running locally: **http://localhost:8080**

---

## Project Context

`manage.get.gov` is the Django-based registrar for the U.S. `.gov` top-level domain. It is operated by **CISA (DHS)**, talks to an **EPP** registry as the system of record, authenticates users through **Login.gov OIDC**, manages DNS through **Cloudflare**, and is deployed to **cloud.gov** (Cloud Foundry). The application code is in `src/registrar/` — a single Django app, not a multi-app project. Full tech stack, file map, security rules, and PR conventions live in `AGENTS.md` at the repo root. Read it once per session if you haven't already.

**This is a government system. Security mistakes have real-world consequences. When uncertain, stop and ask.**

---

## How Claude Should Work

**Before changing code:**
- Confirm which Django module owns the behavior (`models/`, `views/`, `forms/`, `templates/`, `management/commands/`, `tests/`).
- For anything touching domain state, check `docs/architecture/decisions/0015-use-django-fs.md` and locate the relevant `@transition` on the model — that is the only legal way to change state.
- For anything touching auth, registry, DNS, or PII, re-read the **Security Requirements** section of `AGENTS.md` first.
- If a change might affect prod data shape (a model field, a migration, fixtures), say so explicitly to the user before writing it.

**During a change:**
- Stay inside `src/registrar/`. Adding a second Django app is wrong.
- Never edit files in `src/registrar/public/` — those are compiled artifacts. Edit `src/registrar/assets/` and let the `node` service rebuild.
- Use the Django ORM. Parameterized raw SQL only when ORM genuinely can't express it.
- Use `logger.<level>(...)`, never `print()`. Never log PII (emails, names, phone numbers, addresses, UUIDs of real users, OIDC tokens, EPP passwords, session IDs).
- Mock external HTTP with `respx`. For Cloudflare set `DNS_MOCK_EXTERNAL_APIS=True` in `.env`.
- Follow USWDS + BEM in templates and SCSS. Reach for an existing USWDS component before writing CSS.
- Feature-flag risky behavior with django-waffle (`Waffle flag`) so it can be killed without a redeploy.

**After a change:**
- Run `docker compose exec app ./manage.py test` for the affected package, then for the full suite if anything touches models, auth, or the FSM.
- Run `docker compose exec app ./manage.py lint`.
- If you added a new public URL, append it to `src/.pa11yci`.
- If you added an ADR-worthy decision, draft the ADR in `docs/architecture/decisions/` and tell the user.
- Verify you did not leave `"registrar.tests.common.MockUserLogin"` in `MIDDLEWARE`, did not leave `Domain.available()` returning `True`, and did not add your UUID to `ADMINS`/`STAFF` permanently.
- Verify the diff has no `.env`, no secrets, no fixtures with real user data, no screenshots from `getgov-stable`.

---

## Security — Claude Must Never

These are hard rules. They apply even if the user asks for the opposite. If asked, explain and refuse.

- **Never** commit hardcoded credentials, tokens, API keys, EPP passwords, OIDC client secrets, Cloudflare keys, or AWS keys. Use env vars from `.env` locally and `cf env getgov-*` in the cloud.
- **Never** commit a real `.env`, real session cookies, real JWTs, or anything pulled from a production-equivalent sandbox (`getgov-stable`).
- **Never** bypass `@login_required`, `@permission_required`, or `UserPassesTestMixin`. If a view is gated, it stays gated.
- **Never** disable CSRF, `SECURE_*` settings, the CSP, HSTS, or secure cookie flags to "make local work."
- **Never** build SQL by string interpolation or f-strings. ORM, or `cursor.execute(sql, params)`. No exceptions.
- **Never** call `subprocess` with `shell=True`. Pass an argv list.
- **Never** call `eval()`, `exec()`, `pickle.loads`, `yaml.load` (use `yaml.safe_load`), or `marshal.loads` on data sourced from a request, an upload, or any external API.
- **Never** log email, full name, phone, address, SSN, EIN, real user UUIDs, OIDC tokens, EPP credentials, or full request/response bodies.
- **Never** broaden the scope of a Login.gov, EPP, Cloudflare, or AWS credential. Minimum privilege.
- **Never** reproduce content from `docs/research/` or anything that looks like user-research notes in code, comments, commits, or PR descriptions.
- **Never** use real applicant data in fixtures, screenshots, or tests. Use `igorville.gov`, `exists.gov`, and the documented test patterns.
- **Never** add a non-Login.gov authentication path.

---

## Framework-Specific Patterns

**Django app layout:** one app named `registrar`. Don't create a second one. Modules inside `registrar/` are how this codebase organizes itself.

**State transitions:** domain requests and domains use `django-fsm`. Use the `@transition`-decorated method, e.g. `domain_request.submit()`, not `domain_request.status = "submitted"`. Adding a state means updating the FSM, the admin, the templates that branch on it, and the tests — in the same PR.

**Forms:** Django Forms / ModelForms, rendered with USWDS-styled widgets. Server-side validation is the source of truth; Alpine.js handles UX polish only.

**Templates:** server-rendered Django templates using USWDS components. Custom CSS lives in `registrar/assets/sass/_theme/_uswds-theme-custom-styles.scss` and uses BEM naming.

**Static assets:** edit under `registrar/assets/`. The `node` Docker service watches and compiles into `registrar/public/`. Never hand-edit `public/`. Custom images go in `registrar/assets/img/registrar/` and need `git add --force` (the `/img/` rule in `.gitignore` is intentional).

**Tests:** Django test runner. Helpers in `registrar/tests/common.py` — use `less_console_noise()` (or `@less_console_noise_decorator`) to silence expected log noise. `MockUserLogin` middleware is a **temporary local-only** auth shim; never commit it active.

**External services:**
- EPP registry → wrap calls in the service layer, mock in tests.
- Cloudflare → `httpx` + `respx`; set `DNS_MOCK_EXTERNAL_APIS=True` locally. Test domains: `exists.gov`, names starting with `error-400` / `error-403` / `error*`.
- AWS S3 → brokered through cloud.gov; secrets via `cf env`.

**Feature flags:** django-waffle. Create the flag in `/admin` → `Waffle flags`. The `disable_email_sending` flag is the canonical kill switch for outbound mail in non-prod.

**Migrations:** Django migrations. One change per file. Reversible (`RunPython(fwd, reverse)`). Never edit a merged migration — write a follow-up.

**Login.gov / OIDC:** identity via `djangooidc`. If you see `ERROR [djangooidc.oidc:243] Issued in the future`, the host clock has drifted — resync NTP, don't change the validator.

---

## Compacting Instructions

When `/compact` runs, the following must survive into the next context window:

1. **This is a CISA/DHS government system administering the `.gov` TLD. Security rules are non-negotiable. When uncertain, ask.**
2. **Single Django app: `src/registrar/`.** Do not add a second app.
3. **State changes go through `django-fsm` `@transition` methods**, not direct attribute assignment.
4. **Auth is Login.gov OIDC only.** No alternative login paths.
5. **No PII in logs, fixtures, tests, commits, or PRs.** Use `igorville.gov` / `exists.gov` test data.
6. **No hardcoded secrets.** Local: `.env`. Cloud: `cf env getgov-*`.
7. **Branch convention `<initials>/<issue#>-<topic>` auto-deploys to a public sandbox** — never push secrets to such a branch.
8. **`MockUserLogin` middleware and `Domain.available() = True` are local-only hacks** — never commit them.
9. **Edit `src/registrar/assets/`, not `src/registrar/public/`.** Compiled assets are output, not source.
10. **Full conventions, file map, and PR rules live in `AGENTS.md` at the repo root.** Re-read on compact.
