# DNS Hosting Error Handling and Logging

## Team Brief

| | |
|---|---|
| Status | Draft for team discussion |
| Audience | Engineering, Product, Design, Support, Infra |
| Source material | [`dns-error-handling.md`](dns-error-handling.md) |

## Executive Summary

DNS Hosting errors today are unpredictable and hard to trace. The same underlying failure can surface as a generic save error, a raw backend exception, or a 500 page — and we have no reliable way to follow one user action from browser to Cloudflare and back.

This epic proposes a standard pattern for how DNS errors are classified, logged, surfaced to the frontend, and made visible in `/admin`. The goal is not to solve every monitoring and debugging concern in one pass. The goal is to give the team a clear, repeatable way to handle DNS failures so future work is easier to ship, debug, and support.

**A highlight for cross-team velocity:** the epic pilots an admin-editable copy store for DNS hosting errors — design and product update the text in `/admin` with the change live on the next request, no ticket, no code review, no deploy. This phase migrates 8 DNS hosting error codes to prove the pattern. The spreadsheet is used across the registrar beyond error copy, so no single epic will eliminate it — but this is the **first concrete component moving off the spreadsheet**, and a proposed phase 2 (separate ticket, pending proposal buy-in) would extend the same pattern to `validations.py` and the other error namespaces as the next step in that phase-out. See item 7 below and the rollout section for details.

## The Problem We Are Solving

- DNS errors **bubble up inconsistently** across service, view, and UI layers.
- Error responses to the frontend come in **several different JSON formats**, forcing the frontend to special-case each one.
- `/admin` does not provide **enough context for support to trace a failed DNS action**.
- Logs are **not consistently structured** for OpenSearch queries or cross-service debugging.
- We do **not have a shared policy** for when to retry, when to fail fast, and when to show the user a generic 500-style message.
- **User-facing error copy lives in spreadsheets that drift out of sync with code.** Every edit — even a typo fix — costs design or product a ticket, costs engineering a PR/review/deploy cycle, and leaves users staring at the old text in the meantime. The dev team is the serialization point for editorial work that has nothing to do with code.

## Why This Matters

### For users

- Validation and conflict errors should be actionable, not generic.
- When something breaks on our side, users see one consistent, non-alarming message with a reference ID they can give to support.
- A visible `request_id` helps support investigate reported failures faster.

### For support and admins

- A failed DNS update should be traceable without digging through raw logs first.
- `/admin` should show a technical summary that is useful but still sanitized.

### For engineers

- One exception model makes code easier to reason about and test.
- Structured logs make production issues easier to query and triage.
- A defined retry strategy prevents both silent hanging and overly aggressive retries.
- **Stop being the bottleneck for error-copy edits.** Every word change in an error message today costs a ticket, a PR, a review, and a deploy. After this epic, design and product edit copy in `/admin` directly and the dev team is off the critical path.

### For design and product

- User-facing DNS error copy lives in `/admin` as a first-class editable table, not in spreadsheets that drift out of sync with code.
- Edits go live on the next request via cache invalidation — no deploy required.
- Django's built-in audit log captures who changed what and when.

## Proposal in One Sentence

Adopt a single end-to-end DNS error contract: typed backend exceptions, one API error envelope, structured logs with correlation IDs, a clear split between user-correctable and system-failure errors, admin visibility via auditlog + OpenSearch deep-links (no new table), and admin-editable user-facing error copy so non-devs can update messaging without a deploy.

## What We Are Proposing

### 1. Standardize backend errors

Introduce a `DnsHostingError` hierarchy with a small set of shared error codes such as:

- `DNS_ZONE_NOT_FOUND`
- `DNS_RECORD_CONFLICT`
- `DNS_VALIDATION_FAILED`
- `DNS_RATE_LIMIT_EXCEEDED`
- `DNS_AUTH_FAILED`
- `DNS_UPSTREAM_TIMEOUT`
- `DNS_UPSTREAM_ERROR`
- `DNS_UNKNOWN`

This gives us a common vocabulary across services, views, logs, tests, and frontend handling.

### 2. Standardize the frontend/API contract

Every DNS error response should use the same envelope:

```json
{
  "status": "error",
  "code": "DNS_ZONE_NOT_FOUND",
  "message": "We couldn't find the DNS zone for this domain.",
  "request_id": "1234abcd-..."
}
```

