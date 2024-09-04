import logging
from faker import Faker
from django.db import transaction

from registrar.models import (
    User,
    UserGroup,
)
from registrar.models.allowed_email import AllowedEmail


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
            "username": "43a7fa8d-0550-4494-a6fe-81500324d590",
            "first_name": "Jyoti",
            "last_name": "Bock",
            "email": "jyotibock@truss.works",
        },
        {
            "username": "aad084c3-66cc-4632-80eb-41cdf5c5bcbf",
            "first_name": "Aditi",
            "last_name": "Green",
            "email": "aditidevelops+01@gmail.com",
        },
        {
            "username": "be17c826-e200-4999-9389-2ded48c43691",
            "first_name": "Matthew",
            "last_name": "Spence",
        },
        {
            "username": "5f283494-31bd-49b5-b024-a7e7cae00848",
            "first_name": "Rachid",
            "last_name": "Mrad",
            "email": "rachid.mrad@associates.cisa.dhs.gov",
        },
        {
            "username": "eb2214cd-fc0c-48c0-9dbd-bc4cd6820c74",
            "first_name": "Alysia",
            "last_name": "Broddrick",
            "email": "abroddrick@truss.works",
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
            "email": "gaby@truss.works",
        },
        {
            "username": "83c2b6dd-20a2-4cac-bb40-e22a72d2955c",
            "first_name": "Cameron",
            "last_name": "Dixon",
            "email": "cameron.dixon@cisa.dhs.gov",
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
            "username": "2bf518c2-485a-4c42-ab1a-f5a8b0a08484",
            "first_name": "Paul",
            "last_name": "Kuykendall",
        },
        {
            "username": "2a88a97b-be96-4aad-b99e-0b605b492c78",
            "first_name": "Rebecca",
            "last_name": "Hsieh",
            "email": "rebecca.hsieh@truss.works",
        },
        {
            "username": "fa69c8e8-da83-4798-a4f2-263c9ce93f52",
            "first_name": "David",
            "last_name": "Kennedy",
            "email": "david.kennedy@ecstech.com",
        },
        {
            "username": "f14433d8-f0e9-41bf-9c72-b99b110e665d",
            "first_name": "Nicolle",
            "last_name": "LeClair",
            "email": "nicolle.leclair@ecstech.com",
        },
        {
            "username": "24840450-bf47-4d89-8aa9-c612fe68f9da",
            "first_name": "Erin",
            "last_name": "Song",
        },
        {
            "username": "e0ea8b94-6e53-4430-814a-849a7ca45f21",
            "first_name": "Kristina",
            "last_name": "Yin",
        },
        {
            "username": "ac49d7c1-368a-4e6b-8f1d-60250e20a16f",
            "first_name": "Vicky",
            "last_name": "Chin",
            "email": "szu.chin@associates.cisa.dhs.gov",
        },
        {
            "username": "66bb1a5a-a091-4d7f-a6cf-4d772b4711c7",
            "first_name": "Christina",
            "last_name": "Burnett",
            "email": "christina.burnett@cisa.dhs.gov",
        },
        {
            "username": "012f844d-8a0f-4225-9d82-cbf87bff1d3e",
            "first_name": "Riley",
            "last_name": "Orr",
            "email": "riley+320@truss.works",
        },
        {
            "username": "76612d84-66b0-4ae9-9870-81e98b9858b6",
            "first_name": "Anna",
            "last_name": "Gingle",
            "email": "annagingle@truss.works",
        },
    ]

    STAFF = [
        {
            "username": "a5906815-dd80-4c64-aebe-2da6a4c9d7a4",
            "first_name": "Jyoti-Analyst",
            "last_name": "Bock-Analyst",
            "email": "jyotibock+1@truss.works",
        },
        {
            "username": "ffec5987-aa84-411b-a05a-a7ee5cbcde54",
            "first_name": "Aditi-Analyst",
            "last_name": "Green-Analyst",
            "email": "aditidevelops+02@gmail.com",
        },
        {
            "username": "d6bf296b-fac5-47ff-9c12-f88ccc5c1b99",
            "first_name": "Matthew-Analyst",
            "last_name": "Spence-Analyst",
        },
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
            "username": "91a9b97c-bd0a-458d-9823-babfde7ebf44",
            "first_name": "Katherine-Analyst",
            "last_name": "Osos-Analyst",
            "email": "kosos@truss.works",
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
        {
            "username": "5dc6c9a6-61d9-42b4-ba54-4beff28bac3c",
            "first_name": "David-Analyst",
            "last_name": "Kennedy-Analyst",
            "email": "david.kennedy@associates.cisa.dhs.gov",
        },
        {
            "username": "0eb6f326-a3d4-410f-a521-aa4c1fad4e47",
            "first_name": "Gaby-Analyst",
            "last_name": "DiSarli-Analyst",
            "email": "gaby+1@truss.works",
        },
        {
            "username": "cfe7c2fc-e24a-480e-8b78-28645a1459b3",
            "first_name": "Nicolle-Analyst",
            "last_name": "LeClair-Analyst",
            "email": "nicolle.leclair@gmail.com",
        },
        {
            "username": "378d0bc4-d5a7-461b-bd84-3ae6f6864af9",
            "first_name": "Erin-Analyst",
            "last_name": "Song-Analyst",
            "email": "erin.song+1@gsa.gov",
        },
        {
            "username": "9a98e4c9-9409-479d-964e-4aec7799107f",
            "first_name": "Kristina-Analyst",
            "last_name": "Yin-Analyst",
            "email": "kristina.yin+1@gsa.gov",
        },
        {
            "username": "8f42302e-b83a-4c9e-8764-fc19e2cea576",
            "first_name": "Vickster-Analyst",
            "last_name": "Chin-Analyst",
            "email": "szu.chin@ecstech.com",
        },
        {
            "username": "22f88aa5-3b54-4b1f-9c57-201fb02ddba7",
            "first_name": "Christina-Analyst",
            "last_name": "Burnett-Analyst",
            "email": "christina.burnett@gwe.cisa.dhs.gov",
        },
        {
            "username": "d9839768-0c17-4fa2-9c8e-36291eef5c11",
            "first_name": "Alex-Analyst",
            "last_name": "Mcelya-Analyst",
            "email": "ALEXANDER.MCELYA@cisa.dhs.gov",
        },
        {
            "username": "082a066f-e0a4-45f6-8672-4343a1208a36",
            "first_name": "Riley-Analyst",
            "last_name": "Orr-Analyst",
            "email": "riley+321@truss.works",
        },
        {
            "username": "e1e350b1-cfc1-4753-a6cb-3ae6d912f99c",
            "first_name": "Anna-Analyst",
            "last_name": "Gingle-Analyst",
            "email": "annagingle+analyst@truss.works",
        },
    ]

    # Additional emails to add to the AllowedEmail whitelist.
    ADDITIONAL_ALLOWED_EMAILS: list[str] = ["davekenn4242@gmail.com", "rachid_mrad@hotmail.com"]

    def load_users(cls, users, group_name, are_superusers=False):
        logger.info(f"Going to load {len(users)} users in group {group_name}")
        for user_data in users:
            try:
                user, _ = User.objects.get_or_create(username=user_data["username"])
                user.is_superuser = are_superusers
                user.first_name = user_data["first_name"]
                user.last_name = user_data["last_name"]
                if "email" in user_data:
                    user.email = user_data["email"]
                user.is_staff = True
                user.is_active = True
                # This verification type will get reverted to "regular" (or whichever is applicables)
                # once the user logs in for the first time (as they then got verified through different means).
                # In the meantime, we can still describe how the user got here in the first place.
                user.verification_type = User.VerificationTypeChoices.FIXTURE_USER
                group = UserGroup.objects.get(name=group_name)
                user.groups.add(group)
                user.save()
                logger.debug(f"User object created for {user_data['first_name']}")
            except Exception as e:
                logger.warning(e)
        logger.info(f"All users in group {group_name} loaded.")

    def load_allowed_emails(cls, users, additional_emails):
        """Populates a whitelist of allowed emails (as defined in this list)"""
        logger.info(f"Going to load allowed emails for {len(users)} users")
        if additional_emails:
            logger.info(f"Going to load {len(additional_emails)} additional allowed emails")

        # Load user emails
        allowed_emails = []
        for user_data in users:
            user_email = user_data.get("email")
            if user_email and user_email not in allowed_emails:
                allowed_emails.append(AllowedEmail(email=user_email))
            else:
                first_name = user_data.get("first_name")
                last_name = user_data.get("last_name")
                logger.warning(f"Could not add email to whitelist for {first_name} {last_name}.")

        # Load additional emails
        allowed_emails.extend([AllowedEmail(email=email) for email in additional_emails])

        if allowed_emails:
            AllowedEmail.objects.bulk_create(allowed_emails)
            logger.info(f"Loaded {len(allowed_emails)} allowed emails")
        else:
            logger.info("No allowed emails to load")

    @classmethod
    def load(cls):
        # Lumped under .atomic to ensure we don't make redundant DB calls.
        # This bundles them all together, and then saves it in a single call.
        # This is slightly different then bulk_create or bulk_update, in that
        # you still get the same behaviour of .save(), but those incremental
        # steps now do not need to close/reopen a db connection,
        # instead they share one.
        with transaction.atomic():
            cls.load_users(cls, cls.ADMINS, "full_access_group", are_superusers=True)
            cls.load_users(cls, cls.STAFF, "cisa_analysts_group")

            # Combine ADMINS and STAFF lists
            all_users = cls.ADMINS + cls.STAFF
            cls.load_allowed_emails(cls, all_users, additional_emails=cls.ADDITIONAL_ALLOWED_EMAILS)
