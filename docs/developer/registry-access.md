# Working with the registry via EPP

## Overview of parts

**EPP** is the protocol which describes how a registry and registrar communicate with XML over a TCP socket connection.

**epplib** is a Python library implementation of the TCP socket connection. It has helper functions and dataclasses which can be used to send and receive the XML messages.

**epplibwrapper** is a module in this repository which abstracts away the details of authenticating with the registry. It assists with error handling by providing error code constants and an error class with some helper methods.

**Domain** is a Python class. It inherits from `django.db.models.Model` and is therefore part of Django's ORM and has a corresponding table in the local registrar database. Its purpose is to provide a developer-friendly interface to the registry based on *what a registrant or analyst wants to do*, not on the technical details of EPP.

## Debugging in a Python shell

You'll first need access to a Django shell in an environment with valid registry credentials. Only some environments are allowed access: your laptop is probably not one of them. For example:

```shell
cf ssh getgov-ENVIRONMENT
/tmp/lifecycle/shell  # this configures your environment
./manage.py shell
```

You'll next need to import some code.

```
from epplibwrapper import CLIENT as registry, commands
from epplib.models import common
```

Finally, you'll need to craft a request and send it.

```
request = ...
response = registry.send(request, cleaned=True)
```

Note that you'll need to attest that the data you are sending has been sanitized to remove malicious or invalid strings. Use `send(..., cleaned=True)` to do that.

See below for some example commands to send. Replace example data with data which makes sense for your debugging scenario. Other commands are available; see the source code of epplib for more options.


### Get info about a contact

```
request = commands.InfoContact(id='sh8013')
```

### Create a new contact

```
DF = common.DiscloseField
di = common.Disclose(flag=False, fields={DF.FAX, DF.VOICE, DF.ADDR}, types={DF.ADDR: "loc"})
addr = common.ContactAddr(street=['123 Example Dr.'], city='Dulles', pc='20166-6503', cc='US', sp='VA')
pi = common.PostalInfo(name='John Doe', addr=addr, org="Example Inc.", type="loc")
ai = common.ContactAuthInfo(pw='feedabee')

request = commands.CreateContact(id='sh8013', postal_info=pi, email='jdoe@example.com', voice='+1.7035555555', fax='+1.7035555556', auth_info=ai, disclose=di, vat=None, ident=None, notify_email=None)
```

### Create a new domain

```
ai = common.DomainAuthInfo(pw='feedabee')
request = commands.CreateDomain(name="okay.gov", registrant="sh8013", auth_info=ai)
```

### Create a host object

```
request = commands.CreateHost(name="ns1.okay.gov", addrs=[common.Ip(addr="127.0.0.1"), common.Ip(addr="0:0:0:0:0:0:0:1", ip="v6")])
```

### Check if a host is available

```
request = commands.CheckHost(["ns2.okay.gov"])
```

### Update a domain

```
request = commands.UpdateDomain(name="okay.gov", add=[common.HostObjSet(["ns1.okay.gov"])])
```

```
request = commands.UpdateDomain(name="okay.gov", add=[common.DomainContact(contact="sh8014", type="tech")])
```

### How to see the raw XML

To see the XML of a command before the request is sent, call `request.xml()`.

To see the XML of the response, you must send the command using a different method.

```
registry._client.connect()
registry._client.send(registry._login)

request = commands.InfoDomain(name="ok.gov")

registry._client.transport.send(request.xml())
response = registry._client.transport.receive()
```

This is helpful for debugging situations where epplib is not correctly or fully parsing the XML returned from the registry.

### Adding in an 'expiring soon' or 'expired' domain

#### Overview
Expiration dates created by fixtures in sandboxes are not accurate (they are not synced to the OT&E registry and will reset to 
the expiration date to a year from 'today'). In order to view an expiring or expired domain, we need to pull records from the 
OT&E registry. In order to have edit ability, you must be a domain manager of that domain. Below are instructions on how to 
find, add, and then view an expiring or expired domain to a sandbox. As a domain manager you will be able to view the renewal form.

#### Find an expired or expiring domain record

1. Get access to the OT&E registry by asking another team member
2. Click on Reports to download a file of expired or expiring domains
3. Find a domain name from the report, and save it for the command below

#### Duplicate the domain into your sandbox environment of choice and assign to manager and portfolio

6. In a terminal, run these commands:
```
cf ssh getgov-<environment-name>
/tmp/lifecycle/shell
./manage.py shell
from registrar.models import Domain
domain = Domain.objects.get_or_create(name="<that-domain-here>")
```

7. From `/admin` in your sandbox environment, locate the Domain record page of the domain you just created. In Domain Information, add a "requester" and "portfolio" for the org model. Note: To view the domain in the org model, it must be associated with a portfolio and viewed from within that portfolio. 
9. Click Manage Domain which will take you to the app
10. In the Domain Managers section, add yourself as domain manager (Alternatively, you can assign yourself as a Domain Manager in `/admin`. Go to the User domain roles model, click the "Add user domain role +" button, and then add yourself to the domain as a manager.)
11. You should now be able to access your expiring domain in the registrar.


