# AI tool setup in VS Code

> **Status:** Draft — starting point for `@cisagov/dotgov` team review. Pair this with `AI_USAGE_POLICY.md` (the rules) — this file is how to set up the tools so they follow those rules.

This guide gets VS Code configured so the three AI instruction files in this repo (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`) are actually picked up by the tools they target.

You only need the sections for tools you actually use. Most contributors have Copilot and Claude Code; Codex is optional.

---

## Before you start

- **VS Code** installed — <https://code.visualstudio.com/>
- **Docker Desktop** installed and running — the dev stack runs in Docker (see `docs/developer/README.md`)
- **Repo cloned** and opened as the workspace root: `File → Open Folder → manage.get.gov`. The file tree should show `AGENTS.md`, `CLAUDE.md`, `src/`, and `.github/` at the top level. If you opened a subfolder, the AI tools will not find the instruction files.
- **GitHub account** signed in to VS Code — click the Accounts icon in the activity bar.

VS Code will prompt to install the repo's recommended extensions on first open (Python, Pylance, Django, Docker, EditorConfig, GitLens, Copilot, Copilot Chat, Claude Code). Accept those.

---

## Which file each tool reads

| Tool | File it reads | Where it lives |
|---|---|---|
| OpenAI Codex, Cursor, Aider, Windsurf (any AGENTS.md-aware tool) | `AGENTS.md` | repo root |
| Claude Code | `CLAUDE.md` (and `AGENTS.md`) | repo root |
| GitHub Copilot (Chat) | `copilot-instructions.md` | `.github/` |
| ChatGPT / Claude web app | nothing automatic | you paste redacted context manually |

These files don't run anywhere — they're just project background the tool reads before suggesting code.

---

## 1. GitHub Copilot

### Install

1. Open Extensions (`Ctrl/Cmd+Shift+X`).
2. Install **GitHub Copilot** (`GitHub.copilot`).
3. Install **GitHub Copilot Chat** (`GitHub.copilot-chat`).
4. Reload VS Code when prompted.

### Sign in

Sign in with the GitHub account that has a Copilot license. If VS Code does not prompt, run `GitHub Copilot: Sign In` from the command palette (`Ctrl/Cmd+Shift+P`).

### Settings to confirm

The repo ships `.vscode/settings.json` with `github.copilot.chat.codeGeneration.useInstructionFiles` set to `true` — this is what makes Copilot Chat read `copilot-instructions.md`. Verify it is still on after VS Code merges your personal settings.

At <https://github.com/settings/copilot> (account level, do once):

- **Suggestions matching public code:** Block.
- **Allow GitHub to use my code snippets for product improvements:** Off.

### Verify it works

1. Open Copilot Chat (`Ctrl/Cmd+Alt+I` or click the chat icon).
2. Ask: *"What rules should you follow when writing code for this repo?"*
3. Copilot should mention things specific to this project: single Django app, `django-fsm` for state changes, USWDS, no PII in logs, etc. A generic answer ("follow best practices, write clean code") means the file is not being read — check that `.github/copilot-instructions.md` exists and that VS Code opened the repo root.

### Important caveat

Only **Copilot Chat** reads `copilot-instructions.md`. Inline gray-text completions do **not**. For higher-stakes changes (auth, FSM transitions, migrations, security middleware), use Copilot Chat — don't rely on inline suggestions alone.

---

## 2. Claude Code

Claude Code is Anthropic's CLI agent. It runs in the integrated terminal and can also be used via a VS Code extension.

### Install (CLI)

In the integrated terminal (`` Ctrl/Cmd+` ``):

```bash
npm install -g @anthropic-ai/claude-code
```

Requires Node.js 18+ (`node --version`). If Node is not installed, get it from <https://nodejs.org/>.

### Sign in

From the repo root:

```bash
claude
```

First run opens a browser for sign-in. Use the email tied to your Claude Pro or Max subscription.

### Optional: VS Code extension

Anthropic publishes a VS Code extension (`anthropic.claude-code`) that surfaces Claude inside the editor with selection-aware actions ("Explain this", "Refactor this"). It shells out to the same `claude` CLI and reads the same `CLAUDE.md` / `AGENTS.md`.

### Settings

The repo ships `.claude/settings.json` with pre-approved safe commands (`docker compose *`, `./manage.py *`, read-only git) and pre-denied risky ones (`cf push *`, `cf delete *`, `cf env getgov-stable*`, `rm -rf *`, force-push). Claude will still prompt for anything outside both lists.

