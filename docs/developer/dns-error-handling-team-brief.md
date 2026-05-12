# DNS Hosting Error Handling and Logging

## Team Brief

| | |
|---|---|
| Status | Draft for team discussion |
| Audience | Engineering, Product, Design, Support, Infra |
| Source material | [`dns-error-handling.md`](dns-error-handling.md) |

## Overview

Right now, when a DNS action fails, it’s a bit of a mystery for everyone. Finding out "why" usually requires an engineer to go digging through code and logs. 

We’re changing that. Our goal is to make errors predictable, give the team more control over the messaging, and make it easy for Support to help users without needing a developer's help every time.


### Updating Messages on the Fly
Instead of burying error text in the code, we’re moving it to the **Admin Portal**. If Design or Product wants to fix a typo or clarify a message, you can just log in and change it yourself. No more waiting for a code deploy just to fix a "The" to a "Their."

### A Faster Way to Troubleshoot
When a user runs into a snag, they’ll see a unique **Reference ID**. Support can take that ID, search for it, and see the exact history of that specific error. It saves everyone from the "back and forth" and lets us solve problems way faster.

### Clearer Communication
We’re splitting errors into two clear groups:
1. **User Issues:** Things like "this domain is already taken" or "check your spelling." We’ll give users the info they need to fix it themselves.
2. **System Issues:** If Cloudflare or our backend is having a bad day, we’ll be honest about it so the user knows it’s not their fault and they just need to try again in a minute.

### Automatic History
We’re turning on a "history book" for all DNS changes. This means we’ll have a clear record of who did what and when. It’s great for security and even better for figuring out where things went sideways.

## Technical Translation
You might see these terms in the tickets; here is what they actually mean for the rest of us:

* **API Envelope:** Making every error follow the same consistent look and feel.
* **X-Request-ID:** The "Digital Receipt" we give to users.
* **Auditlog:** The automatic history book of changes.
* **Admin-editable copy:** Letting non-devs update text in the browser.
* **Deep-linking:** A one-click button to jump from a problem to the detailed logs in OpenSearch.

## Suggested Rollout

The work is grouped into four phases so each one delivers something usable on its own. Earlier phases unblock the later ones.

### Phase 1: Foundations

The building blocks everything else depends on. Two tracks that can run in parallel: dev foundations and copy.

**Dev track:**

* New DNS-specific error types and a shared list of error codes — [#4920](https://github.com/cisagov/manage.get.gov/issues/4920)
* Reference ID (`request_id`) that flows through every log line — [#4924](https://github.com/cisagov/manage.get.gov/issues/4924)
* One consistent error shape sent back to the browser — [#4925](https://github.com/cisagov/manage.get.gov/issues/4925)

**Copy track (Product/Content, runs in parallel):**

* Writes and approves user-facing copy for all 8 error codes so it's ready when the envelope and seed migration land — [#4999](https://github.com/cisagov/manage.get.gov/issues/4999)

### Phase 2: Service and UI alignment

Wire the new error types into the services and the form so users see the standard shape.

* Cloudflare service raises the new typed errors — [#4921](https://github.com/cisagov/manage.get.gov/issues/4921)
* Remove the duplicate error-wrapping in `DnsHostService` — [#4922](https://github.com/cisagov/manage.get.gov/issues/4922)
* Set timeouts and a bounded retry policy so a stuck Cloudflare call can't hang a worker — [#4923](https://github.com/cisagov/manage.get.gov/issues/4923)
* Surface the reference ID on the 500 error page — [#4928](https://github.com/cisagov/manage.get.gov/issues/4928)
* Tighten `register_nameservers` error handling — [#4997](https://github.com/cisagov/manage.get.gov/issues/4997)
* Register `DnsRecord` / `DnsZone` / `DnsAccount` with `django-auditlog` so support gets a "who changed what" history right away — [#4996](https://github.com/cisagov/manage.get.gov/issues/4996)
* Engineering wires the approved copy from #4999 into the seed migration and `_error_mapping` — [#4950](https://github.com/cisagov/manage.get.gov/issues/4950)

### Phase 3: Visibility, support, and self-serve copy

Make failures easy to investigate and let Design and Product own the copy.

* Structured fields on every DNS log line (zone, record, `cf_ray`, duration, etc.) — [#4926](https://github.com/cisagov/manage.get.gov/issues/4926)
* Narrow `except Exception` to `(IntegrityError, DatabaseError)` in `DnsHostService` DB-write blocks — [#4998](https://github.com/cisagov/manage.get.gov/issues/4998)
* Domain admin OpenSearch deep-links + paste box (uses the request ID and structured fields from earlier phases) — [#4927](https://github.com/cisagov/manage.get.gov/issues/4927)
* Admin-editable user-facing error copy, no deploy needed — [#4931](https://github.com/cisagov/manage.get.gov/issues/4931)
* Developer docs and support runbook finalized — [#4929](https://github.com/cisagov/manage.get.gov/issues/4929)
* Verify the new retry policy in production using OpenSearch — kicks off the moment #4923 and #4926 are live — [#5000](https://github.com/cisagov/manage.get.gov/issues/5000)

### Phase 4: Future-facing

Decisions and follow-ups we don't have to make right now.

* Decide whether OpenSearch + structured logs is enough for request tracing, or whether we should adopt a dedicated tracing tool — [#4930](https://github.com/cisagov/manage.get.gov/issues/4930)
* If admin-editable copy works for DNS, extend the same pattern to Nameserver, DsData, and SecurityEmail errors — no ticket yet

After Phase 1 and 2 are done, we can re-evaluate the scope of Phases 3 and 4.
