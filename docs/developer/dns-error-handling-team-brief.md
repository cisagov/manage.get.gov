# DNS Hosting Error Handling and Logging

## Team Brief

| | |
|---|---|
| Status | Draft for team discussion |
| Audience | Engineering, Product, Design, Support, Infra |
| Source material | [`dns-error-handling.md`](dns-error-handling.md) |

## Executive Summary

Our DNS Hosting error handling works, but it is not predictable enough for users, support, or engineers. The same failure can show up as a generic save error, a raw backend exception, or a 500 page, and today it is hard to trace one user action across the full request path.

This epic proposes a standard pattern for how DNS errors are classified, logged, surfaced to the frontend, and exposed in `/admin`. The goal is not to build a perfect observability platform in one pass. The goal is to give the team a clear, repeatable way to handle DNS failures so future work is easier to ship, debug, and support.

## The Problem We Are Solving

- DNS errors bubble up inconsistently across service, view, and UI layers.
- The frontend does not receive one standard machine-readable error shape.
- `/admin` does not provide enough context for support to trace a failed DNS action.
- Logs are not consistently structured for OpenSearch queries or cross-service debugging.
- We do not have a shared policy for when to retry, when to fail fast, and when to show the user a generic 500-style message.

## Why This Matters

### For users

- Validation and conflict errors should be actionable, not generic.
- System failures should feel calm and consistent.
- A visible `request_id` helps support investigate reported failures faster.

### For support and admins

- A failed DNS update should be traceable without digging through raw logs first.
- `/admin` should show a technical summary that is useful but still sanitized.

### For engineers

- One exception model makes code easier to reason about and test.
- Structured logs make production issues easier to query and triage.
- A defined retry strategy prevents both silent hanging and overly aggressive retries.

## Proposal in One Sentence

Adopt a single end-to-end DNS error contract: typed backend exceptions, one API error envelope, structured logs with correlation IDs, a clear split between user-correctable and system-failure errors, and an admin-visible operation log for support.

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

Create a `DnsOperationLog` view in `/admin` so support can search a `request_id` and quickly see:

- which DNS action failed
- what code it failed with
- what the upstream status was
- how long it took
- a sanitized technical summary

Admins should not see raw Python tracebacks in the normal support workflow.

### 6. Define a retry and failure policy

Use explicit `httpx` timeouts and a clear retry strategy:

- retry idempotent upstream requests when appropriate
- honor `Retry-After` when present
- fail fast on operations that should not be retried automatically

This gives us more predictable behavior under provider issues and timeouts.

## Guiding Principles

- Catch errors close to the source, but let views be the terminal handler for user-facing responses.
- Log with structured fields, not only string messages.
- Do not leak secrets, raw provider credentials, or sensitive request bodies into logs.
- Prefer a small, understandable error taxonomy over a large, overly specific one.
- Optimize for supportability as much as developer convenience.

## What Changes for Each Audience

| Audience | What improves |
|---|---|
| End users | Clearer error messages and more consistent failure states |
| Admins and support | Searchable request-level troubleshooting in `/admin` |
| Engineers | Typed exceptions, cleaner flow, easier testing, better logs |
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

### Phase 3: Observability and support

- Add structured DNS logging fields
- Add `DnsOperationLog` and related `/admin` visibility

### Phase 4: Future-facing improvements

- Evaluate OpenTelemetry or another tracing approach
- Consider admin-editable DNS error copy if we want non-devs to manage user-facing messaging

## Decisions We Need From The Team

- What log retention and access posture are acceptable for `user_email` and related identifiers?
- How much technical detail should `/admin` expose by default?
- Do we want to invest in OpenTelemetry now, or ship manual correlation first and spike tracing separately?
- Does Design want to review the proposed user-facing 4xx and 5xx error copy before implementation starts?

## Recommended Epic Outcome

By the end of this epic, we should have:

- a shared backend-to-frontend error vocabulary
- one documented and implemented error response pattern
- clear rules for what we log and what we do not log
- request-level traceability from UI through upstream DNS calls
- support-friendly visibility in `/admin`
- follow-on tickets that are small enough for engineers to pick up without more discovery

## For Team Review

Use this to align on the approach. We will not polish every implementation detail here that is for ticket refinement. The most important questions are:

1. Do we agree on the core error-handling pattern?
2. Do we agree on the 4xx versus 5xx user experience split?
3. Do we agree on the observability baseline for this epic?
4. Are there any privacy, support, or design concerns that change the proposal?

## Related Docs

- Design doc: [`dns-error-handling.md`](dns-error-handling.md)