This keeps frontend handling simple and makes error states more consistent.

### 3. Treat 4xx and 5xx differently

- 4xx-style errors are usually user-correctable or expected edge cases. These should show specific, actionable messages.
- 5xx-style errors are system failures or upstream failures. These should show a consistent fallback message plus a `request_id`.

This distinction improves user experience and reduces confusion.

### 4. Add correlation and structured logging

Every DNS request should carry a `request_id` through the request lifecycle and include structured fields in logs, such as:

- `request_id`
- `zone_id`
- `record_id`
- `dns_account_id`
- `error_code`
- `upstream_status`
- `cf_ray`
- `duration_ms`

This makes it possible to follow one failed action from UI to backend to Cloudflare.

### 5. Improve admin visibility

Use the tools already in the registrar:

- **Register the DNS models with `django-auditlog`.** `DnsRecord`, `DnsZone`, `DnsAccount`. Auditlog is already installed and used elsewhere, so every successful DNS create/update/delete gets an audit row, a user, and a timestamp — the pattern the team already knows.
- **Rely on OpenSearch for failure investigations.** The structured log fields this epic adds (`request_id`, `zone_id`, `cf_ray`, `upstream_status`, `error_code`, `duration_ms`) make a single OpenSearch query the full diagnostic trail. Failures don't produce auditlog rows (no successful model change), so this is where we look.
- **Add deep-link helpers in `/admin`.** From a domain's admin page, one link jumps to its auditlog entries (for DNS models), another jumps to OpenSearch pre-filtered by the domain name or `request_id`. Support doesn't have to know Lucene query syntax.

Admins should not see raw Python tracebacks in `/admin`. Tracebacks stay in OpenSearch.

### 6. Define a retry and failure policy

Use explicit `httpx` timeouts and a clear retry strategy:

- retry idempotent upstream requests when appropriate
- honor `Retry-After` when present
- fail fast on operations that should not be retried automatically

This gives us more predictable behavior under provider issues and timeouts.

### 7. Make error copy admin-editable (no ticket, no deploy)

DNS user-facing error copy currently lives in spreadsheets that drift out of sync with code. Move it into a small admin-editable Django model (`DnsErrorMessage`) keyed by error code. The initial values for those rows come from Design's one-time pre-launch sign-off ([#4950](https://github.com/cisagov/manage.get.gov/issues/4950)); after launch, ongoing edits happen directly in `/admin`.

**Today**, changing one word means design or product updating the spreadsheet, filing a ticket, waiting on an engineering PR/review/deploy cycle, and a lengthy wait time to delivery for a simple change.

**After this epic**, design or product opens `/admin → DNS error messages`, edits the text, saves — and the next user to hit that error sees the new copy.

Tests assert on the error **code**, not the literal string, so copy edits never break tests. If the DB row is missing or unreachable, exceptions fall back to a code-level default, so the deploy pipeline cannot break on a missing row. Django's built-in audit log captures every change. Whether edits go live immediately or require a review step first is an open question for product and security.

**Scope for phase 1 (this epic):** DNS hosting error messages only — 8 rows, one namespace. This is a deliberate test run to prove the pattern on a small, contained surface before applying it to the higher-traffic validation flows.

**Phase 2 (proposed, separate ticket pending proposal buy-in):** migrate form-validation messages (`validations.py`) and the other error namespaces (`NameserverError`, `DsDataError`, `SecurityEmailError`) into the same store. **This is the next major component moving off the spreadsheet after DNS hosting** — most of the error-related editorial churn today lives in form validation. The spreadsheet is used across the registrar for more than just error copy, so phase 2 doesn't end the spreadsheet entirely; it continues the phase-out that phase 1 starts.

If phase 1 surfaces problems with the pattern (cache behavior, test churn, editor UX, audit-log gaps), we learn with 8 rows migrated instead of 80+. Phase 2 gets scoped and sequenced once phase 1 ships; proposal buy-in on the two-phase approach is the gate for filing the phase-2 ticket.

## Guiding Principles

- Detect errors as early as possible, but turn them into user-facing responses in one place — the view.
- Log errors as structured data (fields like `zone_id`, `error_code`, `request_id`) so we can query them, not just as free-form text.
- Keep secrets, provider credentials, and sensitive request data out of logs.
- Use a small, well-understood set of error types.
- Make it as easy for support to troubleshoot a failure as it is for an engineer to ship one.

