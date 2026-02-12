import logging
from faker import Faker

from registrar.models.portfolio import Portfolio
from registrar.models.suborganization import Suborganization

fake = Faker()
logger = logging.getLogger(__name__)


class SuborganizationFixture:
    """
    Creates 2 pre-defined suborg with the infrastructure to add more.

    Depends on fixtures_portfolios.

    Make sure this class' `load` method is called from `handle`
    in management/commands/load.py, then use `./manage.py load`
    to run this code.
    """

    SUBORGS = [
        {
            "name": "Take it Easy",
        },
        {
            "name": "Welcome to the Machine",
        },
    ]

    @classmethod
    def load(cls):
        """Creates suborganizations."""
        logger.info(f"Going to load {len(cls.SUBORGS)} suborgs")
        portfolios = cls._get_portfolios()
        if not portfolios:
            return

        suborgs_to_create = cls._prepare_suborgs_to_create(portfolios)
        cls._bulk_create_suborgs(suborgs_to_create)

    @classmethod
    def _get_portfolios(cls):
        """Fetches portfolios with organization_name 'Hotel California' and 'Wish You Were Here'
        and logs warnings if not found."""
        try:
            portfolio1 = Portfolio.objects.filter(organization_name="Hotel California").first()
            portfolio2 = Portfolio.objects.filter(organization_name="Wish You Were Here").first()

            if not portfolio1 or not portfolio2:
                logger.warning("One or both portfolios not found.")
                return None
            return portfolio1, portfolio2
        except Exception as e:
            logger.warning(f"Error fetching portfolios: {e}")
            return None

    @classmethod
    def _prepare_suborgs_to_create(cls, portfolios):
        """Prepares a list of suborganizations to create, avoiding duplicates."""
        portfolio1, portfolio2 = portfolios
        suborgs_to_create = []

        try:
            if not Suborganization.objects.filter(name=cls.SUBORGS[0]["name"]).exists():
                suborgs_to_create.append(Suborganization(portfolio=portfolio1, name=cls.SUBORGS[0]["name"]))

            if not Suborganization.objects.filter(name=cls.SUBORGS[1]["name"]).exists():
                suborgs_to_create.append(Suborganization(portfolio=portfolio2, name=cls.SUBORGS[1]["name"]))
        except Exception as e:
            logger.warning(f"Error creating suborg objects: {e}")

        return suborgs_to_create

    @classmethod
    def _bulk_create_suborgs(cls, suborgs_to_create):
        """Bulk creates suborganizations and logs success or errors."""
        if suborgs_to_create:
            try:
                Suborganization.objects.bulk_create(suborgs_to_create)
                logger.info(f"Successfully created {len(suborgs_to_create)} suborgs")
            except Exception as e:
                logger.warning(f"Error bulk creating suborgs: {e}")
