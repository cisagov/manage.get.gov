# AI Usage Policy

> **Status:** Draft — pending .gov team review.
> **Owner:** `@cisagov/dotgov` team.
> **Last reviewed:** _[CONFIRM: insert date on merge]_

This policy governs the use of AI coding assistants — including but not limited to OpenAI Codex, GitHub Copilot, Claude Code, Cursor, and similar tools — by anyone making changes to this repository.

---

## 1. Purpose

`manage.get.gov` is operated by the **Cybersecurity and Infrastructure Security Agency (CISA)** within the U.S. Department of Homeland Security. It administers the public `.gov` top-level domain. AI tools can meaningfully speed up the work, but they also introduce risks — privilege escalation, behavioral misalignment, and limited auditability among them — that require deliberate handling on a sensitive system.

This policy describes what AI tools may see, what they may do, and how the team is accountable for what they produce.

---

## 2. Authority and references

This policy is informed by:

- **CISA et al., _Careful Adoption of Agentic AI Services_** (May 2026). Joint guidance co-authored by CISA, NSA, ASD's ACSC, the Canadian Centre for Cyber Security, NCSC-NZ, and NCSC-UK. Governs the team's use of agentic and autonomous AI coding tools. <https://www.cisa.gov/resources-tools/resources/careful-adoption-agentic-ai-services>
- **CISA et al., _Principles for the Secure Integration of Artificial Intelligence in Operational Technology_** (December 2025). Co-authored by CISA, ASD's ACSC, NSA AISC, FBI, BSI, NCSC-NL, NCSC-NZ, NCSC-UK, and Cyber Centre. Scoped to operational technology; its four principles — understand AI, consider AI use in context, establish governance and assurance, embed safety and security practices — inform this policy. <https://www.cisa.gov/resources-tools/resources/principles-secure-integration-artificial-intelligence-operational-technology>
- **This repository's `CONTRIBUTING.md`**, which enumerates content excluded from the repo regardless of AI use: vendor and procurement information, PII from any source (including user interviews or feedback), user research documentation, compliance documentation that includes IP addresses, and secrets of any kind.
- **`AGENTS.md`** and **`CLAUDE.md`** at the repository root, which describe the secure development conventions every contributor — AI tool or human — is expected to follow.

This policy does not override any CISA, DHS, or contracting authority's policy that applies to a contributor by other means. _[CONFIRM: list any agency-level AI Acceptable Use Policy that takes precedence, or state "none" if no such policy exists for this system.]_

---

## 3. Who this policy applies to

- **`@cisagov/dotgov` team members and CISA contractors working on this repository**: bound by all sections.
- **External (community) contributors opening pull requests**: bound by Sections 4 (Data Boundaries — public data only), 6 (Prohibited Uses), and 7 (Human Accountability). Sections that reference internal sandboxes or credentials do not apply because external contributors do not have access to them.

If you are uncertain which category you fall into, treat yourself as an external contributor and ask in the issue or PR.

---

## 4. Data boundaries

AI tools handle data they are pointed at. What you can show them depends on where the data comes from.

### 4.1 What AI tools MAY be given

- **The entire public repository at <https://github.com/cisagov/manage.get.gov>**, including source code, tests, fixtures, documentation, configuration templates, and the public issue/PR history.
- **Fake / synthetic fixture data already committed to the repo** (e.g., `igorville.gov`, `exists.gov`, contents of `src/registrar/fixtures/`). This data is non-sensitive by design.
- **Public CISA documentation, RFCs, ADRs, and any other publicly published artifact** relevant to the work.
- **Content from non-production cloud.gov sandboxes** (e.g., your personal `getgov-<initials>` sandbox, shared development sandboxes) **— but only by `@cisagov/dotgov` team members** who already have legitimate access. Sandbox content must still be scrubbed of any real PII before being shown to an AI tool.

### 4.2 What AI tools MUST NOT be given

