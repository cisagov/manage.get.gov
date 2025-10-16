# 1. DNS Hosting architecture: use services in registrar app

Date: 2025-10-16

## Status

Accepted

## Context

DNS Hosting is a new product offering that requires some architectural decisions. How much do we need to anticipate isolating the functionality? Is this a service we want to be able to pull out and reuse elsewhere?

## Decision

## Considered Options

### 1. Microservice

### 2. Internal Django app

### 3. Use separate services inside existing registrar app

    We would create two separate services within the registar app: CloudflareService (or DnsHostVendorService) and DnsHostService. CloudflareService would encapsulate all cloudflare-specific calls to the api. DnsVendorService would call that service.

    + If we switched vendors, CloudflareService could be replace with a service based on another vendor's apis and api structure
 
