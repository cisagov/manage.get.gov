# 18. Registry Integration

Date: 2022-02-15

## Status

Accepted

## Context

There are relatively few existing open source software projects which implement registry-registrar communications and even fewer of them in Python.

This creates a twofold problem: first, there are few design patterns which we can consult to determine how to build; second, there are few libraries we can freely use.

The incoming registry vendor has pointed to [FRED’s epplib](https://gitlab.nic.cz/fred/utils/epplib) as a newly-developed example which may suit most of our needs. This library is able to establish the TCP connection. It also contains a number of helper methods for preparing the XML requests and parsing the XML responses.

Commands in the EPP protocol are not synchronous, meaning that the response to a command will acknowledge receipt of it, but may not indicate success or failure.

This creates an additional challenge: we do not desire to have complex background jobs to run polling. The registrar does not anticipate having a volume of daily users to make such an investment worthwhile, nor a supply of system administrators to monitor and troubleshoot such a system.

Beyond these mechanical requirements, we also need a firm understanding of the rules governing how and when commands can be issued to the registry.

## Decision

To use the open source FRED epplib developed by the .cz registry.

To treat commands given to the registry as asynchronous from a user experience perspective. In other words, “the registry has received your request, please check back later”.

To develop the Domain model as the interface to epplib.

## Consequences

Using the Domain model as an interface will funnel interactions with the registry and consolidate rules in a single location. This will be a significant benefit to future maintainers, but it does stretch the normal metaphor of a Django model as representing a database table. This may introduce some confusion or uncertainty.

Treating commands as asynchronous will need support from content managers and user interface designers to help registrants and analysts understand the system’s behavior. Without adequate support, users will experience surprise and frustration.

FRED epplib is in early active development. It may not contain all of the features we’d like. Limitations in what upstream maintainers are able to accept, either due to policy or due to staffing or due to lack of interest, may require CISA to fork the project. This will incur a maintenance burden on CISA.
