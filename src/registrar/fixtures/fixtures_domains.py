import logging
import random
from django.db import transaction
from registrar.fixtures import DomainRequestFixture
from registrar.models import User, DomainRequest

logger = logging.getLogger(__name__)


class DomainFixture(DomainRequestFixture):
    """Create one domain and permissions on it for each user."""

    @classmethod
    def load(cls):
        try:
            users = list(User.objects.all())  # force evaluation to catch db errors
        except Exception as e:
            logger.warning(e)
            return

        # Lumped under .atomic to ensure we don't make redundant DB calls.
        # This bundles them all together, and then saves it in a single call.
        with transaction.atomic():
            # approve each user associated with `in review` status domains
            DomainFixture._approve_domain_requests(users)

    @staticmethod
    def _approve_domain_requests(users):
        """Approves all provided domain requests if they are in the state in_review"""
        for user in users:
            domain_request = DomainRequest.objects.filter(
                creator=user, status=DomainRequest.DomainRequestStatus.IN_REVIEW
            ).last()
            logger.debug(f"Approving {domain_request} for {user}")

            # All approvals require an investigator, so if there is none,
            # assign one.
            if domain_request.investigator is None:
                # All "users" in fixtures have admin perms per prior config.
                # No need to check for that.
                domain_request.investigator = random.choice(users)  # nosec

            domain_request.approve(send_email=False)
            domain_request.save()
