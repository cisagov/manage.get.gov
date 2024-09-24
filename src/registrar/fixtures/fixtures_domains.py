from datetime import timedelta
from django.utils import timezone
import logging
import random
from faker import Faker
from django.db import transaction

from registrar.fixtures.fixtures_requests import DomainRequestFixture
from registrar.fixtures.fixtures_users import UserFixture
from registrar.models import User, DomainRequest
from registrar.models.domain import Domain

fake = Faker()
logger = logging.getLogger(__name__)


class DomainFixture(DomainRequestFixture):
    """Create two domains and permissions on them for each user.
    One domain will have a past expiration date.

    Depends on fixtures_requests.

    Make sure this class' `load` method is called from `handle`
    in management/commands/load.py, then use `./manage.py load`
    to run this code.
    """

    @classmethod
    def load(cls):
        # Lumped under .atomic to ensure we don't make redundant DB calls.
        # This bundles them all together, and then saves it in a single call.
        with transaction.atomic():
            try:
                # Get the usernames of users created in the UserFixture
                created_usernames = [user_data["username"] for user_data in UserFixture.ADMINS + UserFixture.STAFF]

                # Filter users to only include those created by the fixture
                users = list(User.objects.filter(username__in=created_usernames))
            except Exception as e:
                logger.warning(e)
                return

            # Approve each user associated with `in review` status domains
            cls._approve_domain_requests(users)

    @staticmethod
    def _generate_fake_expiration_date(days_in_future=365):
        """Generates a fake expiration date between 1 and 365 days in the future."""
        current_date = timezone.now().date()  # nosec
        return current_date + timedelta(days=random.randint(1, days_in_future))  # nosec

    @staticmethod
    def _generate_fake_expiration_date_in_past():
        """Generates a fake expiration date up to 365 days in the past."""
        current_date = timezone.now().date()  # nosec
        return current_date + timedelta(days=random.randint(-365, -1))  # nosec

    @classmethod
    def _approve_request(cls, domain_request, users, is_expired=False):
        """Helper function to approve a domain request and set expiration dates."""
        if not domain_request:
            return None, None

        if domain_request.investigator is None:
            # Assign random investigator if not already assigned
            domain_request.investigator = random.choice(users)  # nosec

        # Approve the domain request
        domain_request.approve(send_email=False)

        # Set expiration date for domain
        domain = None
        if domain_request.requested_domain:
            domain, _ = Domain.objects.get_or_create(name=domain_request.requested_domain.name)
            domain.expiration_date = (
                cls._generate_fake_expiration_date_in_past() if is_expired else cls._generate_fake_expiration_date()
            )

        return domain

    @classmethod
    def _approve_domain_requests(cls, users):
        """Approves one current and one expired request per user."""
        domain_requests_to_update = []
        domains_to_update = []

        for user in users:
            # Get the latest and second-to-last domain requests
            domain_requests = DomainRequest.objects.filter(
                creator=user, status=DomainRequest.DomainRequestStatus.IN_REVIEW
            ).order_by("-id")[:2]

            # Latest domain request
            domain_request = domain_requests[0] if domain_requests else None
            # Second-to-last domain request (expired)
            domain_request_expired = domain_requests[1] if len(domain_requests) > 1 else None

            # Approve the current and expired domain requests
            approved_domain = cls._approve_request(domain_request, users)
            expired_domain = cls._approve_request(domain_request_expired, users, is_expired=True)

            # Collect objects to update
            if domain_request:
                domain_requests_to_update.append(domain_request)
            if domain_request_expired:
                domain_requests_to_update.append(domain_request_expired)
            if approved_domain:
                domains_to_update.append(approved_domain)
            if expired_domain:
                domains_to_update.append(expired_domain)

        # Perform bulk updates
        cls._bulk_update_requests(domain_requests_to_update)
        cls._bulk_update_domains(domains_to_update)

    @classmethod
    def _bulk_update_requests(cls, domain_requests_to_update):
        """Bulk update domain requests."""
        if domain_requests_to_update:
            try:
                DomainRequest.objects.bulk_update(domain_requests_to_update, ["status", "investigator"])
                logger.info(f"Successfully updated {len(domain_requests_to_update)} requests.")
            except Exception as e:
                logger.error(f"Unexpected error during requests bulk update: {e}")

    @classmethod
    def _bulk_update_domains(cls, domains_to_update):
        """Bulk update domains with expiration dates."""
        if domains_to_update:
            try:
                Domain.objects.bulk_update(domains_to_update, ["expiration_date"])
                logger.info(f"Successfully updated {len(domains_to_update)} domains.")
            except Exception as e:
                logger.error(f"Unexpected error during domains bulk update: {e}")
