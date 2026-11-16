# .GOV DNS Hosting

## Introduction
DNS hosting allows managers of .gov domain to host its DNS with .GOV instead of an outside provider. Eventually we want that to be the default, with the option to host DNS elsewhere as needed. .GOV DNS Hosting is a white label for an external vendor (currently Cloudflare), and interfaces with the vendor through APIs.

We make our API calls through `httpx`. We utilize `htmx` and `Alpine.js` for DOM updates. This allows us to change the UI without refeshing the page to update content. See [ADR]() for more context.

## Scope (last updated: 11-20-2026)

See [Product Summary](https://docs.google.com/document/d/1iaaBi2iXKoVAPzEcRbXQbXwN1_v4Lf67Qz3C95nHLEw/edit?usp=sharing) for details

### Current
MVP
- Target users: newly registered .gov domains managed by brand new users/organizations
- - Domains: must be under an organization and not yet in the registry
- New domains can enroll in .gov DNS Hosting but cannot switch to an external host (without outlier admin support)
- Enrollment is controlled on the admin side (not by the user)
- Record types available:
  - A (IPv4)
  - AAAA (IPv6)
  - MX (mail server)
  - CNAME (redirect domain)
  - PTR (reverse lookup IP address → domain name)
  - TXT
- Features: All CRUD operations for DNS records

### Future

- DNSSEC enabling and disabling
- .gov DNS Hosting by default
- User-enabled switching between .gov DNS Hosting and external DNS Hosting
- Additional record types (NS, CAA, HTTPS, SRV, SVCB)
- Account-level API tokens

## Architectural design

### Database

There are three main entities to set up DNS: Accounts, Zones, and Records. The models are vendor neutral to minimize complexity if switching to a new vendor. Each entity has a table that holds neutral data, a vendor table (ex. VendorDnsAccount) that holds data specific to the vendor (like external vendor-originating ids), while a join table indicates which vendor is currently active (`is_active`).

### Secrets management
[Link]

### Services

DnsHostService calls operations of the vendor, such as CloudflareService. This allows us to swap out the vendor more easily. We don't call CloudflareService directly, only through DnsHostService.

### .gov name servers

.GOV has custom names for our name servers which reflect words found in the United States Declaration of Independence. They are grouped into five name server sets, and each domain is assigned a set. (Ex: `equal.dns.gov`, `nature.dns.gov`, `respect.dns.gov`, `self-evident.dns.gov`, `truths.dns.gov`)

## Development

### Local (and Vendor API Mocking)
- From `/admin`, ensure the waffle flag `dns_hosting` is ON.

 - In local development, we can mock the API calls using MockCloudflareService.
    We use the library `respx` for mocking `httpx` api calls and responses. Through an environment variable, we determine when to use a MockCloudflareService class which mocks the responses of the api calls.
    To utilize the mocks

-  Set the .env value:
```
  DNS_MOCK_EXTERNAL_APIS=True
  ```
- From the DNS Records page (`*/domain/*/dns/records`) Fill and submit a valid record and you will get a success response.
- To mock using an existing account/zone (rather than creating a new one for each dns record created), use the domain
  `exists.gov`
- To trigger a dns record error response, enter a record name that starts with any of the following:
    | Record name starts with | Result|
    |---|---|
    | error-400, error-401, error-403, error-429 | That http status |
    | error-duplicate, error-invalid-name, error-content, error-name-conflict, error-exceed-content-max, error-exceed-combined-content-max | 400 with the real Cloudflare error code and message |
    | any other `error` | 500 |
    | timeout | Connect timeout (exercises the transport error path)

     see [MockCloudflareService._mock_cf_error_response]() to see CF responses

- Setting the `DNS_MOCK_EXTERNAL_APIS` to `False` will utilize the actual Cloudflare test tenant.
To hit CF locally, you will need to set environment variables (see below) in the .env file, which can be retrieved from a sandbox's credentials.

#### Tests
We currently use Mocks and

### Sandbox (and Test Tenant)
By default, sandboxes utilize the Cloudflare .gov test tenant. They _can_ use the MockCloudflareService if `DNS_MOCK_EXTERNAL_APIS=False`.

The following environment variables must be set in cloud.gov per sandbox to test DNS Hosting:

```
DNS_TENANT_KEY = {tenant key}
DNS_SERVICE_EMAIL = {An email address}
DNS_TENANT_ID = {id of the test tenant (as opposed to the prod tenant)}
```

Name servers use the domain `domainops.gov`

See [Sandboxes and notes canvas](https://dhscisa.enterprise.slack.com/docs/T02QH7E1MHA/F060SBLVCSF) to see which sandboxes have the credentials set up.

### Production (and Prod Tenant)
The above variables are set specific to the .gov production tenant.
Name servers use the domain `dns.gov`

### Cloudflare
Note that both the "test" tenant and the prod tenant are actual production environments on the Cloudflare side. So a zone can't simultaneously be active in both the test tenant and the prod tenant.

See [Cloudflare Notes]() for additional context

### Error handling and logging

[dns-error-handling.md]()

### Validation
Validations happen on the form level and then the model level.

### HTMX and Alpine

## Resources

[Figma Designs]()

[Cloudflare]()
