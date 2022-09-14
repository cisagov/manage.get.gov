# Glossary

## OSCAL Specific

### Root Element
This defines the type of content (model) within the body of an OSCAL file. The types of models we have available to us are "catalog", "profile", "component", "system security plan", "assessment plan", "assessment results", and "plan of actions and milestones".

### OSCAL Model
A structure for supporting a specific concept like "catalog" or "system security plan".

### OSCAL Layer
OSCAL architecture is broken into three layers: Assessment, Implementation, and Controls. These are ways to organize the OSCAL models. 

### Assessment Layer
This layer explains how an assessment is planned, performed, and reported. It can contain an "Assessment Plan", "Assessment Results" or "POAM" model. 

### Implementation Layer
This layer provides models for describing how we've implemented our selected controls in a specific system. It can contain "Component Definition" and "System Security Plan" models. 

### Control Layer
A layer including the catalog and profile models. 

### UUID
A document-level identifier that is changed whenever the document is updated.

### Control 
A control is a requirement, which when implemented reduces one aspect of risk in our system. There are "security controls" and "privacy controls". The are grouped together in a "control catalog".

### Catalog
This is how controls are organized by framework providers (like NIST). This allows the controls to be grouped. "Catalog documents" are human readable documents where controls are represented.

### Baseline
Also seen as "overlay", a baseline defines a specific set of selected controls from one or more catalogs. These can be "low", "moderate", or "high" – we need to provide a "moderate" baseline. 

### Profile
A grouping of controls referencing controls from several catalogs – it is a structured machine-readable representation of a baseline. 

### Control Enhancement
Augmentation of a control to build in additional functionality to strengthen the given control.

## Compliance Process

### SSP
System Security Plan. This document outlines all the seucirty requirements for a given system.

### SCR
Significant Change Request. This is a record specific to FedRAMP, the form can be found [here](https://www.fedramp.gov/assets/resources/templates/FedRAMP-Significant-Change-Form-Template.pdf).

### 3PAO
A 3PAO is an organization that has been certified to help cloud service providers and government agencies meet FedRAMP compliance regulations.

### SIA
Security Impact Analysis. It’s a process to determine the effect(s) a proposed change can cause to the security posture of a FISMA system. Conducting a SIA is a mandatory process for all changes. Once the SIA is approved by our CISO team that gets fed into the SCR and submitted to FedRAMP. Then the 3PAO will use the SCR to report back to FedRAMP for their assessment. And since we are an agency FedRAMP authorized system our CISO has final say on the security assessment report that gets delivered to us by the 3PAO. They ask them to perform additional inspection to satisfy the changes.

### POAM
Plan of Action and Milestones. It details tasks that need to be accomplished, and is represented in an OSCAL model.

