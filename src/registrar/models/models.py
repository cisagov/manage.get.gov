from django.contrib.auth.models import User
from django.db import models

# Instructions for graphing:
#
# 1. Run this command (use graph_models -h to understand the options):
#
#       docker-compose exec app ./manage.py graph_models registrar \
#       -a -g --rankdir LR --color-code-deletions --arrow-shape crow -E \
#       > ../docs/architecture/diagrams/models.dot
#
# 2. Install graphviz via brew (if not already installed)
# 3. Run this command:
#
#       dot -Tsvg ../docs/architecture/diagrams/models.dot \
#       -o ../docs/architecture/diagrams/models.svg

# TODO: break this file into multiple files, so it is easier to work with

# TODO: draft ADR

# TODO: proper constraints

"""
Assumptions

* That it is potentially worthwhile or necessary to keep a cached
copy of the registry data (domains, nameservers, hosts).

* That most table rows need to track when they were created or updated,
hence the creation of TimeStampedModel.

* That for every active domain and for every domain application,
there must be a Government Entity recognized by CISA as authorized
to have .gov domains.

* That for every active domain and for every domain application,
there must be an Organization which is responsible for the day-to-day
management of the domains. In smaller governments, this Organization
may be synonymous with the Government Entity, but is still tracked
in its own database table.

* That every Organization has an Authorizing Official responsible
for authenticating that domain requests are genuine
on behalf of the Organization, who may or may not be the highest
elected official of the Organization's Government Entity.

* To restate: Government Entity answers the question of "who should
CISA contact when all else fails" while Organization answers
the question of "who is actually using and managing this domain"

* That every User can create an application for a Draft Domain.

* That Draft Domains during the Application state are absolutely
and 100% separate from real Domains that have been approved and,
therefore, are kept in entirely different tables.

* That every User can create an Organization if it does not exist
and a Government Entity if it does not exist.

* That the first User to create an Organization or a Government Entity
is presumptively the "superuser" with admin rights on that Organization
or Government Entity.

* That CISA is able to remove 

* That, once created, additional Users may be invited, added, or request
access to an Organization via processes that are tbd.

* Users are granted Roles through Organizations. Users may have multiple Roles
within an Organization. Users may belong to multiple Organizations.

* Roles are collections of individual Permissions.

* A future state may support so-called row-level permissions. In other words,
a User may have a Role through an Organization and that Role grants a Permission
but the Permission is Scoped to a specific Resource (such as a single domain,
user, application, etc).

* That all Organizations which share a Government Entity have equal rights
to it. In other words, the "superuser" and any other duly authorized User
of any Organization which is connected to a Government Entity may make edits
to the Government Entity's data. A future state may envision a more complex
set of Permissions.

* That it is useful or worthwhile to provide space for caching
government entity data, such as census data. Future features may include
the ability to manually or automatically update such data and then
to perform various automated or manual verification against the data.
"""

