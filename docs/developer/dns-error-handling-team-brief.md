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
