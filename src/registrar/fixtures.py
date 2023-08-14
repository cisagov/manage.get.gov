import logging
import random
from faker import Faker

from registrar.models import (
    User,
    DomainApplication,
    DraftDomain,
    Contact,
    Website,
)

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

fake = Faker()
logger = logging.getLogger(__name__)


class UserFixture:
    """
    Load users into the database.

    Make sure this class' `load` method is called from `handle`
    in management/commands/load.py, then use `./manage.py load`
    to run this code.
    """

    ADMINS = [
        {
            "username": "5f283494-31bd-49b5-b024-a7e7cae00848",
            "first_name": "Rachid",
            "last_name": "Mrad",
        },
        {
            "username": "eb2214cd-fc0c-48c0-9dbd-bc4cd6820c74",
            "first_name": "Alysia",
            "last_name": "Broddrick",
        },
        {
            "username": "8f8e7293-17f7-4716-889b-1990241cbd39",
            "first_name": "Katherine",
            "last_name": "Osos",
        },
        {
            "username": "70488e0a-e937-4894-a28c-16f5949effd4",
            "first_name": "Gaby",
            "last_name": "DiSarli",
        },
        {
            "username": "83c2b6dd-20a2-4cac-bb40-e22a72d2955c",
            "first_name": "Cameron",
            "last_name": "Dixon",
        },
        {
            "username": "0353607a-cbba-47d2-98d7-e83dcd5b90ea",
            "first_name": "Ryan",
            "last_name": "Brooks",
        },
        {
            "username": "30001ee7-0467-4df2-8db2-786e79606060",
            "first_name": "Zander",
            "last_name": "Adkinson",
        },
        {
            "username": "bb21f687-c773-4df3-9243-111cfd4c0be4",
            "first_name": "Paul",
            "last_name": "Kuykendall",
        },
        {
            "username": "2a88a97b-be96-4aad-b99e-0b605b492c78",
            "first_name": "Rebecca",
            "last_name": "Hsieh",
        },
    ]

    STAFF = [
        {
            "username": "319c490d-453b-43d9-bc4d-7d6cd8ff6844",
            "first_name": "Rachid-Analyst",
            "last_name": "Mrad-Analyst",
            "email": "rachid.mrad@gmail.com",
        },
        {
            "username": "b6a15987-5c88-4e26-8de2-ca71a0bdb2cd",
            "first_name": "Alysia-Analyst",
            "last_name": "Alysia-Analyst",
        },
        {
            "username": "2cc0cde8-8313-4a50-99d8-5882e71443e8",
            "first_name": "Zander-Analyst",
            "last_name": "Adkinson-Analyst",
        },
        {
            "username": "57ab5847-7789-49fe-a2f9-21d38076d699",
            "first_name": "Paul-Analyst",
            "last_name": "Kuykendall-Analyst",
        },
        {
            "username": "e474e7a9-71ca-449d-833c-8a6e094dd117",
            "first_name": "Rebecca-Analyst",
            "last_name": "Hsieh-Analyst",
        },
    ]

    STAFF_PERMISSIONS = [
        {
            "app_label": "auditlog",
            "model": "logentry",
            "permissions": ["view_logentry"],
        },
        {"app_label": "registrar", "model": "contact", "permissions": ["view_contact"]},
        {
            "app_label": "registrar",
            "model": "domainapplication",
            "permissions": ["change_domainapplication"],
        },
        {"app_label": "registrar", "model": "domain", "permissions": ["view_domain"]},
        {"app_label": "registrar", "model": "user", "permissions": ["view_user"]},
    ]

    @classmethod
    def load(cls):
        logger.info("Going to load %s superusers" % str(len(cls.ADMINS)))
        for admin in cls.ADMINS:
            try:
                user, _ = User.objects.get_or_create(
                    username=admin["username"],
                )
                user.is_superuser = True
                user.first_name = admin["first_name"]
                user.last_name = admin["last_name"]
                if "email" in admin.keys(): 
                    user.email = admin["email"]
                user.is_staff = True
                user.is_active = True
                user.save()
                logger.debug("User object created for %s" % admin["first_name"])
            except Exception as e:
                logger.warning(e)
        logger.info("All superusers loaded.")

        logger.info("Going to load %s CISA analysts (staff)" % str(len(cls.STAFF)))
        for staff in cls.STAFF:
            try:
                user, _ = User.objects.get_or_create(
                    username=staff["username"],
                )
                user.is_superuser = False
                user.first_name = staff["first_name"]
                user.last_name = staff["last_name"]
                if "email" in admin.keys(): 
                    user.email = admin["email"]
                user.is_staff = True
                user.is_active = True

                for permission in cls.STAFF_PERMISSIONS:
                    app_label = permission["app_label"]
                    model_name = permission["model"]
                    permissions = permission["permissions"]

                    # Retrieve the content type for the app and model
                    content_type = ContentType.objects.get(
                        app_label=app_label, model=model_name
                    )

                    # Retrieve the permissions based on their codenames
                    permissions = Permission.objects.filter(
                        content_type=content_type, codename__in=permissions
                    )

                    # Assign the permissions to the user
                    user.user_permissions.add(*permissions)

                    # Convert the permissions QuerySet to a list of codenames
                    permission_list = list(
                        permissions.values_list("codename", flat=True)
                    )

                    logger.debug(
                        app_label
                        + " | "
                        + model_name
                        + " | "
                        + ", ".join(permission_list)
                        + " added for user "
                        + staff["first_name"]
                    )

                user.save()
                logger.debug("User object created for %s" % staff["first_name"])
            except Exception as e:
                logger.warning(e)
        logger.info("All CISA analysts (staff) loaded.")


