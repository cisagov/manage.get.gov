---
implementation-status:
  - c-not-implemented
control-origination:
  - c-inherited-cloud-gov
  - c-inherited-cisa
  - c-common-control
  - c-system-specific-control
---

# sc-7.7 - \[catalog\] Split Tunneling for Remote Devices

## Control Statement

Prevent split tunneling for remote devices connecting to organizational systems unless the split tunnel is securely provisioned using safeguards.

## Control guidance

Split tunneling is the process of allowing a remote user or device to establish a non-remote connection with a system and simultaneously communicate via some other connection to a resource in an external network. This method of network access enables a user to access remote devices and simultaneously, access uncontrolled networks. Split tunneling might be desirable by remote users to communicate with local system resources, such as printers or file servers. However, split tunneling can facilitate unauthorized external connections, making the system vulnerable to attack and to exfiltration of organizational information. Split tunneling can be prevented by disabling configuration settings that allow such capability in remote devices and by preventing those configuration settings from being configurable by users. Prevention can also be achieved by the detection of split tunneling (or of configuration settings that allow split tunneling) in the remote device, and by prohibiting the connection if the remote device is using split tunneling. A virtual private network (VPN) can be used to securely provision a split tunnel. A securely provisioned VPN includes locking connectivity to exclusive, managed, and named environments, or to a specific set of pre-approved addresses, without user control.

## Control assessment-objective

split tunneling is prevented for remote devices connecting to organizational systems unless the split tunnel is securely provisioned using safeguards.

______________________________________________________________________

## What is the solution and how is it implemented?

Add control implementation description here for control sc-7.7

______________________________________________________________________
