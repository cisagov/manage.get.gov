# DNS Hosting — Error Handling, Logging & Observability

**Design proposal for the Foot Bridge epic.**

| | |
|---|---|
| **Status** | Review — ready for stakeholder discussion |
| **Author** | Daisy Gutierrez |
| **Last updated** | 2026-04-22 |
| **Audience** | Engineering, Design, Product, Support, leads/SRE |

---

## Executive Summary

DNS hosting errors bubble up inconsistently today. The same failure can surface as a generic "Failed to save DNS record." message, a bare JSON error, or a Django 500 — with no correlation ID tying any of it back to an upstream Cloudflare request. This proposal defines a consistent error-handling pattern from the service layer to the UI and `/admin`, captured in ~12 sub-tickets.

**What changes for users**

- 4xx errors (zone not found, record conflict, validation, rate limit) become specific, actionable inline messages.
- 5xx errors (upstream timeout, auth failure, provider outage) show a single consistent "we couldn't reach our DNS provider" message with a `request_id` the user can quote to support.

**What changes for engineers**

- Typed exceptions (`DnsHostingError` hierarchy with eight codes) replace the bare `APIError`.
- httpx clients get explicit timeouts and a retry policy.
- Every DNS log line emits a structured field set (request_id, zone_id, cf_ray, error_code, duration_ms, …) so OpenSearch queries stop being string grep.
- One JSON error envelope: `{status, code, message, request_id}`.

**What changes for support and content teams**

- `/admin` gains audit coverage for DNS model changes via `django-auditlog`, plus deep-link helpers on the domain page that jump to auditlog entries for the domain's DNS models and to OpenSearch pre-filtered by `request_id` for failure investigation.
- **User-facing error copy moves from spreadsheets to an admin-editable table — a significant process improvement.** Today a single word change in an error message costs a Jira ticket, a developer context-switch, a code review, and a deploy. After this change, design or product self-serves the edit in `/admin`; the new copy is live to users on the next request via cache invalidation. See 17 for the full benefits and workflow — this is one of the larger-lift items in the proposal and one of the highest-leverage wins for cross-team velocity.

**Decisions we need from stakeholders before we start**

