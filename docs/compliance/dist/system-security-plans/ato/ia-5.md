---
implementation-status:
  - c-not-implemented
control-origination:
  - c-inherited-cloud-gov
  - c-inherited-cisa
  - c-common-control
  - c-system-specific-control
---

# ia-5 - \[catalog\] Authenticator Management

## Control Statement

Manage system authenticators by:

- \[a\] Verifying, as part of the initial authenticator distribution, the identity of the individual, group, role, service, or device receiving the authenticator;

- \[b\] Establishing initial authenticator content for any authenticators issued by the organization;

- \[c\] Ensuring that authenticators have sufficient strength of mechanism for their intended use;

- \[d\] Establishing and implementing administrative procedures for initial authenticator distribution, for lost or compromised or damaged authenticators, and for revoking authenticators;

- \[e\] Changing default authenticators prior to first use;

- \[f\] Changing or refreshing authenticators time period by authenticator type or when events occur;

- \[g\] Protecting authenticator content from unauthorized disclosure and modification;

- \[h\] Requiring individuals to take, and having devices implement, specific controls to protect authenticators; and

- \[i\] Changing authenticators for group or role accounts when membership to those accounts changes.

## Control guidance

Authenticators include passwords, cryptographic devices, biometrics, certificates, one-time password devices, and ID badges. Device authenticators include certificates and passwords. Initial authenticator content is the actual content of the authenticator (e.g., the initial password). In contrast, the requirements for authenticator content contain specific criteria or characteristics (e.g., minimum password length). Developers may deliver system components with factory default authentication credentials (i.e., passwords) to allow for initial installation and configuration. Default authentication credentials are often well known, easily discoverable, and present a significant risk. The requirement to protect individual authenticators may be implemented via control [PL-4](#pl-4) or [PS-6](#ps-6) for authenticators in the possession of individuals and by controls [AC-3](#ac-3), [AC-6](#ac-6) , and [SC-28](#sc-28) for authenticators stored in organizational systems, including passwords stored in hashed or encrypted formats or files containing encrypted or hashed passwords accessible with administrator privileges.

Systems support authenticator management by organization-defined settings and restrictions for various authenticator characteristics (e.g., minimum password length, validation time window for time synchronous one-time tokens, and number of allowed rejections during the verification stage of biometric authentication). Actions can be taken to safeguard individual authenticators, including maintaining possession of authenticators, not sharing authenticators with others, and immediately reporting lost, stolen, or compromised authenticators. Authenticator management includes issuing and revoking authenticators for temporary access when no longer needed.

## Control assessment-objective

system authenticators are managed through the verification of the identity of the individual, group, role, service, or device receiving the authenticator as part of the initial authenticator distribution;
system authenticators are managed through the establishment of initial authenticator content for any authenticators issued by the organization;
system authenticators are managed to ensure that authenticators have sufficient strength of mechanism for their intended use;
system authenticators are managed through the establishment and implementation of administrative procedures for initial authenticator distribution; lost, compromised, or damaged authenticators; and the revocation of authenticators;
system authenticators are managed through the change of default authenticators prior to first use;
system authenticators are managed through the change or refreshment of authenticators time period by authenticator type or when events occur;
system authenticators are managed through the protection of authenticator content from unauthorized disclosure and modification;
system authenticators are managed through the requirement for individuals to take specific controls to protect authenticators;
system authenticators are managed through the requirement for devices to implement specific controls to protect authenticators;
system authenticators are managed through the change of authenticators for group or role accounts when membership to those accounts changes.

______________________________________________________________________

## What is the solution and how is it implemented?

<!-- Please leave this section blank and enter implementation details in the parts below. -->

______________________________________________________________________

## Implementation a.

Add control implementation description here for item ia-5_smt.a

______________________________________________________________________

## Implementation b.

Add control implementation description here for item ia-5_smt.b

______________________________________________________________________

## Implementation c.

Add control implementation description here for item ia-5_smt.c

______________________________________________________________________

## Implementation d.

Add control implementation description here for item ia-5_smt.d

______________________________________________________________________

## Implementation e.

Add control implementation description here for item ia-5_smt.e

______________________________________________________________________

## Implementation f.

Add control implementation description here for item ia-5_smt.f

______________________________________________________________________

## Implementation g.

Add control implementation description here for item ia-5_smt.g

______________________________________________________________________

## Implementation h.

Add control implementation description here for item ia-5_smt.h

______________________________________________________________________

## Implementation i.

Add control implementation description here for item ia-5_smt.i

______________________________________________________________________
