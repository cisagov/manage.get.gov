---
implementation-status:
  - c-implemented
control-origination:
  - c-inherited-cloud-gov
---

# cm-5 - \[catalog\] Access Restrictions for Change

## Control Statement

Define, document, approve, and enforce physical and logical access restrictions associated with changes to the system.

## Control guidance

Changes to the hardware, software, or firmware components of systems or the operational procedures related to the system can potentially have significant effects on the security of the systems or individuals’ privacy. Therefore, organizations permit only qualified and authorized individuals to access systems for purposes of initiating changes. Access restrictions include physical and logical access controls (see [AC-3](#ac-3) and [PE-3](#pe-3) ), software libraries, workflow automation, media libraries, abstract layers (i.e., changes implemented into external interfaces rather than directly into systems), and change windows (i.e., changes occur only during specified times).

## Control assessment-objective

physical access restrictions associated with changes to the system are defined and documented;
physical access restrictions associated with changes to the system are approved;
physical access restrictions associated with changes to the system are enforced;
logical access restrictions associated with changes to the system are defined and documented;
logical access restrictions associated with changes to the system are approved;
logical access restrictions associated with changes to the system are enforced.

______________________________________________________________________

## What is the solution and how is it implemented?

We inherit all of this from cloud.gov. 

cloud.gov enforces restrictions on available actions according to the system-provided org and space roles. All actions are logged and available to customers for auditing purposes.

______________________________________________________________________
