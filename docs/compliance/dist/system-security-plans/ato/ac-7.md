---
implementation-status:
  - c-not-implemented
control-origination:
  - c-inherited-cloud-gov
  - c-inherited-cisa
  - c-common-control
  - c-system-specific-control
---

# ac-7 - \[catalog\] Unsuccessful Logon Attempts

## Control Statement

- \[a\] Enforce a limit of number consecutive invalid logon attempts by a user during a time period ; and

- \[b\] Automatically No value found when the maximum number of unsuccessful attempts is exceeded.

## Control guidance

The need to limit unsuccessful logon attempts and take subsequent action when the maximum number of attempts is exceeded applies regardless of whether the logon occurs via a local or network connection. Due to the potential for denial of service, automatic lockouts initiated by systems are usually temporary and automatically release after a predetermined, organization-defined time period. If a delay algorithm is selected, organizations may employ different algorithms for different components of the system based on the capabilities of those components. Responses to unsuccessful logon attempts may be implemented at the operating system and the application levels. Organization-defined actions that may be taken when the number of allowed consecutive invalid logon attempts is exceeded include prompting the user to answer a secret question in addition to the username and password, invoking a lockdown mode with limited user capabilities (instead of full lockout), allowing users to only logon from specified Internet Protocol (IP) addresses, requiring a CAPTCHA to prevent automated attacks, or applying user profiles such as location, time of day, IP address, device, or Media Access Control (MAC) address. If automatic system lockout or execution of a delay algorithm is not implemented in support of the availability objective, organizations consider a combination of other actions to help prevent brute force attacks. In addition to the above, organizations can prompt users to respond to a secret question before the number of allowed unsuccessful logon attempts is exceeded. Automatically unlocking an account after a specified period of time is generally not permitted. However, exceptions may be required based on operational mission or need.

## Control assessment-objective

a limit of number consecutive invalid logon attempts by a user during time period is enforced;
automatically No value found when the maximum number of unsuccessful attempts is exceeded.

______________________________________________________________________

## What is the solution and how is it implemented?

<!-- Please leave this section blank and enter implementation details in the parts below. -->

______________________________________________________________________

## Implementation a.

Add control implementation description here for item ac-7_smt.a

______________________________________________________________________

## Implementation b.

Add control implementation description here for item ac-7_smt.b

______________________________________________________________________
