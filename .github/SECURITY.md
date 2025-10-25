
October is Cybersecurity Awareness Month!
CISA’s Acting Director discusses our focus on government entities and small and medium businesses that are vital to protecting the systems and services that sustain us every day and make America a great place to live and do business.

Microsoft released an update to address a critical remote code execution vulnerability impacting Windows Server Update Service (WSUS) in Windows Server (2012, 2016, 2019, 2022, and 2025), CVE-2025-59287, that a prior update did not fully mitigate. 

CISA strongly urges organizations to implement Microsoft’s updated Windows Server Update Service (WSUS) Remote Code Execution Vulnerability guidance, 1 or risk an unauthenticated actor achieving remote code execution with system privileges. Immediate actions for organizations with affected products are:

Identify servers that are currently configured to be vulnerable to exploitation (i.e., affected servers with WSUS Server Role enabled and ports open to 8530/8531) for priority mitigation.
Apply the out-of-band security update released on October 23, 2025, to all servers identified in Step 1. Reboot WSUS server(s) after installation to complete mitigation. If organizations are unable to apply the update immediately, system administrators should disable the WSUS Server Role and/or block inbound traffic to ports 8530/8531, the default listeners for WSUS, at the host firewall. Of note, do not undo either of these workarounds until after your organization has installed the update.
Apply updates to remaining Windows servers. Reboot servers after installation to complete mitigation.
CISA added CVE-2025-59287 to its Known Exploited Vulnerabilities (KEV) Catalog on October 24, 2025.
 CISA may update this Alert to reflect new guidance issued by CISA or other parties. 

Organizations should report incidents and anomalous activity to CISA’s 24/7 Operations Center at contact@cisa.dhs.gov or (888) 282-0870.

The information in this report is being provided “as is” for informational purposes only. CISA does not endorse any commercial entity, product, company, or service, including any entities, products, or services linked within this document. Any reference to specific commercial entities, products, processes, or services by service mark, trademark, manufacturer, or otherwise, does not constitute or imply endorsement, recommendation, or favoring by CISA.


* If you've found a security or privacy issue on the **.gov top-level domain infrastructure**, email us at help@get.gov.
* If you see a security or privacy issue on **an individual .gov domain**, check [current-full.csv](https://flatgithub.com/cisagov/dotgov-data/blob/main/?filename=current-full.csv) to see whether the domain has a security contact to report your finding directly. You are welcome to Cc help@get.gov on the email.
  * If you are unable to find a contact or receive no response from the security contact, email help@get.gov.

Note that most federal (executive branch) agencies maintain a [vulnerability disclosure policy](https://github.com/cisagov/vdp-in-fceb/).
