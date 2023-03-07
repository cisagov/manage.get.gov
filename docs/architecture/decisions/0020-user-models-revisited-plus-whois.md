# 20. User models revisited, plus WHOIS

Date: 2022-03-01

## Status

Accepted

## Context

In the process of thinking through the details of registry implementation and role-based access control, it has become clear that the registrar has 3 types of contacts:

1. Those for the purpose of allowing CISA to verify the authenticity of a request. In other words, is the organization an eligible U.S.-based government and is the requestor duly authorized to make the request on behalf of their government?
1. Those for the purpose of managing a domain or its DNS configuration.
    * There is ambiguous overlap remaining between use case 1 and 2.
1. Those for the purpose of publishing publicly in WHOIS.

Additionally, there are two mental models of contacts that impact the permissions associated with them and how they can be updated:

1. A contact represents a person: changes made in one part of the system will update in all parts of the system; people are not allowed to make updates unless they are authorized.
1. A contact represents information filled out on a sheet of paper: changes on one “copy” of the information will not update other “copies” of the information; people are allowed to make updates based on their authorization to access and edit the “sheet of paper”.

## Decision

To have a custom `User` model containing un-editable data derived from Login.gov and updated automatically each time a user logs in. In role-based access control, User is the model to which roles attach.

To have a `Contact` model which stores name and contact data. The presence of a foreign key from Contact to User indicates that that contact data has been associated with a Login.gov user account. If a User is deleted, the foreign key column is set to null.

User and Contact follow the “person” mental model.

To have a `PublicContact` model which stores WHOIS data. Domains will be created with the following default values.

PublicContact follows the “sheet of paper” mental model.

### Registrant default values

| Field | Value |
|---|---|
|name     |  CSD/CB – Attn: Cameron Dixon
|org      |  Cybersecurity and Infrastructure Security Agency
|street1  |  CISA – NGR STOP 0645
|street2  |  1110 N. Glebe Rd.
|city     |  Arlington
|sp       |  VA
|pc       |  20598-0645
|cc       |  US

### Administrative default values

| Field | Value |
|---|---|
|name     |  Program Manager
|org      |  Cybersecurity and Infrastructure Security Agency
|street1  |  4200 Wilson Blvd.
|city     |  Arlington
|sp       |  VA
|pc       |  22201
|cc       |  US
|voice    |  +1.8882820870
|email    |  dotgov@cisa.dhs.gov

### Technical default values

Whether this contact will be created by default or not is yet to be determined.

| Field | Value |
|---|---|
|name     |  Registry Customer Service
|org      |  Cybersecurity and Infrastructure Security Agency
|street1  |  4200 Wilson Blvd.
|city     |  Arlington
|sp       |  VA
|pc       |  22201
|cc       |  US
|voice    |  +1.8882820870
|email    |  registrar@dotgov.gov

### Security default values

Whether this contact will be created by default or not is yet to be determined.

The EPP “disclose tags” feature might be used to publish only the email address.

| Field | Value |
|---|---|
|name     |  Registry Customer Service
|org      |  Cybersecurity and Infrastructure Security Agency
|street1  |  4200 Wilson Blvd.
|city     |  Arlington
|sp       |  VA
|pc       |  22201
|cc       |  US
|voice    |  +1.8882820870
|email    |  registrar@dotgov.gov


## Consequences

This has minimal impact on the code we’ve developed so far.

By having PublicContact be an entirely separate model, it ensures that (for better or worse) WHOIS contact data must be updated separately from general Contacts. At present, CISA intends to allow registrants to edit only one contact: security, so this is a minor point of low impact.

In a future state where CISA allows more to be published, it is easy to imagine a set of checkboxes on a contact update form: “[ ] publish this as my technical contact for example.gov”, etc.
