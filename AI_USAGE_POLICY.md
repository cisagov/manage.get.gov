# AI Usage Policy

> **Status:** Draft — starting point for `@cisagov/dotgov` team review. Not in effect. The team will iterate on this together before it becomes binding.
> **Owner:** `@cisagov/dotgov` engineering team.
> **Audience:** every contributor (internal staff, CISA contractors, and external community contributors) who uses an AI tool while working on this repository.
> **Companion documents:** `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, and `CONTRIBUTING.md` — those describe the conventions and constraints that AI-generated code must satisfy. This document describes how AI tools themselves may be used.

---

## 1. Purpose

`manage.get.gov` is operated by the **Cybersecurity and Infrastructure Security Agency (CISA)** within the U.S. Department of Homeland Security. It administers the public `.gov` top-level domain. AI tools can meaningfully speed up development, but they also introduce risks — leaked credentials, leaked PII, behavioral misalignment, and reduced auditability — that require deliberate handling on a sensitive system.

This policy defines what AI tools may see, what they may do, and how contributors stay accountable for what those tools produce. The goal is to allow productivity gains from AI-assisted development while protecting security, privacy, code quality, and contributor accountability.

When uncertain, stop and ask before using AI-generated output or sharing repository context with an AI tool.

---

## 2. Scope

This policy applies to every contributor — `@cisagov/dotgov` team members, CISA contractors, and external community contributors — and to every form of AI-assisted work on this repository, including:

- Code generation
- Code review
- Refactoring
- Test generation
- Documentation drafting
- Debugging
- Architecture suggestions
- Security analysis
- PR descriptions or release notes
- Issue triage and summaries

Internal contributors and contractors are bound by every section below. **External (community) contributors** are bound by §3 (Data Boundaries — public data only), §5 (Prohibited Uses), §6 (Restricted Areas), §7 (Human Accountability), §8 (Prompting Guidelines), and §11 (Incident Handling). Sections that reference internal sandboxes or credentials do not apply because external contributors do not have access to them. If you are uncertain which category you fall into, treat yourself as an external contributor and ask in the issue or PR.

> **A note on tooling reality.** The `@cisagov/dotgov` program does not currently provide AI tools to the team. Contributors use whatever they have access to — free tiers, personal paid plans, or whatever their employer or contracting company provides. That's fine. The rules in this policy apply to *every* tier, not just enterprise tiers, and the contributor is responsible for using the strongest privacy and data-handling settings their tool offers.

This policy does not override any CISA, DHS, or contracting authority policy that applies to a contributor by other means. Where this policy and a higher authority disagree, the higher authority controls.

---

## 3. Approved AI Tool Categories

Contributors may use the following AI tools, subject to this policy:

- GitHub Copilot (chat, inline, agent, code review)
- OpenAI Codex
- Claude Code
- Cursor
- ChatGPT web app
- Claude web app

If you have access to a paid or enterprise tier of any of these tools (through personal subscription or your employer / contracting company), prefer it over the free tier — paid tiers generally carry stronger data-handling terms. Either way, you are responsible for checking your tool's current data-retention and training-on-input settings before sharing repository content (see §10.3).

Use of any other AI tool requires a quick check with the team before it is given any repository content, logs, screenshots, configuration files, or implementation details. The default assumption for an unreviewed tool is that its inputs are retained, used for training, and visible to its operator.

---

## 4. Data Boundaries

AI tools handle the data they are pointed at. What you may show them depends on where the data comes from.

### 4.1 What AI tools MAY be given

- The entire public repository at <https://github.com/cisagov/manage.get.gov>, including source code, tests, fixtures, documentation, configuration templates, and the public issue / PR history.
- Synthetic fixture data already committed to the repo (for example, `igorville.gov`, `exists.gov`, contents of `src/registrar/fixtures/`). This data is non-sensitive by design.
- Public CISA documentation, RFCs, ADRs, and any other publicly published artifact relevant to the work.
- Content from non-production cloud.gov sandboxes (a personal `getgov-<initials>` sandbox, shared dev sandboxes) — **only by `@cisagov/dotgov` team members or contractors** who already have legitimate access. Sandbox content must still be scrubbed of any real PII before being shown to an AI tool.

### 4.2 What AI tools MUST NOT be given

**Production data.** Production data must never be shared with AI tools, in any form. This includes, but is not limited to:

- Production database records
- Production logs
- Production user data
- Domain requester data and domain manager data
- Email addresses, phone numbers, mailing addresses
- SSNs, EINs, or other national / organizational identifiers
- Any other personally identifiable information (PII)
- Registry-sensitive data and DNS-sensitive data
- Cloud.gov environment output (including any rendering of `cf env getgov-*`)
- Vendor account details and procurement information

**PII.** No PII is allowed in AI prompts, screenshots, pasted logs, pasted stack traces, uploaded files, generated examples, or AI-assisted debugging sessions — regardless of source. Always redact or replace PII before involving an AI tool. Use safe placeholders such as:

```text
user@example.test
example.gov
REDACTED_TOKEN
REDACTED_EMAIL
REDACTED_DOMAIN
REDACTED_ACCOUNT_ID
```

**Secrets and credentials.** Never share secrets with AI tools, even for "explain this" purposes. This includes:

- API keys
- Access tokens and refresh tokens
- Session cookies
- Private keys and certificates
- Cloud.gov credentials
- Login.gov client IDs and secrets
- AWS credentials (access keys, IAM role outputs)
- DNS vendor (Cloudflare) credentials
- Registry / EPP credentials
- `.env` files of any flavor
- Environment-variable dumps
- CI/CD secrets and tokens
- OAuth / OIDC client secrets

Do not paste full configuration files into an AI tool if they contain secrets or sensitive deployment details. Redact first.

**Restricted documentation.** Do not share with AI tools:

- Anything pulled from `getgov-stable` or any production-equivalent environment (screenshots, exported records, log excerpts, database rows, pasted UI text).
- Real production database exports, full or partial.
- User research notes from `docs/research/` or anywhere else (excluded from the repo by policy in `CONTRIBUTING.md`).
- Compliance documentation containing IP addresses, network diagrams of cloud.gov boundaries, or any artifact marked for restricted distribution.
- Non-public incident details, procurement-sensitive information, or internal-only operational details.

**Production access.** No AI tool — agentic or otherwise — may operate against production credentials, production database connections, production deploy targets, or production-equivalent sandboxes. There are no exceptions.

When in doubt about whether a piece of data is in scope, treat it as out of scope and ask through the team's standard channel before sharing it.

---

## 5. Acceptable and Prohibited Use

### 5.1 Acceptable use

AI tools may be used for:

- Explaining existing public repository code.
- Drafting tests for contributor review.
- Suggesting refactors that preserve behavior.
- Improving documentation and drafting ADRs, runbook prose, and inline comments.
- Summarizing non-sensitive errors after redaction.
- Creating PR descriptions, release notes, or commit-message summaries from reviewed changes.
- Generating boilerplate that follows existing project patterns.
- Identifying potential edge cases and surfacing likely issues in a diff.
- Reviewing code for readability or maintainability.
- Suggesting security questions for human review.
- Drafting migrations, with the human author responsible for verifying reversibility and zero-downtime safety before applying.
- Configuration and scaffolding for new tests, views, and management commands.

All AI-generated output must be reviewed and validated by the contributor before being committed.

### 5.2 Prohibited use

Contributors must not use AI tools to:

- Process production data, PII, unredacted logs, unredacted stack traces, `.env` files, certificates, private keys, or any other secret.
- Generate or modify code that bypasses authentication or authorization (`@login_required`, `@permission_required`, `UserPassesTestMixin`, analyst / admin / portfolio / requester / domain-manager checks).
- Generate or modify code that disables or weakens CSRF, CSP, HSTS, secure cookies, `SECURE_*` settings, audit logging, or any security middleware (`LoginRequiredMiddleware`, `RestrictAccessMiddleware`, CSRF middleware, CSP middleware, `auditlog` middleware).
- Expand API token, IAM role, or OIDC scope beyond the minimum required for the task.
- Construct SQL with string interpolation, `%` formatting, or f-strings.
- Introduce `shell=True` in subprocess calls.
- Use `eval()`, `exec()`, `pickle.loads`, `yaml.load` (use `yaml.safe_load`), or `marshal.loads` on data sourced from a request, an upload, or any external API.
- Create tests that depend on live EPP, Cloudflare / DNS, AWS, or Login.gov calls.
- Produce changes the contributor does not understand.
- Submit AI-generated code without human review.
- Invent or "fill in" real-looking values for fields that hold secrets, even as examples — use the placeholders documented in `src/.env-example`.
- Reproduce content from `docs/research/` or any user-research material in code, comments, commit messages, PR descriptions, AI-tool conversations, or AI-generated documentation.
- Share repository state with consumer-grade AI tools that train on input where that state includes any of the content listed in §4.2.

If an AI tool suggests a pattern that violates any of the above, reject the suggestion. The hard rules in `AGENTS.md` apply identically to AI-generated and human-written code.

---

## 6. Restricted Areas Requiring Extra Care

AI tools may assist with these areas, but contributors must apply heightened scrutiny and ensure human review covers the risk. Prefer small, focused PRs with explicit review notes:

- Login.gov / OIDC authentication
- Authorization and permission checks (admin, analyst, requester, portfolio, domain-manager)
- CSRF, CSP, HSTS, and security-header configuration
- LoginRequiredMiddleware, RestrictAccessMiddleware, and other security middleware
- Audit logging (`django-auditlog`)
- DNS hosting integrations (Cloudflare and any vendor)
- EPP registry integrations
- AWS SES, AWS S3, and other cloud integrations
- Database migrations and data migrations
- PII handling, logging behavior, and redaction
- Environment files, certificates, secrets, API keys
- CI / CD configuration and cloud.gov deployment configuration
- Anything that touches the `registrar.User` model or session handling

---

## 7. Human Accountability and Disclosure

### 7.1 Accountability

**The human who opens a pull request is fully responsible for every line in it, regardless of how it was produced.** "Copilot wrote it" is not a defense for a security failure, a broken migration, or committed credentials. Before you push, you read the diff, you understand the diff, and you would defend the diff in code review.

The contributor is responsible for:

- Understanding every submitted change.
- Verifying correctness and security impact.
- Running appropriate tests.
- Ensuring generated code follows project conventions and existing service boundaries.
- Ensuring no sensitive data was shared with or generated by AI tools.
- Ensuring no AI output introduces licensing, security, or privacy risk.

Do not submit AI-generated code that you cannot explain, test, or maintain.

### 7.2 Same review bar

AI-assisted pull requests receive the same review treatment as fully human-authored pull requests. CODEOWNERS routes the same way. CI must be green the same way. Reviewers apply the same standard. There is no expedited path and no second-class path.

### 7.3 Disclosure in PR descriptions

AI use does not need to be disclosed in commit messages or code comments. Disclose AI involvement in the PR description when AI assistance materially influenced:

- Architecture
- Security-sensitive logic
- Authentication or authorization behavior
- Database migrations or data migrations
- Large refactors
- Generated tests that define expected behavior

You must also disclose when:

1. **The PR was authored end-to-end by an autonomous AI agent** (Copilot coding agent, Codex cloud, Claude Code in non-interactive mode, or any tool operating without a human in the loop on each change). GitHub already marks these automatically; the assigning human confirms in the PR description that they reviewed the output before merging.
2. **You used an AI tool to produce code, tests, or documentation you did not substantively review** before submitting. This is rare and discouraged — but if it happens, say so in the PR description so reviewers can apply appropriate scrutiny.

Suggested disclosure text:

> AI assistance was used to draft or review portions of this change. I reviewed the output, verified the behavior, and take responsibility for the final implementation.

### 7.4 PR attestation

Every PR description should include this attestation (a copy-paste checklist for the template is fine):

- [ ] I reviewed this change and understand its behavior.
- [ ] I verified this change does not include secrets, credentials, or PII.
- [ ] I ran the relevant tests / checks or documented why they were not run.
- [ ] I accept responsibility for this change, including any AI-assisted portions.

---

## 8. Prompting Guidelines

When prompting an AI tool, give it the minimum context needed.

Prefer prompts such as:

- "Given this redacted Django view, suggest test cases for permission handling."
- "Review this redacted function for readability and edge cases. Do not change authentication behavior."
- "Generate a Django test outline for this behavior using placeholder names only."

Avoid prompts such as:

- "Here are production logs. Find the bug."
- "Here is my `.env` file. Configure the app."
- "Here is a real user record. Write a migration."
- "Bypass this permission check so the test passes."

---

## 9. Code Quality and Testing Expectations

### 9.1 Code quality

AI-assisted code must meet the same standards as human-written code. Contributors must ensure AI-assisted changes:

- Follow existing repository conventions.
- Are readable and maintainable.
- Are appropriately scoped — no drive-by refactors.
- Include tests where behavior changes.
- Do not duplicate existing logic unnecessarily.
- Do not bypass established service boundaries (EPP, Cloudflare, AWS, Login.gov, audit logging).
- Do not weaken security posture.
- Do not introduce unapproved dependencies.
- Do not create unreachable or unused code.
- Do not add comments that merely restate obvious code.

### 9.2 Testing

Before submitting AI-assisted changes, run the tests and checks appropriate to the change. At minimum:

- Run targeted tests for the touched area.
- Run broader test suites when changing shared models, services, settings, middleware, or permissions.
- Run migration checks (`makemigrations --dry-run` and `--check`) when models change.
- Run pa11y and check the affected pages visually when templates, assets, or user-facing flows change.
- Run Bandit and consider OWASP ZAP when security-sensitive code changes.

AI-generated tests are not sufficient on their own. Review them for meaningful assertions and realistic behavior. Reject shallow tests that only verify implementation details or duplicate the generated code's assumptions.

### 9.3 AI-generated security suggestions

AI-generated security suggestions are recommendations, not authority. Before applying one:

- Confirm the behavior against existing project patterns.
- Check whether the change affects authentication or authorization.
- Check whether the change affects sensitive data handling.
- Check whether the change affects deployment or production behavior.
- Add tests that prove the intended security behavior.
- Request human review through the normal PR process.

When uncertain, do not merge until the security impact is understood.

---

## 10. Documentation, Dependencies, and Tool Configuration

### 10.1 Documentation

AI tools may be used to draft or edit documentation, provided no sensitive information is included. Do not use AI tools to process or summarize:

- Non-public incident details
- Production data
- Research participant information
- Procurement-sensitive information
- Compliance documents containing sensitive infrastructure details
- Internal-only operational details, unless explicitly approved

### 10.2 Dependencies and licensing

Do not accept AI suggestions to add new packages, libraries, services, or licenses without human review. Before adding a dependency, verify:

- The dependency is necessary.
- The license is acceptable for federal-government use.
- The package is actively maintained.
- The package does not introduce avoidable security risk.
- The dependency is compatible with cloud.gov deployment.

### 10.3 Tool configuration

The team does not currently provide AI tools centrally. Each contributor is responsible for configuring whatever tool they bring with them.

- **Disable training on input** in any tool that offers the option. Verify the setting per session — many tools default to training-enabled on free or personal tiers.
- **Prefer a paid tier over the free tier** if you have access to one. Paid tiers generally have stronger retention and training guarantees.
- **Configure content exclusions if your tool supports them.** If you use Copilot and your personal or employer account has access to content-exclusion settings, exclude paths that have ever held sensitive content: `src/.env*`, `docs/research/`, and anything matching `*secrets*`, `*credentials*`, `*.pem`, `*.key`. If your tier does not support exclusions, treat those paths as off-limits to the tool yourself — do not open them while the tool is reading your workspace.
- **Never paste credentials, tokens, or secrets** into an AI tool's chat window, even for "explain this" purposes. Redact before pasting.
- **Be deliberate about agent permissions.** Run agentic tools with the minimum permissions required for the task. Do not grant a coding agent write access to branches, repos, or services it does not need.
- **Know what your tool sends.** Some IDE plugins quietly upload the open file, the surrounding workspace, or terminal output. If you do not know what your tool sends, do not point it at this repo until you do.

For step-by-step VS Code setup (install, sign-in, verify), see `docs/developer/ai-tool-setup.md`.

### 10.4 Repository instruction files

This repository ships Markdown files that AI coding tools read for project context. They are guidance, not enforcement — a tool can still suggest something that violates them, which is why human review is the final check.

| Tool | File it reads | Where it lives |
| --- | --- | --- |
| OpenAI Codex, Cursor, Aider, Windsurf, and other AGENTS.md-aware tools | `AGENTS.md` | repo root |
| Claude Code | `CLAUDE.md` (and `AGENTS.md`) | repo root |
| GitHub Copilot (Chat) | `copilot-instructions.md` | `.github/` |
| ChatGPT or Claude web app | No automatic discovery | contributor pastes redacted context manually |

**Open the repo from its root** so AI tools can find these files. Opening a subfolder will cause the tool to fall back to generic behavior.

**Note on GitHub Copilot:** only Copilot Chat reads `copilot-instructions.md`. Inline gray-text completions do not. For higher-stakes changes (auth, FSM transitions, migrations, security middleware), use Copilot Chat or another tool — don't rely on inline suggestions alone.

### 10.5 Minimum safe workflow

For AI-assisted IDE work:

1. Pull the latest `main`.
2. Create a branch named `<initials>/<issue#>-<topic>`.
3. Open the repository root in your IDE.
4. Confirm your AI tool is using the right instruction file (see §10.4).
5. Give the tool only the minimum context it needs.
6. Keep changes small and reviewable.
7. Review every suggestion before accepting it.
8. Run the relevant tests and lints.
9. Confirm no secrets, credentials, or PII were introduced.
10. Submit through the normal PR process with human review.

