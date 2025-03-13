from datetime import timedelta
from django.utils import timezone
import logging
import random
from faker import Faker

from registrar.fixtures.fixtures_requests import DomainRequestFixture
from registrar.fixtures.fixtures_users import UserFixture
from registrar.models import User, DomainRequest
from registrar.models.domain import Domain
from registrar.models.domain_request import DomainRequestFlow

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
    def _approve_request(cls, domain_request, users):
        """Helper function to approve a domain request."""
        if not domain_request:
            return None

        if domain_request.investigator is None:
            # Assign random investigator if not already assigned
            domain_request.investigator = random.choice(users)  # nosec

        # Approve the domain request
        flow = DomainRequestFlow(domain_request)
        flow.approve(send_email=False)

        return domain_request

    @classmethod
    def _approve_domain_requests(cls, users):
        """Approves one current and one expired request per user."""
        domain_requests_to_update = []
        expired_requests = []

        for user in users:
            # Get the latest and second-to-last domain requests
            domain_requests = DomainRequest.objects.filter(
                creator=user, status=DomainRequest.DomainRequestStatus.IN_REVIEW
            ).order_by("-id")[:2]

            # Latest domain request
            domain_request = domain_requests[0] if domain_requests else None
            # Second-to-last domain request (expired)
            domain_request_expired = domain_requests[1] if len(domain_requests) > 1 else None

            # Approve the current domain request
            if domain_request:
                try:
                    cls._approve_request(domain_request, users)
                except Exception as err:
                    logger.warning(f"Cannot approve domain request in fixtures: {err}")
                domain_requests_to_update.append(domain_request)

            # Approve the expired domain request
            if domain_request_expired:
                try:
                    cls._approve_request(domain_request_expired, users)
                except Exception as err:
                    logger.warning(f"Cannot approve domain request (expired) in fixtures: {err}")
                domain_requests_to_update.append(domain_request_expired)
                expired_requests.append(domain_request_expired)

        # Perform bulk update for the domain requests
        cls._bulk_update_requests(domain_requests_to_update)

        # Retrieve all domains associated with the domain requests
        domains_to_update = Domain.objects.filter(domain_info__domain_request__in=domain_requests_to_update)

        # Loop through and update expiration dates for domains
        for domain in domains_to_update:
            domain_request = domain.domain_info.domain_request

            # Set the expiration date based on whether the request is expired
            if domain_request in expired_requests:
                domain.expiration_date = cls._generate_fake_expiration_date_in_past()
            else:
                domain.expiration_date = cls._generate_fake_expiration_date()

        # Perform bulk update for the domains
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
