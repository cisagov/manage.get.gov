import logging

from datetime import date
from string import digits

from django.db import models

from epplibwrapper import (
    CLIENT as registry,
    commands,
    common as epp,
    RegistryError,
    ErrorCode,
)

from .utility.domain_field import DomainField
from .utility.domain_helper import DomainHelper
from .utility.time_stamped_model import TimeStampedModel

from .public_contact import PublicContact

logger = logging.getLogger(__name__)


class Domain(TimeStampedModel, DomainHelper):
    """
    Manage the lifecycle of domain names.

    The registry is the source of truth for this data and this model exists:
        1. To tie ownership information in the registrar to
           DNS entries in the registry

    ~~~ HOW TO USE THIS CLASS ~~~

    A) You can create a Domain object with just a name. `Domain(name="something.gov")`.
    B) Saving the Domain object will not contact the registry, as it may be useful
       to have Domain objects in an `UNKNOWN` pre-created state.
    C) Domain properties are lazily loaded. Accessing `my_domain.expiration_date` will
       contact the registry, if a cached copy does not exist.
    D) Domain creation is lazy. If `my_domain.expiration_date` finds that `my_domain`
       does not exist in the registry, it will ask the registry to create it.
    F) Created is _not_ the same as active aka live on the internet.
    G) Activation is controlled by the registry. It will happen automatically when the
       domain meets the required checks.
    """

    def __init__(self, *args, **kwargs):
        self._cache = {}
        super(Domain, self).__init__(*args, **kwargs)


    class Status(models.TextChoices):
        """
        The status codes we can receive from the registry.

        These are detailed in RFC 5731 in section 2.3.
        https://www.rfc-editor.org/std/std69.txt
        """

        # Requests to delete the object MUST be rejected.
        CLIENT_DELETE_PROHIBITED = "clientDeleteProhibited"
        SERVER_DELETE_PROHIBITED = "serverDeleteProhibited"

        # DNS delegation information MUST NOT be published for the object.
        CLIENT_HOLD = "clientHold"
        SERVER_HOLD = "serverHold"

        # Requests to renew the object MUST be rejected.
        CLIENT_RENEW_PROHIBITED = "clientRenewProhibited"
        SERVER_RENEW_PROHIBITED = "serverRenewProhibited"

        # Requests to transfer the object MUST be rejected.
        CLIENT_TRANSFER_PROHIBITED = "clientTransferProhibited"
        SERVER_TRANSFER_PROHIBITED = "serverTransferProhibited"

        # Requests to update the object (other than to remove this status)
        # MUST be rejected.
        CLIENT_UPDATE_PROHIBITED = "clientUpdateProhibited"
        SERVER_UPDATE_PROHIBITED = "serverUpdateProhibited"

        # Delegation information has not been associated with the object.
        # This is the default status when a domain object is first created
        # and there are no associated host objects for the DNS delegation.
        # This status can also be set by the server when all host-object
        # associations are removed.
        INACTIVE = "inactive"

        # This is the normal status value for an object that has no pending
        # operations or prohibitions.  This value is set and removed by the
        # server as other status values are added or removed.
        OK = "ok"

        # A transform command has been processed for the object, but the
        # action has not been completed by the server.  Server operators can
        # delay action completion for a variety of reasons, such as to allow
        # for human review or third-party action.  A transform command that
        # is processed, but whose requested action is pending, is noted with
        # response code 1001.
        PENDING_CREATE = "pendingCreate"
        PENDING_DELETE = "pendingDelete"
        PENDING_RENEW = "pendingRenew"
        PENDING_TRANSFER = "pendingTransfer"
        PENDING_UPDATE = "pendingUpdate"


    class State(models.TextChoices):
        """These capture (some of) the states a domain object can be in."""

        # the normal state of a domain object -- may or may not be active!
        CREATED = "created"

        # previously existed but has been deleted from the registry
        DELETED = "deleted"

        # the state is indeterminate
        UNKNOWN = "unknown"


    class Cache(property):
        """
        Python descriptor to turn class methods into properties.

        The purpose of subclassing `property` rather than using it directly
        as a decorator (`@Cache`) is to insert generic code to run
        before or after _all_ properties are accessed, modified, or deleted.

        As an example:

                domain = Domain(name="example.gov")
                domain.save()
                                      <--- insert code here
                date = domain.creation_date
                                      <--- or here
                (...other stuff...)
        """

        def __get__(self, obj, objtype=None):
            """Called during get. Example: `r = domain.registrant`."""
            return super().__get__(obj, objtype)

        def __set__(self, obj, value):
            """Called during set. Example: `domain.registrant = 'abc123'`."""
            super().__set__(obj, value)
            # always invalidate cache after sending updates to the registry
            obj._invalidate_cache()

        def __delete__(self, obj):
            """Called during delete. Example: `del domain.registrant`."""
            super().__delete__(obj)


    @classmethod
    def available(cls, domain: str) -> bool:
        """Check if a domain is available."""
        if not cls.string_could_be_domain(domain):
            raise ValueError("Not a valid domain: %s" % str(domain))
        req = commands.CheckDomain([domain])
        return registry.send(req, cleaned=True).res_data[0].avail

    @classmethod
    def registered(cls, domain: str) -> bool:
        """Check if a domain is _not_ available."""
        return not cls.available(domain)

    @Cache
    def contacts(self) -> dict[str, str]:
        """
        Get a dictionary of registry IDs for the contacts for this domain.

        IDs are provided as strings, e.g.

            {"registrant": "jd1234", "admin": "sh8013",...}
        """
        raise NotImplementedError()

    @Cache
    def creation_date(self) -> date:
        """Get the `cr_date` element from the registry."""
        raise NotImplementedError()

    @Cache
    def last_transferred_date(self) -> date:
        """Get the `tr_date` element from the registry."""
        raise NotImplementedError()

    @Cache
    def last_updated_date(self) -> date:
        """Get the `up_date` element from the registry."""
        raise NotImplementedError()

    @Cache
    def expiration_date(self) -> date:
        """Get or set the `ex_date` element from the registry."""
        raise NotImplementedError()

    @expiration_date.setter  # type: ignore
    def expiration_date(self, ex_date: date):
        raise NotImplementedError()

    @Cache
    def password(self) -> str:
        """Get the `auth_info.pw` element from the registry. Not a real password."""
        raise NotImplementedError()

    @Cache
    def nameservers(self) -> list[tuple[str]]:
        """
        Get or set a complete list of nameservers for this domain.

        Hosts are provided as a list of tuples, e.g.

            [("ns1.example.com",), ("ns1.example.gov", "0.0.0.0")]

        Subordinate hosts (something.your-domain.gov) MUST have IP addresses,
        while non-subordinate hosts MUST NOT.
        """
        # TODO: call EPP to get this info instead of returning fake data.
        return [
            ("ns1.example.com",),
            ("ns2.example.com",),
            ("ns3.example.com",),
        ]

    @nameservers.setter  # type: ignore
    def nameservers(self, hosts: list[tuple[str]]):
        # TODO: call EPP to set this info.
        pass

    @Cache
    def statuses(self) -> list[str]:
        """
        Get or set the domain `status` elements from the registry.

        A domain's status indicates various properties. See Domain.Status.
        """
        # implementation note: the Status object from EPP stores the string in
        # a dataclass property `state`, not to be confused with the `state` field here
        raise NotImplementedError()

    @statuses.setter  # type: ignore
    def statuses(self, statuses: list[str]):
        # TODO: there are a long list of rules in the RFC about which statuses
        # can be combined; check that here and raise errors for invalid combinations -
        # some statuses cannot be set by the client at all
        raise NotImplementedError()

    @Cache
    def registrant_contact(self) -> PublicContact:
        """Get or set the registrant for this domain."""
        raise NotImplementedError()

    @registrant_contact.setter  # type: ignore
    def registrant_contact(self, contact: PublicContact):
        raise NotImplementedError()

    @Cache
    def administrative_contact(self) -> PublicContact:
        """Get or set the admin contact for this domain."""
        raise NotImplementedError()

    @administrative_contact.setter  # type: ignore
    def administrative_contact(self, contact: PublicContact):
        raise NotImplementedError()

    @Cache
    def security_contact(self) -> PublicContact:
        """Get or set the security contact for this domain."""
        # TODO: replace this with a real implementation
        contact = PublicContact.get_default_security()
        contact.domain = self
        contact.email = "mayor@igorville.gov"
        return contact

    @security_contact.setter  # type: ignore
    def security_contact(self, contact: PublicContact):
        # TODO: replace this with a real implementation
        pass

    @Cache
    def technical_contact(self) -> PublicContact:
        """Get or set the tech contact for this domain."""
        raise NotImplementedError()

    @technical_contact.setter  # type: ignore
    def technical_contact(self, contact: PublicContact):
        raise NotImplementedError()

    def is_active(self) -> bool:
        """Is the domain live on the inter webs?"""
        # TODO: implement a check -- should be performant so it can be called for
        # any number of domains on a status page
        # this is NOT as simple as checking if Domain.Status.OK is in self.statuses
        return False

    def transfer(self):
        """Going somewhere. Not implemented."""
        raise NotImplementedError()

    def renew(self):
        """Time to renew. Not implemented."""
        raise NotImplementedError()

    def place_client_hold(self):
        """This domain should not be active."""
        raise NotImplementedError()

    def remove_client_hold(self):
        """This domain is okay to be active."""
        raise NotImplementedError()

    def __str__(self) -> str:
        return self.name

    name = DomainField(
        max_length=253,
        blank=False,
        default=None,  # prevent saving without a value
        unique=True,
        help_text="Fully qualified domain name",
    )

    state = models.CharField(
        max_length=21,
        choices=State.choices,
        default=State.UNKNOWN,
        help_text="Very basic info about the lifecycle of this domain object",
    )

    # ForeignKey on UserDomainRole creates a "permissions" member for
    # all of the user-roles that are in place for this domain

    # ManyToManyField on User creates a "users" member for all of the
    # users who have some role on this domain

    # ForeignKey on DomainInvitation creates an "invitations" member for
    # all of the invitations that have been sent for this domain

    def _validate_host_tuples(self, hosts: list[tuple[str]]):
        """
        Helper function. Validate hostnames and IP addresses.

        Raises:
            ValueError if hostname or IP address appears invalid or mismatched.
        """
        for host in hosts:
            hostname = host[0].lower()
            addresses: tuple[str] = host[1:]  # type: ignore
            if not bool(Domain.HOST_REGEX.match(hostname)):
                raise ValueError("Invalid hostname: %s." % hostname)
            if len(hostname) > Domain.MAX_LENGTH:
                raise ValueError("Too long hostname: %s" % hostname)

            is_subordinate = hostname.split(".", 1)[-1] == self.name
            if is_subordinate and len(addresses) == 0:
                raise ValueError("Must supply IP addresses for %s" % hostname)
            if not is_subordinate and len(addresses) > 0:
                raise ValueError("Must not supply IP addresses for %s" % hostname)

            for address in addresses:
                allow = set(":." + digits)
                if any(c not in allow for c in address):
                    raise ValueError("Invalid IP address: %s." % address)

    def _get_or_create_domain(self):
        """Try to fetch info about this domain. Create it if it does not exist."""
        already_tried_to_create = False
        while True:
            try:
                req = commands.InfoDomain(name=self.name)
                return registry.send(req).res_data[0]
            except RegistryError as e:
                if already_tried_to_create:
                    raise e
                if e.code == ErrorCode.OBJECT_DOES_NOT_EXIST:
                    # avoid infinite loop
                    already_tried_to_create = True
                    registrant = self._get_or_create_contact(
                        PublicContact.get_default_registrant()
                    )
                    req = commands.CreateDomain(
                        name=self.name,
                        registrant=registrant.id,
                        auth_info=epp.DomainAuthInfo(
                            pw="2fooBAR123fooBaz"
                        ),  # not a password
                    )
                    registry.send(req)
                    # no error, so go ahead and update state
                    self.state = Domain.State.CREATED
                    self.save()
                else:
                    raise e

    def _get_or_create_contact(self, contact: PublicContact):
        """Try to fetch info about a contact. Create it if it does not exist."""
        while True:
            try:
                req = commands.InfoContact(id=contact.registry_id)
                return registry.send(req).res_data[0]
            except RegistryError as e:
                if e.code == ErrorCode.OBJECT_DOES_NOT_EXIST:
                    create = commands.CreateContact(
                        id=contact.registry_id,
                        postal_info=epp.PostalInfo(  # type: ignore
                            name=contact.name,
                            addr=epp.ContactAddr(
                                street=[
                                    getattr(contact, street)
                                    for street in ["street1", "street2", "street3"]
                                    if hasattr(contact, street)
                                ],
                                city=contact.city,
                                pc=contact.pc,
                                cc=contact.cc,
                                sp=contact.sp,
                            ),
                            org=contact.org,
                            type="loc",
                        ),
                        email=contact.email,
                        voice=contact.voice,
                        fax=contact.fax,
                        auth_info=epp.ContactAuthInfo(pw="2fooBAR123fooBaz"),
                    )
                    # security contacts should only show email addresses, for now
                    if (
                        contact.contact_type
                        == PublicContact.ContactTypeChoices.SECURITY
                    ):
                        DF = epp.DiscloseField
                        create.disclose = epp.Disclose(
                            flag=False,
                            fields={DF.FAX, DF.VOICE, DF.ADDR},
                            types={DF.ADDR: "loc"},
                        )
                    registry.send(create)
                else:
                    raise e

    def _update_or_create_host(self, host):
        raise NotImplementedError()

    def _delete_host(self, host):
        raise NotImplementedError()

    def _fetch_cache(self, fetch_hosts=False, fetch_contacts=False):
        """Contact registry for info about a domain."""
        try:
            # get info from registry
            data = self._get_or_create_domain()
            # extract properties from response
            # (Ellipsis is used to mean "null")
            cache = {
                "auth_info": getattr(data, "auth_info", ...),
                "_contacts": getattr(data, "contacts", ...),
                "cr_date": getattr(data, "cr_date", ...),
                "ex_date": getattr(data, "ex_date", ...),
                "_hosts": getattr(data, "hosts", ...),
                "name": getattr(data, "name", ...),
                "registrant": getattr(data, "registrant", ...),
                "statuses": getattr(data, "statuses", ...),
                "tr_date": getattr(data, "tr_date", ...),
                "up_date": getattr(data, "up_date", ...),
            }
            # remove null properties (to distinguish between "a value of None" and null)
            cleaned = {k: v for k, v in cache if v is not ...}

            # get contact info, if there are any
            if (
                fetch_contacts
                and "_contacts" in cleaned
                and isinstance(cleaned["_contacts"], list)
                and len(cleaned["_contacts"])
            ):
                cleaned["contacts"] = []
                for id in cleaned["_contacts"]:
                    # we do not use _get_or_create_* because we expect the object we
                    # just asked the registry for still exists --
                    # if not, that's a problem
                    req = commands.InfoContact(id=id)
                    data = registry.send(req).res_data[0]
                    # extract properties from response
                    # (Ellipsis is used to mean "null")
                    contact = {
                        "id": id,
                        "auth_info": getattr(data, "auth_info", ...),
                        "cr_date": getattr(data, "cr_date", ...),
                        "disclose": getattr(data, "disclose", ...),
                        "email": getattr(data, "email", ...),
                        "fax": getattr(data, "fax", ...),
                        "postal_info": getattr(data, "postal_info", ...),
                        "statuses": getattr(data, "statuses", ...),
                        "tr_date": getattr(data, "tr_date", ...),
                        "up_date": getattr(data, "up_date", ...),
                        "voice": getattr(data, "voice", ...),
                    }
                    cleaned["contacts"].append(
                        {k: v for k, v in contact if v is not ...}
                    )

            # get nameserver info, if there are any
            if (
                fetch_hosts
                and "_hosts" in cleaned
                and isinstance(cleaned["_hosts"], list)
                and len(cleaned["_hosts"])
            ):
                cleaned["hosts"] = []
                for name in cleaned["_hosts"]:
                    # we do not use _get_or_create_* because we expect the object we
                    # just asked the registry for still exists --
                    # if not, that's a problem
                    req = commands.InfoHost(name=name)
                    data = registry.send(req).res_data[0]
                    # extract properties from response
                    # (Ellipsis is used to mean "null")
                    host = {
                        "name": name,
                        "addrs": getattr(data, "addrs", ...),
                        "cr_date": getattr(data, "cr_date", ...),
                        "statuses": getattr(data, "statuses", ...),
                        "tr_date": getattr(data, "tr_date", ...),
                        "up_date": getattr(data, "up_date", ...),
                    }
                    cleaned["hosts"].append({k: v for k, v in host if v is not ...})

            # replace the prior cache with new data
            self._cache = cleaned
        except RegistryError as e:
            logger.error(e)

    def _invalidate_cache(self):
        """Remove cache data when updates are made."""
        self._cache = {}

    def _get_property(self, property):
        """Get some piece of info about a domain."""
        if property not in self._cache:
            self._fetch_cache(
                fetch_hosts=(property == "hosts"),
                fetch_contacts=(property == "contacts"),
            )
        if property in self._cache:
            return self._cache[property]
        else:
            raise KeyError(
                "Requested key %s was not found in registry cache." % str(property)
            )
