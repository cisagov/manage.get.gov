import logging
import random
from faker import Faker
from django.db import transaction

from registrar.models import User, DomainRequest, DraftDomain, Contact, Website, FederalAgency
from registrar.utility.constants import BranchChoices

fake = Faker()
logger = logging.getLogger(__name__)


class DomainRequestFixture:
    """
    Load domain requests into the database.

    Make sure this class' `load` method is called from `handle`
    in management/commands/load.py, then use `./manage.py load`
    to run this code.
    """

    all_users = User.objects.all()
    all_federal_agencies = FederalAgency.objects.all()

    class GenerateData:
        """Functions that generate dummy data for domain requests"""

        @classmethod
        def fake_contact(cls):
            return {
                "first_name": fake.first_name(),
                "middle_name": None,
                "last_name": fake.last_name(),
                "title": fake.job(),
                "email": fake.ascii_safe_email(),
                "phone": "201-555-5555",
            }

        @classmethod
        def fake_dot_gov(cls):
            return {
                "name": f"{fake.slug()}.gov"
            }

        @classmethod
        def random_user(cls):
            return random.choice(DomainRequestFixture.all_users)

        @classmethod
        def random_federal_agency(cls):
            return random.choice(DomainRequestFixture.all_federal_agencies)

        @classmethod
        def random_federal_type(cls):
            return random.choice(list(BranchChoices))

        @classmethod
        def random_other_contacts(cls):
            fake_contacts = [Contact(**cls.fake_contact()) for _ in range(random.randint(0, 3))]  # nosec
            return Contact.objects.bulk_create(fake_contacts) 
        
        @classmethod
        def random_current_websites(cls):
            fake_websites = [Website(website=fake.uri()) for _ in range(random.randint(0, 3))]  # nosec
            return Website.objects.bulk_create(fake_websites) 
        
        @classmethod
        def random_alternative_domains(cls):
            domain_name = cls.fake_dot_gov().get("name")
            fake_websites = [Website(website=domain_name) for _ in range(random.randint(0, 3))]
            return Website.objects.bulk_create(fake_websites) 

    # any fields not specified here will be filled in with fake data or defaults
    # NOTE BENE: each fixture must have `organization_name` for uniqueness!
    # Here is a more complete example as a template:
    # {
    #     "status": "started",
    #     "organization_name": "Example - Just started",
    #     "generic_org_type": "federal",
    #     "federal_agency": None,
    #     "federal_type": None,
    #     "address_line1": None,
    #     "address_line2": None,
    #     "city": None,
    #     "state_territory": None,
    #     "zipcode": None,
    #     "urbanization": None,
    #     "purpose": None,
    #     "anything_else": None,
    #     "is_policy_acknowledged": None,
    #     "senior_official": None,
    #     "submitter": None,
    #     "other_contacts": [],
    #     "current_websites": [],
    #     "alternative_domains": [],
    # },
    DA = [
        {
            "status": DomainRequest.DomainRequestStatus.STARTED,
            "organization_name": "Example - Finished but not submitted",
        },
        {
            "status": DomainRequest.DomainRequestStatus.SUBMITTED,
            "organization_name": "Example - Submitted but pending investigation",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Example - In investigation",
        },
        {
            "status": DomainRequest.DomainRequestStatus.IN_REVIEW,
            "organization_name": "Example - reqroved",
        },
        {
            "status": DomainRequest.DomainRequestStatus.WITHDRAWN,
            "organization_name": "Example - Withdrawn",
        },
        {
            "status": DomainRequest.DomainRequestStatus.ACTION_NEEDED,
            "organization_name": "Example - Action needed",
        },
        {
            "status": DomainRequest.DomainRequestStatus.REJECTED,
            "organization_name": "Example - Rejected",
        },
    ]

    # Define fake values for non fk fields
    non_fk_fields = [
        {
            "field_name": "status",
            "default_value": "started",
        },
        { "field_name": "generic_org_type", "default_value": "federal",},
        { "field_name": "last_submitted_date", "default_value": fake.date,},
        { "field_name": "federal_type", "default_value": GenerateData.random_federal_type},
        { "field_name": "address_line1", "default_value": fake.street_address},
        {
            "field_name": "address_line2",
            "default_value": fake.street_address
        },
        {
            "field_name": "city",
            "default_value": fake.city
        },
        {
            "field_name": "state_territory",
            "default_value": fake.state_abbr
        },
        {
            "field_name": "zipcode",
            "default_value": fake.postalcode
        },
        {
            "field_name": "purpose",
            "default_value": fake.paragraph
        },
        {
            "field_name": "has_cisa_representative",
            "default_value": False
        },
        {
            "field_name": "anything_else",
            "default_value": fake.paragraph()
        },
        {
            "field_name": "has_anything_else_text",
            "default_value": True
        },
        {
            "field_name": "is_policy_acknowledged",
            "default_value": True
        },
    ]

    # Define fake values for non fk fields
    fk_fields = [
        {
            # field_name, default
            "field_name": "senior_official",
            "default_value": GenerateData.fake_contact,
            "model": Contact,
        },
        {
            "field_name": "submitter",
            "default_value": GenerateData.fake_contact,
            "model": Contact,
        },
        {
            "field_name": "requested_domain",
            "default_value": GenerateData.fake_dot_gov,
            "model": DraftDomain,
        },
        {
            "field_name": "investigator",
            "default_value": GenerateData.random_user,
            "model": User
        },
        {
            "field_name": "federal_agency",
            "default_value": GenerateData.random_federal_agency,
            "model": FederalAgency,
        },
    ]

    # Define fake values for many-to-many fields
    many_to_many_fields = [
        {
            "field_name": "other_contacts",
            "default_value": GenerateData.random_other_contacts,
        },
        {
            "field_name": "current_websites",
            "default_value": GenerateData.random_current_websites,
        },
        {
            "field_name": "alternative_domains",
            "default_value": GenerateData.random_alternative_domains
        }
    ]

    @classmethod
    def _set_non_foreign_key_fields(cls, da: DomainRequest, req: dict):
        """Helper method used by `load`."""

        for field in cls.non_fk_fields:
            field_name = field.get("field_name")
            default_value = field.get("default_value")

            # Populate the field with the default if it doesn't exist.
            # Otherwise just grab from the request dictionary.
            if not req.get(field_name):
                value = default_value() if callable(default_value) else default_value
            else:
                value = req.get(field_name)
            
            setattr(da, field_name, value)

    @classmethod
    def _set_foreign_key_fields(cls, da: DomainRequest, req: dict):
        """Helper method used by `load`."""
        for field in cls.fk_fields:
            field_name = field.get("field_name")
            default_value = field.get("default_value")
            model = field.get("model")

            if not req.get(field_name):
                value = default_value() if callable(default_value) else default_value
            else:
                value = req.get(field_name)
            
            # If a dictionary is returned, try to retrieve the given model.
            # If not, just assign the value normally.
            if isinstance(value, dict):
                created_obj, _ = model.objects.get_or_create(**value)
                setattr(da, field_name, created_obj)
            else:
                setattr(da, field_name, value)

    @classmethod
    def _set_many_to_many_relations(cls, da: DomainRequest, req: dict):
        """Helper method used by `load`."""

        for field in cls.many_to_many_fields:
            field_name = field.get("field_name")
            default_value = field.get("default_value")

            if not req.get(field_name):
                value = default_value() if callable(default_value) else default_value
            else:
                value = req.get(field_name)

            many_to_many_field = getattr(da, field_name)
            if isinstance(value, list):
                many_to_many_field.add(*value)
            elif value is not None:
                many_to_many_field.add(value)

    @classmethod
    def load(cls):
        """Creates domain requests for each user in the database."""
        logger.info("Going to load %s domain requests" % len(cls.DA))
        try:
            users = list(cls.all_users)  # force evaluation to catch db errors
        except Exception as e:
            logger.warning(e)
            return

        # Lumped under .atomic to ensure we don't make redundant DB calls.
        # This bundles them all together, and then saves it in a single call.
        with transaction.atomic():
            cls._create_domain_requests(users)

    @classmethod
    def _create_domain_requests(cls, users):
        """Creates DomainRequests given a list of users"""
        for user in users:
            logger.debug("Loading domain requests for %s" % user)
            for req in cls.DA:
                try:
                    da, _ = DomainRequest.objects.get_or_create(
                        creator=user,
                        organization_name=req["organization_name"],
                    )
                    cls._set_non_foreign_key_fields(da, req)
                    cls._set_foreign_key_fields(da, req)
                    da.save()
                    cls._set_many_to_many_relations(da, req)
                except Exception as e:
                    logger.warning(e)
