# Control Families

Below are a list of control families with relevant descriptions.

## `ac-`: Access Control

This family deals with account management, various levels of access to hardware and software, and access related notifications.

## `ar-`, `ra-`, `tr-`, and `ul`: Privacy Impact and Risk Assessment, Privacy Notice, and Infromation Sharing with Third Parties

These families contain controls around threat modeling, privacy impact, and vulnerability scanning. `ar` was the family name under rev. 4, and `ra` is the name under rev. 5, but these should be examined together when making changes that impact privacy or help reduce risk. 

## `au-`: Audit and Accountability

These controls will deal with anything around logging for events, record keeping, and formatting of logs.

## `ca-`: Assessment, Authorization, and Monitoring

A little meta, but this family deals with how we actively document security and compliance, where we keep POAMs, how we conduct pen testing, etc.

## `cm-`: Configuration Management

This family documents how we restrict softare usage, where we store configuration, and adhere to "law of least functionality" throughout our system. 

## `cp-`: Contingency Planning

This deals with how we handle our backups, disaster recovery, fallbacks, and any other sort of emergency planning. 

## `di-`: Data Quality

There is only one control for `di` and it broadly deals with handling of PII at the organization level. 

## `ia-`: Identification and Authentication

This family deals with restricting access to parts or whole of the system. You will find controls relating to MFA, account access, PIVs to access, etc. Unlike `ac-` controls, this deals with things like how we restrict admin access to our AWS accounts, which will probably be documented in the SSP.

## `sa-`: System and Services Acquisition

This family deals with how we document and monitoring the state of the system. Any information about static analysis and regular system testing will go here.

## `sc-`: System and Communications Protection

This family deals with a lot of hardware controls we can probably inherit from AWS. It also deals with network configuration though, which we will have to document. Things like DDoS protection, minimizing network access between hosts, and hardware separation are documented here. 

## `si-`: System and Information Integrity

This family will contain things like any software scanning for security issues and necessary patches. It also deals with how we handle errors and sanitize user inputs. 

## `sr-`: Supply Chain Risk Management

This family potentially has the most entangled set of controls with other systems in our boundary and will take communication with security and compliance partners to help understand how changes to this system impact SCRM. The controls here range from setting up a SCRM team to how we scan our software to mitigate risk.