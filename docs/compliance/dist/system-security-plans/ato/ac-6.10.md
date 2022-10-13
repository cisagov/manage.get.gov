---
implementation-status:
  - c-implemented
control-origination:
  - c-inherited-cloud-gov
---

# ac-6.10 - \[catalog\] Prohibit Non-privileged Users from Executing Privileged Functions

## Control Statement

Prevent non-privileged users from executing privileged functions.

## Control guidance

Privileged functions include disabling, circumventing, or altering implemented security or privacy controls, establishing system accounts, performing system integrity checks, and administering cryptographic key management activities. Non-privileged users are individuals who do not possess appropriate authorizations. Privileged functions that require protection from non-privileged users include circumventing intrusion detection and prevention mechanisms or malicious code protection mechanisms. Preventing non-privileged users from executing privileged functions is enforced by [AC-3](#ac-3).

## Control assessment-objective

non-privileged users are prevented from executing privileged functions.

______________________________________________________________________

## What is the solution and how is it implemented?

The cloud.gov role-based access control system prevents non-privileged users from executing privileged functions.

______________________________________________________________________