### Verify it works

From the repo root:

```bash
claude
```

Then in the Claude prompt: *"What should you know about this repo before writing code?"*

Expected: Claude summarizes the project as CISA's `.gov` registrar, mentions the single Django app, the FSM rule, Login.gov OIDC, and the security rules. A generic answer means you're not in the repo root or the files weren't committed.

You can also run `/memory` inside Claude Code to see which memory files are loaded — `CLAUDE.md` and `AGENTS.md` should both appear.

---

## 3. OpenAI Codex (optional)

`AGENTS.md` is what Codex, Cursor, Aider, and Windsurf all read. The most common way to use it from VS Code is the Codex CLI plus the optional Codex extension.

### Install

In the integrated terminal:

```bash
npm install -g @openai/codex
```

Optional VS Code extension: install **OpenAI Codex** (`openai.chatgpt`) from the Extensions view.

### Sign in

```bash
codex
```

Browser opens for sign-in. Use the email tied to your ChatGPT or OpenAI account.

### Settings (optional)

Codex reads `AGENTS.md` automatically when run from the repo root. No VS Code setting toggle is required.

For safer defaults, in `~/.codex/config.toml`:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
```

- `workspace-write` lets Codex modify files inside the repo but not outside it.
- `on-request` prompts before running shell commands.

### Verify it works

From the repo root:

```bash
codex
```

Then: *"Summarize the architectural rules I need to follow."*

Expected: Codex mentions the single Django app, FSM for state transitions, USWDS, Login.gov OIDC, no SQL string interpolation, no `shell=True`. Generic answer means the file is not being picked up — confirm `AGENTS.md` exists at the workspace root (case-sensitive on Linux/macOS).

---

## 4. What the repo ships in `.vscode/`

To give every contributor the same starting point, the repo ships two files in `.vscode/`:

**`.vscode/extensions.json`** — VS Code prompts to install these on first open (Python, Pylance, Django, Docker, EditorConfig, GitLens, Copilot, Copilot Chat, Claude Code).

**`.vscode/settings.json`** — workspace defaults: a 120-column ruler (matches Black / Flake8 config), `src/registrar/public/` excluded from search and the file tree (those are compiled assets — never hand-edit), and `github.copilot.chat.codeGeneration.useInstructionFiles` turned on.

Personal `.vscode/` settings (themes, key bindings, anything not in the two shared files) are still gitignored — they will not show up in your PRs.

---

## 5. Quick verification checklist

After setup:

- [ ] `AGENTS.md`, `CLAUDE.md`, and `.github/copilot-instructions.md` are visible in the file tree.
- [ ] Copilot Chat answers a repo-specific question with repo-specific rules.
- [ ] `claude` from the repo root acknowledges `CLAUDE.md` (run `/memory` to confirm).
- [ ] `codex` from the repo root acknowledges `AGENTS.md` (if you use Codex).
- [ ] `docker compose up` runs the dev stack from `src/`.
- [ ] Recommended extensions are installed.

If any of these fail, the AI tool will fall back to generic behavior — which on a CISA-operated system is what the instruction files exist to prevent.

---

## 6. Troubleshooting

**Copilot Chat ignores `copilot-instructions.md`.** Confirm: the file is at exactly `.github/copilot-instructions.md` (not the repo root, not deeper in `.github/`); your workspace root is the repo root; `github.copilot.chat.codeGeneration.useInstructionFiles` is `true` in your settings; you're using Copilot Chat (not inline suggestions — those don't read the file).

**Claude Code doesn't see `CLAUDE.md`.** Run `claude` from the repo root, not from a subdirectory. Run `/memory` to list loaded files. If `CLAUDE.md` is not listed, you're not in the right directory.

**Codex doesn't apply `AGENTS.md` rules.** Confirm the file is at the repo root with that exact filename (case-sensitive on Linux/macOS). Run `codex` from the repo root.

**Two AI tools fighting over inline suggestions.** Pick one for inline; disable the others. In Copilot: `"github.copilot.editor.enableAutoCompletions": false`. In the Claude Code extension settings: turn inline off. Use the others through chat / CLI.

**A personal `~/.claude/CLAUDE.md` is overriding repo rules.** Both load; the repo-level file wins on direct conflicts. If a personal preference is overriding repo policy anyway, remove the conflicting bit from your personal file — repo rules are not optional here.
