import logging

from datetime import date
from django_fsm import FSMField  # type: ignore

from django.db import models

from epplibwrapper import (
    CLIENT as registry,
    commands,
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

    @classmethod
    def available(cls, domain: str) -> bool:
        """Check if a domain is available."""
        if not cls.string_could_be_domain(domain):
            raise ValueError("Not a valid domain: %s" % str(domain))
        req = commands.CheckDomain([domain])
        return registry.send(req).res_data[0].avail

    @classmethod
    def registered(cls, domain: str) -> bool:
        """Check if a domain is _not_ available."""
        return not cls.available(domain)

    @property
    def contacts(self) -> dict[str, str]:
        """
        Get a dictionary of registry IDs for the contacts for this domain.

        IDs are provided as strings, e.g.

            { PublicContact.ContactTypeChoices.REGISTRANT: "jd1234",
              PublicContact.ContactTypeChoices.ADMINISTRATIVE: "sh8013",...}
        """
        raise NotImplementedError()

    @property
    def creation_date(self) -> date:
        """Get the `cr_date` element from the registry."""
        raise NotImplementedError()

    @property
    def last_transferred_date(self) -> date:
        """Get the `tr_date` element from the registry."""
        raise NotImplementedError()

    @property
    def last_updated_date(self) -> date:
        """Get the `up_date` element from the registry."""
        raise NotImplementedError()

    @property
    def expiration_date(self) -> date:
        """Get or set the `ex_date` element from the registry."""
        raise NotImplementedError()

    @expiration_date.setter  # type: ignore
    def expiration_date(self, ex_date: date):
        raise NotImplementedError()

    @property
    def password(self) -> str:
        """
        Get the `auth_info.pw` element from the registry. Not a real password.

        This `auth_info` element is required by the EPP protocol, but the registry is
        using a different mechanism to ensure unauthorized clients cannot perform
        actions on domains they do not own. This field provides no security features.
        It is not a secret.
        """
        raise NotImplementedError()

    @property
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

    @property
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

    @property
    def registrant_contact(self) -> PublicContact:
        """Get or set the registrant for this domain."""
        raise NotImplementedError()

    @registrant_contact.setter  # type: ignore
    def registrant_contact(self, contact: PublicContact):
        raise NotImplementedError()

    @property
    def administrative_contact(self) -> PublicContact:
        """Get or set the admin contact for this domain."""
        raise NotImplementedError()

    @administrative_contact.setter  # type: ignore
    def administrative_contact(self, contact: PublicContact):
        raise NotImplementedError()

    @property
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

    @property
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
        raise NotImplementedError("This is not implemented yet.")

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

    state = FSMField(
        max_length=21,
        choices=State.choices,
        default=State.UNKNOWN,
        protected=True,  # cannot change state directly, particularly in Django admin
        help_text="Very basic info about the lifecycle of this domain object",
    )

    # ForeignKey on UserDomainRole creates a "permissions" member for
    # all of the user-roles that are in place for this domain

    # ManyToManyField on User creates a "users" member for all of the
    # users who have some role on this domain

    # ForeignKey on DomainInvitation creates an "invitations" member for
    # all of the invitations that have been sent for this domain
