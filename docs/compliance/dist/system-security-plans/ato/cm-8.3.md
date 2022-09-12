---
implementation-status:
  - c-not-implemented
control-origination:
  - c-inherited-cloud-gov
  - c-inherited-cisa
  - c-common-control
  - c-system-specific-control
---

# cm-8.3 - \[catalog\] Automated Unauthorized Component Detection

## Control Statement

- \[a\] Detect the presence of unauthorized hardware, software, and firmware components within the system using organization-defined automated mechanisms frequency ; and

- \[b\] Take the following actions when unauthorized components are detected: No value found.

## Control guidance

Automated unauthorized component detection is applied in addition to the monitoring for unauthorized remote connections and mobile devices. Monitoring for unauthorized system components may be accomplished on an ongoing basis or by the periodic scanning of systems for that purpose. Automated mechanisms may also be used to prevent the connection of unauthorized components (see [CM-7(9)](#cm-7.9) ). Automated mechanisms can be implemented in systems or in separate system components. When acquiring and implementing automated mechanisms, organizations consider whether such mechanisms depend on the ability of the system component to support an agent or supplicant in order to be detected since some types of components do not have or cannot support agents (e.g., IoT devices, sensors). Isolation can be achieved , for example, by placing unauthorized system components in separate domains or subnets or quarantining such components. This type of component isolation is commonly referred to as "sandboxing."

## Control assessment-objective

the presence of unauthorized hardware within the system is detected using automated mechanisms frequency;
the presence of unauthorized software within the system is detected using automated mechanisms frequency;
the presence of unauthorized firmware within the system is detected using automated mechanisms frequency;
No value found are taken when unauthorized hardware is detected;
No value found are taken when unauthorized software is detected;
No value found are taken when unauthorized firmware is detected.

______________________________________________________________________

## What is the solution and how is it implemented?

<!-- Please leave this section blank and enter implementation details in the parts below. -->

______________________________________________________________________

## Implementation (a)

Add control implementation description here for item cm-8.3_smt.a

______________________________________________________________________

## Implementation (b)

Add control implementation description here for item cm-8.3_smt.b

______________________________________________________________________
