# DNS Error Handling — A Developer's Guide

**How DNS errors work in manage.get.gov and what you need to know.**

| | |
|---|---|
| **Status** | Ready to build |
| **Author** | Daisy Gutierrez |
| **Last updated** | 2026-04-22 |
| **For** | Engineers and developers (all levels) |

---

## The Big Picture

DNS errors are currently messy. Users get vague error messages. Support can't trace problems. We're fixing that by using specific error types, adding request IDs, and giving support better tools.

---

## What Changes

### For Users
- Specific, actionable error messages instead of generic "Failed to save DNS record."
- A reference ID (request_id) they can give support if something goes wrong

### For Developers
- Use typed error classes instead of generic ones
- Every DNS log line gets useful context (request ID, zone info, error code, etc.)
- Follow a standard pattern everywhere

### For Support
- Look up any problem by request ID
- Click links from `/admin` to see what happened
- Know which Cloudflare error (`cf_ray`) is involved

---

## The 8 Error Types

When Cloudflare says "no," here's what it means:

| What went wrong | Error name | User sees |
|---|---|---|
| Zone doesn't exist | `DNS_ZONE_NOT_FOUND` | "We can't find the DNS zone. It might not be set up yet." |
| Record already exists | `DNS_RECORD_CONFLICT` | "There's already a record with that name. Edit the existing one." |
| Bad data | `DNS_VALIDATION_FAILED` | "That data isn't valid." (+ Cloudflare's reason) |
| Too many requests | `DNS_RATE_LIMIT_EXCEEDED` | "You're going too fast. Wait a moment and try again." |
| Permission denied | `DNS_AUTH_FAILED` | "We couldn't reach Cloudflare. Try again later." |
| Network problem | `DNS_UPSTREAM_TIMEOUT` | "We couldn't reach Cloudflare. Try again later." |
| Cloudflare down | `DNS_UPSTREAM_ERROR` | "We couldn't reach Cloudflare. Try again later." |
| Something unexpected | `DNS_UNKNOWN` | "We couldn't reach Cloudflare. Try again later." |

**Quick rule:** First 4 are the user's problem (they can fix it). Last 4 are our problem (Cloudflare or network).

---

## How It Works (The Flow)

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
  Success? → Audit log (for admin to see)
  Failure? → OpenSearch (for engineers to investigate)
```

Every error gets tagged with a `request_id` so we can trace it from the user's browser through our code to Cloudflare's response.

---

## What Developers Do

### 1. Raise Specific Errors

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

### 2. Catch Errors in Views Only

```python
try:
    dns_service.create_record(...)
except DnsHostingError as exc:
    # One place handles all DNS errors
    return dns_error_response(exc)
```

Services raise. Views catch. Simple.

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

---

## Network Timeouts & Retries

Clear rules for talking to Cloudflare:

- **Give up after:** 3 seconds to connect, 10 seconds to read response
- **Retry automatically:** Once if connection fails (safe at network layer)
- **Retry on error:** For read-only calls (GET) up to 3 times with pauses
- **Never retry:** Write operations (POST, PATCH, DELETE) — might create duplicates

---

## What Gets Logged (Safely)

### Safe to log (no secrets):
- Request ID
- Zone ID / record ID
- HTTP status codes
- How long the operation took
- Cloudflare's `cf_ray` ID
- Error code names

### Never log:
- Request/response bodies (might contain secrets)
- Cloudflare API keys
- Django cookies
- Raw Python tracebacks (they go to OpenSearch only)
- Passwords or tokens

### Log carefully (existing policy applies):
- User email
- Client IP

---

## Finding a Problem (Support Runbook)

User reports: "I got an error. The reference is `abc123-def456`."

**Step 1: Find the error in logs**
- Go to `/admin` → domain → click "DNS logs in OpenSearch"
- Paste request ID or search by domain name
- See everything that happened

**Step 2: Check what they did**
- Click "DNS audit trail" to see successful changes
- Confirm if their action went through or failed

**Step 3: Escalate if needed**
- Find the `cf_ray` value in OpenSearch
- Give Cloudflare that value (not the request ID)

**Step 4: Help the user**
- If 4xx code: tell them how to fix it
- If 5xx code: apologize, ask them to retry

---

## User-Facing Error Messages

### When it's the user's fault (4xx — shown inline):

> "We couldn't find the DNS zone for this domain. It might not be enrolled in DNS hosting yet."

> "A record with that name and type already exists. Edit the existing record instead."

> "The IP address isn't in a valid format."

> "You're making changes too quickly. Please wait a moment and try again."

### When it's our fault (5xx — shown at page level):

> "We couldn't reach our DNS provider. Please try again in a moment. If the problem persists, contact help@get.gov and include this reference: `abc123-def456`."

That's it. No technical jargon. No HTTP status codes. Just "here's what happened" and "here's your reference number."

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

## Editing Error Messages (Product/Design)

**Today:** Changing one error message = code change + PR + deploy = days.

**After this:** Error messages live in a database table. Admins edit them.

### How it works:

1. Go to `/admin` → DNS error messages
2. Find the message you want to change
3. Edit and save
4. **It's live immediately** — no deploy
5. Django tracks who changed what and when

---

## Checklist: New Error Type

If you find a new way things can break:

- [ ] Does it fit one of the 8 types above?
- [ ] Add the new code (e.g., `DNS_NEW_THING`)
- [ ] Write a user-friendly message
- [ ] Add it to the catalog
- [ ] Write a test (exception must be picklable)
- [ ] Update docs

**But first:** Start with `DNS_UNKNOWN`. Only make a new code if you see the same problem multiple times in production.

---

## Testing Error Code

Exceptions must survive being pickled (tests pass them between processes):

```python
def test_my_error_is_picklable(self):
    exc = DnsNotFoundError(
        code=DnsHostingErrorCodes.ZONE_NOT_FOUND,
        upstream_status=404,
 context={"zone_id": "abc123"}
    )
    restored = pickle.loads(pickle.dumps(exc))
    self.assertEqual(restored.code, exc.code)
```

---

## Key Files

- **Error types:** `src/registrar/utility/errors.py`
- **Cloudflare service:** `src/registrar/services/cloudflare_service.py`
- **DNS service:** `src/registrar/services/dns_host_service.py`
- **View layer:** `src/registrar/views/domain.py`
- **Logging context:** `src/registrar/logging_context.py`
- **Admin interface:** `src/registrar/admin.py`

---

## Common Questions

**Q: Should I catch errors everywhere or just in views?**  
A: Views only. Services should raise and let it bubble up.

**Q: What error code should I use?**  
A: Start with `DNS_UNKNOWN`. Promote to a specific code later if you see the pattern again in production.

**Q: Can I change error messages without deploying?**  
A: Yes (once this is done). Go to `/admin` and edit the `DnsErrorMessage` table.

**Q: Do I set the request_id myself?**  
A: No. Middleware sets it automatically. It'll show up in logs.

**Q: Why 3 seconds timeout instead of something else?**  
A: Cloudflare usually responds faster. If they don't in 3 seconds, something's broken and waiting longer won't help.

**Q: What if I don't know whether to log something?**  
A: Ask: "Could this contain user secrets or personal info?" If yes, don't log it.

---

## Full Technical Details

For stakeholder discussions, architectural deep-dives, and implementation details, see the full design document (referenced by the DG team).

---

## Need Help?

- **This guide unclear?** Open an issue or ask in Slack.
- **Error handling question?** Look at existing DNS code for patterns.
- **Incident response?** Check OpenSearch by request_id.