- **Any contents of `getgov-stable`** or any other production-equivalent environment. This includes screenshots, exported records, log excerpts, database rows, and pasted UI text.
- **Real production database exports**, full or partial, under any circumstance.
- **`.env` files or any rendered output of `cf env getgov-*`** — even from non-production sandboxes. These contain credentials (Login.gov client secrets, EPP passwords, Cloudflare API keys, AWS keys, Django `SECRET_KEY`s) that an AI tool's logs, training pipeline, or context window could leak.
- **Any data that is or could be PII** — real applicant names, real email addresses, real phone numbers, real domain-request payloads, real Login.gov UUIDs, real session identifiers, real user-research notes from `docs/research/`, real correspondence with applicants or organizations.
- **Compliance documentation containing IP addresses**, network diagrams of cloud.gov boundaries, or any artifact tagged for restricted distribution.
- **Production access of any kind**: no AI tool, agentic or otherwise, may operate against production credentials, production database connections, or production deploy targets. There are no exceptions.

When in doubt about whether a piece of data is in scope, treat it as out of scope and ask in `#getgov-dev`.

---

## 5. Approved patterns

These uses of AI tools are encouraged on this repository:

- **Code generation and refactoring** against the source tree, where the contributor reads and understands the output before committing.
- **Test writing**, including generating new tests against existing modules.
- **Documentation drafting** for `docs/`, ADRs, runbooks, and inline code comments.
- **Code review assistance** — asking an AI tool to surface likely issues in a diff, including a diff opened by a teammate.
- **Migration drafting**, with the human author responsible for verifying reversibility and zero-downtime safety before applying.
- **Investigative search and explanation** across the codebase (e.g., "where does this state transition happen", "explain this FSM").
- **Configuration and scaffolding** for new tests, views, and management commands.

The AI tool is a force multiplier for the contributor. It is not a substitute for understanding what is being committed.

---

## 6. Prohibited uses

These uses are not permitted on this repository, regardless of who is contributing:

- **Production access.** No AI agent, copilot, or autonomous tool may be granted production credentials, production database access, or production deploy authority. Period.
- **Generating or committing real credentials.** AI tools must not be asked to invent, scaffold, or "fill in" real-looking values for fields that contain secrets, even as examples. Use placeholders documented in `src/.env-example`.
- **Bypassing security controls.** AI tools must not be used to draft code that disables CSRF, CSP, HSTS, `SECURE_*` settings, `@login_required`, OIDC validation, or any other security control. The hard rules in `AGENTS.md` apply identically to AI-generated and human-written code.
- **Constructing SQL with string interpolation**, calling `subprocess` with `shell=True`, or invoking `eval()` / `exec()` / `pickle.loads()` / `yaml.load()` / `marshal.loads()` on request- or external-API-sourced input. If an AI tool suggests these patterns, reject the suggestion.
- **Reproducing content from `docs/research/`** or any user-research material — in code, comments, commit messages, PR descriptions, AI-tool conversations, or AI-generated documentation.
- **Logging PII** in code that AI tools generate, including via "verbose mode" or "debug" logging suggestions that include request bodies, email addresses, or user identifiers.
- **Expanding the scope of any credential** held by the system (Login.gov tokens, EPP credentials, Cloudflare keys, AWS IAM roles) to satisfy an AI tool's suggested implementation. Minimum-privilege wins; if an AI suggestion requires broader scope, the suggestion is wrong.
- **Sharing repository state with consumer-grade AI tools that train on input**, where the input may include any of the content listed in §4.2. _[CONFIRM: if the .gov team has standardized on specific approved tools — e.g., GitHub Copilot Business, Claude via API with ZDR, FedRAMP-authorized offerings — list them here and prohibit others.]_

---

## 7. Human accountability and disclosure

### 7.1 Accountability

**The human who opens a pull request is fully responsible for every line in it, regardless of how it was produced.** "Copilot wrote it" is not a defense for a security failure, a broken migration, or committed credentials. Before you push, you read the diff, you understand the diff, and you would defend the diff in code review.

### 7.2 Same review bar

AI-assisted pull requests receive the same review treatment as fully human-authored pull requests. CODEOWNERS routes the same way. CI must be green the same way. Reviewers apply the same standard. There is no expedited path and no second-class path.

