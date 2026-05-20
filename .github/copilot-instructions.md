# Copilot Instructions for manage.get.gov

## Project overview

This repository contains the source code for the **.gov domain registrar** — the system used by U.S.-based government organizations to request and manage `.gov` domains. It is a Django 4.2 web application deployed on Cloud.gov (Cloud Foundry), backed by PostgreSQL, and integrated with Login.gov (OIDC) and an EPP-based domain registry.

All application source code lives under `src/`. Documentation lives under `docs/`.

---

## Repository layout

```
.github/          GitHub Actions workflows and templates
docs/             Developer, architecture, and operations documentation
  architecture/decisions/   Architecture Decision Records (ADRs)
  developer/                Setup guides, running tests, linting, workflows
  dev-practices/            Code-review standards and accessibility checklist
ops/              Cloud.gov / Cloud Foundry deployment scripts
src/              All application source code
  registrar/      Main Django app (models, views, templates, tests, admin, fixtures)
  epplibwrapper/  Thin wrapper around the EPP registry client (fred-epplib)
  djangooidc/     Login.gov OIDC authentication integration
  api/            Lightweight REST endpoints
  manage.py       Django management entry point
  Dockerfile      Python 3.10 app image
  node.Dockerfile Node.js image for USWDS asset compilation
  docker-compose.yml  Local dev environment (app + db + node + pa11y + owasp)
  Pipfile / Pipfile.lock   Python dependency declaration
  requirements.txt         Pinned Python deps (keep in sync with Pipfile)
  package.json / package-lock.json  Node deps (USWDS, pa11y-ci, sass)
  pyproject.toml  Black and mypy config
  mypy.ini        mypy Django-plugin config
  .flake8         flake8 config (max line length 120, migrations excluded)
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.10 |
| Web framework | Django 4.2 |
| Database | PostgreSQL (via psycopg2) |
| Auth | Login.gov via OIDC (`djangooidc`) |
| State machines | django-fsm (Domain, DomainRequest) |
| Email | AWS SES (boto3) |
| Frontend | U.S. Web Design System (USWDS 3.8.1) + Sass |
| Asset pipeline | `@uswds/compile` / gulp |
| Deployment | Cloud.gov (Cloud Foundry), Docker |
| Audit log | django-auditlog |
| Feature flags | django-waffle |

---

## Local development

The entire development environment is Docker-based.

```bash
cd src
cp .env-example .env      # add secrets (DJANGO_SECRET_KEY, DJANGO_SECRET_LOGIN_KEY)
docker compose build
docker compose up          # starts app (8080), db (5432), and node watcher
```

On startup the app container automatically runs:
1. `python manage.py migrate`
2. `python manage.py createcachetable`
3. `python manage.py load`   ← loads all fixtures / test data
4. `python manage.py runserver 0.0.0.0:8080`

Visit the running app at `http://localhost:8080`.

Environment variables for local dev are in `src/docker-compose.yml`. Secrets go in `src/.env` (never committed). The `.env-example` file shows the required keys.

---

## Running tests

Tests run **inside the Docker container** using Django's test runner.

```bash
cd src

# If the container is already running:
docker compose exec app ./manage.py test
docker compose exec app python -Wa ./manage.py test  # include deprecation warnings

# If no container is running yet:
docker compose run --rm app python manage.py test

# Run a specific test module or class:
docker compose exec app ./manage.py test registrar.tests.test_models
```

Tests are parallel-safe. The CI workflow runs them with `--parallel --verbosity 2`.

### Test helpers

`registrar/tests/common.py` contains shared test utilities:
- `less_console_noise` (context manager) — suppresses noisy but non-failing Django error output during tests.
- `less_console_noise_decorator` — decorator version of the above.
- `MockUserLogin` middleware — bypasses Login.gov in accessibility/security scans; add to `MIDDLEWARE` in settings.py **only while testing**, never commit.

---

## Linting

All linting runs inside Docker against the `app` service.

```bash
cd src

# Run all linters at once via the management command:
docker compose exec app ./manage.py lint

# Or run individual linters:
docker compose exec app flake8 . --count --show-source --statistics
docker compose exec app black --check .
docker compose exec app mypy .
docker compose exec app bandit -r .
```

| Linter | Purpose | Config |
|---|---|---|
| flake8 | Style / error checking | `src/.flake8` (max-line-length=120, migrations excluded) |
| black | Auto-formatting | `src/pyproject.toml` (line-length=120) |
| mypy | Type checking | `src/mypy.ini` + `src/pyproject.toml` |
| bandit | Security scanning | `src/.bandit` |

**Always run linters before and after changes.** The CI pipeline fails if any linter reports an error.

---

## Making database migrations

After changing any model:

```bash
docker compose exec app ./manage.py makemigrations
docker compose exec app ./manage.py migrate
```

Check that migrations are complete (required by CI):

```bash
docker compose run app ./manage.py makemigrations --dry-run --verbosity 3
docker compose run app ./manage.py makemigrations --check
```

Migrations live in `src/registrar/migrations/` and are auto-generated — do not edit them manually unless necessary. They are excluded from flake8 linting.

**PR titles including a migration must be suffixed with ` - MIGRATION`.**

---

## Key application concepts

### Models (`src/registrar/models/`)

All models extend `TimeStampedModel` which provides `created_at` and `updated_at` fields.

