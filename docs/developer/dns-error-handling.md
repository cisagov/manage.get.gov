# DNS Error Handling — A Developer's Guide

| | |
|---|---|
| **Status** | Ready to build |
| **Author** | Daisy Gutierrez |
| **Last updated** | 2026-04-22 |

---

DNS errors today are inconsistent. Users get vague messages, support can't trace problems, and the same failure gets logged more than once. This work adds typed error classes, a request ID in every log line, and admin links into the audit trail and OpenSearch.

---

## This Doc Covers DNS Error Handling Design Proposal Ticket [#4893](https://github.com/cisagov/manage.get.gov/issues/4893)

### Formal acceptance criteria

| AC from #4893 | Where it's covered |
|---|---|
| Document a prototype for bubbling errors up to the frontend | [Current State](#current-state) -> [How It Works](#how-it-works) |
| Document which errors we capture from API calls | [The 8 Error Types](#the-8-error-types) -> [Captured-errors catalog](#captured-errors-catalog) |
| Standardize error codes (backend -> frontend vocabulary) | [Wire-code reference](#wire-code-reference) |
| Document what info we include in logs | [What Gets Logged](#what-gets-logged) |
| What errors to surface in `/admin` | [Admin Panel Features](#admin-panel-features) |
| Break work into bite-sized tickets under epic #4892 | [Sub-tickets and dependencies](#sub-tickets-and-dependencies) — 20 tickets split across [#4892](https://github.com/cisagov/manage.get.gov/issues/4892) (Phases 1–2) and sibling epic [#5005](https://github.com/cisagov/manage.get.gov/issues/5005) (Phases 3–4) |

### Considerations from the planning ticket description

Called out in the body of #4893 (not formal AC).

| Consideration | Where it's covered |
|---|---|
| Pickle safety on exceptions | [Exception Contract](#exception-contract) |
| httpx retry / timeout strategy | [Network Timeouts & Retries](#network-timeouts--retries) |
| Correlation IDs through logs | [How It Works](#how-it-works) + sub-ticket #4924 |
| 4xx vs 5xx distinction | [User-Facing Error Messages](#user-facing-error-messages) |
| Admin vs end-user detail level | [Admin Panel Features](#admin-panel-features) |
| When to "give up" and bubble to the user | [Catch Errors in Views Only](#2-catch-errors-in-views-only) (view is the terminal handler) |

---

## Suggested Rollout

Four phases. Each one delivers something usable on its own; earlier phases unblock the later ones. Phases 1–2 are tracked under epic [#4892](https://github.com/cisagov/manage.get.gov/issues/4892) (the "Foot Bridge" epic); Phases 3–4 under the sibling epic [#5005](https://github.com/cisagov/manage.get.gov/issues/5005) ("Error Handling, continued").

### Phase 1: Foundations [#4892](https://github.com/cisagov/manage.get.gov/issues/4892)

Building blocks everything else depends on. Two tracks that can run in parallel: dev foundations and copy.

**Dev track:**
- Typed DNS error classes and shared error codes — [#4920](https://github.com/cisagov/manage.get.gov/issues/4920)
- `request_id` flows through every log line — [#4924](https://github.com/cisagov/manage.get.gov/issues/4924)
- Register `DnsRecord` / `DnsZone` / `DnsAccount` with `django-auditlog` — [#4996](https://github.com/cisagov/manage.get.gov/issues/4996)

**Copy track needed for Phase 2 (Product/Content, runs in parallel):**
- Writes and approves user-facing copy for all 8 error codes so it's ready when the envelope and seed migration land — [#4999](https://github.com/cisagov/manage.get.gov/issues/4999)

### Phase 2: Service and UI alignment [#4892](https://github.com/cisagov/manage.get.gov/issues/4892)

Wire the new error types into the services and the form.

- `CloudflareService` raises typed errors — [#4921](https://github.com/cisagov/manage.get.gov/issues/4921)
- One consistent JSON error envelope returned to the browser — [#4925](https://github.com/cisagov/manage.get.gov/issues/4925)
- Surface complex Cloudflare validation errors (CNAME/A conflicts, duplicates, TXT length) inline on the form — [#4672](https://github.com/cisagov/manage.get.gov/issues/4672)
- Remove the duplicate error-wrapping in `DnsHostService` — [#4922](https://github.com/cisagov/manage.get.gov/issues/4922)
- Timeouts + bounded retry on the httpx client — [#4923](https://github.com/cisagov/manage.get.gov/issues/4923)
- Surface `request_id` on the 500 page — [#4928](https://github.com/cisagov/manage.get.gov/issues/4928)
- Tighten `register_nameservers` error handling — [#4997](https://github.com/cisagov/manage.get.gov/issues/4997)
- Engineering wires the approved copy from #4999 into `_error_mapping` — [#4950](https://github.com/cisagov/manage.get.gov/issues/4950)

### Phase 3: Visibility, support, and self-serve copy [#5005](https://github.com/cisagov/manage.get.gov/issues/5005)

Make failures easy to investigate and let Design/Product own the copy.

- Structured fields on every DNS log line — [#4926](https://github.com/cisagov/manage.get.gov/issues/4926)
- Narrow `except Exception` to `(IntegrityError, DatabaseError)` in `DnsHostService` DB-write blocks — [#4998](https://github.com/cisagov/manage.get.gov/issues/4998)
- Domain admin OpenSearch deep-links + paste box — [#4927](https://github.com/cisagov/manage.get.gov/issues/4927)
- Admin-editable user-facing error copy — [#4931](https://github.com/cisagov/manage.get.gov/issues/4931)
- Developer docs and support runbook finalized — [#4929](https://github.com/cisagov/manage.get.gov/issues/4929)
- Verify the retry policy in production once #4923 + #4926 are live (kicks off the moment structured logs are flowing) — [#5000](https://github.com/cisagov/manage.get.gov/issues/5000)

### Phase 4: Future-facing [#5005](https://github.com/cisagov/manage.get.gov/issues/5005)

Decisions and follow-ups we don't have to make right now.

- Spike: is OpenSearch + structured logs enough for request tracing? — [#4930](https://github.com/cisagov/manage.get.gov/issues/4930)
- Trim this developer guide to a current-practice reference once Phases 1 & 2 ship — [#5012](https://github.com/cisagov/manage.get.gov/issues/5012)
- Extend the admin-editable copy pattern to `Nameserver` / `DsData` / `SecurityEmail` if v1 proves out (no ticket yet)

After Phase 1 and Phase 2, we will re-evaluate the scope of Phase 3 and Phase 4.

---

## Sub-tickets and dependencies

The work is split across **two sibling epics**, divided on the phase boundary:

- **[#4892](https://github.com/cisagov/manage.get.gov/issues/4892) — "[DRAFT] Improve error handling and logging"** (the "Foot Bridge" epic): **Phases 1 & 2**, 12 tickets.
- **[#5005](https://github.com/cisagov/manage.get.gov/issues/5005) — "Error Handling, continued"**: **Phases 3 & 4**, 8 tickets.

The [Suggested Rollout](#suggested-rollout) groups these into phases; the tables below are the dependency view. **"Blocked by" mirrors the formal GitHub blocked-by relationship on each ticket** — the source of truth — so a Phase 3/4 ticket can legitimately depend on a Phase 1/2 ticket in the other epic. All carry labels `dev`, `Feature: DNS hosting`. **[#4672](https://github.com/cisagov/manage.get.gov/issues/4672) and [#5012](https://github.com/cisagov/manage.get.gov/issues/5012) are the most recent additions.**

### Epic #4892 — Phases 1 & 2

| Title | Issue | Blocked by |
|---|---|---|
| Introduce `DnsHostingError` hierarchy and error codes | [#4920](https://github.com/cisagov/manage.get.gov/issues/4920) | — |
| Propagate `X-Request-ID` through ContextVars | [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) | — |
| Add httpx timeout and retry policy | [#4923](https://github.com/cisagov/manage.get.gov/issues/4923) | — |
| Create and approve user-facing copy for the error codes | [#4999](https://github.com/cisagov/manage.get.gov/issues/4999) | — |
| Register DNS models with `django-auditlog` | [#4996](https://github.com/cisagov/manage.get.gov/issues/4996) | — |
| Surface complex Cloudflare validation errors inline on the form | [#4672](https://github.com/cisagov/manage.get.gov/issues/4672) | [#4805](https://github.com/cisagov/manage.get.gov/issues/4805) (closed) |
| Migrate `CloudflareService` to raise typed `DnsHostingError` subclasses | [#4921](https://github.com/cisagov/manage.get.gov/issues/4921) | [#4920](https://github.com/cisagov/manage.get.gov/issues/4920) |
| Simplify `DnsHostService` to pass exceptions through | [#4922](https://github.com/cisagov/manage.get.gov/issues/4922) | [#4921](https://github.com/cisagov/manage.get.gov/issues/4921) |
| Wire approved user-facing copy into seed migration | [#4950](https://github.com/cisagov/manage.get.gov/issues/4950) | [#4999](https://github.com/cisagov/manage.get.gov/issues/4999) |
| Surface `request_id` on the 500 error page | [#4928](https://github.com/cisagov/manage.get.gov/issues/4928) | [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) |
| Tighten `register_nameservers` error handling | [#4997](https://github.com/cisagov/manage.get.gov/issues/4997) | [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) |
| Standardize DNS API JSON error envelope | [#4925](https://github.com/cisagov/manage.get.gov/issues/4925) | [#4920](https://github.com/cisagov/manage.get.gov/issues/4920), [#4921](https://github.com/cisagov/manage.get.gov/issues/4921), [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) (hard); [#4999](https://github.com/cisagov/manage.get.gov/issues/4999) -> [#4950](https://github.com/cisagov/manage.get.gov/issues/4950) is a copy/release gate, not a build blocker ¹ |

¹ **#4925 dependency note.** Hard blockers: **#4920** (error hierarchy + draft `_error_mapping`), **#4921** (integration tests need a real typed error raised), **#4924** (`request_id`). The approved copy (**#4999 -> #4950**) is a *release gate, not a build blocker* — #4925 builds and merges against draft copy. The #4921/#4925 mismatch is reconciled; nothing depends on #4925.

### Epic #5005 — Phases 3 & 4

| Title | Issue | Blocked by |
|---|---|---|
| Spike: is OpenSearch + structured logs enough for request tracing? | [#4930](https://github.com/cisagov/manage.get.gov/issues/4930) | — |
| Add structured logging fields to DNS services | [#4926](https://github.com/cisagov/manage.get.gov/issues/4926) | [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) ² |
| Admin-editable DNS error message store | [#4931](https://github.com/cisagov/manage.get.gov/issues/4931) | [#4920](https://github.com/cisagov/manage.get.gov/issues/4920) ² |
| Define a pattern for DB-write failures in `DnsHostService` | [#4998](https://github.com/cisagov/manage.get.gov/issues/4998) | [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) ² |
| Domain admin OpenSearch deep-link helpers | [#4927](https://github.com/cisagov/manage.get.gov/issues/4927) | [#4996](https://github.com/cisagov/manage.get.gov/issues/4996), [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) ² |
| Verify the retry policy in action | [#5000](https://github.com/cisagov/manage.get.gov/issues/5000) | [#4923](https://github.com/cisagov/manage.get.gov/issues/4923), [#4926](https://github.com/cisagov/manage.get.gov/issues/4926) ² |
| Developer docs: captured-errors catalog and logging pattern | [#4929](https://github.com/cisagov/manage.get.gov/issues/4929) | [#4926](https://github.com/cisagov/manage.get.gov/issues/4926), [#4927](https://github.com/cisagov/manage.get.gov/issues/4927), [#4931](https://github.com/cisagov/manage.get.gov/issues/4931) |
| Trim this guide to a current-practice reference after Phases 1 & 2 ship | [#5012](https://github.com/cisagov/manage.get.gov/issues/5012) | Phases 1 & 2 of [#4892](https://github.com/cisagov/manage.get.gov/issues/4892) |

² Cross-epic dependency: this Phase 3/4 ticket waits on a Phase 1/2 ticket in #4892. Expected, given the phase order.

**No blockers — can start immediately:** [#4920](https://github.com/cisagov/manage.get.gov/issues/4920), [#4923](https://github.com/cisagov/manage.get.gov/issues/4923), [#4924](https://github.com/cisagov/manage.get.gov/issues/4924), [#4930](https://github.com/cisagov/manage.get.gov/issues/4930), [#4996](https://github.com/cisagov/manage.get.gov/issues/4996), [#4999](https://github.com/cisagov/manage.get.gov/issues/4999).

---

## Current State

What the code looks like before this work. Each ticket in the epic replaces a piece of this.

- **`CloudflareService`** (`src/registrar/services/cloudflare_service.py`) — every method catches `httpx.RequestError` and `httpx.HTTPStatusError`, logs an f-string, and re-raises. Two methods wrap with a generic `APIError(...)`. The httpx client has **no timeout** and **no retries**.
- **`DnsHostService`** (`src/registrar/services/dns_host_service.py`) — wraps Cloudflare exceptions with `raise APIError(str(e)) from e` in a couple of methods. This re-wraps the same error type and produces a second log line for the same failure.
- **View layer** (`src/registrar/views/domain.py`) — catches `(APIError, RequestError)` and shows a generic `messages.error("Failed to save DNS record.")`. JSON responses use two different shapes (`{"status": "error", "message": ...}` and `{"error": ...}`).
- **Exception classes** (`src/registrar/utility/errors.py`) — `NameserverError`, `DsDataError`, and `SecurityEmailError` already follow a typed code-based pattern. DNS hosting has only a bare `APIError(Exception)` with no codes, no subclasses, no status propagation. We mirror the `NameserverError` pattern.
- **Logging** — `logging_context.py` uses ContextVars for `user_email`, `ip_address`, `request_path`, but the middleware that sets them is gated on `IS_PRODUCTION`. `DatabaseConnectionMiddleware` reads `HTTP_X_REQUEST_ID` directly but doesn't share it. DNS service logs are f-strings with no `request_id`, `cf_ray`, `duration_ms`, or `error_code`.
- **Admin** — `DnsRecordAdmin` is minimal. No ModelAdmin for `DnsAccount`, `DnsZone`, or `DnsVendor`. Support can't see DNS operation history from `/admin`.

---

## The 8 Error Types

What each Cloudflare error means:

| What went wrong | Error name | User sees |
|---|---|---|
| Zone doesn't exist | `DNS_ZONE_NOT_FOUND` | "We can't find the DNS zone. It might not be set up yet." |
| Record already exists | `DNS_RECORD_CONFLICT` | "A record with that name already exists. Names must be unique." (reuses the existing model-level validation string) |
| Bad data | `DNS_VALIDATION_FAILED` | "That data isn't valid." (+ Cloudflare's reason) |
| Too many requests | `DNS_RATE_LIMIT_EXCEEDED` | "You're going too fast. Wait a moment and try again." |
| Permission denied | `DNS_AUTH_FAILED` | "We couldn't reach Cloudflare. Try again later." |
| Network problem | `DNS_UPSTREAM_TIMEOUT` | "We couldn't reach Cloudflare. Try again later." |
| Cloudflare down | `DNS_UPSTREAM_ERROR` | "We couldn't reach Cloudflare. Try again later." |
| Something unexpected | `DNS_UNKNOWN` | "We couldn't reach Cloudflare. Try again later." |

**Quick rule:** First 4 are the user's problem (they can fix it). Last 4 are our problem (Cloudflare or network).

### Wire-code reference

Use this when wiring up the exception in code or asserting on it in tests.

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

Every `DnsHostingError` carries: `code` (enum), `message` (from `_error_mapping`), `upstream_status` (int or None), `context` (dict of primitives). Subclasses are coarse categories. Carry finer distinctions in `code` and `context` rather than adding new subclasses.

### Captured-errors catalog

The reference for every DNS failure condition we know about today. Update when a new code is added.

| Source | Trigger | Code | User surface | Admin surface | Log level |
|---|---|---|---|---|---|
| Cloudflare 404 on POST `/zones/.../dns_records` | Zone record not found (stale local DB, race, test fixture) | `DNS_ZONE_NOT_FOUND` | Inline: "We couldn't find the DNS zone for this domain. It may not be enrolled in DNS hosting yet." | OpenSearch log line with `error_code=DNS_ZONE_NOT_FOUND` | warning |
| Cloudflare 409 | Duplicate record (same name+type). Rare — the local model validation at `dns_record.py` should catch most duplicates first; this fires only on races / vendor-side duplicates. | `DNS_RECORD_CONFLICT` | Inline field error using the existing model validation string ("A record with that name already exists. Names must be unique.") | OpenSearch log line | warning |
| Cloudflare 400 | Invalid record content | `DNS_VALIDATION_FAILED` | Inline field error (reuse Cloudflare's reason when safe) | OpenSearch log line | warning |
| Cloudflare 429 | Rate limit | `DNS_RATE_LIMIT_EXCEEDED` | "You're making changes too quickly — please wait a moment and try again." | OpenSearch log line; backoff metadata visible | warning |
| Cloudflare 401 / 403 | Invalid auth token or scope | `DNS_AUTH_FAILED` | Generic "couldn't reach DNS provider" + `request_id` | OpenSearch log line; critical | error |
| httpx `ConnectTimeout` / `ReadTimeout` / `WriteTimeout` | Network blip, Cloudflare slowdown | `DNS_UPSTREAM_TIMEOUT` | Generic + `request_id`, encourage retry | OpenSearch log line; `duration_ms` present | error |
| httpx `ConnectError` / `NetworkError` / DNS failure | Loss of connectivity to Cloudflare | `DNS_UPSTREAM_TIMEOUT` (catch-all for transport) | Generic + `request_id` | OpenSearch log line | error |
| Cloudflare 5xx | Provider outage | `DNS_UPSTREAM_ERROR` | Generic + `request_id` | OpenSearch log line | error |
| Any other Cloudflare status | Unexpected | `DNS_UNKNOWN` | Generic + `request_id` | OpenSearch log line with full upstream body (redacted) | error |
| Local model/form validation (existing, out of scope) | Invalid TTL, MX priority, CNAME conflict, bad DNS name | (uses `ValidationError`, not `DnsHostingError`) | Inline form field error | Django admin default | debug |

For successes (DNS record create/update/delete that landed), see django-auditlog at `/admin/auditlog/logentry/`. The catalog above covers failures only.

---

## Validation Errors vs. Other Exceptions

DNS failures fall into three kinds, each handled a different way:

**1. Local form/model validation — Django `ValidationError`.** Bad TTL, MX priority, a malformed DNS name, a conflict we can detect from our own data. The form catches these *before* we ever call Cloudflare. They surface as inline field errors and never become a `DnsHostingError`. This already works and is out of scope for the epic — it's the last row of the [Captured-errors catalog](#captured-errors-catalog).

**2. Cloudflare validation errors — the data passes our form checks, but Cloudflare rejects it.** Some rules can't be checked locally; Cloudflare returns a 400 or 409 and we have to relay its reason. These map to `DnsValidationError` (`DNS_VALIDATION_FAILED`) and the conflict case (`DNS_RECORD_CONFLICT`). Today we only write them to the logs — [#4672](https://github.com/cisagov/manage.get.gov/issues/4672) is the ticket that surfaces them inline on the form. The complex cases it covers:

| Cloudflare rule | What the user sees |
|---|---|
| A CNAME can't share a name with an A/AAAA record (and vice-versa) | "A CNAME record with that name already exists." (on A/AAAA) — "An A or AAAA record with that name already exists." (on CNAME) |
| No duplicate record (identical type, name, and content) | "You already entered this DNS record. DNS records must be unique." |
| Combined TXT content for one name can't exceed 8192 characters | "Combined content length of records with this name and type must not exceed 8192 characters." |

Because a Cloudflare validation error is tied to a specific field, the one-message JSON envelope isn't enough on its own. Two ways to handle that — decide before the envelope ticket ([#4925](https://github.com/cisagov/manage.get.gov/issues/4925)) is split:

- **Extend the envelope** with an optional `fields: {name: message, ...}` map for validation failures (more uniform), or
- **Let the view own per-field mapping** — the service raises `DnsValidationError` with `context={"field_errors": {...}}` and the view renders per-field errors through Django's form machinery, reserving the envelope for non-form JSON endpoints.

**3. Everything else — our problem, not the user's.** Auth failures, timeouts, upstream 5xx, anything unexpected. The user can't fix these by editing a field. They bubble up to the view unchanged, get logged with a `request_id`, and show a generic page-level message ("We couldn't reach our DNS provider…") with that reference. No inline field error.

**Rule of thumb:** if the user can fix it by changing what they typed, it's a validation error and belongs inline on the field. If they can't, it's an operational error and belongs at the page level with a `request_id`.

---

## How It Works

```
User clicks "Save"
     ↓
View catches the error
     ↓
Log it with a request_id (unique ID for this whole operation)
     ↓
Tell user what happened (friendly message + request_id)
     ↓
In background:
  Success? -> Audit log (for admin to see)
  Failure? -> OpenSearch (for engineers to investigate)
```

Every request gets a unique `request_id` from `RequestLoggingMiddleware` ([#4924](https://github.com/cisagov/manage.get.gov/issues/4924)). The same ID flows into every log line for the request and into the JSON error response returned to the browser, so a user-reported reference ID traces back to the exact server-side events.

---

## What Developers Do

### The full failure flow (Cloudflare -> service -> view)

The end-to-end shape of one failed DNS save after this epic ships. Read this first; the numbered rules below are the principles behind it.

**Layer 1 — `CloudflareService` raises a typed error** (sub-ticket [#4921](https://github.com/cisagov/manage.get.gov/issues/4921)).

When the service maps a raw `HTTPStatusError` from Cloudflare to a typed exception, the status-to-subclass mapping lives in a single `_STATUS_TO_ERROR` dict and one helper at module scope, reused by every Cloudflare method.

```python
# cloudflare_service.py — module scope

_STATUS_TO_ERROR = {
    400: (DnsValidationError, DnsHostingErrorCodes.VALIDATION_FAILED),
    401: (DnsAuthError,       DnsHostingErrorCodes.AUTH_FAILED),
    403: (DnsAuthError,       DnsHostingErrorCodes.AUTH_FAILED),
    404: (DnsNotFoundError,   DnsHostingErrorCodes.ZONE_NOT_FOUND),
    409: (DnsValidationError, DnsHostingErrorCodes.RECORD_CONFLICT),
    429: (DnsRateLimitError,  DnsHostingErrorCodes.RATE_LIMIT_EXCEEDED),
}


def _typed_dns_error(e: HTTPStatusError, **context) -> DnsHostingError:
    """Map a Cloudflare HTTP error to the right DnsHostingError subclass and log once."""
    status = e.response.status_code
    ctx = {"cf_ray": e.response.headers.get("cf-ray"), **context}
    exc_cls, code = _STATUS_TO_ERROR.get(status, (DnsHostingError, DnsHostingErrorCodes.UNKNOWN))
    logger.exception(
        "Cloudflare returned %s for DNS request",
        status,
        extra={"upstream_status": status, "error_code": code.name, **ctx},
    )
    return exc_cls(code=code, upstream_status=status, context=ctx)


class CloudflareService:
    def create_dns_record(self, zone_id, record_data):
        url = f"/zones/{zone_id}/dns_records"
        try:
            resp = self.client.post(url, json=record_data)
            resp.raise_for_status()
        except HTTPStatusError as e:
            # Cloudflare returned a 4xx or 5xx — map the status code to a typed error.
            raise _typed_dns_error(e, zone_id=zone_id, record_type=record_data.get("type")) from e
        except RequestError as e:
            # Network / timeout — no HTTP response came back, so there's no status code
            # to map. Raise the transport-error subclass directly.
            raise DnsTransportError(
                code=DnsHostingErrorCodes.UPSTREAM_TIMEOUT,
                context={"zone_id": zone_id, "exc_class": type(e).__name__},
            ) from e
        return resp.json()
```

Two failure shapes come back from `httpx`:

- **`HTTPStatusError`** — Cloudflare gave us a response, but it was 4xx/5xx. The helper maps the status code to the right typed subclass.
- **`RequestError`** — no response came back at all (connect failure, timeout, DNS lookup failed). There's no status code to map, so the service raises `DnsTransportError` directly with `code=UPSTREAM_TIMEOUT`.

Adding a new status code is one line in the `_STATUS_TO_ERROR` dict. The helper is testable on its own — feed it a fake `HTTPStatusError` and assert the returned exception type and code.

The service logs **once** here, at the point of failure, with the raw Cloudflare context (`upstream_status`, `error_code`, `cf_ray`, `zone_id`, etc.). `logger.exception(...)` attaches the full Python traceback. The middleware's ContextVars (`request_id`, `user_email`, `ip_address`, `request_path`) are merged into the same log line by the `JsonFormatter`, so one entry has both the Cloudflare-side and request-side context. Nothing downstream needs to log again.

> **Today vs. after #4924:** the `request_id` ContextVar isn't wired up yet — [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) delivers it, and until then that field stays empty on log lines. `user_email`, `ip_address`, and `request_path` only populate in production; non-prod lines show the `"Anonymous"` / `"Unknown IP"` defaults from `logging_context.py`.

**Layer 2 — `DnsHostService` passes the typed exception through unchanged** (sub-ticket [#4922](https://github.com/cisagov/manage.get.gov/issues/4922)). The current try/except around the Cloudflare call is removed. The local DB save keeps its own narrow try/except for DB errors only (sub-ticket [#4998](https://github.com/cisagov/manage.get.gov/issues/4998)).

```python
# Before (today):
def create_dns_record(self, x_zone_id, form_record_data):
    try:
        vendor_record_data = self.dns_vendor_service.create_dns_record(x_zone_id, form_record_data)
    except (APIError, HTTPStatusError) as e:
        logger.error(f"Error creating DNS record: {str(e)}")
        raise APIError(str(e)) from e   # ← duplicate log, type collapsed to string
    try:
        DnsRecord.create_from_vendor_data(x_zone_id, vendor_record_data)
    except Exception as e:               # ← too broad
        logger.error(f"Failed to save record {form_record_data} in database: {str(e)}.")
        raise
    ...

# After (post-#4922 + #4998):
def create_dns_record(self, x_zone_id, form_record_data):
    # CloudflareService raises typed DnsHostingErrors; let them through.
    vendor_record_data = self.dns_vendor_service.create_dns_record(x_zone_id, form_record_data)
    try:
        DnsRecord.create_from_vendor_data(x_zone_id, vendor_record_data)
    except (IntegrityError, DatabaseError) as e:
        logger.error(
            "Failed to persist DNS record",
            extra={"zone_id": x_zone_id, "error_class": type(e).__name__},
        )
        raise
    ...
```

**Layer 3 — the view catches and renders the JSON envelope** (sub-ticket [#4925](https://github.com/cisagov/manage.get.gov/issues/4925)):

```python
try:
    self.dns_host_service.create_dns_record(zone_id, form_record_data)
except DnsHostingError as exc:
    return dns_error_response(exc, request=request)
```

`dns_error_response` reads `exc.code`, picks the right HTTP status from the [Wire-code reference](#wire-code-reference) Severity column, and returns:

```json
{
  "status": "error",
  "code": "DNS_ZONE_NOT_FOUND",
  "message": "We couldn't find the DNS zone for this domain.",
  "request_id": "1a2b3c4d-..."
}
```

Python's `from e` chain preserves the original `HTTPStatusError` in the traceback, so engineers searching by `request_id` in OpenSearch can still see Cloudflare's response body, status, and `cf-ray`.

### 1. Raise Specific Errors

When you already know which condition you're handling (zone missing, validation failed, etc.), raise the typed subclass directly:

```python
# Don't:
raise APIError("something went wrong")

# Do:
raise DnsNotFoundError(
    code=DnsHostingErrorCodes.ZONE_NOT_FOUND,
    upstream_status=404,
    context={"zone_id": "abc123"}
)
```

When you instead have a raw `HTTPStatusError` from Cloudflare and need to pick the subclass from the status code, use the `_typed_dns_error` helper (see the full failure flow below). Direct raise for known conditions; helper for "I just got this status code, classify it for me."

Once you raise, you're done — Python's exception propagation walks back up the call stack until something catches it. As long as nothing in between wraps the call in a `try/except`, the typed error lands in the view's `except DnsHostingError` block, which matches the base class *and* every subclass, so one catch covers all the codes.

### 2. Catch Errors in Views Only

```python
try:
    dns_service.create_record(...)
except DnsHostingError as exc:
    # One place handles all DNS errors
    return dns_error_response(exc)
```

Services raise. Views catch.

**What about exceptions that aren't `DnsHostingError`?** Don't add a fallback `except Exception` in the view — it would swallow real bugs. Anything that isn't a `DnsHostingError` (a `DatabaseError`, a programming error, anything unexpected) propagates to Django's default 500 handling: the user sees `500.html` with the `request_id` shown (sub-ticket [#4928](https://github.com/cisagov/manage.get.gov/issues/4928)), and engineers find the full traceback in OpenSearch by that same ID.

### 3. Include Useful Context

When you raise an error, attach:
- The error code (which one it is)
- The HTTP status from Cloudflare (if there was one)
- Context dict (zone ID, record ID, anything that helps debugging)

### 4. Test the Error Code, Not the Message

```python
# Good — message can change
self.assertEqual(exc.code, DnsHostingErrorCodes.ZONE_NOT_FOUND)

# Bad — breaks when copy changes
self.assertIn("We couldn't find", str(exc))
```

Exceptions must also survive `pickle.dumps`/`pickle.loads` (the parallel test runner serializes them across processes):

```python
def test_my_error_is_picklable(self):
    exc = DnsNotFoundError(code=DnsHostingErrorCodes.ZONE_NOT_FOUND, upstream_status=404)
    restored = pickle.loads(pickle.dumps(exc))
    self.assertEqual(restored.code, exc.code)
```

---

## Exception Contract

Three rules for `DnsHostingError` and its subclasses:

1. **Only simple values on the exception.** `str`, `int`, dict-of-primitives. The parallel test runner pickles exceptions across processes; an `httpx.Response` object or a lambda in `context` breaks the pickle and the test run fails in confusing ways.
2. **The code, not the string, is the source of truth.** `_error_mapping` in `errors.py` provides default copy. After sub-ticket #4931, the admin-editable `DnsErrorMessage` table can override it. Tests assert on `exc.code` rather than the message string.
3. **Adding a new error type:** add the enum value, add a subclass if the new category doesn't fit an existing one, add the `_error_mapping` entry, ship a seed migration with the user-facing copy. Update the [Wire-code reference](#wire-code-reference) and [Captured-errors catalog](#captured-errors-catalog).

---

## Network Timeouts & Retries

Sub-ticket [#4923](https://github.com/cisagov/manage.get.gov/issues/4923). All values are in **seconds**. Leads should confirm or adjust before prod.

> Addresses [#4893](https://github.com/cisagov/manage.get.gov/issues/4893)'s description item: *"Define a retry strategy for httpx calls (when to fail fast vs. when to retry)."* Not a formal AC checkbox but called out as a consideration in the planning ticket.

### Timeouts

```python
httpx.Timeout(connect=3, read=10, write=10, pool=5)
```

- `connect=3` — Cloudflare's edge is normally sub-second. 3 seconds covers transient issues without hanging.
- `read=10` / `write=10` — DNS changes are small payloads. 10 seconds is generous but bounded.
- `pool=5` — `httpx` keeps a small pool of open connections to Cloudflare and reuses them, so we're not opening a fresh TCP connection every time. `pool=5` is the longest a request will wait for a free connection from that pool. Waiting more than 5 seconds means we have more concurrent DNS calls than the pool can serve — either the pool is too small for our load, or something is holding connections longer than expected (a slow Cloudflare day, a connection leak, an unexpected spike). We want it to fail fast rather than wait indefinitely: on timeout `httpx` raises `PoolTimeout` (a `RequestError`), the service raises `DnsTransportError(code=UPSTREAM_TIMEOUT)`, and it shows up in the logs as a clear signal to investigate.

### Hung Cloudflare calls

**Today (no timeout):** a hung Cloudflare call can pin a gunicorn worker until the OS-level TCP keepalive gives up (minutes) or gunicorn kills the worker (often 30s, returns a 502 with no app log).

**After this ticket:** the worst case is bounded.
- **Write calls (POST/PATCH/DELETE — the DNS save path):** no retry. Worst case = one attempt = ~13 seconds (`connect` + `read`).
- **Read calls (GET/HEAD):** up to 2 attempts + 1 backoff pause = ~27 seconds worst case. Sized to fit comfortably inside gunicorn's 30s worker timeout so we never hand a request over to the worker killer.

So adding timeouts + bounded retries holds the worker for **less** time than the current unbounded state, not more. The worker is released cleanly and the user gets a real error response with a `request_id` instead of a 502 from gunicorn.

### Retry: transport level

```python
httpx.HTTPTransport(retries=2)
```

Retries only the *initial connect*. Safe at any HTTP method because httpx only retries before it sees a response — no risk of double-creating a DNS record.

### Retry: at the app level (with backoff)

**Only for read-only calls (GET, HEAD).** Triggers:

- HTTP 429 — wait the number of seconds in the `Retry-After` header, then retry.
- HTTP 5xx — wait with increasing pauses (e.g. 1s, 2s, 4s) with a small random offset so all retries don't land at the same moment.
- Network errors (timeouts, connection drops) — same backoff as 5xx.

Cap at **2 total attempts** in all cases. We deliberately stay under 30 seconds of worker time — gunicorn kills workers that run longer than that, which would turn a recoverable Cloudflare blip into a 502 with no app log.

### Never retry writes (POST, PATCH, DELETE)

Retrying a write that already succeeded but was slow can create a duplicate DNS record. Writes fail fast; the user sees the error with a `request_id` and can decide whether to try again.

---

## What Gets Logged

Every DNS failure is written to OpenSearch as a structured JSON log line, keyed by `request_id`. That's where engineers debug, so the goal is rich logs there with nothing sensitive leaking out.

**Logged to OpenSearch — this is how we debug:**
- `request_id`, `zone_id` / `record_id`
- HTTP status (`upstream_status`) and Cloudflare's `cf_ray`
- `duration_ms`, `error_code`
- Full Python tracebacks. These live in OpenSearch only — they're essential for debugging, and are never shown to users or in `/admin`.

**Never logged anywhere — logs are retained and searchable:**
- API keys, tokens, `Authorization` headers, passwords
- Session cookies / CSRF tokens
- Request and response bodies — a TXT record's content can hold secrets. Log a redacted, truncated copy only if genuinely needed.

**PII — logged, but under the existing retention policy:**
- User email
- Client IP

---

## Structured logging in production

The registrar's app logs go to indices matching the pattern `logs-app*`. View them in cloud.gov logs > Dev Tools via:

```text
GET logs-app*/_mapping
```

The path a DNS log line travels from our code to a searchable field in OpenSearch:

1. **Service logs once.** `CloudflareService` (via the `_typed_dns_error` helper) calls `logger.exception(...)` at the point of failure with DNS-specific `extra={"upstream_status": ..., "error_code": ..., ...}` and raises the typed `DnsHostingError`.
2. **`JsonFormatter` emits one JSON document per log line** (`src/registrar/config/settings.py`). Beyond Python's defaults (`timestamp`, `level`, `name`, `lineno`, `message`), every line carries:
    - **DNS fields** from `extra={}` — `upstream_status`, `error_code`, `cf_ray`, `zone_id`, etc.
    - **Request context** from ContextVars — `user_email`, `ip_address`, `request_path`, `request_id`. `request_id` arrives with [#4924](https://github.com/cisagov/manage.get.gov/issues/4924); `user_email` / `ip_address` default to `"Anonymous"` / `"Unknown IP"` outside production.
    - `exception` — full traceback, only when `logger.exception(...)` is used.
3. **Cloud.gov forwards stdout** into the `logs-app*` OpenSearch indices and wraps our JSON under a top-level `app` object. So `error_code` becomes `app.error_code`, `request_id` becomes `app.request_id`, etc. **OpenSearch queries need the `app.` prefix.**
4. **OpenSearch dynamic mapping** indexes each `app.*` field the first time it's seen.

### Caveats

- **Search prefix is `app.*`, not top-level.** Query as `app.error_code:"DNS_ZONE_NOT_FOUND"` or `app.request_id:"..."`.
- **`message` and `exception` stay inside `@message` as text** — cloud.gov's ingester doesn't promote them to discrete `app.*` fields. Tracebacks are full-text searchable but not aggregable.

---

## User-Facing Error Messages

### When it's the user's fault (4xx — shown inline):

> "We couldn't find the DNS zone for this domain. It might not be enrolled in DNS hosting yet."

> "A record with that name already exists. Names must be unique."

> "The IP address isn't in a valid format."

> "You're making changes too quickly. Please wait a moment and try again."

### When it's our fault (5xx — shown at page level):

> "We couldn't reach our DNS provider. Please try again in a moment. If the problem persists, share this reference with support: `abc123-def456`."

---

## Admin Panel Features

### Admins will see:

1. **Success tracker** — when DNS records are created/updated/deleted, it appears in an audit log
2. **Quick links** — one click from the domain page to:
   - All DNS changes for this domain (audit log)
   - All recent DNS problems (OpenSearch)
3. **Message editor** — change error copy without deploying code

### Admins won't see:

- Python tracebacks
- Raw Cloudflare responses
- API credentials

---

## Editing Error Messages

Error messages live in a database table (sub-ticket [#4931](https://github.com/cisagov/manage.get.gov/issues/4931)). Go to `/admin` -> DNS error messages, edit the row, save. Live immediately. Django audits the change.

---

## Key Files

- **Error types:** `src/registrar/utility/errors.py`
- **Cloudflare service:** `src/registrar/services/cloudflare_service.py`
- **DNS service:** `src/registrar/services/dns_host_service.py`
- **View layer:** `src/registrar/views/domain.py`
- **Logging context:** `src/registrar/logging_context.py`
- **Admin interface:** `src/registrar/admin.py`
