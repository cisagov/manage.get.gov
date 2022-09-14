---
implementation-status:
  - c-not-implemented
control-origination:
  - c-inherited-cloud-gov
  - c-inherited-cisa
  - c-common-control
  - c-system-specific-control
---

# si-3 - \[catalog\] Malicious Code Protection

## Control Statement

- \[a\] Implement No value found malicious code protection mechanisms at system entry and exit points to detect and eradicate malicious code;

- \[b\] Automatically update malicious code protection mechanisms as new releases are available in accordance with organizational configuration management policy and procedures;

- \[c\] Configure malicious code protection mechanisms to:

  - \[1\] Perform periodic scans of the system frequency and real-time scans of files from external sources at No value found as the files are downloaded, opened, or executed in accordance with organizational policy; and
  - \[2\]  No value found ; and send alert to personnel or roles in response to malicious code detection; and

- \[d\] Address the receipt of false positives during malicious code detection and eradication and the resulting potential impact on the availability of the system.

## Control guidance

System entry and exit points include firewalls, remote access servers, workstations, electronic mail servers, web servers, proxy servers, notebook computers, and mobile devices. Malicious code includes viruses, worms, Trojan horses, and spyware. Malicious code can also be encoded in various formats contained within compressed or hidden files or hidden in files using techniques such as steganography. Malicious code can be inserted into systems in a variety of ways, including by electronic mail, the world-wide web, and portable storage devices. Malicious code insertions occur through the exploitation of system vulnerabilities. A variety of technologies and methods exist to limit or eliminate the effects of malicious code.

Malicious code protection mechanisms include both signature- and nonsignature-based technologies. Nonsignature-based detection mechanisms include artificial intelligence techniques that use heuristics to detect, analyze, and describe the characteristics or behavior of malicious code and to provide controls against such code for which signatures do not yet exist or for which existing signatures may not be effective. Malicious code for which active signatures do not yet exist or may be ineffective includes polymorphic malicious code (i.e., code that changes signatures when it replicates). Nonsignature-based mechanisms also include reputation-based technologies. In addition to the above technologies, pervasive configuration management, comprehensive software integrity controls, and anti-exploitation software may be effective in preventing the execution of unauthorized code. Malicious code may be present in commercial off-the-shelf software as well as custom-built software and could include logic bombs, backdoors, and other types of attacks that could affect organizational mission and business functions.

In situations where malicious code cannot be detected by detection methods or technologies, organizations rely on other types of controls, including secure coding practices, configuration management and control, trusted procurement processes, and monitoring practices to ensure that software does not perform functions other than the functions intended. Organizations may determine that, in response to the detection of malicious code, different actions may be warranted. For example, organizations can define actions in response to malicious code detection during periodic scans, the detection of malicious downloads, or the detection of maliciousness when attempting to open or execute files.

## Control assessment-objective

No value found malicious code protection mechanisms are implemented at system entry and exit points to detect malicious code;
No value found malicious code protection mechanisms are implemented at system entry and exit points to eradicate malicious code;
malicious code protection mechanisms are updated automatically as new releases are available in accordance with organizational configuration management policy and procedures;
malicious code protection mechanisms are configured to perform periodic scans of the system frequency;
malicious code protection mechanisms are configured to perform real-time scans of files from external sources at No value found as the files are downloaded, opened, or executed in accordance with organizational policy;
malicious code protection mechanisms are configured to No value found in response to malicious code detection;
malicious code protection mechanisms are configured to send alerts to personnel or roles in response to malicious code detection;
the receipt of false positives during malicious code detection and eradication and the resulting potential impact on the availability of the system are addressed.

______________________________________________________________________

## What is the solution and how is it implemented?

<!-- Please leave this section blank and enter implementation details in the parts below. -->

______________________________________________________________________

## Implementation a.

Add control implementation description here for item si-3_smt.a

______________________________________________________________________

## Implementation b.

Add control implementation description here for item si-3_smt.b

______________________________________________________________________

## Implementation c.

Add control implementation description here for item si-3_smt.c

______________________________________________________________________

## Implementation d.

Add control implementation description here for item si-3_smt.d

______________________________________________________________________