class TimeStampedModel(models.Model):
    """
    An abstract base model that provides self-updating
    `created_at` and `updated_at` fields.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class CommonEPPModel(models.Model):
    """
    An abstract base model that provides common fields
    seen on several EPP objects.
    """
    # identifier of the sponsoring client
    cl_id = models.CharField(max_length=2)
    # identifier of the client that created the domain object
    cr_id = models.CharField(max_length=2)
    # date and time of domain- object creation.
    cr_date = models.CharField(max_length=2)
    # identifier of the client that last updated the domain object (null ok)
    up_id = models.CharField(max_length=2)
    # date and time of the most recent domain-object modification (null ok)
    up_date = models.CharField(max_length=2)
    # date and time of the most recent successful domain-object transfer (null ok)
    tr_date = models.CharField(max_length=2)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class AddressModel(models.Model):
    """
    An abstract base model that provides common fields
    for postal addresses.
    """
    # contact's street (null ok)
    street1 = models.CharField(max_length=2)
    # contact's street (null ok)
    street2 = models.CharField(max_length=2)
    # contact's street (null ok)
    street3 = models.CharField(max_length=2)
    # contact's city
    city = models.CharField(max_length=2)
    # contact's state or province (null ok)
    sp = models.CharField(max_length=2)
    # contact's postal code (null ok)
    pc = models.CharField(max_length=2)
    # contact's country code
    cc = models.CharField(max_length=2)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class ContactModel(models.Model):
    """
    An abstract base model that provides common fields
    for contact information.
    """
    voice = models.CharField(max_length=2)
    fax = models.CharField(max_length=2)
    email = models.CharField(max_length=2)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class UserProfile(TimeStampedModel, ContactModel, AddressModel):
    user = models.OneToOneField(User, null=True, on_delete=models.SET_NULL)


class HostStatus(TimeStampedModel):
    # business logic is needed to determine
    # if given statuses can live together (some are mutually exclusive)
    # TODO: consider use of simple state machine
    status = models.CharField(max_length=2)


class DomainStatus(TimeStampedModel):
    # business logic is needed to determine
    # if given statuses can live together (some are mutually exclusive)
    # TODO: consider use of simple state machine
    status = models.CharField(max_length=2)


class ContactStatus(TimeStampedModel):
    # business logic is needed to determine
    # if given statuses can live together (some are mutually exclusive)
    # TODO: consider use of simple state machine
    status = models.CharField(max_length=2)


class City(models.Model):
    # TODO: ability to populate with census data
    name = models.CharField(max_length=2)


class State(models.Model):
    # TODO: ability to populate with census data
    name = models.CharField(max_length=2)


class County(models.Model):
    # TODO: ability to populate with census data
    name = models.CharField(max_length=2)


class Tribe(models.Model):
    # TODO: ability to populate with census data
    name = models.CharField(max_length=2)


class Territory(models.Model):
    # TODO: ability to populate with census data
    name = models.CharField(max_length=2)


class FederalAgency(models.Model):
    # TODO: ability to populate with data from ???
    name = models.CharField(max_length=2)


class GovEntity(TimeStampedModel):
    # TODO: choices ????
    entity_type = models.CharField(max_length=2)
    fallback_contact_instructions = models.CharField(max_length=2)
    city = models.ManyToManyField(City)
    state = models.ManyToManyField(State)
    county = models.ManyToManyField(County)
    tribe = models.ManyToManyField(Tribe)
    territory = models.ManyToManyField(Territory)
    agency = models.ManyToManyField(FederalAgency)



class AuthorizingOfficial(TimeStampedModel, ContactModel, AddressModel):
    # contact's name
    name = models.CharField(max_length=2)
    # alternative contacting instructions (could also be foreign key to AO record)
    alt_contact_info = models.CharField(max_length=2)
    # an AO may or may not have a user in the system
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)


class Organization(TimeStampedModel, AddressModel):
    name = models.CharField(max_length=2)
    entity = models.ForeignKey(GovEntity, on_delete=models.CASCADE)
    authorizing_official = models.ForeignKey(AuthorizingOfficial, on_delete=models.CASCADE)


class Rejection(models.Model):
    reason = models.CharField(max_length=2)


class Application(TimeStampedModel):
    # user who is making the request
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    # the person who says this user is allowed to request this domain
    authorizing_official = models.ForeignKey(AuthorizingOfficial, on_delete=models.CASCADE)
    # the government who CISA says is allowed to request a .gov domain
    authorizing_entity = models.ForeignKey(GovEntity, on_delete=models.CASCADE)
    # the subdivision or department this user belongs to
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)
    domain_name = models.CharField(max_length=2)
    is_exception_requested = models.BooleanField()
    # if the user wants an ineligible domain name, they may give a reason for their request
    exception_rationale = models.CharField(max_length=2)
    is_expedited_requested = models.BooleanField()
    # if the user wants a fast response, they may give a reason for their request
    expedited_rationale = models.CharField(max_length=2)
    hsts_acknowledged = models.BooleanField()
    # reason for requesting the domain
    purpose = models.CharField(max_length=2)
    # Choices ??? -- also, TODO: use a state machine to model the business logic
    status = models.CharField(max_length=2)
    # choices ???
    rejection_codes = models.ManyToManyField(Rejection)
    assignee = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="assigned")


class ApplicationStatusHistory(TimeStampedModel):
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    prior_status = models.CharField(max_length=2)
    status = models.CharField(max_length=2)
    change_note = models.CharField(max_length=2)


class Domain(TimeStampedModel, CommonEPPModel):
    # fully qualified name (unique)
    name  = models.CharField(max_length=2)
    # identifier assigned to the domain object when created
    roid  = models.CharField(max_length=2) # NS1_EXAMPLE1-REP
    # the date and time of the domain object's registration expiration
    ex_date = models.CharField(max_length=2)
    # can have 1..* statuses
    status = models.ManyToManyField(DomainStatus)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)


class Host(TimeStampedModel, CommonEPPModel):
    # fully qualified name
    name  = models.CharField(max_length=2)
    # identifier assigned to the host object when created
    roid  = models.CharField(max_length=2) # NS1_EXAMPLE1-REP
    # can have 1..* statuses
    status = models.ManyToManyField(HostStatus)
    # domain this host belongs to
    addr = models.ForeignKey(Domain, on_delete=models.PROTECT, related_name="host")
    # domain this host is a name server for
    ns = models.ForeignKey(Domain, on_delete=models.PROTECT, related_name="nameserver")


class HostIP(TimeStampedModel):
    address = models.CharField(max_length=2)
    # choices "v4", "v6"
    version = models.CharField(max_length=2)
    # host this IP belongs to
    addr = models.ForeignKey(Host, on_delete=models.SET_NULL, null=True)


class DomainContact(TimeStampedModel, CommonEPPModel, ContactModel):
    # server-unique identifier of the contact object
    server_id = models.CharField(max_length=2)
    # identifier assigned to the contact object when created
    roid = models.CharField(max_length=2)
    # can have 1..* statuses
    status = models.ManyToManyField(ContactStatus)
    # TODO: voice telephone number must be spliced on extension for EPP
    # require exceptional server-operator handling
    disclose = models.CharField(max_length=2)
    # type is "registrant", "admin", "tech", or "billing"
    contact_type = models.CharField(max_length=2)
    # TODO: unique together for (contact_type, domain)
    domain = models.ForeignKey(Domain, on_delete=models.PROTECT)
    # a contact may or may not have a user in the system
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)


class DomainContactPostalInfo(TimeStampedModel, AddressModel):
    # contact's name
    name = models.CharField(max_length=2)
    # contact's org (null ok)
    org = models.CharField(max_length=2)
    # postal address represented in unrestricted UTF-8 = "loc"
    # postal address that can be represented in the 7-bit US-ASCII character set = "int"
    postal_type = models.CharField(max_length=2)
    # TODO: unique together (contact, postal_type)... no more than one of each type per contact
    contact = models.ForeignKey(DomainContact, on_delete=models.PROTECT)


class DraftDomain(TimeStampedModel):
    # fully qualified name (unique)
    name  = models.CharField(max_length=2)
    application = models.ForeignKey(Application, on_delete=models.PROTECT)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT)


class DraftHost(TimeStampedModel):
    # fully qualified name
    name  = models.CharField(max_length=2)
    # domain this host belongs to
    addr = models.ForeignKey(DraftDomain, on_delete=models.PROTECT, related_name="host")
    # domain this host is a name server for
    ns = models.ForeignKey(DraftDomain, on_delete=models.PROTECT, related_name="nameserver")


class DraftHostIP(TimeStampedModel):
    address = models.CharField(max_length=2)
    # choices "v4", "v6"
    version = models.CharField(max_length=2)
    # host this IP belongs to
    addr = models.ForeignKey(DraftHost, on_delete=models.SET_NULL, null=True)


class DraftDomainContact(TimeStampedModel, ContactModel):
    # type is "registrant", "admin", "tech", or "billing"
    contact_type = models.CharField(max_length=2)
    # TODO: unique together for (contact_type, domain)
    domain = models.ForeignKey(DraftDomain, on_delete=models.PROTECT)
    # a contact may or may not have a user in the system
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)


class DraftDomainContactPostalInfo(TimeStampedModel, AddressModel):
    # contact's name
    name = models.CharField(max_length=2)
    # contact's org (null ok)
    org = models.CharField(max_length=2)
    contact = models.OneToOneField(DraftDomainContact, on_delete=models.PROTECT)


class Permission(models.Model):
    """
    A list of discreet actions available in the application
    """
    name = models.CharField(max_length=2)
    description = models.CharField(max_length=2)


class Role(models.Model):
    """
    A collection of Permissions gathered for easy assignment to a user
    """
    name = models.CharField(max_length=2)
    description = models.CharField(max_length=2)
    permissions = models.ManyToManyField(Permission)


class Scope(models.Model):
    # TODO: OrganizationUserRole needs a way to limit a role to
    # specific domains, users, entities, applications
    # (noting that all non-staff members are limited to their
    # Organization regardless of anything else, that will be hardcoded)
    pass


class OrganizationUserRole(TimeStampedModel):
    """
    A user mapped to their organization and their roles within the organization
    """
    roles = models.ManyToManyField(Role)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
