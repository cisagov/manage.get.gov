import logging
from faker import Faker
from django.db import transaction

from registrar.fixtures.fixtures_users import UserFixture
from registrar.models import User
from registrar.models.portfolio import Portfolio
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.utility.portfolio_helper import UserPortfolioRoleChoices

fake = Faker()
logger = logging.getLogger(__name__)


class UserPortfolioPermissionFixture:
    """Create user portfolio permissions for each user.
    Each user will be admin on 2 portfolios.

    Depends on fixture_portfolios"""

    @classmethod
    def load(cls):
        logger.info("Going to set user portfolio permissions")

        # Lumped under .atomic to ensure we don't make redundant DB calls.
        # This bundles them all together, and then saves it in a single call.
        with transaction.atomic():
            try:
                # Get the usernames of users created in the UserFixture
                created_usernames = [user_data["username"] for user_data in UserFixture.ADMINS + UserFixture.STAFF]

                # Filter users to only include those created by the fixture
                users = list(User.objects.filter(username__in=created_usernames))

                portfolios = list(Portfolio.objects.all())
            except Exception as e:
                logger.warning(e)
                return

            user_portfolio_permissions_to_create = []
            for user in users:
                for portfolio in portfolios:
                    try:
                        if not UserPortfolioPermission.objects.filter(user=user, portfolio=portfolio).exists():
                            user_portfolio_permission = UserPortfolioPermission(
                                user=user,
                                portfolio=portfolio,
                                roles=[UserPortfolioRoleChoices.ORGANIZATION_ADMIN],
                            )
                            user_portfolio_permissions_to_create.append(user_portfolio_permission)
                        else:
                            logger.info(
                                f"Permission exists for user '{user.username}' "
                                "on portfolio '{portfolio.organization_name}'."
                            )
                    except Exception as e:
                        logger.warning(e)

            # Bulk create domain requests
            if len(user_portfolio_permissions_to_create) > 0:
                UserPortfolioPermission.objects.bulk_create(user_portfolio_permissions_to_create)
