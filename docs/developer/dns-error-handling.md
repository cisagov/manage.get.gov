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

- `/admin` gains a `DnsOperationLog` — search a user-reported `request_id` and see operation, upstream status, `cf_ray`, and a redacted upstream body without leaving Django.
- **User-facing error copy moves from spreadsheets to an admin-editable table — a significant process improvement.** Today a single word change in an error message costs a Jira ticket, a developer context-switch, a code review, and a deploy. After this change, design or product self-serves the edit in `/admin`; the new copy is live to users on the next request via cache invalidation. See 17 for the full benefits and workflow — this is one of the larger-lift items in the proposal and one of the highest-leverage wins for cross-team velocity.

**Decisions we need from stakeholders before we start**

- leads: retention posture for `user_email` in logs, final httpx timeout numbers.
- Design: review or claim ownership of the 4xx message copy in 11.
- Product/security: editorial policy for admin-edited messages — trust the audit log, or require review before an edit goes live? (17.5)
- leads + leadership: direction on the distributed-tracing spike. Today a `request_id` ContextVar stitches a single Django process's logs together, but we have no way to follow one user action across service boundaries (browser → Django → httpx → Cloudflare) or to see latency breakdowns per hop. The spike would evaluate adopting a tracing backend — OpenTelemetry (open standard, self-host or vendor-neutral), Sentry (already in use for errors; tracing is an add-on), Datadog or Honeycomb (paid SaaS, richer analytics) — versus staying with the manual `request_id` approach. Decision drivers: cost, vendor lock-in, leads/ops burden, and whether support's needs are met by `request_id` + `DnsOperationLog` alone. See the Distributed tracing section for the full comparison.

Full detail follows.

---

## Distribution

This document is the living design proposal. It is versioned in the repo at [`docs/developer/dns-error-handling.md`](dns-error-handling.md)
---

## Table of Contents