### 10.6 Tool output is not policy

If an AI tool suggests something that conflicts with this policy, the repo's security requirements (`AGENTS.md`), or existing project architecture, reject the suggestion. The policy, the repository instruction files, the tests, and the human review process all take precedence over AI-generated suggestions.

---

## 11. Incident Handling

If you believe AI tool use on this repository has resulted in:

- A secret, credential, certificate, or token being exposed (in the repo, in an AI tool's chat history, or in any third-party log);
- Real PII being shared with an AI tool;
- Production or production-equivalent data being shared with an AI tool;
- Production access being granted to an AI agent.

Then:

1. **Stop work immediately.** Do not push, merge, or run anything else against the affected scope.
2. **Notify the `@cisagov/dotgov` team lead** through the team's standard internal channel, following the team's incident-reporting process.
3. **Rotate affected secrets or credentials** per `docs/operations/runbooks/rotate_application_secrets.md`. Suspected exposure of a Login.gov, EPP, Cloudflare, or AWS credential triggers the standard secrets-rotation runbook.
4. **Remove exposed sensitive data** from prompts, local files, branches, commits, or PRs where possible. Note: removing content from a third-party AI tool's chat history may not be possible — assume it persists.
5. **Document the exposure** according to the team's incident-response process so review and follow-up actions can run.

Do not attempt to quietly fix or hide accidental exposure. Disclosure inside the team is mandatory; the team will handle external disclosure if it is required.

---

## 12. Summary

AI tools are allowed as engineering assistants, not autonomous contributors. Contributors must protect sensitive data, preserve security controls, validate generated output, and remain accountable for every submitted change. When the policy and the prompt disagree, the policy wins.

---

## 13. Policy and instruction-file review

### 13.1 This policy

This policy is reviewed by the `@cisagov/dotgov` team at minimum **every six months** and after any of the following:

- A new CISA or DHS AI policy is published that affects this system.
- The team adopts a new class of AI tool not anticipated in this version.
- An incident occurs that this policy did not anticipate.
- A material change to the system's architecture or trust boundary (a new external integration, a new identity provider, a new data sink).

Proposed changes are made via pull request. The PR must be reviewed by at least one `@cisagov/dotgov` team member with security authority for the system.

### 13.2 Instruction files (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`)

The per-tool instruction files drift faster than the policy because they describe concrete codebase facts (apps, commands, conventions) that change over time. To keep them useful instead of misleading:

- **Quarterly refresh.** The `@cisagov/dotgov` team owner reviews all three files at least quarterly and after any material codebase change (new Django app, new external integration, changes to lint or test commands, new security middleware, branch/PR conventions changing). The check is: pull `main`, skim each file, and update any line that no longer matches reality.
- **Treat the files as living documentation.** A stale instruction file is worse than no instruction file — it gives AI tools wrong context confidently. If you notice something stale while working, fix it in the same PR or open a follow-up.
- **Out-of-band updates are encouraged.** Any contributor can open a PR to correct a stale fact without waiting for the quarterly cycle.

(This addresses the decay concern raised in PR #4919 — AGENTS-style files do drift, so the response is a scheduled refresh plus low-friction in-line corrections, not "set it and forget it.")

---

## 14. Adoption follow-ups

Tracked here so the operational pieces this policy depends on are not forgotten. None of these block the policy from being written; they block it from being *enforced*.

- [ ] **Pull request template.** The §7.4 attestation checklist must land in `.github/pull_request_template.md` so every PR pre-fills it. Without this, the attestation is policy text that no one is forced to see.
- [ ] **Copilot custom instructions location.** Move `copilot-instructions.md` (currently at repo root as a draft) to `.github/copilot-instructions.md` so GitHub Copilot actually picks it up.
- [ ] **Reporting channel.** Section 11 currently says "the team's standard internal channel" — replace with the team's actual incident-reporting destination once decided (Slack channel name, email alias, ticket queue, or a link to the team's incident runbook).
- [ ] **Approved-tools list refresh.** Section 3 lists tool *categories*. If the team ever does get centrally-provided AI tools, this section should be updated to name them. For now it stays generic because each contributor uses their own.
- [ ] **Content-exclusion guidance.** Section 10.3 describes what to do if your tool supports content exclusions. If the team converges on a specific recommended tool / tier, we can replace the generic guidance with concrete setup steps.
- [ ] **Higher-authority AUPs.** Section 2 says agency-level CISA / DHS AI Acceptable Use Policies, if any, take precedence. Decide whether to enumerate them here or leave the deference clause general.