## What Changes for Each Audience

| Audience | What improves |
|---|---|
| End users | Clearer error messages and more consistent failure states |
| Admins and support | Searchable request-level troubleshooting in `/admin` |
| **Design and product** | **Edit user-facing DNS error copy directly in `/admin` — no ticket, no deploy** |
| Engineers | Typed exceptions, cleaner flow, easier testing, fewer copy-edit interruptions, better logs |
| Infra and observability | Structured log fields and easier OpenSearch queries |

## Suggested Rollout

### Phase 1: Foundations

- Introduce DNS-specific typed exceptions and shared error codes
- Add `request_id` propagation through middleware and logging context
- Define the standard DNS API error envelope

### Phase 2: Service and UI alignment

- Update `CloudflareService` to raise typed exceptions
- Remove redundant error wrapping in `DnsHostService`
- Update DNS views to use the standardized envelope and message rules

### Phase 3: Observability, support, and self-serve copy

- Add structured DNS logging fields
- Register DNS models with `django-auditlog` and add OpenSearch deep-link helpers in the domain admin page
- Add admin-editable user-facing DNS error copy (`DnsErrorMessage`) so design and product can update messaging without a deploy

### Phase 4: Future-facing improvements

- Decide whether OpenSearch + structured log fields is enough for request tracing, or whether we need to adopt a dedicated tracing tool
- Consider extending the admin-editable copy pattern to other error namespaces (Nameserver, DsData, SecurityEmail) if v1 proves out

## Sub-tickets filed

