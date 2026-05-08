from datetime import timedelta
import logging
import random

from django.utils import timezone

from registrar.fixtures.fixtures_requests import DomainRequestFixture
from registrar.fixtures.fixtures_users import UserFixture
from registrar.models import User, DomainRequest
from registrar.models.domain import Domain

logger = logging.getLogger(__name__)


class StandardUserDomainFixture(DomainRequestFixture):
    """
    Creates domain requests and domains for standard test users.

    For each standard user:
      - 7 IN_REVIEW requests are approved, creating a domain per request. Each
        domain's state is then forced to cover every Domain.State value plus
        expired and expiring-soon variants. These domains will show up as "unknown" in EPP still,
      - Additional non-approved requests cover the remaining DomainRequestStatus
        values (excluding INELIGIBLE).

    Domain states are forced via Domain.objects.filter(...).update(state=...) which
    bypasses FSMField(protected=True) on Domain.state — no EPP/OT&E commands are
    sent. These domains exist solely for UI filter testing.

    Depends on fixtures_users (STANDARD_USERS must be loaded first).

    Make sure this class' `load` method is called from `handle`
    in management/commands/load.py, then use `./manage.py load`
    to run this code.
    """

    # Each entry produces one approved domain request and one domain whose state
    # is forced to _target_state after approval.
    DOMAIN_STATE_CONFIGS = [
        {
            "organization_name": "Standard User - Domain Unknown",
            "_target_state": Domain.State.UNKNOWN,
        },
        {
            "organization_name": "Standard User - Domain DNS Needed",
            "_target_state": Domain.State.DNS_NEEDED,
        },
        {
            "organization_name": "Standard User - Domain Ready",
            "_target_state": Domain.State.READY,
        },
        {
            "organization_name": "Standard User - Domain On Hold",
            "_target_state": Domain.State.ON_HOLD,
        },
        {
            "organization_name": "Standard User - Domain Deleted",
            "_target_state": Domain.State.DELETED,
        },
        {
            "organization_name": "Standard User - Domain Expired",
            "_target_state": Domain.State.READY,
            "_expired": True,
        },
        {
            "organization_name": "Standard User - Domain Expiring Soon",
            "_target_state": Domain.State.READY,
            "_expiring_soon": True,
        },
    ]

    # Non-approved requests covering all remaining DomainRequestStatus values.
    # APPROVED is already represented by the 7 approved requests above.
    # INELIGIBLE is intentionally excluded.
    STATUS_REQUEST_CONFIGS = [
        {
            "status": DomainRequest.DomainRequestStatus.STARTED,
            "organization_name": "Standard User - Started",
        },
        {
            "status": DomainRequest.DomainRequestStatus.SUBMITTED,
            "organization_name": "Standard User - Submitted",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Standard User - In Review",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Standard User - In Review",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Standard User - In Review",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Standard User - In Review",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Standard User - In Review",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Standard User - In Review",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Standard User - In Review",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Standard User - In Review",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW_OMB,
            "organization_name": "Standard User - In Review OMB",
        },
        {
            "status": DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            "organization_name": "Standard User - Action Needed",
        },
        {
            "status": DomainRequest.DomainRequestStatus.WITHDRAWN,
            "organization_name": "Standard User - Withdrawn",
        },
        {
            "status": DomainRequest.DomainRequestStatus.REJECTED,
            "organization_name": "Standard User - Rejected",
        },
    ]

    @classmethod
    def load(cls):
        standard_usernames = [u["username"] for u in UserFixture.STANDARD_USERS]
        users = list(User.objects.filter(username__in=standard_usernames))

        if not users:
            logger.warning("Standard users not found, skipping StandardUserDomainFixture.")
            return

        cls._create_status_requests(users)
        cls._create_domains(users)

    @classmethod
    def _create_status_requests(cls, users):
        """Bulk-creates the non-approved status requests for each standard user."""
        requests_to_create = []
        for user in users:
            for config in cls.STATUS_REQUEST_CONFIGS:
                try:
                    request = DomainRequest(
                        requester=user,
                        organization_name=config["organization_name"],
                    )
                    cls._set_non_foreign_key_fields(request, config)
                    cls._set_foreign_key_fields(request, {}, user)
                    requests_to_create.append(request)
                except Exception as e:
                    logger.warning(f"Error preparing status request for {user}: {e}")

        cls._bulk_create_requests(requests_to_create)

        for request in requests_to_create:
            try:
                cls._set_many_to_many_relations(request, {})
            except Exception as e:
                logger.warning(e)

    @classmethod
    def _create_domains(cls, users):
        """
        Uses the 7 IN_REVIEW requests per standard user and approves them with
        approve(), creating a Domain and a UserDomainRole.MANAGER for the requester), then bulk-updates the request
        statuses. Domain states are forced in _force_domain_states().
        """
        for user in users:
            approved_pairs = []
            # get all the in_review requests for this user, up to the number of domain state configs we have
            in_review_requests = list(
                DomainRequest.objects.filter(
                    requester=user,
                    status=DomainRequest.DomainRequestStatus.IN_REVIEW,
                ).order_by("id")[: len(cls.DOMAIN_STATE_CONFIGS)]
            )

            if len(in_review_requests) != len(cls.DOMAIN_STATE_CONFIGS):
                logger.warning(
                    f"Not enough IN_REVIEW requests for user {user.username} to approve. "
                    f"Expected {len(cls.DOMAIN_STATE_CONFIGS)}, found {len(in_review_requests)}."
                )
                continue

            for request, config in zip(in_review_requests, cls.DOMAIN_STATE_CONFIGS):
                try:
                    request.investigator = random.choice(User.objects.filter(is_staff=True))  # nosec
                    request.approve(send_email=False)
                    approved_pairs.append((request, config))
                except Exception as e:
                    logger.warning(f"Cannot approve domain request for {user}: {e}")

            if approved_pairs:
                try:
                    DomainRequest.objects.bulk_update([r for r, _ in approved_pairs], ["status", "investigator"])
                except Exception as e:
                    logger.error(f"Error bulk updating domain requests for {user}: {e}")

            cls._force_domain_states(approved_pairs)

    @classmethod
    def _force_domain_states(cls, approved_pairs):
        """
        Forces each approved domain into its target state via queryset update().
        Domain.state is FSMField(protected=True), so direct attribute assignment raises AttributeError
        — queryset update() issues a raw SQL UPDATE that bypasses the FSM with no EPP calls.
        Expect these domains to throw errors or switch back to "unknown" if any code tries to send EPP commands for them
        (such as clicking 'manage' on the domain's table)
        """
        today = timezone.now().date()
        for request, config in approved_pairs:
            try:
                domain = Domain.objects.get(domain_info__domain_request=request)
            except Domain.DoesNotExist:
                logger.warning(f"Domain not found for request {request.id}, skipping state update.")
                continue

            target_state = config["_target_state"]

            if config.get("_expired"):
                expiration_date = today - timedelta(days=random.randint(1, 365))  # nosec
            elif config.get("_expiring_soon"):
                expiration_date = today + timedelta(days=random.randint(1, 30))  # nosec
            else:
                expiration_date = today + timedelta(days=random.randint(31, 365))  # nosec

            Domain.objects.filter(id=domain.id).update(
                state=target_state,
                expiration_date=expiration_date,
                is_enrolled_in_dns_hosting=True,
            )
