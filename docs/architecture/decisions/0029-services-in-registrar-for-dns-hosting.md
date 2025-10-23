# 29. DNS Hosting architecture: use services in registrar app

Date: 2025-10-16

## Status

Accepted

## Context

DNS Hosting is a new product offering that requires some architectural decisions. How much do we anticipate isolating the functionality of dns hosting? Is this a service we want to be able to pull out and reuse elsewhere? We are currently not aware of a need to reuse and apply the dns product elsewhere outside of this project. Isolation would mean we could scale independently, but that may not be needed.

## Decision

(#2) Use separate services inside existing registrar app

This design separates out vendor specific code and data and minimizes architecture changes for faster implementation and carries the least risk

## Considered Options



### 1. Internal Django app

This would mean creating an app `dns_hosting` as an app inside of the project (parallel to `registrar`). Migrations would be separate, but the db would be the same.

+ Cleaner organization of dns code from registrar code
+ Can be lifted more easily if we intend to reuse it elsewhere later
+ Migrations can be worked on separately from `registrar`

- Possible mixing of templates and views between the apps could get confusing
- As new devs onboarded and worked on it, they would need to be aware of the need to make sure there is only one-way dependency
- YAGNI (You Aren't Gonna Need It) - we don't currently have a need to use the functionality elsewhere. We might spend extra development time for something we might not need

### 2. Use separate services inside existing registrar app

We would create two separate services within the registar app: CloudflareService (or DnsHostVendorService) and DnsHostService. CloudflareService would encapsulate all cloudflare-specific calls to the api. DnsVendorService would call CloudflareSerivce methods, and would be the only service to call CloudflareService.

+ If we switched vendors, CloudflareService could be replace with a service based on another vendor's apis and api structure
+ Can get organizational separation by using different modules within the app
+ No risk of dependency issues between different apps
+ Higher velocity to get started with minimal infrastructural changes
+ By combining faster implementation with a slow rollout to users, we can monitor behavior and switch strategies if we see that we need to adjust
+ Developers don't need to be aware of avoiding two-way dependencies

- would need to pull out the code if we wanted a separate app later

### 3. Microservice

+ No dependencies to clash
+ Clean separation of concerns
+ Could use a different stack if desired
+ Could scale independently of the registrar

- Would need to build out an additional API on the registrar side or add infrastructure to communicate between services
-  YAGNI (You Aren't Gonna Need It) - we don't currently have a need to use the functionality elsewhere (over-engineering) We could end up spending extra development time on something we will not need.
- Using microservices would introduce many complexities in deployment, debugging, and monitoring
