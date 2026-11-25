# AGENTS

Instructions for AI coding agents working in the `manage.get.gov` repository.

## Before making changes

Read and follow [CONTRIBUTING.md](http://CONTRIBUTING.md), the README, and [copilot-instructions.md](http://copilot-instructions.md) before making changes to this repository. Their requirements apply to work performed by coding agents.

You should also review any inline code documentation, documentation related to dependencies, and [architectural decision records](https://github.com/cisagov/manage.get.gov/tree/main/docs/architecture/decisions) (ADRs) relevant to the part of the repository you are changing.

Do not assume that a public issue or roadmap item is available for you to implement. The .gov team has an active development team and roadmap, and work represented in a public issue may already be planned or underway. Follow the contribution expectations in `CONTRIBUTING.md`.

When a prompt is ambiguous, identify the ambiguity rather than making assumptions about product requirements, .gov processes and procedures, security requirements, or intended registrar behavior.

## Scope of changes

Make the smallest reasonable change needed to complete the requested task.

* Do not make unrelated refactors, dependency upgrades, formatting changes, or cleanup.  
* Preserve existing behavior unless the task requires changing it.  
* Follow existing project conventions before introducing new patterns or abstractions. If a new pattern or abstraction is preferred, provide an explanation why it was chosen over existing patterns, and any trade-offs.  
* Do not add or replace dependencies unless they are necessary for the task.  
* Do not change public interfaces, data models, migrations, permissions, authentication or authorization behavior, infrastructure, or deployment configuration without making the impact clear to the human contributor.  
* Do not implement additional features merely because they appear related or useful. If additional features do appear useful or related, highlight those to the human contributor for review.

If you discover an unrelated problem while working on a task, report it to the human contributor rather than expanding the scope of the change, including potential follow-on work to address the problem.

## Protect sensitive information

This is a public repository. Follow the sensitive-information requirements in `CONTRIBUTING.md`.

Never add sensitive or non-public information to source code, tests, fixtures, examples, documentation, logs, screenshots, commit messages, issues, or pull requests.

If a requested change appears to require exposing sensitive information, stop and tell the human contributor.

## Security and privacy

Treat changes involving authentication, authorization, permissions, user or registrant information, domain management, registry interactions, infrastructure, and deployment as security- or privacy-sensitive.

* Do not weaken authentication, authorization, validation, privacy, logging, auditing, or other security controls to simplify an implementation or make a test pass.  
* Do not bypass an existing security control without explicit direction and a clear explanation of the impact.  
* Do not introduce real credentials or production data for testing.  
* Do not publicly disclose a suspected vulnerability.

If you discover a potential security or privacy vulnerability while working on a task, notify the human contributor rather than opening a public issue or including unnecessary exploit details in a public pull request. Follow the reporting requirements in `CONTRIBUTING.md` and `SECURITY.md`.

## Product and policy behavior

The .gov registrar implements product rules and policies that may not be apparent from code alone.

Do not presume or invent .gov procedure, eligibility requirements, domain lifecycle rules, permissions, or other business rules when the intended behavior is unclear.

Prefer existing documented behavior, tests, architecture decisions, and established implementation patterns. When those sources do not resolve an ambiguity, identify it for the human contributor.

A technically reasonable implementation is not necessarily the intended product or policy behavior.

## Testing and validation

Changes that affect behavior should include appropriate tests when practical.

Before proposing or committing a change:

1. Run the automated tests, linters, formatters, and other repository checks relevant to the files you changed.  
2. Review the resulting diff for unintended changes.  
3. Report which checks you ran and whether they passed.  
4. Clearly identify checks you could not run and why.  
5. Call out assumptions, known limitations, or areas that require particular human review.

Never claim that a test, check, command, or manual verification succeeded unless you actually performed it.

Do not delete, disable, skip, or weaken a test solely to make a change pass. When fixing a bug, add or update a regression test when practical.

## Generated files and dependencies

Do not add or upgrade dependencies unless required by the task. If a dependency change is necessary, make it explicit to the human contributor and in the pull request.

Do not manually edit generated output when the repository provides tooling to generate it. Use the repository's documented processes for generated files, where it exists. If no documentation exists, but there is tooling to generate output, ensure that such tools are identified for the human reviewer.

Do not perform opportunistic dependency upgrades as part of an unrelated change.

## Human review and responsibility

AI-generated changes are not presumed to be correct.

The human contributor directing the work remains responsible for reviewing, validating, and submitting the change. Make assumptions, uncertainties, failed checks, security-sensitive changes, and other areas requiring human attention clear to them.

Do not represent a change as having been reviewed or approved by a human merely because an agent created or validated it.

## Attribution requirements

Maintainers need to be able to identify when a coding agent materially contributed to a change.

If you create or substantially modify repository content, or perform Git or GitHub actions on behalf of a contributor, disclose your involvement in every commit you create and every pull request you open.

Attribution supplements human responsibility; it does not replace it.

For all agents, use the attribution identity documented by the agent's provider. Include the model and version, if known. Do not invent an email address or identity. If more than one coding agent materially contributed, identify each one.

Rules:

* Always name the specific agent and, when known, the model or version used. Do not use a vague label such as "AI" or "bot".  
* Keep one trailer per agent. If multiple agents materially contributed to a commit or pull request, include one trailer for each.  
* Preserve applicable attribution trailers when amending or rebasing agent-generated work, or when a pull request description is updated.  
* Do not add the human contributor's name as an agent or impersonate a human.  
* If the agent wrote or substantially edited the pull request description, say so. Don’t overstate or understate the agent’s involvement.  
* Include the disclosure even when a commit or pull request contains a mix of human-written and agent-written code or commits.

### Commits

Add a `Co-authored-by` trailer to every commit you create or materially contribute to. Put the trailer at the end of the commit message, separated from the body by a blank line.

```
Fix off-by-one error in pagination

Co-authored-by: <Agent Name>(<model or version, if known>) <agent-email@example.com>
```

### Pull request descriptions

Every pull request that includes material contributions from a coding agent for the PR or any included commits must disclose that involvement.

Include an attribution section at the bottom of the pull request description:

```
---
### AI assistance

🤖 This pull request was created with the assistance of <Agent Name> (<model or version, if known>), directed by @<github-username>.
```

## Checklist before committing or opening a pull request

Before creating a commit or opening a pull request, verify that:

1. The change is within the requested scope.  
2. The change complies with `CONTRIBUTING.md`.  
3. No sensitive or non-public information has been introduced.  
4. Relevant tests and checks have been run, and their results are reported accurately.  
5. Assumptions, limitations, and areas requiring human review are identified.  
6. Every commit you materially contributed to contains the appropriate `Co-authored-by` trailer.  
7. The pull request contains the required AI-assistance disclosure.  
8. The attribution accurately describes the agent's involvement.