All 13 sub-tickets are filed under epic **[#4892 — Improve error handling and logging](https://github.com/cisagov/manage.get.gov/issues/4892)**. Each is a sub-issue of #4892 with `blocked_by` relationships. Labels: `dev`, `Feature: DNS hosting`. Project: `.gov Product Board` (status `👶 New`). No assignees.

| # | Title | Issue | Blocked by |
|---|---|---|---|
| 1 | Introduce `DnsHostingError` hierarchy and error codes | [#4920](https://github.com/cisagov/manage.get.gov/issues/4920) | — |
| 2 | Migrate `CloudflareService` to raise typed `DnsHostingError` subclasses | [#4921](https://github.com/cisagov/manage.get.gov/issues/4921) | [#4920](https://github.com/cisagov/manage.get.gov/issues/4920) |
| 3 | Simplify `DnsHostService` to pass exceptions through | [#4922](https://github.com/cisagov/manage.get.gov/issues/4922) | [#4921](https://github.com/cisagov/manage.get.gov/issues/4921) |
| 4 | Add httpx timeout and retry policy | [#4923](https://github.com/cisagov/manage.get.gov/issues/4923) | — |
| 5 | Propagate `X-Request-ID` through ContextVars | [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) | — |
| 6 | Standardize DNS API JSON error envelope | [#4925](https://github.com/cisagov/manage.get.gov/issues/4925) | [#4920](https://github.com/cisagov/manage.get.gov/issues/4920), [#4924](https://github.com/cisagov/manage.get.gov/issues/4924), [#4950](https://github.com/cisagov/manage.get.gov/issues/4950) |
| 7 | Add structured logging fields to DNS services | [#4926](https://github.com/cisagov/manage.get.gov/issues/4926) | [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) |
| 8 | Admin visibility: register DNS models with auditlog + OpenSearch deep-link helpers | [#4927](https://github.com/cisagov/manage.get.gov/issues/4927) | [#4926](https://github.com/cisagov/manage.get.gov/issues/4926) |
| 9 | Surface `request_id` on the 500 error page | [#4928](https://github.com/cisagov/manage.get.gov/issues/4928) | [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) |
| 10 | Developer docs: captured-errors catalog and logging pattern | [#4929](https://github.com/cisagov/manage.get.gov/issues/4929) | [#4920](https://github.com/cisagov/manage.get.gov/issues/4920), [#4921](https://github.com/cisagov/manage.get.gov/issues/4921), [#4922](https://github.com/cisagov/manage.get.gov/issues/4922), [#4923](https://github.com/cisagov/manage.get.gov/issues/4923), [#4924](https://github.com/cisagov/manage.get.gov/issues/4924), [#4925](https://github.com/cisagov/manage.get.gov/issues/4925), [#4926](https://github.com/cisagov/manage.get.gov/issues/4926) |
| 11 | Spike: is OpenSearch + structured logs enough for request tracing? | [#4930](https://github.com/cisagov/manage.get.gov/issues/4930) | — |
| 12 | Admin-editable DNS error message store | [#4931](https://github.com/cisagov/manage.get.gov/issues/4931) | [#4920](https://github.com/cisagov/manage.get.gov/issues/4920) |
| 13 | Design review of user-facing 4xx and 5xx error copy | [#4950](https://github.com/cisagov/manage.get.gov/issues/4950) | — |

**No blockers**: [#4920](https://github.com/cisagov/manage.get.gov/issues/4920), [#4923](https://github.com/cisagov/manage.get.gov/issues/4923), [#4924](https://github.com/cisagov/manage.get.gov/issues/4924), [#4930](https://github.com/cisagov/manage.get.gov/issues/4930), [#4950](https://github.com/cisagov/manage.get.gov/issues/4950).

## Decisions We Need From The Team

- **Log retention and access.** Are our current log retention and access defaults acceptable for the fields this epic adds, or does DNS-hosting logging need a different posture? Two tiers to confirm separately:
  - **PII:** `user_email` and client IP. These already live in `logging_context.py` today — this epic inherits them, doesn't introduce them. Does current retention cover them, or do we need a shorter window / masking?
  - **Vendor identifiers (new in this epic):** `dns_account_id` (Cloudflare account tag), `zone_id`, `record_id`, `cf_ray`, `upstream_status`, `error_code`, `duration_ms`, `request_id`. These don't identify a person but do describe the shape of a DNS request. Are the defaults fine for these, or do any of them need restricted access?
- How much technical detail should `/admin` show by default?
- **Proposed out of scope for this epic, parked for leadership:** whether to adopt a dedicated request-tracing tool (e.g., OpenTelemetry). That is a program-level architectural decision that affects every service the team owns, not just DNS hosting. What this epic ships — OpenSearch + structured fields (`request_id`, `zone_id`, `cf_ray`, `duration_ms`, `error_code`) — already lets us reconstruct a failed request's lifecycle with a single query, which is sufficient for DNS error-handling needs. The broader tracing-tool question is filed as #4930 for leadership to pick up when they're ready; it should not gate this epic's delivery.
- Design review and sign-off on the user-facing 4xx and 5xx error copy is a required step before implementation. This is filed as **[#4950](https://github.com/cisagov/manage.get.gov/issues/4950)** and blocks the API envelope ticket ([#4925](https://github.com/cisagov/manage.get.gov/issues/4925)). Proposed copy is in [`dns-error-handling.md` section 10](dns-error-handling.md#10-user-facing-error-messaging). **The reviewed messages become the initial values of the admin-editable `DnsErrorMessage` rows** — after sign-off, Design and product can keep editing them in `/admin` with no further dev cycle.

## Recommended Epic Outcome

By the end of this epic, we should have:

- a shared backend-to-frontend error vocabulary
- one documented and implemented error response pattern
- clear rules for what we log and what we do not log
- request-level traceability from UI through upstream DNS calls
- support-friendly visibility in `/admin`
- follow-on tickets that are small enough for engineers to pick up without more discovery

## For Team Review

Let’s use this to align on the approach. We will not iron out every implementation detail here that is for ticket refinement.

1. Do we agree on the overall approach — one shared way to classify DNS errors, send them to the frontend, log them, and surface them in `/admin`, instead of each flow handling errors its own way? (See items 1, 2, 4, and 5.)
2. Do we agree that user-correctable errors (bad input, duplicates, rate limiting) should show specific, actionable messages, while system failures (timeouts, provider outages, auth problems) show a single consistent "something went wrong on our end" message with a reference ID? (See item 3.)
3. Do we agree on how much visibility we want for DNS errors after this epic — structured logs in OpenSearch searchable by reference ID, `django-auditlog` entries in `/admin` for successful DNS changes, deep-link helpers that jump from `/admin` to OpenSearch for the full trail, and a reference ID on every user-visible error? (See items 4 and 5.)
4. Are there any privacy, support, or design concerns that change the proposal?

## Related Docs

- Design doc: [`dns-error-handling.md`](dns-error-handling.md)