### 7.3 Required disclosure

You must disclose AI involvement in two cases:

1. **The pull request was authored end-to-end by an autonomous AI agent** (e.g., GitHub Copilot coding agent, Codex cloud, Claude Code in non-interactive mode, or any tool operating without a human in the loop on each change). GitHub already marks these automatically; the requirement here is that the human assigning the work confirms in the PR description that they will review the output before merging.
2. **You used an AI tool to produce code, tests, or documentation that you did not substantively review** before submitting. This is rare and discouraged — but if it happens, say so in the PR description so reviewers can apply appropriate scrutiny.

Disclosure is not required for ordinary AI-assisted authorship where the human reviewed and understood every change. Disclosure is encouraged but optional when AI tooling was load-bearing on a non-obvious design decision, since that context helps reviewers.

### 7.4 Commit attribution

Commits authored end-to-end by a GitHub Copilot agent or similar will appear as such automatically in the commit log. Contributors are not required to add `Co-Authored-By:` trailers for ordinary AI assistance.

---

## 8. Tool configuration requirements

_[CONFIRM: the .gov team should specify which of the following are mandatory before this section is binding. The defaults below are conservative.]_

- **Use organization-licensed tooling where available.** _[CONFIRM: list which tools the .gov team has procured under terms that prohibit training on input — e.g., GitHub Copilot Business/Enterprise, Claude Team/Enterprise, etc.]_
- **Disable training on input** in any tool that offers the option. Verify the setting per session; some tools default to training enabled on free or personal tiers.
- **Set content exclusions** in Copilot at the organization level for the cisagov organization to exclude paths that have ever held sensitive content (`src/.env*`, `docs/research/`, any path matching `*secrets*`, `*credentials*`, `*.pem`, `*.key`).
- **Never paste credentials, tokens, or secrets** into an AI tool's chat window, even for "explain this" purposes. Redact before pasting.
- **Be deliberate about agent permissions.** Per CISA's _Careful Adoption of Agentic AI Services_, agentic tools should run with the minimum permissions required for the task. Do not grant a coding agent write access to branches, repos, or services it does not need.

---

## 9. Incident response

If you believe AI tool use on this repository has resulted in:

- A secret, credential, or token being exposed (in the repo, in an AI tool's chat history, or in any third-party log);
- Real PII being shared with an AI tool;
- Production data being shared with an AI tool;
- Production access being granted to an AI agent;

**Stop, do not push or merge anything else, and report immediately to the `@cisagov/dotgov` team lead and CISA security.** _[CONFIRM: insert the .gov team's preferred reporting channel — e.g., a Slack channel name, an email alias, or a specific incident form URL.]_

Suspected exposure of a Login.gov, EPP, Cloudflare, or AWS credential triggers the standard secrets rotation runbook (`docs/operations/runbooks/rotate_application_secrets.md`).

---

## 10. Policy review

This policy is reviewed by the `@cisagov/dotgov` team at minimum **every six months** and after any of the following:

- A new CISA or DHS AI policy is published that affects this system;
- The team adopts a new class of AI tool not anticipated in this version;
- An incident occurs that this policy did not anticipate;
- A material change to the system's architecture or trust boundary (e.g., new external integration, new identity provider).

Proposed changes are made via pull request. The PR must be reviewed by at least one `@cisagov/dotgov` team member with security authority for the system.

---

## 11. Open items

These items were left explicitly unresolved in the v1 draft and should be filled in before this policy is treated as binding:

- [ ] Insert effective date and review date in the header.
- [ ] List any CISA / DHS agency-level AI Acceptable Use Policy that takes precedence over §2.
- [ ] In §6, list specifically approved and specifically prohibited AI tools by name and tier.
- [ ] In §8, specify which tool configuration requirements are mandatory vs. recommended for the .gov team's procured tooling.
- [ ] In §9, insert the canonical reporting channel.
- [ ] Decide whether this policy applies to AI use in adjacent activities (issue triage, PR summaries, design research, written documentation outside the repo) or only to code contributions.