1. [Why this document exists](#1-why-this-document-exists)
2. [Goals and non-goals](#2-goals-and-non-goals)
3. [Current state (before this work)](#3-current-state-before-this-work)
4. [Target architecture](#4-target-architecture)
5. [Cross-cutting decisions](#5-cross-cutting-decisions)
6. [Error-code vocabulary](#6-error-code-vocabulary)
7. [Captured-errors catalog](#7-captured-errors-catalog)
8. [PII and log hygiene](#8-pii-and-log-hygiene)
9. [API error envelope contract](#9-api-error-envelope-contract)
10. [User-facing error messaging](#10-user-facing-error-messaging)
11. [Admin visibility and support workflow](#11-admin-visibility-and-support-workflow)
12. [httpx resilience policy](#12-httpx-resilience-policy)
13. [Distributed tracing (OpenTelemetry and alternatives)](#13-distributed-tracing-opentelemetry-and-alternatives)
14. [Exception contract for contributors](#14-exception-contract-for-contributors)
15. [Support runbook — tracing a DNS failure](#15-support-runbook--tracing-a-dns-failure)
16. [Admin-editable error message store](#16-admin-editable-error-message-store)
17. [Integration with in-flight prototype work](#17-integration-with-in-flight-prototype-work)
18. [Decisions needed from stakeholders](#18-decisions-needed-from-stakeholders)

---

## 1. Why this document exists

The DNS Hosting feature (`DnsHostService` + `CloudflareService`) reaches an external provider (Cloudflare) on behalf of the user. A single user action — "add a DNS A record" — may traverse: the user's browser → a Django HTMX view → `DnsHostService` → `CloudflareService` → httpx → Cloudflare's API. Failures can originate at any layer, and today they bubble up inconsistently:

- `CloudflareService` catches `httpx.RequestError` and `httpx.HTTPStatusError`, logs, and re-raises.
- `DnsHostService` sometimes wraps with `APIError(str(e))`, sometimes doesn't.
- The view catches `(APIError, RequestError)` and surfaces a single generic "Failed to save DNS record." message regardless of whether the cause was auth, rate limiting, a missing zone, or a network blip.
- HTMX responses mix `{"status": "error", "message": "..."}` and `{"error": "..."}` — the frontend has to special-case.
- No correlation ID ties the user-visible error to the JSON log line in OpenSearch.
- Support cannot trace a reported failure from `/admin` back to an upstream Cloudflare request.

This document defines a consistent pattern for where errors are caught, what they're wrapped in, what gets logged, what the user sees, and what `/admin` sees — so that a developer picking up any DNS-related ticket has a single source of truth to refer to.

## 2. Goals and non-goals

### Goals

- **One error contract from upstream to UI.** Typed exceptions in the backend → one JSON envelope on the wire → one user-facing template strategy.
- **Correlation.** Every user-visible DNS error carries a `request_id` that matches a specific line in OpenSearch and (for DNS operations) a row in `/admin`.
- **Consistency over granularity.** A small set of well-named exception subclasses (seven), not a large taxonomy.
- **Resilience defaults.** Timeouts and retries configured explicitly, not inherited from httpx defaults.
- **Clear policy.** "When do we give up?" "What do admins see?" "What can we log?".

### Non-goals

- **Full OpenTelemetry adoption.** Deferred to the spike ticket (#11). The manual `request_id` ContextVar  is the bare minimum.
- **Redesigning the DNS form validation layer.** In-model / in-form validation (`validations.py`, `models/dns/dns_record.py` `.clean()`) is in wowrk solid and out of scope.
- **Cross-cutting log-format changes.** The JSON formatter in `config/settings.py` stays as-is; we extend it with new structured fields, not replace it.
- **A new CSS/UX design for errors.** We reuse the existing USWDS alert components and the Django messages framework. Design consultation (see §10) may refine the specific copy.

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
- No correlation ID in the DNS service logs. No `cf_ray` captured. No `duration_ms`. No `error_code`. (Prototype branch `dg/4893-error-handling-improvements-proto` has since added `cf_ray` capture on `create_dns_record` and `update_dns_record`, and verified end-to-end on 2026-04-23 against the live Cloudflare API — a real ray ID of the form `9f0fb528c8e290be-IAD` is now logged on success and present in `DnsNotFoundError.context["cf_ray"]` on 404. See §17.)

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
        │       │             ┌────────────────────────────┐
        │       │             │  DomainDNSRecordsView      │  ← catches DnsHostingError
        │       │             │  (terminal handler)        │     logs with structured fields
        │       │             └────────────────────────────┘     returns JSON envelope
        │       │                            │
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
        │       └───── DnsOperationLog row (admin-visible audit trail) ──────┐
        │                                                                    │
        └───── OpenSearch log line w/ request_id, cf_ray, upstream_status ───┘
```

- **Services raise.** Never return sentinels, never swallow.
- **View catches.** One `except DnsHostingError as exc:` block per DNS endpoint, delegates to `dns_error_response(exc)` helper.
- **`request_id` threads through** via ContextVar, into every log line, into the JSON envelope, into `500.html`, into `DnsOperationLog`.

## 5. Cross-cutting decisions

These are answered here so sub-tickets inherit them instead of re-deciding.

| Question (from original issue) | Decision |
|---|---|
| Security/privacy: what can we log? | Field-level allow/deny list (see §8). Audit retention posture with leads before broad rollout. |
| Frontend error shape? | JSON envelope: `{status, code, message, request_id}`. See §9. |
| Which errors to surface in /admin? | `DnsOperationLog` — structured technical summary, not a raw traceback. See §11. |
| How specific should API error types be? | Seven subclasses. See §6. Coarse categories beat sprawling taxonomies. |
| request_id / trace_id passthrough? | Yes — `request_id_var` ContextVar, set in `RequestLoggingMiddleware`, echoed in response header and JSON envelope. Full distributed tracing deferred to the spike (§13). |
| How to display 500 errors? | Generic "we couldn't reach our DNS provider" message + `request_id`. See §10. |
| Distinguish 4xx vs 5xx in the UX? | Yes. 4xx → actionable inline error. 5xx → generic + request_id. See §10. |
| How to bubble up errors? | Log at the source with structured fields, raise a typed `DnsHostingError` subclass. Never log-and-swallow. Never convert to `None` in place of raising. See §4 and §14. |
| Pickling? | Exceptions must be picklable. See §14. |
| httpx recommendations? | Explicit timeouts, transport retries on idempotent calls only, manual backoff on 429/5xx w/ Retry-After. See §12. |
| When do we "give up"? | At the view layer. Services never terminate user flows. See §4. |
| Admin vs end-user detail? | Admin sees structured summary + `cf_ray` + upstream status. End-user sees code + message + `request_id`. Neither sees the raw Python traceback. See §11. |
| Retry strategy? | Only for idempotent HTTP methods. Honor `Retry-After`. Cap attempts. See §12. |
| Log schema for OpenSearch? | JSON formatter already exists. Extend with the field list in §8. |
| OpenTelemetry? | Spike first; `request_id` ContextVar is the floor. See §13. |
| High-priority errors? | Visible via `DnsOperationLog` in `/admin` and OpenSearch filters on `error_code`. Dashboard work lives in the epic, not this doc. |
| Backend→frontend error code mapping? | §6 is the source of truth. |
| Log content pattern? | `logger.xxx(msg, extra={...})` with the §8 allow-list fields. |

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

Every `DnsHostingError` carries: `code` (enum), `message` (from `_error_mapping`), `upstream_status` (int or None), `context` (dict of primitives). Subclasses are coarse categories; finer distinctions are carried in `code` and `context`, not in new subclasses.

## 7. Captured-errors catalog

This catalog is the reference for every DNS failure condition we know about today. Update when a new code is added.

| Source | Trigger | Code | User surface | Admin surface | Log level |
|---|---|---|---|---|---|
| Cloudflare 404 on `POST /zones/.../dns_records` | Zone record not found (stale local DB, race, test fixture) | `DNS_ZONE_NOT_FOUND` | Inline: "We couldn't find the DNS zone for this domain. It may not be enrolled in DNS hosting yet." | `DnsOperationLog` row with `outcome=failure`, `error_code=ZONE_NOT_FOUND` | `warning` |
| Cloudflare 409 | Duplicate record (same name+type) | `DNS_RECORD_CONFLICT` | Inline field error | log row | `warning` |
| Cloudflare 400 | Invalid record content (field Cloudflare refuses) | `DNS_VALIDATION_FAILED` | Inline field error (reuse CF's human-readable reason when safe) | log row | `warning` |
| Cloudflare 429 | Rate limit | `DNS_RATE_LIMIT_EXCEEDED` | "You're making changes too quickly — please wait a moment and try again." | log row; backoff metadata visible | `warning` |
| Cloudflare 401 / 403 | Invalid auth token or scope | `DNS_AUTH_FAILED` | Generic "couldn't reach DNS provider" + `request_id` | log row; critical | `error` |
| httpx `ConnectTimeout` / `ReadTimeout` / `WriteTimeout` | Network blip, Cloudflare slowdown | `DNS_UPSTREAM_TIMEOUT` | Generic + `request_id`, encourage retry | log row; duration_ms present | `error` |
| httpx `ConnectError` / `NetworkError` / DNS failure | Loss of connectivity to Cloudflare | `DNS_UPSTREAM_TIMEOUT` (catch-all for transport) | Generic + `request_id` | log row | `error` |
| Cloudflare 5xx | Provider outage | `DNS_UPSTREAM_ERROR` | Generic + `request_id` | log row | `error` |
| Any other Cloudflare status | Unexpected | `DNS_UNKNOWN` | Generic + `request_id` | log row with full upstream body (redacted) | `error` |
| Local model/form validation (existing, out of scope) | Invalid TTL, MX priority, CNAME conflict, bad DNS name | (uses `ValidationError`, not `DnsHostingError`) | Inline form field error | Django admin default | `debug` |

Post-launch: add a row every time a new production incident surfaces a code we hadn't catalogued.

## 8. PII and log hygiene

The registrar is a government system. We treat application log streams as subject to the same handling posture as application data. **leads sign-off required** on retention before the field list below goes live in production.

### 8.1 Safe to log unmasked

- `request_id` — UUID or externally-provided, no PII.
- `dns_account_id` — vendor account tag (Cloudflare).
- `zone_id` — vendor zone ID.
- `record_id` — vendor DNS record ID.
- `cf_ray` — Cloudflare `cf-ray` response header. Availability verified end-to-end (real ray IDs returned on both success and error paths; see §17).
- `upstream_status` — HTTP status integer.
- `error_code` — `DnsHostingErrorCodes` name.
- `duration_ms` — integer latency.
- `attempt` — integer retry counter.
- `outcome` — `"success"` or `"failure"`.
- Operation name — `"create_record"`, `"update_zone_dns_settings"`, etc.

### 8.2 Restricted / conditional

- `user_email` — PII. Already carried in `logging_context.user_email_var`. Keep, but audit retention with leads. Acceptable for the medium term; revisit if retention extends beyond current policy.
- Client IP — already in `logging_context.ip_address_var`. Same treatment as `user_email`.

### 8.3 Never log

- Request bodies. DNS record `content` may contain secrets (TXT used for service tokens, DKIM keys, etc.).
- `X-Auth-Email`, `X-Auth-Key`, `Authorization`, or any Cloudflare credential.
- Django session cookies or CSRF tokens.
- Raw stack traces in any user-facing surface (UI, admin, 500 page). Tracebacks stay in OpenSearch.
- Upstream response bodies without redaction in `DnsOperationLog` (truncate ≤ 2 KB, scrub token-like patterns).

### 8.4 Redaction

`DnsOperationLog.upstream_body_truncated` stores at most 2 KB of the upstream response body with token-like patterns scrubbed. Use a conservative allow-list (leave Cloudflare error codes and human-readable reasons; redact anything matching typical secret patterns). Implementation belongs in a small utility covered by unit tests.

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

- `status` is always `"error"` for failure cases. (Keeps the envelope discriminable from success fragments without sniffing HTTP status.)
- `code` is the wire name (ALL_CAPS_SNAKE) from §6.
- `message` is the localized user-facing message from `_error_mapping`.
- `request_id` echoes the ContextVar value so users (and their support rep) can quote it when reporting the failure.

HTTP status is derived from the code severity:

- 4xx codes → HTTP 400 (bad request) or 409 (conflict) or 429 (rate limit).
- 5xx codes → HTTP 502 (bad gateway) for upstream issues, HTTP 504 (gateway timeout) for timeouts, HTTP 500 for unknowns.

Construction lives in `utility/api_responses.dns_error_response(exc)`. Frontend reads `code` and `message`, not the HTTP status, for presentation logic.

The bare `{"error": "..."}` shape used by some legacy API views is **retired for DNS endpoints only**. Non-DNS endpoints are not in scope for this change.

## 10. User-facing error messaging

Design consultation recommended (see "Consult Design as needed" in the parent ticket). Copy below is a starting point; expect refinement.

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

The reference is `request_id`. Support looks it up in OpenSearch or `DnsOperationLog`.

For unhandled 500s (anything not caught by DNS-specific handlers), the existing `500.html` template already has a "log identifier" block — ticket #9 wires it to `request_id`.

### Tags

Reuse the existing Django messages tagging convention already in the `base.html` template (`GenericError`, `NameserverError`, etc.). Add `DnsError` as a new tag so CSS can differentiate if design wants different treatment.

## 11. Admin visibility and support workflow

### 11.1 What admins see

The `DnsOperationLog` admin (new in the admin-visibility ticket) lists:

- timestamp
- user_email
- request_id (click to filter all rows for this request)
- operation name (`create_record`, `update_zone_dns_settings`, …)
- dns_account_id
- zone_id
- record_id (when applicable)
- error_code (filter + facet)
- upstream_status
- cf_ray (useful for escalating to Cloudflare support)
- duration_ms
- outcome (success / failure)
- upstream_body_truncated (≤ 2 KB, redacted — displayed in a read-only `<pre>` block on the detail page, not in the list view)

### 11.2 What admins do NOT see

- **Raw Python tracebacks.** Those stay in OpenSearch. If a support ticket truly needs a traceback, an engineer fetches it by `request_id`.
- Unredacted upstream response bodies.
- Request bodies.
- Cloudflare credentials.

### 11.3 Why not just query OpenSearch?

Every PR that touches `DnsOperationLog`:

> `DnsOperationLog` is a **bounded, admin-UI correlation surface**. It is not a log replacement. Different audience (support vs. engineer), different retention (TTL'd days, not months), different UX (clickable admin rows, not Lucene queries). Support staff should be able to action a user-reported `request_id` without SSO-ing into OpenSearch.

### 11.4 Retention

Default 30 days, managed by a Django management command run nightly. Final number from leads before launch.

## 12. httpx resilience policy

### 12.1 Timeouts

`httpx.Timeout(connect=3, read=10, write=10, pool=5)` on every DNS client. Prototype values — leads should confirm or revise before prod. Rationale:

- `connect=3` — Cloudflare's edge is geographically close and typically sub-second; 3s covers transient issues.
- `read=10` / `write=10` — DNS changes are usually small payloads; 10s is generous but bounded.
- `pool=5` — waiting on a pool slot longer than this indicates we're under-provisioned.

### 12.2 Transport retries

`httpx.HTTPTransport(retries=2)`. Low-level connect-error retries only; safe at the transport layer for any method (httpx only retries before a response is received).

### 12.3 Manual retry w/ backoff

Idempotent methods only (GET, HEAD). Conditions:

- HTTP 429 → honor `Retry-After` (seconds). Cap at 3 total attempts.
- HTTP 5xx → exponential backoff with jitter (e.g., 1s, 2s, 4s). Cap at 3 total attempts.
- `RequestError` (timeout, network) → backoff identical to 5xx. Cap at 3 total attempts.

### 12.4 Mutating methods

No automatic retry on POST, PATCH, DELETE. Rationale: Cloudflare does not universally accept an idempotency key, and retrying a successful-but-slow POST can create duplicate records. Future work: evaluate idempotency-key support and revisit. Out of scope for this plan.

### 12.5 Circuit breaker (explicitly deferred)

We do not implement a circuit breaker. `DNS_AUTH_FAILED` and sustained `DNS_UPSTREAM_TIMEOUT` failures are visible in `DnsOperationLog` and in OpenSearch for human intervention.

## 13. Distributed tracing (OpenTelemetry and alternatives)

The original issue specifically called out OpenTelemetry. A full spike is scheduled as the distributed-tracing evaluation ticket. This section frames the trade-off so the spike has a starting point.

### 13.1 What `request_id` ContextVar gives us

- Every JSON log line correlatable by ID.
- UI ↔ Django ↔ services ↔ Cloudflare lifecycle visible (modulo Cloudflare: `cf-ray` gives us the CF side).
- Minimal leads — one ContextVar, one middleware line, one formatter field.
- Zero external dependencies.

### 13.2 What it does not give us

- Automatic spans across Django views, DB queries, httpx calls.
- Latency breakdowns (how much of the 2.3s was DB vs. Cloudflare vs. rendering?).
- Flame graphs.
- Cross-service propagation if we add more backend services in the future.

### 13.3 Evaluation criteria for the spike

For each of {OpenTelemetry + OTLP, Sentry tracing, Datadog APM, Honeycomb Beelines, status-quo manual spans}:

- Installation cost (ongoing leads, license, agent overhead).
- Automatic vs. manual instrumentation for Django views and httpx.
- Compatibility with / replacement for the `request_id` ContextVar.
- FedRAMP / data-handling posture.
- Rough weeks to adopt.

### 13.4 Decision ownership

If the spike lands a strong OTel recommendation **before** the API error envelope or structured-logging tickets start, the **team lead** decides whether to halt the ContextVar track and pivot, or to ship the ContextVar plumbing as planned and layer OTel on top later. This is explicit so no dev in-flight on those tickets has to make the call alone.

## 14. Exception contract for contributors

When adding a new `DnsHostingError` subclass or new `DnsHostingErrorCodes` value:

### 14.1 Pickle safety

Exceptions **must** survive `pickle.dumps(exc)` → `pickle.loads(...)`. Reason: the parallel test runner serializes exceptions across process boundaries, and non-picklable exceptions silently corrupt test output — we have been bitten by MagicMock pickling failures before.

Rules:

- `__init__` takes only pickle-safe primitives: `str`, `int`, `dict` of primitives.
- No live `httpx.Response` objects attached. If you need response data, extract the fields you want (`upstream_status`, `cf_ray`, truncated body text) into plain strings/ints.
- No lambdas or closures in `context`.
- No open file handles, generators, or thread objects.

Add a round-trip test:

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
- 5xx codes share the generic template (§10); the code is what distinguishes them, not the message.

### 14.3 Adding to the catalog

Update:

- The §6 error-code vocabulary table.
- The wire-name mapping helper (`code.to_wire()`).
- The §7 captured-errors catalog.

### 14.4 When in doubt

Start with `DNS_UNKNOWN`. Promote to a named code only when a pattern of production incidents justifies the distinction. Don't pre-invent codes for hypothetical Cloudflare responses we've never seen.

## 15. Support runbook — tracing a DNS failure

A user reports: "I tried to add an A record and got an error. It said the reference was `1a2b3c4d-5e6f-7890-1234-567890abcdef`."

1. **Django `/admin`** → `DnsOperationLog` → search by `request_id`. You'll see the operation name, user_email, zone_id, error_code, upstream_status, cf_ray, duration_ms, and a redacted upstream body excerpt. For most tickets this is enough.
2. **OpenSearch** → filter `request_id: "1a2b3c4d-..."` for the full log trail across the lifecycle of that request (middleware, DB queries, service calls). Use when the admin row is insufficient or an engineer needs the full traceback.
3. **Cloudflare support** → escalate using the `cf_ray` value. Do NOT share `request_id` with Cloudflare (it's our internal correlation, not theirs).
4. **User-facing follow-up** → if the code was 4xx-user-correctable, point them to the inline guidance. If 5xx, confirm it's transient and ask them to retry; if sustained, escalate to the engineering team.

## 16. Admin-editable error message store

User-facing DNS error copy currently lives in spreadsheets that drift out of sync with code. The admin-editable message store ticket moves DNS hosting message text into a small admin-editable Django model so design and product can update copy in `/admin` without a deploy — and tests continue to pass because they reference the error **code**, not a literal string.

### 16.0 Why this matters — process impact

This is the highest-leverage item in the proposal for cross-team velocity. It is not just a refactor; it fundamentally changes **who** can change error copy and **how fast**.

**Today** — changing a single word in an error message requires:

1. Design/product files a ticket ("please change 'cannot find zone' to 'couldn't find zone'").
2. An engineer is assigned; context-switches from their current work.
3. Engineer edits the string in code, writes or updates a test asserting the new literal text.
4. PR opened, review requested, review cycles (often ≥ 1 day).
5. Merge, wait for the next deploy window.
6. Users see the new text — sometimes days or weeks after the request.

Every step above costs calendar time and engineering attention — for a change that is purely editorial. Multiply by the number of tabs / columns in the existing spreadsheet and the cost compounds. Drift between "the spreadsheet of record" and "what the code actually ships" is chronic.

**After this ticket** — the same change is:

1. Design/product opens `/admin → DNS error messages`, finds the row by `code`, edits the message, saves.
2. Next user to hit that error sees the new copy. No process restart, no deploy. A `post_save` signal invalidates the in-process cache so the next read from any worker picks up the change.
3. Django admin's built-in `LogEntry` captures who changed what and when — the audit trail is automatic.

**Concrete wins**

- **Zero engineering time** spent on editorial changes. Devs stop being a serialization point for copy updates.
- **No deploy required** for copy updates. Emergency wording fixes (typo, wrong URL, stale support email) can ship in minutes instead of hours.
- **Eliminates spreadsheet/code drift.** The DB is the source of truth; spreadsheets go away entirely for DNS error copy.
- **Tests don't break when copy changes** — tests assert on `exc.code`, not on literal strings (see §16.4). This alone pays for the ticket in avoided test churn.
- **Audit trail is automatic** via `LogEntry` — no separate change log to maintain.
- **Preserves safety net.** If the DB row is missing or the store is unreachable, exceptions fall back to the code-level `_error_mapping` dict, so users always see something meaningful and the deploy pipeline never breaks on a missing row.

**Trade-offs / things to decide**

- **Editorial policy.** Do edits go live immediately, or do we require design+product sign-off inside admin first (e.g., a draft/published state)? Section 17.5 flags this as an open decision. The default (trust the audit log) is the fastest but least gated.

### 16.1 Scope (v1)

- **DNS hosting only.** Just `DnsHostingErrorCodes`. If the pattern is well-received, follow-up tickets migrate `NameserverError`, `DsDataError`, `SecurityEmailError`, and `GenericError`.
- **Error messages only.** Not form labels, not success copy, not email templates. Those are candidates for a future, broader content registry but are not in scope here.

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

1. `/admin` → DNS error messages.
2. Find the row by `code` (e.g., `ZONE_NOT_FOUND`).
3. Edit the message text. Save. The change is live to users on the next request.
4. Django admin `LogEntry` records who edited what and when — available via `/admin/admin/logentry/`.

### 16.6 Deploy / fixture contract

- Fixture seeds each `DnsHostingErrorCodes` value with the text currently in `_error_mapping`.
- On a **fresh environment**, `loaddata` (or a data migration) creates the rows.
- On **existing environments** with admin edits, fixture loads must never overwrite — use `update_or_create` with `defaults=` only on fresh envs, or gate behind a management command.
- Engineers: changes to the *fallback* text in `_error_mapping` are only user-visible on fresh environments where no DB row exists yet. If you need to update production copy, do it through `/admin`, not code.

### 16.7 Out of scope (punts noted for future tickets)

- Draft/published states or approval workflow (security/compliance can request in a follow-up).
- Non-DNS exception classes (`Nameserver`, `DsData`, `SecurityEmail`, `Generic`) — one pattern at a time.

## 17. Integration with in-flight prototype work

This section reconciles this design with parallel in-flight work on DNS error handling (a prototype PR that introduces `CloudflareValidationError` and hardcoded user-facing constants). The two efforts are **compatible, not competing**. Notes below capture how the prototype's artifacts map onto this design so the migration path is explicit when the full typed-error and admin-editable-copy tickets land.

### 17.1 `cf_ray` availability is confirmed, not a question

Previous drafts of this document treated `cf_ray` capture as theoretical. As of 2026-04-23 it is verified end-to-end:

- `create_dns_record` and `update_dns_record` in [`cloudflare_service.py`](../../src/registrar/services/cloudflare_service.py) extract `resp.headers.get("cf-ray")` on both success and error paths and include it in log output.
- A real Cloudflare response carried `cf-ray=9f0fb528c8e290be-IAD` through the httpx client, into the log line, and into `DnsNotFoundError.context["cf_ray"]` on 404.
- Unit tests cover both branches of the read: header present ([`test_create_dns_record_404_raises_dns_not_found_error`](../../src/registrar/tests/services/test_cloudflare_service.py)) and header absent ([`test_create_dns_record_404_without_cf_ray_header`](../../src/registrar/tests/services/test_cloudflare_service.py)).

`cf_ray` is therefore a first-class field in the structured log set (§8.1) and the `DnsOperationLog` surface (§11) — the remaining work is propagating capture to the other `CloudflareService` methods using a shared helper rather than re-deciding whether to capture it at all.

### 17.2 `CloudflareValidationError` → `DnsHostingError` subclass

The prototype's `CloudflareValidationError` is exactly the kind of specific, named exception the §6 vocabulary envisions. When the typed-error hierarchy lands:

- `CloudflareValidationError` becomes (or is replaced by) `DnsValidationError` / `DnsRecordConflictError` extending `DnsHostingError`.
- Stable `DnsHostingErrorCodes` values — at minimum `DNS_RECORD_CONFLICT` and `DNS_VALIDATION_FAILED` (both already in §6) — are the wire contract. No catch-all "validation failed" code.
- Callers that currently `except CloudflareValidationError` migrate to `except DnsHostingError` + branch on `exc.code`.

Migration is mechanical — the prototype's choice of exception shape was the correct shape; only the base class and code attribute need to change.

### 17.3 Hardcoded message constants → admin-editable store

The prototype stores user-facing copy (e.g., `CF_DUPLICATE_RECORD_MESSAGE`) as Python constants. That is the right tradeoff for an in-flight PR that must ship before the `DnsErrorMessage` table exists, but it recreates the spreadsheet-drift problem §16 explicitly exists to eliminate.

**Planned migration when §16 lands:**

- Each constant is replaced with `utility/messages.get_user_message("dns", <code>)` keyed on the stable error code.
- The constant remains in-file as the `_error_mapping` fallback (§16.3) so the system stays functional if the DB row is missing or the store is unreachable.
- Leave a `# TODO(#4893/#4932): replace with get_user_message lookup` comment on every constant now so the migration is obvious to whoever picks it up.

### 17.4 View-layer mapping vs. the error envelope

The prototype's view layer emits per-field form errors (e.g., `{"name": "...", "content": "..."}`) so the DNS form can highlight the offending input. The §9 envelope contract currently returns one message per response, which is correct for non-form JSON endpoints but **insufficient** for the DNS record form UX.

Two viable resolutions — decide before the envelope ticket is split:

1. **Extend the envelope** with an optional `fields: {name: message, ...}` attribute, populated only when the error is a validation failure tied to specific inputs. All other envelope fields (`status`, `code`, `message`, `request_id`) stay unchanged.
2. **Keep the view owning form-level mapping.** The service raises `DnsValidationError` with structured context (e.g., `context={"field_errors": {...}}`), the view renders the form with per-field errors using standard Django form machinery, and the envelope is reserved for non-form JSON endpoints.

Either works; (1) is more uniform, (2) is closer to how Django form errors are rendered elsewhere in the codebase. Flag for the envelope ticket owner — do not silently pick one.

### 17.5 `cf_errors` raw payload → `DnsOperationLog.upstream_body_truncated`

The prototype attaches a `cf_errors` list (parsed from the Cloudflare error response body) to `CloudflareValidationError`. That list is exactly what §11's `DnsOperationLog.upstream_body_truncated` wants to record — structured, already-parsed, and free of credentials.

When the admin-visibility ticket lands, the logging middleware can:

```python
if isinstance(exc, DnsHostingError) and getattr(exc, "cf_errors", None):
    upstream_body = json.dumps(exc.cf_errors)[:2048]  # already structured, just truncate
else:
    upstream_body = redact(response_body)[:2048]      # raw-text fallback path
```

Action item for the typed-error ticket: **preserve `cf_errors` as a documented attribute on `DnsHostingError`** (optional, `list[dict] | None`), so the `DnsOperationLog` writer has a single well-typed place to read structured upstream error data without re-parsing response bodies.

## 18. Decisions needed from stakeholders

These are the questions this proposal does not answer alone — they need input from leads, design, product, or leadership before implementation can finalize.

| # | Decision | Owner(s) | Blocks |
|---|---|---|---|
| 1 | Retention posture for `user_email` in logs | leads | §8 rollout |
| 2 | Final httpx timeout values (current draft: `connect=3, read=10, write=10, pool=5`) | leads | httpx resilience ticket |
| 3 | Sign-off on 4xx user-facing copy in §10 | Design | API error envelope ticket |
| 4 | `DnsOperationLog` retention (draft: 30 days) | leads + security | Admin visibility ticket |
| 5 | Distributed-tracing direction: OpenTelemetry, Sentry, Datadog, Honeycomb, or status quo | Leadership + leads | Distributed-tracing spike; may change scope of the request_id ContextVar ticket |
| 6 | Editorial policy for admin-edited error copy (§16.5) — review required, or trust audit log? | Product + security | Admin-editable message store ticket |
| 7 | Safely retry record Cloudflare create/update/delete without causing duplicates | Engineering (future) | Deferred — not blocking |

Each unresolved decision has a sub-ticket dependency noted so we know what is blocked.

---
