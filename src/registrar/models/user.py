import logging

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q, Exists, OuterRef

from registrar.models import DomainInformation, UserDomainRole, PortfolioInvitation, UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioPermissionChoices, UserPortfolioRoleChoices

from .domain_invitation import DomainInvitation
from .transition_domain import TransitionDomain
from .verified_by_staff import VerifiedByStaff
from .domain import Domain
from .domain_request import DomainRequest
from registrar.utility.waffle import flag_is_active_for_user
from waffle.decorators import flag_is_active
from django.utils import timezone
from datetime import timedelta

from phonenumber_field.modelfields import PhoneNumberField  # type: ignore


logger = logging.getLogger(__name__)


class User(AbstractUser):
    """
    A custom user model that performs identically to the default user model
    but can be customized later.

    If the `user` object already exists, said user object
    will be updated if any updates are made to it through Login.gov.
    """

    class Meta:
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
        ]

        permissions = [
            ("analyst_access_permission", "Analyst Access Permission"),
            ("full_access_permission", "Full Access Permission"),
        ]

    class VerificationTypeChoices(models.TextChoices):
        """
        Users achieve access to our system in a few different ways.
        These choices reflect those pathways.

        Overview of verification types:
        - GRANDFATHERED: User exists in the `TransitionDomain` table
        - VERIFIED_BY_STAFF: User exists in the `VerifiedByStaff` table
        - INVITED: User exists in the `DomainInvitation` table
        - REGULAR: User was verified through IAL2
        - FIXTURE_USER: User was created by fixtures
        """

        GRANDFATHERED = "grandfathered", "Legacy user"
        VERIFIED_BY_STAFF = "verified_by_staff", "Verified by staff"
        REGULAR = "regular", "Verified by Login.gov"
        INVITED = "invited", "Invited by a domain manager"
        # We need a type for fixture users (rather than using verified by staff)
        # because those users still do get "verified" through normal means
        # after they login.
        FIXTURE_USER = "fixture_user", "Created by fixtures"

    # #### Constants for choice fields ####
    RESTRICTED = "restricted"
    STATUS_CHOICES = ((RESTRICTED, RESTRICTED),)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=None,  # Set the default value to None
        null=True,  # Allow the field to be null
        blank=True,  # Allow the field to be blank
        verbose_name="user status",
        help_text='Users in "restricted" status cannot make updates in the registrar or start a new request.',
    )

    domains = models.ManyToManyField(
        "registrar.Domain",
        through="registrar.UserDomainRole",
        related_name="users",
    )

    phone = PhoneNumberField(
        null=True,
        blank=True,
    )

    middle_name = models.CharField(
        null=True,
        blank=True,
    )

    title = models.CharField(
        null=True,
        blank=True,
        verbose_name="title / role",
    )

    verification_type = models.CharField(
        choices=VerificationTypeChoices.choices,
        null=True,
        blank=True,
        help_text="The means through which this user was verified",
    )

    @property
    def finished_setup(self):
        """
        Tracks if the user finished their profile setup or not. This is so
        we can globally enforce that new users provide additional account information before proceeding.
        """
        user_values = [
            self.first_name,
            self.last_name,
            self.title,
            self.phone,
        ]

        return None not in user_values and "" not in user_values

    def __str__(self):
        # this info is pulled from Login.gov
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''} {self.email or ''}"
        elif self.email:
            return self.email
        else:
            return self.username

    @classmethod
    def get_default_user(cls):
        """Returns the default "system" user"""
        default_creator, _ = User.objects.get_or_create(username="System")
        return default_creator

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

    def get_num_expiring_domains(self, request):
        """Return number of expiring domains"""
        domain_ids = self.get_user_domain_ids(request)
        now = timezone.now().date()
        expiration_window = 60
        threshold_date = now + timedelta(days=expiration_window)
        acceptable_statuses = [Domain.State.UNKNOWN, Domain.State.DNS_NEEDED, Domain.State.READY]

        num_of_expiring_domains = Domain.objects.filter(
            id__in=domain_ids,
            expiration_date__isnull=False,
            expiration_date__lte=threshold_date,
            expiration_date__gt=now,
            state__in=acceptable_statuses,
        ).count()
        return num_of_expiring_domains

    def get_rejected_requests_count(self):
        """Return count of rejected requests"""
        return self.domain_requests_created.filter(status=DomainRequest.DomainRequestStatus.REJECTED).count()

    def get_ineligible_requests_count(self):
        """Return count of ineligible requests"""
        return self.domain_requests_created.filter(status=DomainRequest.DomainRequestStatus.INELIGIBLE).count()

    def get_formatted_name(self):
        """Returns the contact's name in Western order."""
        names = [n for n in [self.first_name, self.middle_name, self.last_name] if n]
        return " ".join(names) if names else "Unknown"

    def has_contact_info(self):
        return bool(self.title or self.email or self.phone)

    def _has_portfolio_permission(self, portfolio, portfolio_permission):
        """The views should only call this function when testing for perms and not rely on roles."""

        if not portfolio:
            return False

        user_portfolio_perms = self.portfolio_permissions.filter(portfolio=portfolio, user=self).first()
        if not user_portfolio_perms:
            return False

        return portfolio_permission in user_portfolio_perms._get_portfolio_permissions()

    def has_view_portfolio_permission(self, portfolio):
        return self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.VIEW_PORTFOLIO)

    def has_edit_portfolio_permission(self, portfolio):
        return self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.EDIT_PORTFOLIO)

    def has_any_domains_portfolio_permission(self, portfolio):
        return self._has_portfolio_permission(
            portfolio, UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS
        ) or self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS)

    def has_view_members_portfolio_permission(self, portfolio):
        if not portfolio:
            return False
        return self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.VIEW_MEMBERS)

    def has_edit_members_portfolio_permission(self, portfolio):
        if not portfolio:
            return False
        return self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.EDIT_MEMBERS)

    def has_view_all_domains_portfolio_permission(self, portfolio):
        """Determines if the current user can view all available domains in a given portfolio"""
        return self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS)

    def has_view_all_domain_requests_portfolio_permission(self, portfolio):
        """Determines if the current user can view all available domains in a given portfolio"""
        return self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS)

    def has_any_requests_portfolio_permission(self, portfolio):
        if not portfolio:
            return False
        return self._has_portfolio_permission(
            portfolio, UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS
        ) or self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.EDIT_REQUESTS)

    def has_view_all_requests_portfolio_permission(self, portfolio):
        """Determines if the current user can view all available domain requests in a given portfolio"""
        return self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS)

    def has_edit_request_portfolio_permission(self, portfolio):
        return self._has_portfolio_permission(portfolio, UserPortfolioPermissionChoices.EDIT_REQUESTS)

    def is_portfolio_admin(self, portfolio):
        return self.has_edit_portfolio_permission(portfolio)

    def get_first_portfolio(self):
        permission = self.portfolio_permissions.first()
        if permission:
            return permission.portfolio
        return None

    def get_num_portfolios(self):
        return self.get_portfolios().count()

    def get_portfolios(self):
        return self.portfolio_permissions.all()

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

        # Checks if the user needs verification.
        # The user needs identity verification if they don't meet
        # any special criteria, i.e. we are validating them "regularly"
        return verification_type == cls.VerificationTypeChoices.REGULAR

    def set_user_verification_type(self):
        """
        Given pre-existing data from TransitionDomain, VerifiedByStaff, and DomainInvitation,
        set the verification "type" defined in VerificationTypeChoices.
        """
        email_or_username = self.email if self.email else self.username
        retrieved = DomainInvitation.DomainInvitationStatus.RETRIEVED
        verification_type = self.get_verification_type_from_email(email_or_username, invitation_status=retrieved)

        # An existing user may have been invited to a domain after they got verified.
        # We need to check for this condition.
        if verification_type == User.VerificationTypeChoices.INVITED:
            invitation = (
                DomainInvitation.objects.filter(email=email_or_username, status=retrieved)
                .order_by("created_at")
                .first()
            )

            # If you joined BEFORE the oldest invitation was created, then you were verified normally.
            # (See logic in get_verification_type_from_email)
            if not invitation and self.date_joined < invitation.created_at:
                verification_type = User.VerificationTypeChoices.REGULAR

        self.verification_type = verification_type

    @classmethod
    def get_verification_type_from_email(cls, email, invitation_status=DomainInvitation.DomainInvitationStatus.INVITED):
        """Retrieves the verification type based off of a provided email address"""

        verification_type = None
        if TransitionDomain.objects.filter(Q(username=email) | Q(email=email)).exists():
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

    def check_portfolio_invitations_on_login(self):
        """When a user first arrives on the site, we need to retrieve any portfolio
        invitations that match their email address."""
        for invitation in PortfolioInvitation.objects.filter(
            email__iexact=self.email, status=PortfolioInvitation.PortfolioInvitationStatus.INVITED
        ):
            only_single_portfolio = (
                not flag_is_active_for_user(self, "multiple_portfolios") and self.get_first_portfolio() is None
            )
            if only_single_portfolio or flag_is_active(None, "multiple_portfolios"):
                try:
                    invitation.retrieve()
                    invitation.save()
                except RuntimeError:
                    # retrieving should not fail because of a missing user, but
                    # if it does fail, log the error so a new user can continue
                    # logging in
                    logger.warn("Failed to retrieve invitation %s", invitation, exc_info=True)
            else:
                logger.warn("User already has a portfolio, did not retrieve invitation %s", invitation, exc_info=True)

    def on_each_login(self):
        """Callback each time the user is authenticated.

        When a user arrives on the site each time, we need to retrieve any domain
        invitations that match their email address.

        We also need to check if they are logging in with the same e-mail
        as a transition domain and update our domainInfo objects accordingly.
        """

        self.check_domain_invitations_on_login()
        self.check_portfolio_invitations_on_login()

    def is_org_user(self, request):
        portfolio = request.session.get("portfolio")
        return portfolio is not None and self.has_view_portfolio_permission(portfolio)

    def is_any_org_user(self):
        return self.get_num_portfolios() > 0

    def is_multiple_orgs_user(self, request):
        has_multiple_portfolios_feature_flag = flag_is_active(request, "multiple_portfolios")
        num_portfolios = self.get_num_portfolios()
        return has_multiple_portfolios_feature_flag and num_portfolios > 1

    def get_user_domain_ids(self, request):
        """Returns either the domains ids associated with this user on UserDomainRole or Portfolio"""
        portfolio = request.session.get("portfolio")
        if self.is_org_user(request) and self.has_view_all_domains_portfolio_permission(portfolio):
            return DomainInformation.objects.filter(portfolio=portfolio).values_list("domain_id", flat=True)
        else:
            return UserDomainRole.objects.filter(user=self).values_list("domain_id", flat=True)

    def get_user_domain_request_ids(self, request):
        """Returns either the domain request ids associated with this user on UserDomainRole or Portfolio"""
        portfolio = request.session.get("portfolio")

        if self.is_org_user(request) and self.has_view_all_domain_requests_portfolio_permission(portfolio):
            return DomainRequest.objects.filter(portfolio=portfolio).values_list("id", flat=True)
        else:
            return UserDomainRole.objects.filter(user=self).values_list("id", flat=True)

    def get_active_requests_count_in_portfolio(self, request):
        """Return count of active requests for the portfolio associated with the request."""
        # Get the portfolio from the session using the existing method

        portfolio = request.session.get("portfolio")

        if not portfolio:
            return 0  # No portfolio found

        allowed_states = [
            DomainRequest.DomainRequestStatus.SUBMITTED,
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
        ]

        # Now filter based on the portfolio retrieved
        active_requests_count = self.domain_requests_created.filter(
            status__in=allowed_states, portfolio=portfolio
        ).count()

        return active_requests_count

    def is_only_admin_of_portfolio(self, portfolio):
        """Check if the user is the only admin of the given portfolio."""

        admin_permission = UserPortfolioRoleChoices.ORGANIZATION_ADMIN

        admins = UserPortfolioPermission.objects.filter(portfolio=portfolio, roles__contains=[admin_permission])
        admin_count = admins.count()

        # Check if the current user is in the list of admins
        if admin_count == 1 and admins.first() and admins.first().user == self:
            return True  # The user is the only admin

        # If there are other admins or the user is not the only one
        return False

    def has_personal_assets(self) -> bool:
        """
        True if this user has any domain role on a domain whose DomainInformation.portfolio is NULL.
        This ignores the current session/org and works even if the user ALSO has portfolios.
        """
        no_portfolio = DomainInformation.objects.filter(
            domain_id=OuterRef("domain_id"),
            portfolio__isnull=True,
        )
        return UserDomainRole.objects.filter(user=self).filter(Exists(no_portfolio)).exists()

    def personal_domain_ids(self):
        """
        IDs of domains this user manages that are NOT in any portfolio.
        """
        return (
            DomainInformation.objects.filter(portfolio__isnull=True, domain__userdomainrole__user=self)
            .values_list("domain_id", flat=True)
            .distinct()
        )
