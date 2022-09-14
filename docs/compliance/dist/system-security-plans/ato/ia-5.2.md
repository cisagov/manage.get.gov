---
implementation-status:
  - c-not-implemented
control-origination:
  - c-inherited-cloud-gov
  - c-inherited-cisa
  - c-common-control
  - c-system-specific-control
---

# ia-5.2 - \[catalog\] Public Key-based Authentication

## Control Statement

- \[a\] For public key-based authentication:

  - \[1\] Enforce authorized access to the corresponding private key; and
  - \[2\] Map the authenticated identity to the account of the individual or group; and

- \[b\] When public key infrastructure (PKI) is used:

  - \[1\] Validate certificates by constructing and verifying a certification path to an accepted trust anchor, including checking certificate status information; and
  - \[2\] Implement a local cache of revocation data to support path discovery and validation.

## Control guidance

Public key cryptography is a valid authentication mechanism for individuals, machines, and devices. For PKI solutions, status information for certification paths includes certificate revocation lists or certificate status protocol responses. For PIV cards, certificate validation involves the construction and verification of a certification path to the Common Policy Root trust anchor, which includes certificate policy processing. Implementing a local cache of revocation data to support path discovery and validation also supports system availability in situations where organizations are unable to access revocation information via the network.

## Control assessment-objective

authorized access to the corresponding private key is enforced for public key-based authentication;
the authenticated identity is mapped to the account of the individual or group for public key-based authentication;
when public key infrastructure (PKI) is used, certificates are validated by constructing and verifying a certification path to an accepted trust anchor, including checking certificate status information;
when public key infrastructure (PKI) is used, a local cache of revocation data is implemented to support path discovery and validation.

______________________________________________________________________

## What is the solution and how is it implemented?

<!-- Please leave this section blank and enter implementation details in the parts below. -->

______________________________________________________________________

## Implementation (a)

Add control implementation description here for item ia-5.2_smt.a

______________________________________________________________________

## Implementation (b)

Add control implementation description here for item ia-5.2_smt.b

______________________________________________________________________
