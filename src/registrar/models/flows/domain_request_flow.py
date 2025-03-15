import logging

# from django import apps
from django.conf import settings
from registrar.models.domain_request import DomainRequest
from viewflow import fsm
from django.utils import timezone
from django.apps import apps
from registrar.models.federal_agency import FederalAgency
from registrar.utility.errors import FSMDomainRequestError, FSMErrorCodes

logger = logging.getLogger(__name__)


class DomainRequestFlow(object):
    """
    Controls the "flow" between states of the Domain Request object
    Only pass DomainRequest to this class
    """

    status = fsm.State(DomainRequest.DomainRequestStatus, default=DomainRequest.DomainRequestStatus.STARTED)

    def __init__(self, domain_request):
        self.domain_request = domain_request

    @status.setter()
    def _set_domain_request_status(self, value):
        self.domain_request.__dict__["status"] = value

    @status.getter()
    def _get_domain_request_status(self):
        return self.domain_request.status

    @status.transition(
        source=[
            DomainRequest.DomainRequestStatus.STARTED,
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            DomainRequest.DomainRequestStatus.WITHDRAWN,
        ],
        target=DomainRequest.DomainRequestStatus.SUBMITTED,
    )
    def submit(self):
        """Submit an domain request that is started.

        As a side effect, an email notification is sent."""

        # check our conditions here inside the `submit` method so that we
        # can raise more informative exceptions

        # requested_domain could be None here
        if not hasattr(self.domain_request, "requested_domain") or self.domain_request.requested_domain is None:
            raise ValueError("Requested domain is missing.")

        DraftDomain = apps.get_model("registrar.DraftDomain")
        if not DraftDomain.string_could_be_domain(self.domain_request.requested_domain.name):
            raise ValueError("Requested domain is not a valid domain name.")
        # if the domain has not been submitted before this  must be the first time
        if not self.domain_request.first_submitted_date:
            self.domain_request.first_submitted_date = timezone.now().date()

        # Update last_submitted_date to today
        self.domain_request.last_submitted_date = timezone.now().date()
        self.domain_request.save()

        # Limit email notifications to transitions from Started and Withdrawn
        limited_statuses = [DomainRequest.DomainRequestStatus.STARTED, DomainRequest.DomainRequestStatus.WITHDRAWN]

        bcc_address = ""
        if settings.IS_PRODUCTION:
            bcc_address = settings.DEFAULT_FROM_EMAIL

        if self.domain_request.status in limited_statuses:
            self.domain_request._send_status_update_email(
                "submission confirmation",
                "emails/submission_confirmation.txt",
                "emails/submission_confirmation_subject.txt",
                send_email=True,
                bcc_address=bcc_address,
            )

    def domain_is_not_active(self):
        return self.domain_request.domain_is_not_active()

    def investigator_exists_and_is_staff(self):
        return self.domain_request.investigator_exists_and_is_staff()

    @status.transition(
        source=[
            DomainRequest.DomainRequestStatus.SUBMITTED,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            DomainRequest.DomainRequestStatus.APPROVED,
            DomainRequest.DomainRequestStatus.REJECTED,
            DomainRequest.DomainRequestStatus.INELIGIBLE,
        ],
        target=DomainRequest.DomainRequestStatus.IN_REVIEW,
        conditions=[domain_is_not_active, investigator_exists_and_is_staff],
    )
    def in_review(self):
        """Investigate an domain request that has been submitted.

        This action is logged.

        This action cleans up the rejection status if moving away from rejected.

        As side effects this will delete the domain and domain_information
        (will cascade) when they exist."""

        if self.domain_request.status == DomainRequest.DomainRequestStatus.APPROVED:
            self.domain_request.delete_and_clean_up_domain("in_review")
        elif self.domain_request.status == DomainRequest.DomainRequestStatus.REJECTED:
            self.domain_request.rejection_reason = None
        elif self.domain_request.status == DomainRequest.DomainRequestStatus.ACTION_NEEDED:
            self.domain_request.action_needed_reason = None

        literal = DomainRequest.DomainRequestStatus.IN_REVIEW
        # Check if the tuple exists, then grab its value
        in_review = literal if literal is not None else "In Review"
        logger.info(f"A status change occurred. {self.domain_request} was changed to '{in_review}'")

    @status.transition(
        source=[
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.APPROVED,
            DomainRequest.DomainRequestStatus.REJECTED,
            DomainRequest.DomainRequestStatus.INELIGIBLE,
        ],
        target=DomainRequest.DomainRequestStatus.ACTION_NEEDED,
        conditions=[domain_is_not_active, investigator_exists_and_is_staff],
    )
    def action_needed(self):
        """Send back an domain request that is under investigation or rejected.

        This action is logged.

        This action cleans up the rejection status if moving away from rejected.

        As side effects this will delete the domain and domain_information
        (will cascade) when they exist.

        Afterwards, we send out an email for action_needed in def save().
        See the function send_custom_status_update_email.
        """

        if self.domain_request.status == DomainRequest.DomainRequestStatus.APPROVED:
            self.domain_request.delete_and_clean_up_domain("action_needed")

        elif self.domain_request.status == DomainRequest.DomainRequestStatus.REJECTED:
            self.rejection_reason = None

        # Check if the tuple is setup correctly, then grab its value.

        literal = DomainRequest.DomainRequestStatus.ACTION_NEEDED
        action_needed = literal if literal is not None else "Action Needed"
        logger.info(f"A status change occurred. {self.domain_request} was changed to '{action_needed}'")

    @status.transition(
        source=[
            DomainRequest.DomainRequestStatus.SUBMITTED,
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            DomainRequest.DomainRequestStatus.REJECTED,
        ],
        target=DomainRequest.DomainRequestStatus.APPROVED,
        conditions=[investigator_exists_and_is_staff],
    )
    def approve(self, send_email=True):
        """Approve an domain request that has been submitted.

        This action cleans up the rejection status if moving away from rejected.

        This has substantial side-effects because it creates another database
        object for the approved Domain and makes the user who created the
        domain request into an admin on that domain. It also triggers an email
        notification."""

        should_save = False
        if self.domain_request.federal_agency is None:
            self.domain_request.federal_agency = FederalAgency.objects.filter(agency="Non-Federal Agency").first()
            should_save = True

        if self.domain_request.is_requesting_new_suborganization():
            self.domain_request.sub_organization = self.domain_request.create_requested_suborganization()
            should_save = True

        if should_save:
            self.domain_request.save()

        # create the domain
        Domain = apps.get_model("registrar.Domain")

        # == Check that the domain_request is valid == #
        if Domain.objects.filter(name=self.domain_request.requested_domain.name).exists():
            raise FSMDomainRequestError(code=FSMErrorCodes.APPROVE_DOMAIN_IN_USE)

        # == Create the domain and related components == #
        created_domain = Domain.objects.create(name=self.domain_request.requested_domain.name)
        self.domain_request.approved_domain = created_domain

        # copy the information from DomainRequest into domaininformation
        DomainInformation = apps.get_model("registrar.DomainInformation")
        DomainInformation.create_from_da(domain_request=self.domain_request, domain=created_domain)

        # create the permission for the user
        UserDomainRole = apps.get_model("registrar.UserDomainRole")
        UserDomainRole.objects.get_or_create(
            user=self.domain_request.creator, domain=created_domain, role=UserDomainRole.Roles.MANAGER
        )

        if self.domain_request.status == DomainRequest.DomainRequestStatus.REJECTED:
            self.domain_request.rejection_reason = None
        elif self.domain_request.status == DomainRequest.DomainRequestStatus.ACTION_NEEDED:
            self.domain_request.action_needed_reason = None

        # == Send out an email == #
        self.domain_request._send_status_update_email(
            "domain request approved",
            "emails/status_change_approved.txt",
            "emails/status_change_approved_subject.txt",
            send_email=send_email,
        )

    @status.transition(
        source=[
            DomainRequest.DomainRequestStatus.SUBMITTED,
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
        ],
        target=DomainRequest.DomainRequestStatus.WITHDRAWN,
    )
    def withdraw(self):
        """Withdraw an domain request that has been submitted."""

        self.domain_request._send_status_update_email(
            "withdraw",
            "emails/domain_request_withdrawn.txt",
            "emails/domain_request_withdrawn_subject.txt",
        )

    @status.transition(
        source=[
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            DomainRequest.DomainRequestStatus.APPROVED,
        ],
        target=DomainRequest.DomainRequestStatus.REJECTED,
        conditions=[domain_is_not_active, investigator_exists_and_is_staff],
    )
    def reject(self):
        """Reject an domain request that has been submitted.

        This action is logged.

        This action cleans up the action needed status if moving away from action needed.

        As side effects this will delete the domain and domain_information
        (will cascade) when they exist.

        Afterwards, we send out an email for reject in def save().
        See the function send_custom_status_update_email.
        """

        if self.domain_request.status == DomainRequest.DomainRequestStatus.APPROVED:
            self.domain_request.delete_and_clean_up_domain("reject")

    @status.transition(
        source=[
            DomainRequest.DomainRequestStatus.IN_REVIEW,
            DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            DomainRequest.DomainRequestStatus.APPROVED,
            DomainRequest.DomainRequestStatus.REJECTED,
        ],
        target=DomainRequest.DomainRequestStatus.INELIGIBLE,
        conditions=[domain_is_not_active, investigator_exists_and_is_staff],
    )
    def reject_with_prejudice(self):
        """The applicant is a bad actor, reject with prejudice.

        No email As a side effect, but we block the applicant from editing
        any existing domains/domain requests and from submitting new aplications.
        We do this by setting an ineligible status on the user, which the
        permissions classes test against. This will also delete the domain
        and domain_information (will cascade) when they exist."""

        if self.domain_request.status == DomainRequest.DomainRequestStatus.APPROVED:
            self.domain_request.delete_and_clean_up_domain("reject_with_prejudice")

        self.domain_request.creator.restrict_user()
