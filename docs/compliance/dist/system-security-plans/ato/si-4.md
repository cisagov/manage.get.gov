---
implementation-status:
  - c-not-implemented
control-origination:
  - c-inherited-cloud-gov
  - c-inherited-cisa
  - c-common-control
  - c-system-specific-control
---

# si-4 - \[catalog\] System Monitoring

## Control Statement

- \[a\] Monitor the system to detect:

  - \[1\] Attacks and indicators of potential attacks in accordance with the following monitoring objectives: monitoring objectives ; and
  - \[2\] Unauthorized local, network, and remote connections;

- \[b\] Identify unauthorized use of the system through the following techniques and methods: techniques and methods;

- \[c\] Invoke internal monitoring capabilities or deploy monitoring devices:

  - \[1\] Strategically within the system to collect organization-determined essential information; and
  - \[2\] At ad hoc locations within the system to track specific types of transactions of interest to the organization;

- \[d\] Analyze detected events and anomalies;

- \[e\] Adjust the level of system monitoring activity when there is a change in risk to organizational operations and assets, individuals, other organizations, or the Nation;

- \[f\] Obtain legal opinion regarding system monitoring activities; and

- \[g\] Provide system monitoring information to personnel or roles No value found.

## Control guidance

System monitoring includes external and internal monitoring. External monitoring includes the observation of events occurring at external interfaces to the system. Internal monitoring includes the observation of events occurring within the system. Organizations monitor systems by observing audit activities in real time or by observing other system aspects such as access patterns, characteristics of access, and other actions. The monitoring objectives guide and inform the determination of the events. System monitoring capabilities are achieved through a variety of tools and techniques, including intrusion detection and prevention systems, malicious code protection software, scanning tools, audit record monitoring software, and network monitoring software.

Depending on the security architecture, the distribution and configuration of monitoring devices may impact throughput at key internal and external boundaries as well as at other locations across a network due to the introduction of network throughput latency. If throughput management is needed, such devices are strategically located and deployed as part of an established organization-wide security architecture. Strategic locations for monitoring devices include selected perimeter locations and near key servers and server farms that support critical applications. Monitoring devices are typically employed at the managed interfaces associated with controls [SC-7](#sc-7) and [AC-17](#ac-17) . The information collected is a function of the organizational monitoring objectives and the capability of systems to support such objectives. Specific types of transactions of interest include Hypertext Transfer Protocol (HTTP) traffic that bypasses HTTP proxies. System monitoring is an integral part of organizational continuous monitoring and incident response programs, and output from system monitoring serves as input to those programs. System monitoring requirements, including the need for specific types of system monitoring, may be referenced in other controls (e.g., [AC-2g](#ac-2_smt.g), [AC-2(7)](#ac-2.7), [AC-2(12)(a)](#ac-2.12_smt.a), [AC-17(1)](#ac-17.1), [AU-13](#au-13), [AU-13(1)](#au-13.1), [AU-13(2)](#au-13.2), [CM-3f](#cm-3_smt.f), [CM-6d](#cm-6_smt.d), [MA-3a](#ma-3_smt.a), [MA-4a](#ma-4_smt.a), [SC-5(3)(b)](#sc-5.3_smt.b), [SC-7a](#sc-7_smt.a), [SC-7(24)(b)](#sc-7.24_smt.b), [SC-18b](#sc-18_smt.b), [SC-43b](#sc-43_smt.b) ). Adjustments to levels of system monitoring are based on law enforcement information, intelligence information, or other sources of information. The legality of system monitoring activities is based on applicable laws, executive orders, directives, regulations, policies, standards, and guidelines.

## Control assessment-objective

the system is monitored to detect attacks and indicators of potential attacks in accordance with monitoring objectives;
the system is monitored to detect unauthorized local connections;
the system is monitored to detect unauthorized network connections;
the system is monitored to detect unauthorized remote connections;
unauthorized use of the system is identified through techniques and methods;
internal monitoring capabilities are invoked or monitoring devices are deployed strategically within the system to collect organization-determined essential information;
internal monitoring capabilities are invoked or monitoring devices are deployed at ad hoc locations within the system to track specific types of transactions of interest to the organization;
detected events are analyzed;
detected anomalies are analyzed;
the level of system monitoring activity is adjusted when there is a change in risk to organizational operations and assets, individuals, other organizations, or the Nation;
a legal opinion regarding system monitoring activities is obtained;
system monitoring information is provided to personnel or roles No value found.

______________________________________________________________________

## What is the solution and how is it implemented?

<!-- Please leave this section blank and enter implementation details in the parts below. -->

______________________________________________________________________

## Implementation a.

Add control implementation description here for item si-4_smt.a

______________________________________________________________________

## Implementation b.

Add control implementation description here for item si-4_smt.b

______________________________________________________________________

## Implementation c.

Add control implementation description here for item si-4_smt.c

______________________________________________________________________

## Implementation d.

Add control implementation description here for item si-4_smt.d

______________________________________________________________________

## Implementation e.

Add control implementation description here for item si-4_smt.e

______________________________________________________________________

## Implementation f.

Add control implementation description here for item si-4_smt.f

______________________________________________________________________

## Implementation g.

Add control implementation description here for item si-4_smt.g

______________________________________________________________________
