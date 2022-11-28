import logging
import re

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django_fsm import FSMField, transition  # type: ignore

from epp.mock_epp import domain_info, domain_check

from .utility.time_stamped_model import TimeStampedModel

logger = logging.getLogger(__name__)


class Domain(TimeStampedModel):
    """
    Manage the lifecycle of domain names.

    The registry is the source of truth for this data and this model exists:
        1. To tie ownership information in the registrar to
           DNS entries in the registry; and
        2. To allow a new registrant to draft DNS entries before their
           application is approved
    """

    class Meta:
        constraints = [
            # draft domains may share the same name, but
            # once approved, they must be globally unique
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_active=True),
                name="unique_domain_name_in_registry",
            ),
        ]

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

    # a domain name is alphanumeric or hyphen, up to 63 characters, doesn't
    # begin or end with a hyphen, followed by a TLD of 2-6 alphabetic characters
    DOMAIN_REGEX = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.[A-Za-z]{2,6}")

    @classmethod
    def normalize(cls, domain: str, tld=None) -> str:  # noqa: C901
        """Return `domain` in form `<second level>.<tld>`, if possible.

        This does not guarantee the returned string is a valid domain name."""
        cleaned = domain.lower()
        # starts with https or http
        if cleaned.startswith("https://"):
            cleaned = cleaned[8:]
        if cleaned.startswith("http://"):
            cleaned = cleaned[7:]
        # has url parts
        if "/" in cleaned:
            cleaned = cleaned.split("/")[0]
        # has query parts
        if "?" in cleaned:
            cleaned = cleaned.split("?")[0]
        # has fragments
        if "#" in cleaned:
            cleaned = cleaned.split("#")[0]
        # replace disallowed chars
        re.sub(r"^[^A-Za-z0-9.-]+", "", cleaned)

        parts = cleaned.split(".")
        # has subdomains or invalid repetitions
        if cleaned.count(".") > 0:
            # remove invalid repetitions
            while parts[-1] == parts[-2]:
                parts.pop()
            # remove subdomains
            parts = parts[-2:]
        hasTLD = len(parts) == 2
        if hasTLD:
            # set correct tld
            if tld is not None:
                parts[-1] = tld
        else:
            # add tld
            if tld is not None:
                parts.append(tld)
            else:
                raise ValueError("You must specify a tld for %s" % domain)

        cleaned = ".".join(parts)

        return cleaned

    @classmethod
    def string_could_be_domain(cls, domain: str | None) -> bool:
        """Return True if the string could be a domain name, otherwise False."""
        if not isinstance(domain, str):
            return False
        return bool(cls.DOMAIN_REGEX.match(domain))

    @classmethod
    def available(cls, domain: str) -> bool:
        """Check if a domain is available.

        Not implemented. Returns a dummy value for testing."""
        return domain_check(domain)

    def transfer(self):
        """Going somewhere. Not implemented."""
        pass

    def renew(self):
        """Time to renew. Not implemented."""
        pass

    def _get_property(self, property):
        """Get some info about a domain."""
        if not self.is_active:
            return None
        if not hasattr(self, "info"):
            try:
                # get info from registry
                self.info = domain_info(self.name)
            except Exception as e:
                logger.error(e)
                # TODO: back off error handling
                return None
        if hasattr(self, "info"):
            if property in self.info:
                return self.info[property]
            else:
                raise KeyError(
                    "Requested key %s was not found in registry data." % str(property)
                )
        else:
            # TODO: return an error if registry cannot be contacted
            return None

    @transition(field="is_active", source="*", target=True)
    def activate(self):
        """This domain should be made live."""
        DomainApplication = apps.get_model("registrar.DomainApplication")
        if hasattr(self, "domain_application"):
            if self.domain_application.status != DomainApplication.APPROVED:
                raise ValueError("Cannot activate. Application must be approved.")
        if Domain.objects.filter(name=self.name, is_active=True).exists():
            raise ValueError("Cannot activate. Domain name is already in use.")
        # TODO: depending on the details of our registry integration
        # we will either contact the registry and deploy the domain
        # in this function OR we will verify that it has already been
        # activated and reject this state transition if it has not
        pass

    @transition(field="is_active", source="*", target=False)
    def deactivate(self):
        """This domain should not be live."""
        # there are security concerns to having this function exist
        # within the codebase; discuss these with the project lead
        # if there is a feature request to implement this
        raise Exception("Cannot revoke, contact registry.")

    @property
    def sld(self):
        """Get or set the second level domain string."""
        return self.name.split(".")[0]

    @sld.setter
    def sld(self, value: str):
        parts = self.name.split(".")
        tld = parts[1] if len(parts) > 1 else ""
        if Domain.string_could_be_domain(f"{value}.{tld}"):
            self.name = f"{value}.{tld}"
        else:
            raise ValidationError("%s is not a valid second level domain" % value)

    @property
    def tld(self):
        """Get or set the top level domain string."""
        parts = self.name.split(".")
        return parts[1] if len(parts) > 1 else ""

    @tld.setter
    def tld(self, value: str):
        sld = self.name.split(".")[0]
        if Domain.string_could_be_domain(f"{sld}.{value}"):
            self.name = f"{sld}.{value}"
        else:
            raise ValidationError("%s is not a valid top level domain" % value)

    def __str__(self) -> str:
        return self.name

    @property
    def roid(self):
        return self._get_property("roid")

    @property
    def status(self):
        return self._get_property("status")

    @property
    def registrant(self):
        return self._get_property("registrant")

    @property
    def sponsor(self):
        return self._get_property("sponsor")

    @property
    def creator(self):
        return self._get_property("creator")

    @property
    def creation_date(self):
        return self._get_property("creation_date")

    @property
    def updator(self):
        return self._get_property("updator")

    @property
    def last_update_date(self):
        return self._get_property("last_update_date")

    @property
    def expiration_date(self):
        return self._get_property("expiration_date")

    @property
    def last_transfer_date(self):
        return self._get_property("last_transfer_date")

    name = models.CharField(
        max_length=253,
        blank=False,
        default=None,  # prevent saving without a value
        help_text="Fully qualified domain name",
    )

    # we use `is_active` rather than `domain_application.status`
    # because domains may exist without associated applications
    is_active = FSMField(
        choices=[
            (True, "Yes"),
            (False, "No"),
        ],
        default=False,
        # TODO: how to edit models in Django admin if protected = True
        protected=False,
        help_text="Domain is live in the registry",
    )

    # TODO: determine the relationship between this field
    # and the domain application's `creator` and `submitter`
    owners = models.ManyToManyField(
        "registrar.User",
        help_text="",
    )
