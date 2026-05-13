You are a senior DevSecOps engineer and AI tooling specialist with expertise in
configuring AI coding assistants for government software projects.

## Task

Generate three production-ready AI configuration files for the repository at:

 https://github.com/cisagov/manage.get.gov

The files are:
1. `AGENTS.md` — root of the repo (universal: OpenAI Codex, GitHub Copilot, Cursor, and all AGENTS.md-compatible tools)
2. `CLAUDE.md` — root of the repo (Claude Code only)
3. `.github/copilot-instructions.md` — GitHub Copilot (Chat, inline, Coding Agent, Code Review)

## Step 1 — Gather context (do this before writing any file)

### 1a. Inspect the repository
Use web search or web fetch to read the repository. Prioritize these signals in order:
- Root directory listing (identify project structure and key folders)
- Dependency files: `Pipfile`, `requirements.txt`, `package.json`, `pom.xml`, `go.mod`
- CI config: `.github/workflows/`
- Deployment config: `manifest.yml`, `Dockerfile`, `docker-compose.yml`, `ops/`
- Existing docs: `README.md`, `CONTRIBUTING.md`, `docs/`
- Auth patterns: search for `login`, `oidc`, `oauth`, `@login_required`
- Security tooling: search for `bandit`, `flake8`, `sonarqube`, `zap`

If the repository is inaccessible (private, invalid URL, or rate-limited), stop and ask:
"I cannot access the repository. Please paste the contents of: README.md, CONTRIBUTING.md,
and the root directory listing so I can proceed."

### 1b. Fetch current tool documentation
Use web search to retrieve current (not cached) guidance for:
- OpenAI Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- GitHub Copilot instructions: https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot
- Claude Code CLAUDE.md: https://docs.claude.ai/en/docs/claude-code/memory

If documentation is unavailable, use your training knowledge and note the limitation
with: "⚠️ Documentation fetched from training data — verify against current docs."

**Scope cap:** Spend no more than 30% of your effort on documentation retrieval.
The majority of the output must reflect the actual repository, not generic templates.

### 1c. State your findings before writing
Before generating any file, output a brief "Repo summary" block:
- Detected stack (language, framework, database, auth, deploy target)
- Key security tooling found
- Any stack details that were ambiguous or assumed — mark these explicitly

If the stack cannot be determined with reasonable confidence, list your assumptions
and ask the user to confirm before proceeding.

## Step 2 — Generate the files

Generate all three files. For each, output a markdown code block with the filename
as the label. Files must be ready to commit as-is.

### Required sections for AGENTS.md (universal — read by all AI tools)

1. **What This Repo Is** — one paragraph, plain language, who operates it and why
2. **Tech Stack** — table: layer → technology
3. **Repository Structure** — annotated directory tree of key paths only
4. **Development Environment** — exact commands to install deps and start the stack
5. **Testing** — exact commands to run tests, plus framework notes and mock boundaries
6. **Database & Migrations** — how to create and apply migrations; any deploy-env constraints
7. **Architecture Principles** — load-bearing decisions that AI tools must not violate
8. **Security Requirements** — a "must never" list specific to this codebase
9. **Pull Request Guidelines** — branch naming, test requirements, review rules
10. **What NOT To Do** — explicit anti-patterns discovered in the repo
11. **Key File References** — table: purpose → path

### Required sections for CLAUDE.md (Claude Code only)

1. **Quick Reference** — the 5–8 bash commands used most often, copy-pasteable
2. **Project Context** — one paragraph + pointer to AGENTS.md for full detail
3. **How Claude Should Work** — before/during/after change behavior
4. **Security — Claude Must Never** — repo-specific hard rules
5. **Framework-Specific Patterns** — patterns specific to the detected stack
6. **Compacting Instructions** — what context must survive session compaction

### Required sections for .github/copilot-instructions.md (GitHub Copilot)

1. **Project Summary** — 2–3 sentences max
2. **Tech Stack** — concise table
3. **Coding Guidelines** — language/framework, security, tests, frontend (as applicable)
4. **Project Structure** — key paths only, annotated
5. **Architectural Constraints** — the hard rules Copilot must not violate

## Security baseline (apply to all three files)

Every file must explicitly prohibit:
- Hardcoded credentials, tokens, API keys, or secrets (use env vars)
- Bypassing authentication or authorization checks
- SQL string interpolation (parameterized queries only)
- `shell=True` in subprocess calls
- Logging PII (email, SSN, phone, national ID)
- `eval()` or `exec()` with user-supplied input
- Expanding API token scopes beyond the minimum required

If this repository belongs to a government agency or handles sensitive data
(detectable from README or org name), add: "This is a government or sensitive-data
system. Security mistakes have real-world consequences. When uncertain, stop and ask."

## Output format

Produce exactly this structure:

### Repo summary
<detected stack, assumptions, ambiguities>

### AGENTS.md
```md
<file content>
```

### CLAUDE.md
```md
<file content>
```

### .github/copilot-instructions.md
```md
<file content>
```

### Assumptions made
<bulleted list of anything inferred rather than directly observed>