- leads: retention posture for `user_email` in logs, final httpx timeout numbers.
- Design: review or claim ownership of the 4xx message copy in 11.
- Product/security: editorial policy for admin-edited messages — trust the audit log, or require review before an edit goes live? (17.5)
- **Proposed out of scope, parked for leadership:** whether to adopt a dedicated request-tracing tool (e.g., OpenTelemetry). That is a program-level architectural decision spanning every service the team owns — one that sits above the DNS hosting epic. What this epic delivers — OpenSearch + structured fields — lets us reconstruct a failed request's full lifecycle with a single `request_id:"..."` query (browser action → middleware → DB → service → Cloudflare), which is sufficient for DNS error-handling needs. The broader tracing-tool question is filed as #4930 for a future leadership conversation and should not gate this epic's delivery. See [section 13](#13-request-tracing-is-opensearch-enough) for the comparison.

Full detail follows.

---

---

## Table of Contents

1. [Why this document exists](#1-why-this-document-exists)
2. [Goals and non-goals](#2-goals-and-non-goals)
3. [Current state (before this work)](#3-current-state-before-this-work)
4. [Target architecture](#4-target-architecture)
5. [Decisions that apply across the whole epic](#5-decisions-that-apply-across-the-whole-epic)
6. [Error-code vocabulary](#6-error-code-vocabulary)
7. [Captured-errors catalog](#7-captured-errors-catalog)
8. [PII and log hygiene](#8-pii-and-log-hygiene)
9. [API error envelope contract](#9-api-error-envelope-contract)
10. [User-facing error messaging](#10-user-facing-error-messaging)
11. [Admin visibility and support workflow](#11-admin-visibility-and-support-workflow)
12. [httpx resilience policy](#12-httpx-resilience-policy)
13. [Request tracing: is OpenSearch enough?](#13-request-tracing-is-opensearch-enough)
14. [Exception contract for contributors](#14-exception-contract-for-contributors)
15. [Support runbook — tracing a DNS failure](#15-support-runbook--tracing-a-dns-failure)
16. [Admin-editable error message store](#16-admin-editable-error-message-store)
17. [Integration with in-flight prototype work](#17-integration-with-in-flight-prototype-work)
18. [Decisions needed from stakeholders](#18-decisions-needed-from-stakeholders)
19. [Sub-tickets filed](#19-sub-tickets-filed)

---

## 1. Why this document exists

Today DNS failures bubble up inconsistently across the `CloudflareService` → `DnsHostService` → view stack:

- `CloudflareService` catches `httpx.RequestError` and `httpx.HTTPStatusError`, logs, and re-raises.
- `DnsHostService` sometimes wraps with `APIError(str(e))`, sometimes doesn't.
- The view catches `(APIError, RequestError)` and shows a generic "Failed to save DNS record." regardless of whether the cause was auth, rate limit, missing zone, or network blip.
- HTMX responses mix `{"status": "error", "message": "..."}` and `{"error": "..."}` — the frontend special-cases both.
- No correlation ID ties the user-visible error to the OpenSearch log line.
- Support cannot trace a reported failure from `/admin` back to the upstream Cloudflare request.

This document defines a consistent pattern — where errors are caught, what they're wrapped in, what gets logged, what the user sees, and what `/admin` sees — so any developer picking up a DNS ticket has a single source of truth.

## 2. Goals and non-goals

### Goals

- **One error contract from upstream to UI.** Typed exceptions in the backend → one JSON envelope on the wire → one user-facing template strategy.
- **Correlation.** Every user-visible DNS error carries a `request_id` that matches a specific line in OpenSearch and (for DNS operations) a row in `/admin`.
- **Consistency over granularity.** Seven named exception subclasses.
- **Resilience defaults.** Timeouts and retries always set explicitly.
- **Clear policy.** "When do we give up?" "What do admins see?" "What can we log?".

### Non-goals

- **Adopting a dedicated distributed-tracing tool.** Deferred to the spike ([section 13](#13-request-tracing-is-opensearch-enough)). `request_id` in OpenSearch is the floor, and for our one-app-plus-Cloudflare topology it may well be the ceiling too.
- **Redesigning the DNS form validation layer.** In-model / in-form validation (`validations.py`, `models/dns/dns_record.py` `.clean()`) is solid and out of scope.
- **Cross-cutting log-format changes.** The JSON formatter in `config/settings.py` stays as-is; we extend it with new structured fields and leave the formatter itself unchanged.
- **A new CSS/UX design for errors.** We reuse the existing USWDS alert components and the Django messages framework. Design consultation (see [section 10](#10-user-facing-error-messaging)) may refine the specific copy.

## 3. Current state (before this work)

### 3.1 Service layer

- [`src/registrar/services/cloudflare_service.py`](../../src/registrar/services/cloudflare_service.py) — every method catches `httpx.RequestError` and `httpx.HTTPStatusError`, logs an f-string, and re-raises as-is. Two methods (`create_dns_record`, `update_dns_record`) additionally wrap with `APIError(...)` on `HTTPStatusError`. The `httpx.Client()` is constructed with no timeout and no retries.
- [`src/registrar/services/dns_host_service.py`](../../src/registrar/services/dns_host_service.py) — wraps with `raise APIError(str(e)) from e` in `create_dns_record` and `update_and_save_dns_record`. Other methods pass exceptions through unchanged.

### 3.2 View layer

- [`src/registrar/views/domain.py`](../../src/registrar/views/domain.py) `DomainDNSRecordsView.post` catches `(APIError, RequestError)`, logs, and shows a generic `messages.error(request, "Failed to save DNS record.")`. For a missing zone, returns `JsonResponse({"status": "error", "message": "DNS zone not found. Domain may not be enrolled."}, status=400)`.
- The 500 handler in [`src/registrar/views/utility/error_views.py`](../../src/registrar/views/utility/error_views.py) renders `500.html` which has a "log identifier" block that is currently a placeholder.

### 3.3 Exception classes

[`src/registrar/utility/errors.py`](../../src/registrar/utility/errors.py) already has a mature code-based pattern: `NameserverError` + `NameserverErrorCodes`, `DsDataError` + `DsDataErrorCodes`, `SecurityEmailError` + `SecurityEmailErrorCodes`. DNS hosting has only a bare `APIError(Exception)` — no subclasses, no codes, no status propagation. We mirror the `NameserverError` pattern for DNS hosting.

### 3.4 Logging

- [`src/registrar/logging_context.py`](../../src/registrar/logging_context.py) uses `ContextVar` for `user_email`, `ip_address`, `request_path`.
- [`RequestLoggingMiddleware`](../../src/registrar/registrar_middleware.py) sets those ContextVars. **Note:** currently guarded by `if getattr(settings, "IS_PRODUCTION", False)`, which means local development logs are missing this context entirely.
- [`DatabaseConnectionMiddleware`](../../src/registrar/registrar_middleware.py) reads `HTTP_X_REQUEST_ID` directly from `request.META` — not propagated to anyone else.
- `JsonFormatter` in [`config/settings.py`](../../src/registrar/config/settings.py) emits JSON logs and merges `extra=` kwargs into the log record. OpenSearch-ready.
- No correlation ID in the DNS service logs. No `cf_ray` captured. No `duration_ms`. No `error_code`. (Prototype branch `dg/4893-error-handling-improvements-proto` has since added `cf_ray` capture on `create_dns_record` and `update_dns_record`, and verified end-to-end on 2026-04-23 against the live Cloudflare API — a real ray ID of the form `9f0fb528c8e290be-IAD` is now logged on success and present in `DnsNotFoundError.context["cf_ray"]` on 404. See [section 17](#17-integration-with-in-flight-prototype-work).)

### 3.5 Admin

[`DnsRecordAdmin`](../../src/registrar/admin.py) is minimal: list/search on fields. **No ModelAdmin** exists for `DnsAccount`, `DnsZone`, or `DnsVendor`. Support staff cannot see DNS operation history in `/admin` today.

## 4. Target architecture

```
  ┌──────────────┐    user action (HTMX POST)
  │   browser    │───────────────────────────┐
  └──────────────┘                           │
        ▲                                    ▼
        │                      ┌────────────────────────────┐
        │     rendered HTMX    │  RequestLoggingMiddleware  │  ← sets request_id ContextVar
        │  fragment / toast    └────────────────────────────┘
        │       │                            │
        │       │                            ▼
        │       │             ┌────────────────────────────┐        ┌───────────────────────────┐
        │       │             │  DomainDNSRecordsView      │        │  DnsErrorMessage          │
        │       │             │  (terminal handler)        │◀───────│  (admin-editable copy)    │
        │       │             │  catches DnsHostingError,  │  resolves   keyed by error code;   │
        │       │             │  logs, returns envelope    │  message   edited in /admin; falls │
        │       │             └────────────────────────────┘  text      back to _error_mapping  │
        │       │                            │                       └───────────────────────────┘
        │       │                            ▼
        │       │             ┌────────────────────────────┐
        │       │             │  DnsHostService            │  ← passes typed errors through
        │       │             └────────────────────────────┘
        │       │                            │
        │       │                            ▼
        │       │             ┌────────────────────────────┐
        │       │             │  CloudflareService         │  ← raises DnsHostingError subclasses
        │       │             │  (httpx w/ timeouts+retry) │     with code, upstream_status, context
        │       │             └────────────────────────────┘
        │       │                            │
        │       │                            ▼
        │       │                      Cloudflare API
        │       │
        │       └───── django-auditlog row (successful model changes) ───────┐
        │                                                                    │
        └───── OpenSearch log line w/ request_id, cf_ray, upstream_status ───┘
```

- **Services raise.** Never return sentinels, never swallow.
- **View catches.** One `except DnsHostingError as exc:` block per DNS endpoint, delegates to `dns_error_response(exc)` helper.
- **`request_id` threads through** via ContextVar, into every log line, into the JSON envelope, into `500.html`, and into the OpenSearch record for deep-dive investigation.
- **Successful DNS changes are audited via `django-auditlog`** on the DNS models (`DnsRecord`, `DnsZone`, `DnsAccount`). This is the pattern the registrar already uses for domains and other resources — no new table. Admin deep-link helpers on the domain page jump to the auditlog entries for that domain.
- **Failure investigations go through OpenSearch**, reached via one-click deep-link from `/admin` pre-filtered by `request_id` or domain name. Support doesn't have to know Lucene syntax; the link is built for them.
- **User-facing message text is resolved at render time** by `DnsHostingError.message`: explicit override → admin-edited row in `DnsErrorMessage` (keyed by code, edited in `/admin`, cached in-process with signal invalidation) → code-level `_error_mapping` fallback. The DB is authoritative; the code dict is the safety net. See [section 16](#16-admin-editable-error-message-store) for the full design and [section 16.6](#16-admin-editable-error-message-store) for the deploy / seed contract.

## 5. Decisions that apply across the whole epic

These are answered once, here, so every sub-ticket starts from the same answer — no re-debate in individual PRs.

| Question (from original issue) | Decision |
|---|---|
| Security/privacy: what can we log? | Field-level allow/deny list (see [section 8](#8-pii-and-log-hygiene)). Audit retention posture with leads before broad rollout. |
| Frontend error shape? | JSON envelope: `{status, code, message, request_id}`. See [section 9](#9-api-error-envelope-contract). |
| Which errors to surface in /admin? | Successful changes via `django-auditlog` on DNS models; failures via OpenSearch reached through a deep-link from the domain admin page. See [section 11](#11-admin-visibility-and-support-workflow). |
| How specific should API error types be? | Seven subclasses. See [section 6](#6-error-code-vocabulary). Coarse categories beat sprawling taxonomies. |
| request_id / trace_id passthrough? | Yes — `request_id_var` ContextVar, set in `RequestLoggingMiddleware`, echoed in response header and JSON envelope. Full distributed tracing deferred to the spike ([section 13](#13-request-tracing-is-opensearch-enough)). |
| How to display 500 errors? | Generic "we couldn't reach our DNS provider" message + `request_id`. See [section 10](#10-user-facing-error-messaging). |
| Distinguish 4xx vs 5xx in the UX? | Yes. 4xx → actionable inline error. 5xx → generic + request_id. See [section 10](#10-user-facing-error-messaging). |
| How to bubble up errors? | Log at the source with structured fields, raise a typed `DnsHostingError` subclass. Never log-and-swallow. Never convert to `None` in place of raising. See [section 4](#4-target-architecture) and [section 14](#14-exception-contract-for-contributors). |
| Pickling? | Exceptions must be picklable. See [section 14](#14-exception-contract-for-contributors). |
| httpx recommendations? | Explicit timeouts, transport retries on idempotent calls only, manual backoff on 429/5xx w/ Retry-After. See [section 12](#12-httpx-resilience-policy). |
| When do we "give up"? | At the view layer. Services never terminate user flows. See [section 4](#4-target-architecture). |
| Admin vs end-user detail? | Admin sees structured summary + `cf_ray` + upstream status. End-user sees code + message + `request_id`. Neither sees the raw Python traceback. See [section 11](#11-admin-visibility-and-support-workflow). |
| Retry strategy? | Only for idempotent HTTP methods. Honor `Retry-After`. Cap attempts. See [section 12](#12-httpx-resilience-policy). |
| Log schema for OpenSearch? | JSON formatter already exists. Extend with the field list in [section 8](#8-pii-and-log-hygiene). |
| Request tracing beyond OpenSearch? | OpenSearch + structured fields covers most of our needs; spike decides if we need more. See [section 13](#13-request-tracing-is-opensearch-enough). |
| High-priority errors? | Visible via OpenSearch filters on `error_code` (reached from `/admin` via deep-link). |

## 6. Error-code vocabulary

Defined on `DnsHostingErrorCodes(IntEnum)` and raised via `DnsHostingError` subclasses in `utility/errors.py`, mirroring `NameserverError`.

| Wire code | Enum | Subclass | Upstream status | Severity |
|---|---|---|---|---|
| `DNS_ZONE_NOT_FOUND` | `ZONE_NOT_FOUND` | `DnsNotFoundError` | 404 | 4xx |
| `DNS_RECORD_CONFLICT` | `RECORD_CONFLICT` | `DnsValidationError` | 409 | 4xx |
| `DNS_VALIDATION_FAILED` | `VALIDATION_FAILED` | `DnsValidationError` | 400 | 4xx |
| `DNS_RATE_LIMIT_EXCEEDED` | `RATE_LIMIT_EXCEEDED` | `DnsRateLimitError` | 429 | 4xx (retryable) |
| `DNS_AUTH_FAILED` | `AUTH_FAILED` | `DnsAuthError` | 401 / 403 | 5xx-equivalent |
| `DNS_UPSTREAM_TIMEOUT` | `UPSTREAM_TIMEOUT` | `DnsTransportError` | (none) | 5xx |
| `DNS_UPSTREAM_ERROR` | `UPSTREAM_ERROR` | `DnsUpstreamError` | 5xx | 5xx |
| `DNS_UNKNOWN` | `UNKNOWN` | `DnsHostingError` (base) | any | 5xx |

Every `DnsHostingError` carries: `code` (enum), `message` (from `_error_mapping`), `upstream_status` (int or None), `context` (dict of primitives). Subclasses are categories; finer distinctions belong in `code` and `context`.

## 7. Captured-errors catalog

This catalog is the reference for every DNS failure condition we know about today. Update when a new code is added.

| Source | Trigger | Code | User surface | Admin surface | Log level |
|---|---|---|---|---|---|
| Cloudflare 404 on `POST /zones/.../dns_records` | Zone record not found (stale local DB, race, test fixture) | `DNS_ZONE_NOT_FOUND` | Inline: "We couldn't find the DNS zone for this domain. It may not be enrolled in DNS hosting yet." | OpenSearch log line with `error_code=DNS_ZONE_NOT_FOUND` | `warning` |
| Cloudflare 409 | Duplicate record (same name+type) | `DNS_RECORD_CONFLICT` | Inline field error | log row | `warning` |
| Cloudflare 400 | Invalid record content (field Cloudflare refuses) | `DNS_VALIDATION_FAILED` | Inline field error (reuse CF's human-readable reason when safe) | log row | `warning` |
| Cloudflare 429 | Rate limit | `DNS_RATE_LIMIT_EXCEEDED` | "You're making changes too quickly — please wait a moment and try again." | log row; backoff metadata visible | `warning` |
| Cloudflare 401 / 403 | Invalid auth token or scope | `DNS_AUTH_FAILED` | Generic "couldn't reach DNS provider" + `request_id` | log row; critical | `error` |
| httpx `ConnectTimeout` / `ReadTimeout` / `WriteTimeout` | Network blip, Cloudflare slowdown | `DNS_UPSTREAM_TIMEOUT` | Generic + `request_id`, encourage retry | log row; duration_ms present | `error` |
| httpx `ConnectError` / `NetworkError` / DNS failure | Loss of connectivity to Cloudflare | `DNS_UPSTREAM_TIMEOUT` (catch-all for transport) | Generic + `request_id` | log row | `error` |
| Cloudflare 5xx | Provider outage | `DNS_UPSTREAM_ERROR` | Generic + `request_id` | log row | `error` |
| Any other Cloudflare status | Unexpected | `DNS_UNKNOWN` | Generic + `request_id` | log row with full upstream body (redacted) | `error` |
| Local model/form validation (existing, out of scope) | Invalid TTL, MX priority, CNAME conflict, bad DNS name | (raises `ValidationError` instead of `DnsHostingError`) | Inline form field error | Django admin default | `debug` |

Post-launch: add a row every time a new production incident surfaces a code we hadn't catalogued.

## 8. PII and log hygiene

The registrar is a government system. We treat application log streams as subject to the same handling posture as application data. **leads sign-off required** on retention before the field list below goes live in production.

### 8.1 Safe to log unmasked

- `request_id` — UUID or externally-provided, no PII.
- `dns_account_id` — vendor account tag (Cloudflare).
- `zone_id` — vendor zone ID.
- `record_id` — vendor DNS record ID.
- `cf_ray` — Cloudflare `cf-ray` response header. Availability verified end-to-end (real ray IDs returned on both success and error paths; see [section 17](#17-integration-with-in-flight-prototype-work)).
- `upstream_status` — HTTP status integer.
- `error_code` — `DnsHostingErrorCodes` name.
- `duration_ms` — integer latency.
- `attempt` — integer retry counter.
- `outcome` — `"success"` or `"failure"`.
- Operation name — `"create_record"`, `"update_zone_dns_settings"`, etc.

### 8.2 Restricted / conditional

- `user_email` — PII, carried in `logging_context.user_email_var`. Keep, but audit retention with leads.
- Client IP — `logging_context.ip_address_var`. Same treatment as `user_email`.

### 8.3 Never log

- Request bodies. DNS record `content` may contain secrets (TXT used for service tokens, DKIM keys, etc.).
- `X-Auth-Email`, `X-Auth-Key`, `Authorization`, or any Cloudflare credential.
- Django session cookies or CSRF tokens.
- Raw stack traces in any user-facing surface (UI, admin, 500 page). Tracebacks stay in OpenSearch.
- Upstream response bodies without redaction when logged to OpenSearch (truncate ≤ 2 KB, scrub token-like patterns).

### 8.4 Redaction

When DNS service code logs an upstream response body to OpenSearch, it truncates to ≤ 2 KB and scrubs token-like patterns before logging. Use a conservative allow-list (leave Cloudflare error codes and human-readable reasons; redact anything matching typical secret patterns). Implementation belongs in a small utility covered by unit tests.

## 9. API error envelope contract

Every DNS endpoint returns this exact shape on error:

```json
{
  "status": "error",
  "code": "DNS_ZONE_NOT_FOUND",
  "message": "We couldn't find the DNS zone for this domain.",
  "request_id": "1a2b3c4d-5e6f-7890-1234-567890abcdef"
}
```

HTTP status derived from severity: 4xx codes → 400 / 409 / 429; 5xx codes → 502 (upstream), 504 (timeout), 500 (unknown). `code` is ALL_CAPS_SNAKE from [section 6](#6-error-code-vocabulary); `message` comes from `_error_mapping`; `request_id` echoes the ContextVar so users can quote it to support.

Construction lives in `utility/api_responses.dns_error_response(exc)`. Frontend reads `code` and `message`, not the HTTP status, for presentation logic.

The bare `{"error": "..."}` shape used by some legacy API views is **retired for DNS endpoints only**. Non-DNS endpoints are not in scope for this change.

## 10. User-facing error messaging

Design review of this copy is **required** before [#4925](https://github.com/cisagov/manage.get.gov/issues/4925) merges — filed as [#4950](https://github.com/cisagov/manage.get.gov/issues/4950). These strings become the initial `DnsErrorMessage` rows ([section 16](#16-admin-editable-error-message-store)); after sign-off, design edits them in `/admin` without a dev cycle.

### 4xx — actionable inline errors

Shown as USWDS alert components or inline field errors adjacent to the offending input.

| Code | Copy |
|---|---|
| `DNS_ZONE_NOT_FOUND` | We couldn't find the DNS zone for this domain. It may not be enrolled in DNS hosting yet. |
| `DNS_RECORD_CONFLICT` | A record with that name and type already exists. Edit the existing record instead. |
| `DNS_VALIDATION_FAILED` | `<reuse Cloudflare's reason when safe, e.g., "The IP address isn't in a valid format.">` |
| `DNS_RATE_LIMIT_EXCEEDED` | You're making changes too quickly. Please wait a moment and try again. |

### 5xx — generic fallback with correlation ID

Shown as a USWDS alert at the page level. Never inline.

> We couldn't reach our DNS provider. Please try again in a moment. If the problem persists, contact <help@get.gov> and include this reference: `1a2b3c4d-5e6f-7890-1234-567890abcdef`.

For unhandled 500s, the existing `500.html` "log identifier" block is wired to `request_id` by ticket #9.

### Tags

Reuse the existing Django messages tagging convention already in the `base.html` template (`GenericError`, `NameserverError`, etc.). Add `DnsError` as a new tag so CSS can differentiate if design wants different treatment.

## 11. Admin visibility and support workflow

Admin visibility uses infrastructure the registrar already has — `django-auditlog` for successful model changes, OpenSearch for failure investigation — plus one piece of new UX: deep-link helpers from the domain admin page into both.

### 11.1 How successful DNS changes are audited

`django-auditlog` is already used across the registrar. Registering `DnsRecord`, `DnsZone`, and `DnsAccount` adds audit coverage — every create / update / delete produces an entry with user, timestamp, and field-level diff. Auditlog does NOT capture failures (no model was saved, so no entry); failures go to OpenSearch ([section 11.3](#11-admin-visibility-and-support-workflow)).

### 11.2 How failures are investigated

Failures land in OpenSearch as JSON log lines with structured fields ([section 3](#3-current-state-before-this-work)): `request_id`, `dns_account_id`, `zone_id`, `record_id`, `cf_ray`, `upstream_status`, `error_code`, `duration_ms`. A single OpenSearch query `request_id:"..."` reconstructs the full lifecycle of a failed DNS action — middleware → DB → service → Cloudflare.

### 11.3 Which DNS operations show up, and where

**One-liner test for contributors:** *"If a user could reasonably report 'I tried to X and something went wrong,' X should be captured."*

| Operation | Triggered by | Where it lands |
|---|---|---|
| Create DNS record | User submits the form | Success → auditlog on `DnsRecord`. Failure → OpenSearch. |
| Update DNS record | User edits a record | Success → auditlog on `DnsRecord`. Failure → OpenSearch. |
| Delete DNS record | User deletes a record | Success → auditlog on `DnsRecord`. Failure → OpenSearch. |
| Enroll domain in DNS hosting | Admin action | Success → auditlog on `DnsAccount` / `DnsZone`. Failure → OpenSearch. |
| Unenroll domain | Admin action | Success → auditlog. Failure → OpenSearch. |
| Update zone DNS settings | Admin action | Success → auditlog on `DnsZone`. Failure → OpenSearch. |

**Operations that explicitly do NOT get captured:**

- Read-only lookups (`get_zone_by_id`, `get_account_zones`, `get_dns_record`).
- Internal helper calls inside an orchestration flow (sub-calls inside enrollment).
- Background sync, periodic polls, health probes (if / when those exist).
- Form-validation failures that never reach the DNS service layer. They surface inline on the form and never touch Cloudflare, so auditlog sees nothing and OpenSearch has nothing DNS-specific to show.

### 11.4 Deep-link helpers from the domain admin page

From a domain's admin detail page, add two links:

- **"DNS audit trail for this domain"** → auditlog list pre-filtered by the domain's `DnsRecord` / `DnsZone` / `DnsAccount` object IDs.
- **"DNS logs in OpenSearch for this domain"** → pre-built OpenSearch URL filtered by `domain_name` (or `request_id` if the ticket quotes one).

### 11.5 What admins do NOT see in `/admin`

Raw Python tracebacks, unredacted upstream response bodies, request bodies, and Cloudflare credentials. Tracebacks stay in OpenSearch; an engineer fetches them by `request_id` when needed.

### 11.6 Retention

No new retention plumbing. Auditlog follows existing registrar policy; OpenSearch follows infra's existing log policy. Confirm with infra before launch that DNS-hosting fields are covered.

## 12. httpx resilience policy

### 12.1 Timeouts

`httpx.Timeout(connect=3, read=10, write=10, pool=5)` on every DNS client. Prototype values — leads should confirm before prod.

### 12.2 Transport retries

`httpx.HTTPTransport(retries=2)`. Low-level connect-error retries only; safe at the transport layer for any method (httpx only retries before a response is received).

### 12.3 Manual retry w/ backoff

Idempotent methods only (GET, HEAD). Conditions:

- HTTP 429 → honor `Retry-After` (seconds). Cap at 3 total attempts.
- HTTP 5xx → exponential backoff with jitter (e.g., 1s, 2s, 4s). Cap at 3 total attempts.
- `RequestError` (timeout, network) → backoff identical to 5xx. Cap at 3 total attempts.

### 12.4 Mutating methods

No automatic retry on POST, PATCH, DELETE — Cloudflare doesn't universally accept an idempotency key, and retrying a slow-but-successful POST can create duplicate records.

### 12.5 Circuit breaker (explicitly deferred)

We do not implement a circuit breaker. `DNS_AUTH_FAILED` and sustained `DNS_UPSTREAM_TIMEOUT` failures are visible in OpenSearch (reached via the domain admin deep-link) for human intervention.

## 13. Request tracing: is OpenSearch enough?

**OpenSearch is the incumbent and already gets us most of the way.** The spike (#4930) decides whether the remaining gap justifies adopting a dedicated tracing tool.

### 13.1 What OpenSearch + structured log fields already gives us

Once the DNS-hosting work in this proposal is complete, every log line across middleware, DB queries, service calls, and httpx requests carries `request_id`, `zone_id`, `record_id`, `dns_account_id`, `error_code`, `upstream_status`, `cf_ray`, and `duration_ms`. A single query in OpenSearch —

```
request_id: "1a2b3c4d-..."
```

— returns the full lifecycle of one user action in chronological order, including the Cloudflare side via `cf_ray`. Support can act on this without SSO-ing into anywhere new.

### 13.2 What OpenSearch does not give us

- **Automatic span instrumentation.** Tracing tools include Django, DB, and httpx plugins that emit structured spans for free. With OpenSearch we emit a log line at every hop and pay the author-cost forever.
- **Parent-child relationships / flame graphs.** Answering "how much of the 2.3s was DB vs. Cloudflare vs. rendering?" is possible but manual: you read duration_ms fields across log lines. A tracing tool renders this as a waterfall.
- **Standardized wire format for future services.** Tracing tools speak industry-standard span formats; any future service we add (or vendor we integrate with) can emit spans a tracing backend ingests directly. Flat log records don't travel that way.
- **Sampling & retention tuned for traces.** Log retention is chosen for logs; trace retention is usually shorter with heavier sampling on busy paths.

### 13.3 What the spike needs to answer

Only one question: **is the gap in 13.2 big enough to justify adopting a new tool?**

Default answer should be "OpenSearch is enough" — we have one app talking to one vendor, already pay for OpenSearch, and support's `request_id` workflow is already served by structured logs + auditlog. For each alternative considered, document: the specific gap it fills, operating cost (infra, license, agent overhead), FedRAMP posture, rough weeks to adopt, and what changes in the shipped ContextVar + log-field work.

### 13.4 Decision ownership

If the spike recommends adopting a new tool **before** the API error envelope or structured-logging tickets start, the **team lead** decides whether to halt those tickets and pivot, or to proceed with them as planned and layer the new tool on top later. This is explicit so no dev in-flight has to make the call alone.

## 14. Exception contract for contributors

When adding a new `DnsHostingError` subclass or new `DnsHostingErrorCodes` value:

### 14.1 Pickle safety

Exceptions **must** survive `pickle.dumps(exc)` → `pickle.loads(...)` — the parallel test runner serializes exceptions across process boundaries. Rules: `__init__` takes only pickle-safe primitives (`str`, `int`, `dict` of primitives); no live `httpx.Response` objects, lambdas, closures, file handles, or generators. Add a round-trip test:

```python
def test_dns_hosting_error_is_picklable(self):
    exc = DnsNotFoundError(
        code=DnsHostingErrorCodes.ZONE_NOT_FOUND,
        upstream_status=404,
        context={"zone_id": "abc123", "cf_ray": "xyz"},
    )
    restored = pickle.loads(pickle.dumps(exc))
    self.assertEqual(restored.code, exc.code)
    self.assertEqual(restored.upstream_status, exc.upstream_status)
    self.assertEqual(restored.context, exc.context)
```

### 14.2 Code/message mapping

- Every `DnsHostingErrorCodes` entry has a user-facing message in `_error_mapping`.
- Messages are written to be shown verbatim to an end user — no internal jargon, no Cloudflare terminology the user hasn't seen, no stack trace excerpts.
- 5xx codes share the generic template ([section 10](#10-user-facing-error-messaging)); the code differentiates them; the user-facing message text is the same.

### 14.3 Adding to the catalog

Update the [section 6](#6-error-code-vocabulary) vocabulary table, the `code.to_wire()` helper, and the [section 7](#7-captured-errors-catalog) errors catalog.

### 14.4 When in doubt

Start with `DNS_UNKNOWN`. Promote to a named code only when a pattern of production incidents justifies the distinction. Don't pre-invent codes for hypothetical Cloudflare responses we've never seen.

## 15. Support runbook — tracing a DNS failure

A user reports: "I tried to add an A record and got an error. It said the reference was `1a2b3c4d-5e6f-7890-1234-567890abcdef`."

1. **Django `/admin` — domain page.** Navigate to the domain. Two deep-link helpers:
   - *DNS audit trail for this domain* → Django auditlog entries for `DnsRecord` / `DnsZone` / `DnsAccount`. Shows any successful changes recently (create/update/delete). Confirms whether the user's request actually persisted.
   - *DNS logs in OpenSearch for this domain* → OpenSearch pre-filtered by the domain name. Shows the full lifecycle of recent requests, including failures.
2. **OpenSearch by `request_id`.** Filter `request_id: "1a2b3c4d-..."` (click the admin deep-link, or paste the user's reference ID). Returns the full log trail: middleware → DB → service → Cloudflare. Look at `error_code`, `upstream_status`, `cf_ray`, `duration_ms`. For most tickets this is enough.
3. **Cloudflare support** → escalate using the `cf_ray` value from the OpenSearch log line. Do NOT share `request_id` with Cloudflare — it's our internal correlation ID.
4. **User-facing follow-up** → if the code was 4xx-user-correctable, point them to the inline guidance. If 5xx, confirm it's transient and ask them to retry; if sustained, escalate to the engineering team.

## 16. Admin-editable error message store

User-facing DNS error copy currently lives in spreadsheets that drift out of sync with code. The admin-editable message store ticket moves DNS hosting message text into a small admin-editable Django model so design and product can update copy in `/admin` without a deploy — and tests continue to pass because they reference the error **code** rather than a literal string.

### 16.0 Why this matters — process impact

Today, changing a single word in an error message costs a Jira ticket, an engineer context-switch, a code review, and a deploy — sometimes days of calendar time for a purely editorial change. After this ticket, design or product edits the row in `/admin` and the next request sees new copy, with no deploy and no engineer in the loop. `LogEntry` provides the audit trail automatically; the code-level `_error_mapping` dict is the fallback if the DB row is missing. Tests assert on `exc.code` rather than literal strings, so they stop breaking when copy changes.

**Trade-off to decide:** Do edits go live immediately, or require review before publish? Section 17.5 flags this as an open decision.

### 16.1 Scope: phase 1 (this epic)

- **DNS hosting only.** Just `DnsHostingErrorCodes` — 8 rows, one namespace.
- **Error messages only.** Form labels, success copy, and email templates are out of scope.
- **Pilot scope.** Proves the mechanism on a small, contained surface before applying it to higher-traffic, stakeholder-sensitive flows (`validations.py`, `NameserverError`, etc.).

### 16.1.1 Scope: phase 2 (proposed, pending proposal buy-in)

Once phase 1 is proven, phase 2 would migrate form validation messages in `validations.py` and the existing error namespaces (`NameserverError`, `DsDataError`, `SecurityEmailError`). Not filed yet; pending buy-in on the two-phase approach and what phase 1 reveals about cache/test/editor-UX issues.

### 16.2 Model

```python
class DnsErrorMessage(models.Model):
    namespace = models.CharField(max_length=32, default="dns")
    code = models.CharField(max_length=64)           # matches DnsHostingErrorCodes.name
    message = models.TextField()
    internal_notes = models.TextField(blank=True)    # "where this message appears"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["namespace", "code"], name="dns_error_message_unique_namespace_code"),
        ]
```

### 16.3 Source-of-truth rules

- **Admin edits are authoritative.** Fixtures seed the initial rows on fresh environments; they never overwrite existing rows in staging or production.
- **Code-level `_error_mapping` is the fallback** — used only when the DB row is missing or the store is unreachable. Never a hard dependency on the DB.
- **Exceptions resolve lazily.** `DnsHostingError.message` is a property that reads from `utility/messages.get_user_message(namespace, code)` with the `_error_mapping` dict as the fallback. Admin edits take effect without a process restart via a `post_save` cache-invalidation signal.

### 16.4 Test pattern

Tests must not assert on literal message strings — they would break every time product edits the copy. Two correct patterns:

```python
# Preferred — structured assertion on the error code.
self.assertEqual(exc.code, DnsHostingErrorCodes.ZONE_NOT_FOUND)

# When a test really does exercise the rendered user copy (e.g., an integration
# test against the HTMX fragment), fetch the current value at assertion time:
from registrar.utility.messages import get_user_message
expected = get_user_message("dns", "ZONE_NOT_FOUND") or <fallback>
self.assertIn(expected, response.content.decode())
```

### 16.5 Editor workflow (for design / product)

`/admin` → DNS error messages → find the row by `code` → edit → save. Change is live on the next request. `LogEntry` records the edit automatically.

### 16.6 Deploy / fixture contract

Initial values come from Design ([#4950](https://github.com/cisagov/manage.get.gov/issues/4950)); the seed migration writes them into `DnsErrorMessage`. Fresh environments get all rows created; existing environments use `get_or_create` — never overwrite admin edits. Changes to `_error_mapping` fallback text are only user-visible where no DB row exists; update production copy through `/admin`.

## 17. Integration with in-flight prototype work

This section reconciles this design with parallel in-flight work on DNS error handling (a prototype PR that introduces `CloudflareValidationError` and hardcoded user-facing constants). Notes below capture how the prototype's artifacts map onto this design so the migration path is clear when the full typed-error and admin-editable-copy tickets are ready.

### 17.1 `cf_ray` availability is confirmed

Previous drafts of this document treated `cf_ray` capture as theoretical. As of 2026-04-23 it is verified end-to-end:

- `create_dns_record` and `update_dns_record` in [`cloudflare_service.py`](../../src/registrar/services/cloudflare_service.py) extract `resp.headers.get("cf-ray")` on both success and error paths and include it in log output.
- A real Cloudflare response carried `cf-ray=9f0fb528c8e290be-IAD` through the httpx client, into the log line, and into `DnsNotFoundError.context["cf_ray"]` on 404.
- Unit tests cover both branches of the read: header present ([`test_create_dns_record_404_raises_dns_not_found_error`](../../src/registrar/tests/services/test_cloudflare_service.py)) and header absent ([`test_create_dns_record_404_without_cf_ray_header`](../../src/registrar/tests/services/test_cloudflare_service.py)).

`cf_ray` is therefore a first-class field in the structured log set ([section 8.1](#8-pii-and-log-hygiene)) that support sees via the OpenSearch deep-link from `/admin` ([section 11](#11-admin-visibility-and-support-workflow)) — the remaining work is propagating capture to the other `CloudflareService` methods using a shared helper rather than re-deciding whether to capture it at all.

### 17.2 `CloudflareValidationError` → `DnsHostingError` subclass

The prototype's `CloudflareValidationError` is exactly the kind of specific, named exception the [section 6](#6-error-code-vocabulary) vocabulary envisions. When the typed-error hierarchy lands:

- `CloudflareValidationError` becomes (or is replaced by) `DnsValidationError` / `DnsRecordConflictError` extending `DnsHostingError`.
- Stable `DnsHostingErrorCodes` values — at minimum `DNS_RECORD_CONFLICT` and `DNS_VALIDATION_FAILED` (both already in [section 6](#6-error-code-vocabulary)) — are the wire contract. No catch-all "validation failed" code.
- Callers that currently `except CloudflareValidationError` migrate to `except DnsHostingError` + branch on `exc.code`.

Migration is mechanical — only the base class and code attribute need to change.

### 17.3 Hardcoded message constants → admin-editable store

The prototype stores user-facing copy (e.g., `CF_DUPLICATE_RECORD_MESSAGE`) as Python constants. That is the right tradeoff for an in-flight PR that must merge before the `DnsErrorMessage` table exists, but it recreates the spreadsheet-drift problem [section 16](#16-admin-editable-error-message-store) explicitly exists to eliminate.

When [section 16](#16-admin-editable-error-message-store) lands: replace each constant with `utility/messages.get_user_message("dns", <code>)`, keep the constant as the `_error_mapping` fallback, and add `# TODO(#4893/#4932): replace with get_user_message lookup` to every constant now so the migration is obvious.

### 17.4 View-layer mapping vs. the error envelope

The prototype's view layer emits per-field form errors (e.g., `{"name": "...", "content": "..."}`) so the DNS form can highlight the offending input. The [section 9](#9-api-error-envelope-contract) envelope contract currently returns one message per response, which is correct for non-form JSON endpoints but **insufficient** for the DNS record form UX.

Two viable resolutions — decide before the envelope ticket is split:

1. **Extend the envelope** with an optional `fields: {name: message, ...}` attribute for validation failures.
2. **Keep the view owning form-level mapping** — service raises `DnsValidationError` with `context={"field_errors": {...}}`, view renders per-field errors via Django form machinery, envelope reserved for non-form JSON endpoints.

(1) is more uniform; (2) matches how Django form errors are rendered elsewhere. Flag for the envelope ticket owner — do not silently pick one.

### 17.5 `cf_errors` raw payload → structured OpenSearch logging

The prototype attaches a `cf_errors` list (parsed from the Cloudflare error response body) to `CloudflareValidationError`. That list is exactly what the structured-logging ticket ([section 3](#3-current-state-before-this-work)) wants in OpenSearch — already parsed, free of credentials, and queryable by support.

When the structured-logging ticket lands, the DNS service can log:

```python
if getattr(exc, "cf_errors", None):
    log_extra["cf_errors"] = exc.cf_errors          # already structured
else:
    log_extra["cf_body"] = redact(response_body)[:2048]  # raw-text fallback
```

Action item for the typed-error ticket: **preserve `cf_errors` as a documented attribute on `DnsHostingError`** (optional, `list[dict] | None`), so the structured-logger has a single well-typed place to read structured upstream error data without re-parsing response bodies.

### 17.6 `request_id` on the prototype branch lives on the request object

The `request_id` ContextVar slot is declared in [`logging_context.py`](../../src/registrar/logging_context.py) (`request_id_var`), but on the prototype branch `dg/4893-error-handling-improvements-proto` the middleware does *not* yet write to it. Instead, [`RequestLoggingMiddleware`](../../src/registrar/registrar_middleware.py) stores the ID on `request._dns_request_id` and echoes it back as an `X-Request-ID` response header. Callers that need the ID read it via `getattr(request, "_dns_request_id", None)` — see [`utility/api_responses.get_request_id`](../../src/registrar/utility/api_responses.py).

Intentional prototype-scope choice — wiring through the shared `set_user_log_context()` API adds review surface and regression risk not needed to demonstrate the error flow. [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) is the proper home; once it lands, every `request._dns_request_id` reference migrates to `request_id_var.get()`.

## 18. Decisions needed from stakeholders

These are the questions this proposal does not answer alone — they need input from leads, design, product, or leadership before implementation can finalize.

| # | Decision | Owner(s) | Blocks |
|---|---|---|---|
| 1 | Retention posture for `user_email` in logs | leads | [section 8](#8-pii-and-log-hygiene) rollout |
| 2 | Final httpx timeout values (current draft: `connect=3, read=10, write=10, pool=5`) | leads | httpx resilience ticket |
| 3 | Sign-off on 4xx user-facing copy in [section 10](#10-user-facing-error-messaging) (required) — filed as [#4950](https://github.com/cisagov/manage.get.gov/issues/4950), blocks [#4925](https://github.com/cisagov/manage.get.gov/issues/4925) | Design | API error envelope ticket ([#4925](https://github.com/cisagov/manage.get.gov/issues/4925)) |
| 4 | Confirm existing `django-auditlog` and OpenSearch retention policies cover DNS model changes and DNS log lines (no new retention plumbing introduced) | leads + security | Admin visibility ticket |
| 5 | Is OpenSearch + structured fields enough for request tracing, or do we adopt a dedicated tracing tool? | Leadership + leads | Request-tracing spike; may change scope of the request_id ContextVar ticket |
| 6 | Editorial policy for admin-edited error copy ([section 16.5](#16-admin-editable-error-message-store)) — review required, or trust audit log? | Product + security | Admin-editable message store ticket |
| 7 | Safely retry record Cloudflare create/update/delete without causing duplicates | Engineering (future) | Deferred — not blocking |

## 19. Sub-tickets filed

All 13 sub-tickets are filed under **[#4892](https://github.com/cisagov/manage.get.gov/issues/4892)** with `blocked_by` relationships. Labels: `dev`, `Feature: DNS hosting`. Project: `.gov Product Board`.

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

---
