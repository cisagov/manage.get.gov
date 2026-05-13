# GitHub Copilot — Repository Instructions

> Commit this file to **`.github/copilot-instructions.md`** in the repository root.

These instructions apply to Copilot Chat, inline completions, the coding agent, and code review across this repository.

> **This is a CISA / DHS government system** administering the U.S. `.gov` top-level domain. Security mistakes have real-world consequences. When uncertain, stop and ask in the PR or issue. Full conventions live in `AGENTS.md` at the repo root.

---

## Project Summary

`manage.get.gov` is a Django-based domain name registrar for the U.S. `.gov` TLD, operated by CISA (DHS). It authenticates users via Login.gov OIDC, talks to an EPP registry as the system of record, manages DNS through Cloudflare, and is deployed to cloud.gov (Cloud Foundry). All application code lives in a single Django app at `src/registrar/`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+, JavaScript, SCSS |
| Framework | Django (single app: `registrar`) |
| Frontend | USWDS, Alpine.js, Sass (gulp) |
| Auth | Login.gov OIDC (`djangooidc`) |
| Database | PostgreSQL (cloud.gov RDS broker) |
| State machines | `django-fsm` |
| Feature flags | `django-waffle` |
| External APIs | EPP registry, Cloudflare, AWS S3 |
| HTTP / mocking | `httpx` + `respx` |
| Local dev | Docker Compose |
| Deploy | Cloud Foundry on cloud.gov |
| Tests | Django test runner, pa11y-ci, OWASP ZAP |

---

## Coding Guidelines

### Python / Django

- Target Python 3.10+ and modern Django idioms. Use type hints on new public functions and methods.
- Stay inside the single `registrar` app. Organize new code as modules inside `registrar/`, not as new Django apps.
- Use the Django ORM. If you must drop to raw SQL, use `cursor.execute(sql, params)` with parameter binding — **never** f-strings or `%` formatting into a SQL string.
- Change domain or domain-request state through the `django-fsm` `@transition` method on the model, never by direct attribute assignment.
- Use `logger.<level>(...)` for diagnostics. **Never** `print()`. **Never** log PII (email, name, phone, address, real user UUID, OIDC token, EPP credential, session ID, full request body).
- Mock external services in tests with `respx` against `httpx`. Use `DNS_MOCK_EXTERNAL_APIS=True` for Cloudflare.
- Use Waffle flags for risky new behavior so it can be disabled without a redeploy.
- For settings that vary by environment, read from `os.environ` (validated in `settings.py`); never hardcode.
- Use `subprocess.run([...], shell=False)` — never `shell=True`.
- Never call `eval()`, `exec()`, `pickle.loads`, `yaml.load` (use `yaml.safe_load`), or `marshal.loads` on data that could originate from a request, upload, or external API.

### Security

- **No hardcoded credentials, tokens, API keys, EPP passwords, OIDC secrets, Cloudflare keys, or AWS keys.** Pull from env vars (`.env` locally, `cf env getgov-*` in cloud.gov).
- **No bypassing of `@login_required`, `@permission_required`, or `UserPassesTestMixin`.** If a view is gated, it stays gated.
- **No disabling** of CSRF, CSP, HSTS, `SECURE_*` settings, or secure cookie flags to make something work locally.
- **No expansion** of Login.gov, EPP, Cloudflare, or AWS credential scope beyond what the task requires.
- **No PII** in logs, fixtures, tests, commit messages, PR descriptions, or code comments. Use `igorville.gov` / `exists.gov` as test data.
- **No real production data** in screenshots, fixtures, or anywhere in the repo. Per `CONTRIBUTING.md`: vendor info, PII, user research, compliance docs containing IPs, and secrets of any kind are never committed.

### Tests

- Place new tests under `src/registrar/tests/`.
- Use the Django test runner — no pytest-only features.
- Use `less_console_noise()` (or `@less_console_noise_decorator`) from `registrar.tests.common` to silence expected error output rather than deleting the log calls.
- Use `MockUserLogin` middleware only as a temporary local aid — never leave it in committed `MIDDLEWARE`.
- For Cloudflare-touching tests: set `DNS_MOCK_EXTERNAL_APIS=True` and use the documented sentinel domains (`exists.gov`, `error-400.*`, `error-403.*`, `error*`).
- Add or update tests for every behavior change. New view → new test. New model field → fixture + test coverage.

### Frontend (USWDS / Alpine.js / SCSS)

- Use a USWDS component before writing custom CSS. Custom classes follow BEM naming.
- Edit source files under `src/registrar/assets/`. **Never** edit `src/registrar/public/` directly — those are compiled outputs that the `node` Docker service regenerates.
- Custom images go in `src/registrar/assets/img/registrar/`; the `/img/` `.gitignore` rule means they need `git add --force`.
- When adding a new public URL, append it to `src/.pa11yci` so the accessibility scan covers it.
- Keep validation server-side. Alpine.js is for UX polish, not for enforcing rules.

---

## Project Structure

```
.github/workflows/test.yaml         # CI: Django tests + pa11y-ci + OWASP ZAP
.github/workflows/deploy-sandbox.yaml  # Auto-deploys `<initials>/*` branches
.github/CODEOWNERS                  # Path-based default reviewers
docs/architecture/decisions/        # ADRs — required reading before architectural changes
docs/developer/README.md            # Canonical local dev guide
docs/operations/runbooks/           # On-call procedures
ops/                                # Cloud Foundry deploy scripts
src/docker-compose.yml              # Local orchestration
src/Pipfile, src/Pipfile.lock       # Python deps
src/package.json                    # JS deps (gulp, USWDS)
src/.env-example                    # Local secrets template — copy to .env, never commit .env
src/.pa11yci                        # Accessibility scan URL list
src/manage.py                       # Django entry point
src/registrar/                      # The single Django app — all code lives here
src/registrar/models/domain.py      # Domain model; available() check
src/registrar/fixtures/             # Fixtures incl. fixtures_users.py
src/registrar/management/commands/  # Custom manage.py commands (e.g. load)
src/registrar/tests/common.py       # less_console_noise, MockUserLogin
```

---

## Architectural Constraints

Hard rules. Do not suggest changes that violate these.

1. **One Django app: `registrar`.** Do not introduce a second app for organization.
2. **`django-fsm` owns state transitions.** Use `@transition`-decorated methods on the model. Never `obj.status = "approved"`.
3. **EPP is the system of record** for registry data. On conflict, EPP wins.
4. **Login.gov OIDC is the only auth.** No local password auth, social login, or API keys for human users.
5. **USWDS first.** Reach for an existing USWDS component before writing custom CSS or new components.
6. **Feature-flag risky changes with Waffle.** Code paths that aren't ready for everyone live behind a Waffle flag.
7. **Source assets live in `registrar/assets/`; compiled assets in `registrar/public/` are output only.**
8. **Migrations are immutable once merged.** Write a follow-up migration; never edit a migration on `main`.
9. **Branches named `<initials>/<issue#>-<topic>` auto-deploy to a public cloud.gov sandbox** — never push secrets, real PII, or production data to such a branch.
10. **Merge, don't rebase, when bringing `main` into a feature branch.** History preservation is intentional.

### Pull Request Expectations

- Branch name: `<initials>/<issue#>-<short-description>`.
- One issue per PR; link with `Closes #<issue>`.
- CI must be green: Django tests, lint, pa11y-ci, OWASP ZAP.
- Add or update tests for behavior changes.
- Update `src/.pa11yci` when adding a new public URL.
- Update or write an ADR when changing architecture (state machine, auth flow, registry interface).