Key models:
- `Domain` — a registered `.gov` domain; uses `django-fsm` for lifecycle state (unknown → ready, on hold, deleted, etc.)
- `DomainRequest` — a government entity's request for a new domain; uses `django-fsm` for approval workflow states (started → submitted → in review → approved/rejected/etc.)
- `DomainInformation` — details attached to an approved domain
- `Portfolio` — an organization grouping multiple domains
- `User` — extends Django's `AbstractUser`; authenticated via Login.gov UUID
- `UserDomainRole`, `UserPortfolioPermission` — RBAC join models

### State machines

`Domain` and `DomainRequest` use `django-fsm` (`FSMField`, `@transition`). Always trigger transitions via the provided transition methods — never set `status` directly.

### EPP registry integration (`src/epplibwrapper/`)

Wraps `fred-epplib` to communicate with the `.gov` EPP registry. All registry calls are made through the singleton `CLIENT` (imported as `registry`). Interactions with the registry must be wrapped in try/except for `RegistryError`.

**For local development**, the registry is not available. To bypass the availability check when submitting a domain request locally, temporarily set `Domain.available()` to `return True`.

### Admin interface (`src/registrar/admin.py`)

Django Admin is heavily customized. Analyst users (staff) have limited views; full-access users (superusers) see everything. Fixtures in `src/registrar/fixtures/fixtures_users.py` define `ADMINS` and `STAFF` lists used to seed dev/sandbox environments.

### Views (`src/registrar/views/`)

Views use Django class-based and function-based views with HTMX for dynamic interactions. JSON views power datatable endpoints. Decorators in `registrar/decorators.py` enforce permission checks.

### Templates (`src/registrar/templates/`)

Django templates using USWDS components. `base.html` and `dashboard_base.html` are the main layout templates. Custom accessible components follow USWDS patterns.

### Frontend assets (`src/registrar/assets/`)

- USWDS Sass files live in `registrar/assets/_theme/`.
- The `node` Docker service watches for changes and recompiles automatically via gulp.
- Custom images go in `registrar/assets/img/registrar/` and must be force-added to git: `git add --force <img-file>` (the `/img/` directory is in `.gitignore`).
- Compiled assets are served from `registrar/public/`.

### Feature flags

django-waffle is used for feature flags. Check and modify flags via Django Admin or management commands. The `WaffleFlag` model in `registrar/models/waffle_flag.py` mirrors waffle flags for admin display.

---

## Branch and PR conventions

- **Branch naming**: `initials/issue-number-description` (e.g., `ab/1234-update-documentation`). Branches starting with `initials/` auto-deploy to a personal sandbox when a PR exists.
- **Merge strategy**: Merge and squash to main.  Never rebase main. 
- **PR title format**: `#issue_number: Descriptive name ideally matching ticket name - [sandbox]`
  - Add ` - MIGRATION` suffix if the PR includes a migration.
- **PR size**: Keep PRs small and focused.

---

## Dependency management

When adding or updating Python dependencies:
1. Update `Pipfile`.
2. Run `pipenv lock` to update `Pipfile.lock`.
3. **Also update `requirements.txt`** — both files must stay in sync (checked in PR review). The PR checklist explicitly requires this.

---

## Accessibility

Accessibility is a first-class concern.

- New pages **must** be added to `src/.pa11yci` for automated accessibility scanning.
- The pa11y-ci tool runs in CI (`docker compose run pa11y npm run pa11y-ci`).
- USWDS CSS classes follow the BEM naming convention.
- All UI changes must pass the [accessibility checklist](../docs/dev-practices/code_review.md).

---

## CI workflows (`.github/workflows/`)

The main test workflow is `test.yaml`. It runs on pushes/PRs to `main`:

| Job | What it does |
|---|---|
| `python-linting` | Runs flake8, black, mypy, bandit inside Docker |
| `python-test` | Runs Django tests with `--parallel` inside Docker |
| `django-migrations-complete` | Verifies no unmade migrations exist |
| `pa11y-scan` | Accessibility scan via pa11y-ci |

**All jobs build the Docker image** — changes to `Dockerfile` or `Pipfile.lock` affect all CI jobs.

Other notable workflows: `deploy-sandbox.yaml` (auto-deploys on push to personal branches with PRs), `security-check.yaml`, `migrate.yaml`, `reset-db.yaml`.

---

## Environments

| Name | Description |
|---|---|
| `stable` | Production |
| `staging` | Pre-production staging |
| `development` | Integration/dev environment |
| `<initials>` sandbox | Per-developer sandboxes on Cloud.gov |

All non-production environments use an **email allowlist** (`AllowedEmail` model). Add email addresses via fixtures or Django Admin before expecting emails to be delivered in sandboxes.

---

## Common errors and workarounds

| Error | Workaround |
|---|---|
| `Issued in the future` (OpenID login) | Re-sync system clock: `sudo sntp -sS time.nist.gov` |
| Domain availability check fails locally | Temporarily set `Domain.available()` to `return True` |
| CSS changes not reflected | Wait for the `node` watcher, or run `npx gulp compile` manually |
| Image not tracked by git | Use `git add --force <img-file>` (img/ is in .gitignore) |
| Windows line-ending issues in manage.py | Add `.gitattributes` with `* text eol=lf` or change global git setting |
| Tests print error noise that is not failures | Wrap test code in `less_console_noise()` context manager |
| Can't access /admin on local/sandbox | Add your Login.gov UUID to `ADMINS` or `STAFF` in `fixtures_users.py` and reload fixtures |

---

## Secrets

Never commit secrets. Secrets required locally:
- `DJANGO_SECRET_KEY` — Django secret key
- `DJANGO_SECRET_LOGIN_KEY` — Base64-encoded private key for Login.gov JWT
- AWS credentials (SES, S3) — optional for most development tasks

These go in `src/.env` (copied from `src/.env-example`).
