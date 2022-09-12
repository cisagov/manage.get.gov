---
implementation-status:
  - c-not-implemented
control-origination:
  - c-inherited-cloud-gov
  - c-inherited-cisa
  - c-common-control
  - c-system-specific-control
---

# cm-7.5 - \[catalog\] Authorized Software — Allow-by-exception

## Control Statement

- \[a\] Identify software programs;

- \[b\] Employ a deny-all, permit-by-exception policy to allow the execution of authorized software programs on the system; and

- \[c\] Review and update the list of authorized software programs frequency.

## Control guidance

Authorized software programs can be limited to specific versions or from a specific source. To facilitate a comprehensive authorized software process and increase the strength of protection for attacks that bypass application level authorized software, software programs may be decomposed into and monitored at different levels of detail. These levels include applications, application programming interfaces, application modules, scripts, system processes, system services, kernel functions, registries, drivers, and dynamic link libraries. The concept of permitting the execution of authorized software may also be applied to user actions, system ports and protocols, IP addresses/ranges, websites, and MAC addresses. Organizations consider verifying the integrity of authorized software programs using digital signatures, cryptographic checksums, or hash functions. Verification of authorized software can occur either prior to execution or at system startup. The identification of authorized URLs for websites is addressed in [CA-3(5)](#ca-3.5) and [SC-7](#sc-7).

## Control assessment-objective

software programs are identified;
a deny-all, permit-by-exception policy to allow the execution of authorized software programs on the system is employed;
the list of authorized software programs is reviewed and updated frequency.

______________________________________________________________________

## What is the solution and how is it implemented?

<!-- Please leave this section blank and enter implementation details in the parts below. -->

______________________________________________________________________

## Implementation (a)

Add control implementation description here for item cm-7.5_smt.a

______________________________________________________________________

## Implementation (b)

Add control implementation description here for item cm-7.5_smt.b

______________________________________________________________________

## Implementation (c)

Add control implementation description here for item cm-7.5_smt.c

______________________________________________________________________
