# .GOV DNS Hosting

## Introduction
DNS hosting allows managers of .gov domain to host its DNS with .GOV instead of an outside provider. Eventually .GOV hosting will be the default, with the option to host DNS elsewhere as needed. .GOV DNS Hosting is a white label for an external vendor (currently Cloudflare), and interfaces with the vendor through APIs.

We make our API calls through [httpx](https://www.python-httpx.org/). We utilize [htmx](https://htmx.org/) and [Alpine.js](https://alpinejs.dev/) for DOM updates. This allows us to change the UI without refreshing the page to update content. See [ADR](../architecture/decisions/0031-adopt-htmx-and-alpine-for-dynamic-content.md) and [HTMX and Alpine](#htmx-and-alpine) for more context.

## Scope (last updated: 11-20-2026)

See [Product Summary](https://docs.google.com/document/d/1iaaBi2iXKoVAPzEcRbXQbXwN1_v4Lf67Qz3C95nHLEw/edit?usp=sharing) for details

### Current
MVP
- Target users: newly registered .GOV domains managed by brand new users/organizations
- - Domains: must be under an organization and not yet in the registry
- New domains can enroll in .GOV DNS Hosting but cannot switch to an external host (without outlier admin support)
- Enrollment is controlled on the admin side (not by the user)
- Record types available:
  - A (IPv4)
  - AAAA (IPv6)
  - MX (mail server)
  - CNAME (redirect domain)
  - PTR (reverse lookup IP address → domain name)
  - TXT
- Features: All CRUD operations for DNS records; "Are you sure?" modals when advancing and data is not saved

### Future

- DNSSEC enabling and disabling
- .GOV DNS Hosting by default
- User-enabled switching between .GOV DNS Hosting and external DNS Hosting
- Additional record types (NS, CAA, HTTPS, SRV, SVCB)
- Account-level API tokens

## Architectural design

### Database

There are three main entities needed to set up DNS within the app: accounts, zones, and records. The models are vendor neutral to minimize complexity if switching to a new vendor. Each entity has a table that holds neutral data, a vendor table that holds data specific to the vendor (like external vendor-originating ids), while a join table indicates which vendor is currently active (`is_active`). For example, for accounts the three models/tables are `DnsAccount`, `DnsAccount_VendorDnsAccount`, and `VendorDnsAccount`.

### Secrets management
See [Secrets doc](https://docs.google.com/document/d/1IZjcmzL6q7DKsNTHbt5L0QbmESePeftsBUYa1Zy9C0U/edit?tab=t.qo2cobtxbilu#heading=h.lq5cblj3tmqm)

### Services

DnsHostService calls operations of the vendor, such as CloudflareService. This allows us to swap out the vendor more easily. We don't call CloudflareService directly, only through DnsHostService.

### .gov name servers

.GOV has custom names for our name servers which reflect words found in the United States Declaration of Independence. They are grouped into five name server sets, and each domain is assigned a set. (Ex: `equal.dns.gov`, `nature.dns.gov`, `respect.dns.gov`, `self-evident.dns.gov`, `truths.dns.gov`)

### Enrolling a domain

For MVP, an analyst can go to the domain page in /admin and click a button to "enroll" a domain in DNS. The enrollment button only shows for domains in an organization in the `DNS needed` state.  In the background, an account gets created, a zone under that account is created, and name servers are assigned. Account creation happens at the vendor and the data is also saved in the registrar's database. Name servers are then registered through EPP to the registry and will appear in the .gov zone file. The domain's DNS is then active. DNS-enrolled domains show a user-facing status of "Active" in the application (rather than "Ready" when not enrolled). In /admin, the backend state is displayed, which is still "Ready".

## Development

From `/admin`, ensure the waffle flag `dns_hosting` is ON.

### Local (and Vendor API Mocking)

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
To hit CF locally, you will need to set environment variables (see Sandbox section below) in the .env file, which can be retrieved from a sandbox's credentials.

### Sandbox (and Test Tenant)
By default, sandboxes utilize the Cloudflare .gov test tenant. (They _can_ use the MockCloudflareService if `DNS_MOCK_EXTERNAL_APIS=False`.)

The following environment variables must be set in cloud.gov per sandbox's getgov-credentials to test DNS Hosting using Cloudflare:

```
DNS_TENANT_KEY = {test tenant key}
DNS_SERVICE_EMAIL = {testing email address}
DNS_TENANT_ID = {id of the test tenant (as opposed to the prod tenant)}
```

Name servers use the domain `domainops.gov`. Because name servers get registered to OT&E (the registry sandbox), the domains are never active nor are the name servers authoritative. Note that for new domains, the vendor zone will be deleted after 28 days if not activated, so they will get of sync with the database.

See [Sandboxes and notes canvas](https://dhscisa.enterprise.slack.com/docs/T02QH7E1MHA/F060SBLVCSF) to see which sandboxes have the credentials set up.


### Production (and Prod Tenant)
The above variables are set specific to the .gov production tenant.
Name servers use the domain `dns.gov`.

### Fixtures
Locally (or more accurately when `DNS_MOCK_EXTERNAL_APIS=True`), when fixtures are loaded, about half of the domains created by the [domains fixture](../../src/registrar/fixtures/fixtures_domains.py) are enrolled in DNS Hosting. Five of those domains get at least one of each type of the in-scope records added. Fixtures do not enroll domains in DNS unless the api is mocked so that we don't create unnecessary clutter in the CF test tenant.

### Cloudflare
Note that both the "test" tenant and the prod tenant are actual production environments on the Cloudflare side. So, a zone can't simultaneously be active in both the test tenant and the prod tenant.

See [Cloudflare Notes (TBD)](TBD) for additional information

### Error handling and logging

See [dns-error-handling.md](dns-error-handling.md)

### Validation
Validations happen first on the form/model level. If a validation fails, the error is displayed in the form. If those validations pass, Cloudflare may catch something our application did not. In that case, CF will return an error, and we display a message based on the response from CF. This could be unforeseen errors, or errors that we intentionally left for CF to handle due to complexity. For example, a TXT record's content field has a combined max characters limit across records. In this case, we opt not to evaluate on the form/model level, and allow CF to evaluate the record data against other domain records and return the error if invalid.

Regarding messaging, if the error is something the user can do something about, we leave the form open and let them know what the issue was, if known, and if it is not something they can do something about (ex. 500 error), we close the form and display a more generic "something went wrong message".

### HTMX and Alpine
We use Alpine for simple operations like open/close of a form that don't require hitting the backend. HTMX is used when there is an update or information is needed from the backend. For example, when we update one record, rather than refresh the entire page with a newly updated page template, we only return the part of the DOM that needs updating, which is the record's row in the records table.

## Additional Resources

[Figma Designs](https://figma-gov.com/design/s2v7XTn7HTC9B0jtAJEbSX/.gov-registrar-Enterprise-Mode?node-id=4049-2982&p=f&t=Eg5EQPodeM5RYR8l-0)

[DNS Records content doc](https://docs.google.com/document/d/1u-K1yQKb16H3AWj33mH2e1LJme6Ay9dNXMG8isiOXWk/edit?tab=t.mmn4g5qk3h9r#heading=h.tmnw472kv8mr)

[System-generated alert message content](https://docs.google.com/spreadsheets/d/1hF7_n_zo3EpfbgqqqPUMtSMZXynMtRMsBMlcIqZ91ns/edit?usp=sharing)

[Cloudflare (TBD)](TBD)