class DomainApplicationFixture:
    """
    Load domain applications into the database.

    Make sure this class' `load` method is called from `handle`
    in management/commands/load.py, then use `./manage.py load`
    to run this code.
    """

    # any fields not specified here will be filled in with fake data or defaults
    # NOTE BENE: each fixture must have `organization_name` for uniqueness!
    # Here is a more complete example as a template:
    # {
    #     "status": "started",
    #     "organization_name": "Example - Just started",
    #     "organization_type": "federal",
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
    #     "authorizing_official": None,
    #     "submitter": None,
    #     "other_contacts": [],
    #     "current_websites": [],
    #     "alternative_domains": [],
    # },
    DA = [
        {
            "status": "started",
            "organization_name": "Example - Finished but not Submitted",
        },
        {
            "status": "submitted",
            "organization_name": "Example - Submitted but pending Investigation",
        },
        {
            "status": "in review",
            "organization_name": "Example - In Investigation",
        },
        {
            "status": "in review",
            "organization_name": "Example - Approved",
        },
        {
            "status": "withdrawn",
            "organization_name": "Example - Withdrawn",
        },
    ]

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
        return f"{fake.slug()}.gov"

    @classmethod
    def _set_non_foreign_key_fields(cls, da: DomainApplication, app: dict):
        """Helper method used by `load`."""
        da.status = app["status"] if "status" in app else "started"
        da.organization_type = (
            app["organization_type"] if "organization_type" in app else "federal"
        )
        da.federal_agency = (
            app["federal_agency"]
            if "federal_agency" in app
            # Random choice of agency for selects, used as placeholders for testing.
            else random.choice(DomainApplication.AGENCIES)  # nosec
        )

        da.federal_type = (
            app["federal_type"]
            if "federal_type" in app
            else random.choice(["executive", "judicial", "legislative"])  # nosec
        )
        da.address_line1 = (
            app["address_line1"] if "address_line1" in app else fake.street_address()
        )
        da.address_line2 = app["address_line2"] if "address_line2" in app else None
        da.city = app["city"] if "city" in app else fake.city()
        da.state_territory = (
            app["state_territory"] if "state_territory" in app else fake.state_abbr()
        )
        da.zipcode = app["zipcode"] if "zipcode" in app else fake.postalcode()
        da.urbanization = app["urbanization"] if "urbanization" in app else None
        da.purpose = app["purpose"] if "purpose" in app else fake.paragraph()
        da.anything_else = app["anything_else"] if "anything_else" in app else None
        da.is_policy_acknowledged = (
            app["is_policy_acknowledged"] if "is_policy_acknowledged" in app else True
        )

    @classmethod
    def _set_foreign_key_fields(cls, da: DomainApplication, app: dict, user: User):
        """Helper method used by `load`."""
        if not da.investigator:
            da.investigator = (
                User.objects.get(username=user.username)
                if "investigator" in app
                else None
            )

        if not da.authorizing_official:
            if (
                "authorizing_official" in app
                and app["authorizing_official"] is not None
            ):
                da.authorizing_official, _ = Contact.objects.get_or_create(
                    **app["authorizing_official"]
                )
            else:
                da.authorizing_official = Contact.objects.create(**cls.fake_contact())

        if not da.submitter:
            if "submitter" in app and app["submitter"] is not None:
                da.submitter, _ = Contact.objects.get_or_create(**app["submitter"])
            else:
                da.submitter = Contact.objects.create(**cls.fake_contact())

        if not da.requested_domain:
            if "requested_domain" in app and app["requested_domain"] is not None:
                da.requested_domain, _ = DraftDomain.objects.get_or_create(
                    name=app["requested_domain"]
                )
            else:
                da.requested_domain = DraftDomain.objects.create(
                    name=cls.fake_dot_gov()
                )

    @classmethod
    def _set_many_to_many_relations(cls, da: DomainApplication, app: dict):
        """Helper method used by `load`."""
        if "other_contacts" in app:
            for contact in app["other_contacts"]:
                da.other_contacts.add(Contact.objects.get_or_create(**contact)[0])
        elif not da.other_contacts.exists():
            other_contacts = [
                Contact.objects.create(**cls.fake_contact())
                for _ in range(random.randint(0, 3))  # nosec
            ]
            da.other_contacts.add(*other_contacts)

        if "current_websites" in app:
            for website in app["current_websites"]:
                da.current_websites.add(
                    Website.objects.get_or_create(website=website)[0]
                )
        elif not da.current_websites.exists():
            current_websites = [
                Website.objects.create(website=fake.uri())
                for _ in range(random.randint(0, 3))  # nosec
            ]
            da.current_websites.add(*current_websites)

        if "alternative_domains" in app:
            for domain in app["alternative_domains"]:
                da.alternative_domains.add(
                    Website.objects.get_or_create(website=domain)[0]
                )
        elif not da.alternative_domains.exists():
            alternative_domains = [
                Website.objects.create(website=cls.fake_dot_gov())
                for _ in range(random.randint(0, 3))  # nosec
            ]
            da.alternative_domains.add(*alternative_domains)

    @classmethod
    def load(cls):
        """Creates domain applications for each user in the database."""
        logger.info("Going to load %s domain applications" % len(cls.DA))
        try:
            users = list(User.objects.all())  # force evaluation to catch db errors
        except Exception as e:
            logger.warning(e)
            return

        for user in users:
            logger.debug("Loading domain applications for %s" % user)
            for app in cls.DA:
                try:
                    da, _ = DomainApplication.objects.get_or_create(
                        creator=user,
                        organization_name=app["organization_name"],
                    )
                    cls._set_non_foreign_key_fields(da, app)
                    cls._set_foreign_key_fields(da, app, user)
                    da.save()
                    cls._set_many_to_many_relations(da, app)
                except Exception as e:
                    logger.warning(e)


class DomainFixture(DomainApplicationFixture):

    """Create one domain and permissions on it for each user."""

    @classmethod
    def load(cls):
        try:
            users = list(User.objects.all())  # force evaluation to catch db errors
        except Exception as e:
            logger.warning(e)
            return

        for user in users:
            # approve one of each users in review status domains
            application = DomainApplication.objects.filter(
                creator=user, status=DomainApplication.IN_REVIEW
            ).last()
            logger.debug(f"Approving {application} for {user}")
            application.approve()
            application.save()
