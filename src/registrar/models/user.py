from enum import Enum
import logging

from django.contrib.auth.models import AbstractUser
from django.db import models

from registrar.models.user_domain_role import UserDomainRole

from .domain_invitation import DomainInvitation
from .transition_domain import TransitionDomain
from .verified_by_staff import VerifiedByStaff
from .domain import Domain
from .domain_request import DomainRequest

from phonenumber_field.modelfields import PhoneNumberField  # type: ignore


logger = logging.getLogger(__name__)


class User(AbstractUser):
    """
    A custom user model that performs identically to the default user model
    but can be customized later.
    """

    class VerificationTypeChoices(models.TextChoices):
        """
        Users achieve access to our system in a few different ways.
        These choices reflect those pathways.
        """
        GRANDFATHERED = "grandfathered", "Legacy user"
        VERIFIED_BY_STAFF = "verified_by_staff", "Verified by staff"
        REGULAR = "regular", "Verified by Login.gov"
        INVITED = "invited", "Invited by a domain manager"

    # #### Constants for choice fields ####
    RESTRICTED = "restricted"
    STATUS_CHOICES = ((RESTRICTED, RESTRICTED),)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=None,  # Set the default value to None
        null=True,  # Allow the field to be null
        blank=True,  # Allow the field to be blank
    )

    domains = models.ManyToManyField(
        "registrar.Domain",
        through="registrar.UserDomainRole",
        related_name="users",
    )

    phone = PhoneNumberField(
        null=True,
        blank=True,
        help_text="Phone",
        db_index=True,
    )

    verification_type = models.CharField(
        choices=VerificationTypeChoices.choices,
        null=True,
        blank=True,
        help_text="The means through which this user was verified",
    )

    def __str__(self):
        # this info is pulled from Login.gov
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''} {self.email or ''}"
        elif self.email:
            return self.email
        else:
            return self.username

    def restrict_user(self):
        self.status = self.RESTRICTED
        self.save()

    def unrestrict_user(self):
        self.status = None
        self.save()

    def is_restricted(self):
        return self.status == self.RESTRICTED

    def get_approved_domains_count(self):
        """Return count of approved domains"""
        allowed_states = [Domain.State.UNKNOWN, Domain.State.DNS_NEEDED, Domain.State.READY, Domain.State.ON_HOLD]
        approved_domains_count = self.domains.filter(state__in=allowed_states).count()
        return approved_domains_count

    def get_active_requests_count(self):
        """Return count of active requests"""
        allowed_states = [
            DomainRequest.DomainRequestStatus.SUBMITTED,
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
        ]
        active_requests_count = self.domain_requests_created.filter(status__in=allowed_states).count()
        return active_requests_count

    def get_rejected_requests_count(self):
        """Return count of rejected requests"""
        return self.domain_requests_created.filter(status=DomainRequest.DomainRequestStatus.REJECTED).count()

    def get_ineligible_requests_count(self):
        """Return count of ineligible requests"""
        return self.domain_requests_created.filter(status=DomainRequest.DomainRequestStatus.INELIGIBLE).count()

    def has_contact_info(self):
        return bool(self.contact.title or self.contact.email or self.contact.phone)

    @classmethod
    def needs_identity_verification(cls, email, uuid):
        """A method used by our oidc classes to test whether a user needs email/uuid verification
        or the full identity PII verification"""

        # An existing user who is a domain manager of a domain (that is,
        # they have an entry in UserDomainRole for their User)
        try:
            existing_user = cls.objects.get(username=uuid)
            if existing_user and UserDomainRole.objects.filter(user=existing_user).exists():
                return False
        except cls.DoesNotExist:
            # Do nothing when the user is not found, as we're checking for existence.
            pass
        except Exception as err:
            raise err

        # We can't set the verification type here because the user may not
        # always exist at this point. We do it down the line.
        verification_type = cls.get_verification_type_from_email(email)

        # The user needs identity verification if they don't meet
        # any special criteria, i.e. we are validating them "regularly"
        needs_verification = verification_type == cls.VerificationTypeChoices.REGULAR
        return needs_verification

    def set_user_verification_type(self):
        # Would need to check audit log
        retrieved = DomainInvitation.DomainInvitationStatus.RETRIEVED
        verification_type = self.get_verification_type_from_email(self.email, invitation_status=retrieved)
        self.verification_type = verification_type

    @classmethod
    def get_verification_type_from_email(cls, email, invitation_status=DomainInvitation.DomainInvitationStatus.INVITED):
        """Retrieves the verification type based off of a provided email address"""
        
        verification_type = None
        if TransitionDomain.objects.filter(username=email).exists():
            # A new incoming user who is a domain manager for one of the domains
            # that we inputted from Verisign (that is, their email address appears
            # in the username field of a TransitionDomain)
            verification_type = cls.VerificationTypeChoices.GRANDFATHERED
        elif VerifiedByStaff.objects.filter(email=email).exists():
            # New users flagged by Staff to bypass ial2
            verification_type = cls.VerificationTypeChoices.VERIFIED_BY_STAFF
        elif DomainInvitation.objects.filter(email=email, status=invitation_status).exists():
                # A new incoming user who is being invited to be a domain manager (that is,
            # their email address is in DomainInvitation for an invitation that is not yet "retrieved").
            verification_type = cls.VerificationTypeChoices.INVITED
        else:
            verification_type = cls.VerificationTypeChoices.REGULAR
        
        return verification_type

    def check_domain_invitations_on_login(self):
        """When a user first arrives on the site, we need to retrieve any domain
        invitations that match their email address."""
        for invitation in DomainInvitation.objects.filter(
            email__iexact=self.email, status=DomainInvitation.DomainInvitationStatus.INVITED
        ):
            try:
                invitation.retrieve()
                invitation.save()
            except RuntimeError:
                # retrieving should not fail because of a missing user, but
                # if it does fail, log the error so a new user can continue
                # logging in
                logger.warn("Failed to retrieve invitation %s", invitation, exc_info=True)

    def create_domain_and_invite(self, transition_domain: TransitionDomain):
        transition_domain_name = transition_domain.domain_name
        transition_domain_status = transition_domain.status
        transition_domain_email = transition_domain.username

        # type safety check.  name should never be none
        if transition_domain_name is not None:
            new_domain = Domain(name=transition_domain_name, state=transition_domain_status)
            new_domain.save()
            # check that a domain invitation doesn't already
            # exist for this e-mail / Domain pair
            domain_email_already_in_domain_invites = DomainInvitation.objects.filter(
                email=transition_domain_email.lower(), domain=new_domain
            ).exists()
            if not domain_email_already_in_domain_invites:
                # Create new domain invitation
                new_domain_invitation = DomainInvitation(email=transition_domain_email.lower(), domain=new_domain)
                new_domain_invitation.save()

    def on_each_login(self):
        """Callback each time the user is authenticated.

        When a user arrives on the site each time, we need to retrieve any domain
        invitations that match their email address.

        We also need to check if they are logging in with the same e-mail
        as a transition domain and update our domainInfo objects accordingly.
        """

        self.check_domain_invitations_on_login()

    class Meta:
        permissions = [
            ("analyst_access_permission", "Analyst Access Permission"),
            ("full_access_permission", "Full Access Permission"),
        ]
