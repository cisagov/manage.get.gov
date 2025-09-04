import logging
import random
from faker import Faker

from registrar.models import User, DomainRequest, FederalAgency
from registrar.models.portfolio import Portfolio
from registrar.models.senior_official import SeniorOfficial


fake = Faker()
logger = logging.getLogger(__name__)


class PortfolioFixture:
    """
    Creates 2 pre-defined portfolios with the infrastructure to add more.

    Make sure this class' `load` method is called from `handle`
    in management/commands/load.py, then use `./manage.py load`
    to run this code.
    """

    PORTFOLIOS = [
        {
            "organization_name": "Hotel California",
        },
        {
            "organization_name": "Wish You Were Here",
        },
    ]

    @classmethod
    def fake_so(cls):
        return {
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "title": fake.job(),
            "email": fake.ascii_safe_email(),
            "phone": "201-555-5555",
        }

    @classmethod
    def _set_non_foreign_key_fields(cls, portfolio: Portfolio, portfolio_dict: dict):
        """Helper method used by `load`."""
        portfolio.organization_type = (
            portfolio_dict["organization_type"]
            if "organization_type" in portfolio_dict
            else DomainRequest.OrganizationChoices.FEDERAL
        )
        portfolio.notes = portfolio_dict["notes"] if "notes" in portfolio_dict else None
        portfolio.address_line1 = (
            portfolio_dict["address_line1"] if "address_line1" in portfolio_dict else fake.street_address()
        )
        portfolio.address_line2 = portfolio_dict["address_line2"] if "address_line2" in portfolio_dict else None
        portfolio.city = portfolio_dict["city"] if "city" in portfolio_dict else fake.city()
        portfolio.state_territory = (
            portfolio_dict["state_territory"] if "state_territory" in portfolio_dict else fake.state_abbr()
        )
        portfolio.zipcode = portfolio_dict["zipcode"] if "zipcode" in portfolio_dict else fake.postalcode()
        portfolio.urbanization = portfolio_dict["urbanization"] if "urbanization" in portfolio_dict else None
        portfolio.security_contact_email = (
            portfolio_dict["security_contact_email"] if "security_contact_email" in portfolio_dict else fake.email()
        )

    @classmethod
    def _set_foreign_key_fields(cls, portfolio: Portfolio, portfolio_dict: dict, user: User):
        """Helper method used by `load`."""
        if not portfolio.senior_official:
            if portfolio_dict.get("senior_official") is not None:
                portfolio.senior_official, _ = SeniorOfficial.objects.get_or_create(**portfolio_dict["senior_official"])
            else:
                portfolio.senior_official = SeniorOfficial.objects.create(**cls.fake_so())

        if not portfolio.federal_agency:
            if portfolio_dict.get("federal_agency") is not None:
                portfolio.federal_agency, _ = FederalAgency.objects.get_or_create(name=portfolio_dict["federal_agency"])
            else:
                federal_agencies = FederalAgency.objects.all()
                # Random choice of agency for selects, used as placeholders for testing.
                portfolio.federal_agency = random.choice(federal_agencies)  # nosec

    @classmethod
    def load(cls):
        """Creates portfolios."""
        logger.info("Going to load %s portfolios" % len(cls.PORTFOLIOS))
        try:
            user = User.objects.all().last()
        except Exception as e:
            logger.warning(e)
            return

        portfolios_to_create = []
        for portfolio_data in cls.PORTFOLIOS:
            organization_name = portfolio_data["organization_name"]

            # Check if portfolio with the organization name already exists
            if Portfolio.objects.filter(organization_name=organization_name).exists():
                logger.info(
                    f"Portfolio with organization name '{organization_name}' already exists, skipping creation."
                )
                continue

        try:
            portfolio = Portfolio(
                requester=user,
                organization_name=portfolio_data["organization_name"],
            )
            cls._set_non_foreign_key_fields(portfolio, portfolio_data)
            cls._set_foreign_key_fields(portfolio, portfolio_data, user)
            portfolios_to_create.append(portfolio)
        except Exception as e:
            logger.warning(e)

        # Bulk create portfolios
        if len(portfolios_to_create) > 0:
            try:
                Portfolio.objects.bulk_create(portfolios_to_create)
                logger.info(f"Successfully created {len(portfolios_to_create)} portfolios")
            except Exception as e:
                logger.warning(f"Error bulk creating portfolios: {e}")
