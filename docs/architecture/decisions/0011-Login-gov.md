# n. Login.gov

Date: 2022-09-26

## Status

Approved

## Context

Logging users into the system is an exceptionally important aspect of the new build.

As Login.gov is a peer project within TTS–TTS being the umbrella organization which grew out of and now encompasses 18F–use of it for authentication purposes is a customary choice for 18F projects. 

## Decision

To use Login.gov.

## Consequences

Consequences can be explored along several dimensions.

Security: Login.gov’s sole purpose is to ensure users are authentically who they claim to be. This singularity of purpose gives them an advantage over vendors who offer user authentication as one of many products. It is a product developed by government for government. Login.gov is in the process of achieving certification of compliance with NIST’s IAL2 standard (for identity proofing) from a third-party assessment organization.

Equity: Login.gov is committed to reducing the disparate impact of automated fraud detection. Regardless, the ability to which they are able to do so will be constrained by inherent inequities in the technological solutions available. Users of get.gov are anticipated to be mainly government employees, so the unfair burden placed on some users of Login.gov may be mitigated by resources available to them through their employer. This cannot be guaranteed, however.

Cost: Cost was not a factor in consideration. Login.gov is expected to be neither surprisingly cheaper nor surprisingly more expensive than alternative options.
