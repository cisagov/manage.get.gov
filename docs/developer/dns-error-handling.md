# DNS Error Handling

**Last updated** 2026-06-16

## Intro

For DNS error handling we introduce typed exception classes paired with a centralized error-code-to-message mapping (`_error_mapping` in `src/registrar/utility/errors.py`). This replaces the hardcoded error strings scattered throughout the code today.

**How to use it in the code:** When something goes wrong (Cloudflare is down, a zone doesn't exist, the network times out), raise a typed DnsHostingError subclass from the service layer. Python's exception propagation carries it up the call stack automatically — through `DnsHostService` (which does nothing with it) and into the view's `except DnsHostingError` block. The view then looks up the user-facing message in our error mapping and returns a standardized JSON response with the error code, message, and a request_id the user can share with support.

> **Design decision (and what new callers need to know)**
>
> **What we decided:** `CloudflareService` logs the failure once and raises a typed `DnsHostingError`. `DnsHostService` does nothing with it (no try/except). The view catches the typed error on purpose so it can handle the user-facing business logic — which message to show, which HTTP status to return, which template to render. The view does **not** log again.
>
> **At the time of writing, only the DNS records form view calls these services.** When we add a new caller (another view, a background job, an admin action, anything) you **must** catch `DnsHostingError` and decide what to render for your caller.
>
> **Why we chose this:**
>
> - **One place owns the user-facing copy.** Product and Design approve the wording in [#4999](https://github.com/cisagov/manage.get.gov/issues/4999); engineering wires the approved strings into the mapping in [#4950](https://github.com/cisagov/manage.get.gov/issues/4950). The view looks up the message by code and renders it.
> - **One log line per failure.** Today a single Cloudflare 400 produces *three* nearly-identical ERROR log lines (one in `CloudflareService`, one in `DnsHostService`, one in the view). After this work, the service logs once at the source and nothing duplicates it.
> - **The service is the safety net.** Logging at the source guarantees the failure is captured no matter who calls the service e.g. a future view, a background job, a management command.

**What's in this doc:**

- **Error Types** — the error codes we handle today, what triggers each, and how to look them up
- **What Developers Do** — the 4 rules: raise specific errors, catch only in views, include context, test by code not by message
- **Worked Example** — end-to-end flow of one failed DNS save to show the rules in action
- **Network Timeouts & Retries** — why we timeout, how long we wait, and when we retry (write operations never retry; read operations do with backoff)
- **Key Files** — where the error classes, services, views, and logging live

**Maintaining this doc:**  This guide covers what's being built right now. Future phases will add deeper features that will result in this doc requiring an update (including changing the "last updated" date at the top of the doc).

**How DNS errors are handled (summary):**

- Typed exception classes for every DNS failure
- A standardized JSON error response returned to the browser
- Structured fields on every log line
- A clear rule for where to raise and where to catch

Reference this when you're writing or debugging DNS-related code.

---

## Error Types

When Cloudflare says "no," here's what it means:

| What went wrong | Error name | User sees |
|---|---|---|
| Zone doesn't exist | `DNS_ZONE_NOT_FOUND` | TBD |
| Record already exists | `DNS_RECORD_CONFLICT` | "A record with that name already exists. Names must be unique." (reuses the existing model-level validation string) |
| Bad data | `DNS_VALIDATION_FAILED` | TBD |
| Too many requests | `DNS_RATE_LIMIT_EXCEEDED` | TBD |
| Permission denied | `DNS_AUTH_FAILED` | TBD |
| Network problem | `DNS_UPSTREAM_TIMEOUT` | TBD |
| Cloudflare down | `DNS_UPSTREAM_ERROR` | TBD |
| Something unexpected | `DNS_UNKNOWN` | TBD |

> "TBD" copy is finalized in [#4999](https://github.com/cisagov/manage.get.gov/issues/4999) (Product/Content owns the wording). This table is updated when those strings are approved.

**Quick rule:** 4xx codes are the user's problem (they can fix it). 5xx codes are our problem (Cloudflare or network).

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

| Source | Trigger | Code | User surface | Log level |
|---|---|---|---|---|
| Cloudflare 404 on POST `/zones/.../dns_records` | Zone record not found (stale local DB, race, test fixture) | `DNS_ZONE_NOT_FOUND` | Inline; TBD copy (see #4999) | warning |
| Cloudflare 409 | Duplicate record (same name+type). Rare — the local model validation at `dns_record.py` should catch most duplicates first; this fires only on races / vendor-side duplicates. | `DNS_RECORD_CONFLICT` | Inline field error using the existing model validation string ("A record with that name already exists. Names must be unique.") | warning |
| Cloudflare 400 | Invalid record content | `DNS_VALIDATION_FAILED` | Inline field error (reuse Cloudflare's reason when safe) | warning |
| Cloudflare 429 | Rate limit | `DNS_RATE_LIMIT_EXCEEDED` | Inline; TBD copy (see #4999) | warning |
| Cloudflare 401 / 403 | Invalid auth token or scope | `DNS_AUTH_FAILED` | Generic "couldn't reach DNS provider" + `request_id` | error |
| httpx `ConnectTimeout` / `ReadTimeout` / `WriteTimeout` | Network blip, Cloudflare slowdown | `DNS_UPSTREAM_TIMEOUT` | Generic + `request_id`, encourage retry | error |
| httpx `ConnectError` / `NetworkError` / DNS failure | Loss of connectivity to Cloudflare | `DNS_UPSTREAM_TIMEOUT` (catch-all for transport) | Generic + `request_id` | error |
| Cloudflare 5xx | Provider outage | `DNS_UPSTREAM_ERROR` | Generic + `request_id` | error |
| Any other Cloudflare status | Unexpected | `DNS_UNKNOWN` | Generic + `request_id` | error |
| Local model/form validation (existing, out of scope) | Invalid TTL, MX priority, CNAME conflict, bad DNS name | (uses `ValidationError`, not `DnsHostingError`) | Inline form field error | debug |

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
```

Every request gets a unique `request_id` from `RequestLoggingMiddleware` (#4924). The same ID flows into every log line for the request and into the JSON error response returned to the browser, so a user-reported reference ID can be traced back to the exact server-side events.

---

## What Developers Do

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

When you have an upstream `HTTPStatusError` and need to figure out which subclass fits based on the status code, use the `_typed_dns_error` helper instead — see the [full example](#full-example-of-the-failure-flow) below. Direct raise for known conditions; helper for "I just got this status code, classify it for me."

Once you raise, you're done. Python's exception propagation walks back up the call stack until something catches the exception. As long as no code in between wraps the call in a `try/except`, the typed error lands in the view's `except DnsHostingError` block (Rule #2). `except DnsHostingError` matches the base class *and* every subclass, so one catch covers all the codes.

### 2. Catch Errors in Views Only

```python
try:
    dns_service.create_record(...)
except DnsHostingError as exc:
    # The view catches on purpose to handle the user-facing business logic:
    # which message to show, which HTTP status, which template to render, etc.
    # No logger call here as the service already logged.
    return dns_error_response(exc)
```

Services log and raise. Views catch and render. A DNS failure produces exactly one log line — at the service, where the error is born, with full Cloudflare context.

`dns_error_response(exc)` reads `exc.code`, looks up the HTTP status in the Severity column of the [Wire-code reference](#wire-code-reference), and sends this JSON response back to the browser. Every DNS endpoint uses the same response:

```json
{
  "status": "error",
  "code": "DNS_ZONE_NOT_FOUND",
  "message": "We couldn't find the DNS zone for this domain.",
  "request_id": "1a2b3c4d-..."
}
```

Every DNS endpoint returns this same response on failure. HTMX templates (views) read the `code` to render the right inline / page-level message; `request_id` is what the user shares with support, what we will use to track the request.

**What about exceptions that aren't `DnsHostingError`?** Don't add a fallback `except Exception` in the view as that will swallow actual bugs. Anything that isn't a `DnsHostingError` (a `DatabaseError`, a programming bug, anything unexpected) propagates up to Django's default 500 handling. The user sees the `500.html` page with the `request_id` shown (sub-ticket [#4928](https://github.com/cisagov/manage.get.gov/issues/4928)) and engineers find the full traceback in OpenSearch by that same ID. After [#4922](https://github.com/cisagov/manage.get.gov/issues/4922) ships, `APIError` is gone — the `DnsHostingError` hierarchy replaces it, so you won't see it listed alongside `DatabaseError` above.

### 3. Include Useful Context

When you raise an error, attach:

- The error code (which one it is)
- The HTTP status from Cloudflare (if there was one)
- Context dict (zone ID, record ID, anything that helps debugging)

### 4. Test the Error Code, Not the Message

```python
self.assertEqual(exc.code, DnsHostingErrorCodes.ZONE_NOT_FOUND)

# Breaks when copy changes
self.assertIn("We couldn't find", str(exc))
```

Exceptions must also survive `pickle.dumps`/`pickle.loads` (the parallel test runner serializes them across processes):

```python
def test_my_error_is_picklable(self):
    exc = DnsNotFoundError(code=DnsHostingErrorCodes.ZONE_NOT_FOUND, upstream_status=404)
    restored = pickle.loads(pickle.dumps(exc))
    self.assertEqual(restored.code, exc.code)
```

### Full example of the failure flow

The four rules above in practice. End-to-end example of one failed DNS save once the typed-error work lands.

**Layer 1 — `CloudflareService` raises a typed error** (sub-ticket [#4921](https://github.com/cisagov/manage.get.gov/issues/4921)).

When the service is mapping a raw `HTTPStatusError` from Cloudflare to a typed exception, the status-to-subclass mapping lives in a single `_STATUS_TO_ERROR` dict and one helper at module scope, reused by every Cloudflare function.

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
            # Network / timeout — no HTTP response was received, so there's no status code
            # to map. Raise the transport-error subclass directly.
            raise DnsTransportError(
                code=DnsHostingErrorCodes.UPSTREAM_TIMEOUT,
                context={"zone_id": zone_id, "exc_class": type(e).__name__},
            ) from e
        return resp.json()
```

Two failure shapes from `httpx`:

- **`HTTPStatusError`** — Cloudflare gave us a response, but it was 4xx/5xx. The helper maps the status code to the right typed subclass.
- **`RequestError`** — no response came back at all (connect failure, timeout, DNS lookup failed). No status code exists to map, so the service raises `DnsTransportError` directly with `code=UPSTREAM_TIMEOUT`.

Adding a new status code is a line in the `_STATUS_TO_ERROR` dict. The helper is testable on its own — feed it a fake `HTTPStatusError` and assert the returned exception type and code.

The service logs **once** here, at the point of failure, with the raw Cloudflare context (`upstream_status`, `error_code`, `cf_ray`, `zone_id`, etc.). `logger.exception(...)` attaches the full Python traceback. The middleware's ContextVars (`request_id`, `user_email`, `ip_address`, `request_path`) are merged into the same log line by the `JsonFormatter`, so a single log entry has the Cloudflare-side context *and* the request-side context. Nothing downstream needs to log again.

> **Today vs. after #4924:** the `request_id` ContextVar is not wired up in the current code; [#4924](https://github.com/cisagov/manage.get.gov/issues/4924) deliver this. Until then the field stays empty on log lines. Also, `user_email`, `ip_address`, and `request_path` only populate in production environments — non-prod log lines show the `"Anonymous"` / `"Unknown IP"` defaults from `logging_context.py`. That gate stays in place after #4924 for privacy reasons.

**Layer 2 — `DnsHostService` passes the typed exception through unchanged** (sub-ticket [#4922](https://github.com/cisagov/manage.get.gov/issues/4922)). The current try/except around the Cloudflare call is removed. Because Python propagates exceptions up the call stack automatically, removing the `try/except` is all it takes — the typed error from `CloudflareService` flows straight through `DnsHostService` and into the view.

```python
# Before (today):
def create_dns_record(self, x_zone_id, form_record_data):
    try:
        vendor_record_data = self.dns_vendor_service.create_dns_record(x_zone_id, form_record_data)
    except (APIError, HTTPStatusError) as e:
        logger.error(f"Error creating DNS record: {str(e)}")
        raise APIError(str(e)) from e   # ← duplicate log, type collapsed to string
    ...

# After (post-#4922):
def create_dns_record(self, x_zone_id, form_record_data):
    # CloudflareService raises typed DnsHostingErrors; let them through.
    vendor_record_data = self.dns_vendor_service.create_dns_record(x_zone_id, form_record_data)
    ...
```

**Layer 3 — the view catches and renders the JSON response** (sub-ticket [#4925](https://github.com/cisagov/manage.get.gov/issues/4925)):

```python
try:
    self.dns_host_service.create_dns_record(zone_id, form_record_data)
except DnsHostingError as exc:
    # The view handles the user-facing business logic:
    # look up the message in our error mapping, pick the HTTP status from
    # the Severity column, decides which to render.
    return dns_error_response(exc, request=request)
```

The view does **not** log again. The service's log line already captured everything (Cloudflare-side fields from `extra={}` + middleware-injected fields like `request_id` and `user_email`). `dns_error_response` returns the JSON response shown in [Rule #2](#2-catch-errors-in-views-only).

---

## Structured logging in production

The registrar's app logs go to indices matching the pattern `logs-app*`. You can view in cloud.gov logs > Dev Tools via:

```text
GET logs-app*/_mapping
```

The path a DNS log line travels from our code to a searchable field in OpenSearch:

1. **Service logs once.** `CloudflareService` (via the `_typed_dns_error` helper) calls `logger.exception(...)` at the point of failure with DNS-specific `extra={"upstream_status": ..., "error_code": ..., ...}` and raises the typed `DnsHostingError`.

2. **`JsonFormatter` emits one JSON document per log line** ([`src/registrar/config/settings.py`](../../src/registrar/config/settings.py)). Beyond Python's defaults (`timestamp`, `level`, `name`, `lineno`, `message`), every line carries:
    - **DNS fields** from `extra={}` — `upstream_status`, `error_code`, `cf_ray`, `zone_id`, etc.
    - **Request context** from ContextVars — `user_email`, `ip_address`, `request_path`, `request_id`. `request_id` will be added via [#4924](https://github.com/cisagov/manage.get.gov/issues/4924). `user_email` / `ip_address` default to `"Anonymous"` / `"Unknown IP"` outside production.
    - `exception` — full traceback, only when `logger.exception(...)` is used on the upstream.

3. **Cloud.gov forwards stdout** into the `logs-app*` OpenSearch indices and wraps our JSON under a top-level `app` object. So `error_code` becomes `app.error_code`, `request_id` becomes `app.request_id`, etc. **OpenSearch queries need the `app.` prefix.**

4. **OpenSearch dynamic mapping** indexes each `app.*` field once received for the first time.

### Caveats

- **Search prefix is `app.*`, not top-level.** Query as `app.error_code:"DNS_ZONE_NOT_FOUND"`, `app.request_id:"..."`
- **`message` and `exception` stay inside `@message` as text** — cloud.gov's ingester does not promote them to discrete fields under `app.*`. Tracebacks are full-text searchable but not aggregable.

---

## Exception Contract

Two rules for `DnsHostingError` and its subclasses:

1. **Only simple values on the exception.** `str`, `int`, dict-of-primitives. The parallel test runner pickles exceptions across processes; an `httpx.Response` object or a lambda in `context` breaks the pickle and the test run fails in confusing ways.
2. **The code, not the string, is the source of truth.** `_error_mapping` in `errors.py` provides the default user-facing copy. Tests assert on `exc.code` rather than the message string.

---

## Network Timeouts & Retries

This section describes the timeout and retry policy for the DNS httpx client — all values are in **seconds**. The work addresses a consideration from planning ticket [#4893](https://github.com/cisagov/manage.get.gov/issues/4893) ("Define a retry strategy for httpx calls — when to fail fast vs. when to retry"). Implementation is tracked in [#4923](https://github.com/cisagov/manage.get.gov/issues/4923); production verification in [#5000](https://github.com/cisagov/manage.get.gov/issues/5000).

### Timeouts

```python
httpx.Timeout(connect=3, read=10, write=10, pool=5)
```

- `connect=3` — Cloudflare's edge is normally sub-second. 3 seconds covers transient issues without hanging.
- `read=10` / `write=10` — DNS changes are small payloads. 10 seconds is enough.
- `pool=5` — `httpx` keeps a small pool of open HTTP connections to Cloudflare and reuses them across requests (so we're not opening a fresh TCP connection every time). The `pool=5` timeout sets the longest a request will wait for a free connection from that pool. If it's waiting more than 5 seconds, it means we have more concurrent DNS calls happening than the pool can serve. Either:
  - the pool is too small for our actual load, OR
  - something is holding connections longer than expected (a slow Cloudflare day, a connection leak in our code, an unexpected spike).

  We want this to fail fast instead of waiting indefinitely for a free connection from the HTTP connection pool. With the configured pool=5s timeout, if no connection becomes available within 5 seconds, `httpx` raises a `PoolTimeout` (a `RequestError`), our service then raises `DnsTransportError(code=UPSTREAM_TIMEOUT)`, and the failure shows up in the logs. That gives us a clear signal to investigate, such as increase the pool size, check for a connection leak, or look at concurrency.

### Why timeouts matter

**Today (no timeout):** a hung Cloudflare call can pin a gunicorn worker until the OS-level TCP keepalive gives up (minutes) or gunicorn kills the worker (30s, returns a 502).

**After this ticket:** the worst case is capped.

- **Write calls (POST/PATCH/DELETE — the DNS save path):** no retry. Worst case = one attempt = ~13 seconds (`connect` + `read`).
- **Read calls (GET/HEAD):** up to 2 attempts + 1 backoff pause ≈ ~27 seconds worst case. Sized to fit comfortably inside gunicorn's 30s worker timeout so we never hand a request over to the worker killer.

So adding timeouts + capped retries holds the worker for **less** time than the current uncapped state, not more. The worker finishes the request and returns to the pool, and the user gets a real error response with a `request_id` instead of a 502 from gunicorn.

### Retry: transport level

```python
httpx.HTTPTransport(retries=2)
```

Retries only the *initial connect*. Httpx only retries before it sees a response, so retries stop the moment Cloudflare has actually received the request.

### Retry: at the app level (with backoff)

**Only for read-only calls (GET, HEAD).** Triggers:

- HTTP 429 — wait the number of seconds in the `Retry-After` header, then retry.
- HTTP 5xx — wait with increasing pauses (e.g. 1s, 2s, 4s) with a small random offset.
- Network errors (timeouts, connection drops) — same backoff as 5xx.

Cap at **2 total attempts** in all cases. We deliberately stay under 30 seconds of worker time — gunicorn kills workers that run longer, which would turn a recoverable Cloudflare blip into a 502.

### Never retry writes (POST, PATCH, DELETE)

Retrying a write that already succeeded but was slow can create a duplicate DNS record. Writes fail fast; the user sees the error with a `request_id` and can decide whether to try again.

### Where this lives

The policy is implemented in `src/registrar/services/dns_http_client.py`. `build_dns_client()` returns the shared `httpx.Client` (timeout + connect retries via `HTTPTransport`), and `RetryTransport` adds the app-level read retries and converts a network failure into `DnsTransportError`. `DnsHostService` and the DNS records view both use this client.

### Reproducing a hung response in dev

With `DNS_MOCK_EXTERNAL_APIS` on, save a DNS record whose name starts with `timeout-` (e.g. `timeout-test`). `MockCloudflareService` raises a connect timeout for that prefix, which surfaces as a `DnsTransportError`. Use an `error-500` / `error-400` / `error-403` prefix to exercise the matching HTTP error responses.

---

## User-Facing Error Messages

Approved copy is owned by Product/Content under [#4999](https://github.com/cisagov/manage.get.gov/issues/4999). Until that ticket closes, the messages in this section and in the [Error Types](#error-types) table are **TBD** — the one exception is the duplicate-record message, which reuses the existing model-level validation string.

### When it's the user's fault (4xx — shown inline)

> "A record with that name already exists. Names must be unique." (existing model-level validation string)

> *The other 4xx messages — `DNS_ZONE_NOT_FOUND`, `DNS_VALIDATION_FAILED`, `DNS_RATE_LIMIT_EXCEEDED` — are **TBD** in #4999.*

### When it's our fault (5xx — shown at page level)

> *TBD in #4999. The pattern is: a generic "couldn't reach our DNS provider, try again" message that always includes the reference ID for support.*

---

## Key Files

- **Error types:** `src/registrar/utility/errors.py`
- **DNS http client (timeout + retry policy):** `src/registrar/services/dns_http_client.py`
- **Cloudflare service:** `src/registrar/services/cloudflare_service.py`
- **DNS service:** `src/registrar/services/dns_host_service.py`
- **View layer:** `src/registrar/views/domain.py`
- **Logging context:** `src/registrar/logging_context.py`
- **Middleware:** `src/registrar/registrar_middleware.py`
