import logging
from faker import Faker

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
            "username": "1f8f8556-99d3-4b87-abbc-2fc204d89787",
            "first_name": "Aditi",
            "last_name": "Green",
            "title": "Engineer",
            "email": "aditi.green@ecstech.com",
        },
        {
            "username": "3e8613e2-e1f8-404d-a692-e5dc077828b2",
            "first_name": "Abe",
            "last_name": "Alam",
            "email": "abraham.alam@ecstech.com",
        },
        {
            "username": "8f8e7293-17f7-4716-889b-1990241cbd39",
            "first_name": "Katherine",
            "last_name": "Osos",
            "email": "kosos@truss.works",
            "title": "Grove keeper",
        },
        {
            "username": "47b9668b-6764-4818-a8cd-3505494093a6",
            "first_name": "Natalie",
            "last_name": "Wong",
            "email": "Wai-wan.wong@ecstech.com",
            "title": "Designer",
        },
        {
            "username": "70488e0a-e937-4894-a28c-16f5949effd4",
            "first_name": "Gaby",
            "last_name": "DiSarli",
            "email": "gaby@truss.works",
            "title": "De Stijl",
        },
        {
            "username": "83c2b6dd-20a2-4cac-bb40-e22a72d2955c",
            "first_name": "Cameron",
            "last_name": "Dixon",
            "email": "cameron.dixon@cisa.dhs.gov",
            "title": "Product owner",
        },
        {
            "username": "2a88a97b-be96-4aad-b99e-0b605b492c78",
            "first_name": "Rebecca",
            "last_name": "Hsieh",
            "email": "rebecca.hsieh@truss.works",
            "title": "Catlady",
        },
        {
            "username": "f14433d8-f0e9-41bf-9c72-b99b110e665d",
            "first_name": "Nicolle",
            "last_name": "LeClair",
            "email": "nicolle.leclair@ecstech.com",
            "title": "Nightowl",
        },
        {
            "username": "24840450-bf47-4d89-8aa9-c612fe68f9da",
            "first_name": "Erin",
            "last_name": "Song",
            "title": "Catlady 2",
        },
        {
            "username": "e0ea8b94-6e53-4430-814a-849a7ca45f21",
            "first_name": "Kristina",
            "last_name": "Yin",
            "title": "Hufflepuff prefect",
        },
        {
            "username": "63688d43-82c6-480c-8e49-8a1bfdd33b9f",
            "first_name": "Elizabeth",
            "last_name": "Liao",
            "email": "elizabeth.liao@cisa.dhs.gov",
            "title": "Software Engineer",
        },
        {
            "username": "c9c64cd5-bc76-45ef-85cd-4f6eefa9e998",
            "first_name": "Samiyah",
            "last_name": "Key",
            "email": "skey@truss.works",
            "title": "Designer",
        },
        {
            "username": "f20b7a53-f40d-48f8-8c12-f42f35eede92",
            "first_name": "Kimberly",
            "last_name": "Aralar",
            "email": "kimberly.aralar@gsa.gov",
            "title": "Designer",
        },
        {
            "username": "4aa78480-6272-42f9-ac29-a034ebdd9231",
            "first_name": "Kaitlin",
            "last_name": "Abbitt",
            "email": "kaitlin.abbitt@cisa.dhs.gov",
            "title": "Product Manager",
        },
        {
            "username": "89f2db87-87a2-4778-a5ea-5b27b585b131",
            "first_name": "Jaxon",
            "last_name": "Silva",
            "email": "jaxon.silva@cisa.dhs.gov",
            "title": "Designer",
        },
        {
            "username": "d579b8eb-16cf-4830-9341-70ecf227a644",
            "first_name": "Kim",
            "last_name": "Allen",
            "email": "kim+dotgov@truss.works",
            "title": "Farmer",
        },
        {
            "username": "0f784268-a481-445e-9e37-ea2be43ce318",
            "first_name": "Daisy",
            "last_name": "Gutierrez",
            "email": "dgutierrez@guydo.com",
            "title": "Lima",
        },
        {
            "username": "fb3671a7-4513-49d7-9723-4c41ed23f608",
            "first_name": "Tara",
            "last_name": "Kolden",
            "email": "tara.kolden@contractors.truss.works",
        },
        {
            "username": "742ea84a-9450-44a4-9d3f-dca56a0a8597",
            "first_name": "Charlie",
            "last_name": "Wells",
            "email": "charles.wells@ecstech.com",
            "title": "ADMIN",
        },
        {
            "username": "eb2214cd-fc0c-48c0-9dbd-bc4cd6820c74",
            "first_name": "Alysia",
            "last_name": "Broddrick",
            "email": "abroddrick@truss.works",
            "title": "I drink coffee and know things",
        },
        {
            "username": "41407964-a570-4c5c-9179-ddbf45326eeb",
            "first_name": "Samir",
            "last_name": "Mishra",
            "email": "samir.mishra@ecstech.com",
            "title": "Code Mage",
        },
    ]

    STAFF = [
        {
            "username": "32275d92-eff2-4df4-9b90-4963056c850",
            "first_name": "Aditi",
            "last_name": "Green",
            "title": "Aditi-Analyst",
            "email": "aditi.green01@ecstech.com",
        },
        {
            "username": "acfdf02c-2438-4e66-b219-73104b2e3153",
            "first_name": "Abe-Analyst",
            "last_name": "Alam-Analyst",
            "email": "abraham.alam+1@ecstech.com",
        },
        {
            "username": "91a9b97c-bd0a-458d-9823-babfde7ebf44",
            "first_name": "Katherine-Analyst",
            "last_name": "Osos-Analyst",
            "email": "kosos+1@truss.works",
        },
        {
            "username": "e474e7a9-71ca-449d-833c-8a6e094dd117",
            "first_name": "Rebecca-Analyst",
            "last_name": "Hsieh-Analyst",
        },
        {
            "username": "0eb6f326-a3d4-410f-a521-aa4c1fad4e47",
            "first_name": "Gaby-Analyst",
            "last_name": "DiSarli-Analyst",
            "email": "gaby+1@truss.works",
        },
        {
            "username": "02f96e16-fff9-4eb1-bb7e-e61a17c63f3f",
            "first_name": "Nicolle-Analyst",
            "last_name": "LeClair-Analyst",
            "email": "nicolle.leclair.gov@ecstech.com",
        },
        {
            "username": "106632de-8681-43db-85dd-83857c55660f",
            "first_name": "Natalie-Analyst",
            "last_name": "Wong-Analyst",
            "email": "wai-wan.wong@associates.cisa.dhs.gov",
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
            "username": "0c27b05d-0aa3-45fa-91bd-83ee307708df",
            "first_name": "Elizabeth-Analyst",
            "last_name": "Liao-Analyst",
            "email": "elizabeth.liao@gwe.cisa.dhs.gov",
        },
        {
            "username": "ee1e68da-41a5-47f7-949b-d8a4e9e2b9d2",
            "first_name": "Samiyah-Analyst",
            "last_name": "Key-Analyst",
            "email": "skey+1@truss.works",
        },
        {
            "username": "cf2b32fe-280d-4bc0-96c2-99eec09ba4da",
            "first_name": "Kimberly-Analyst",
            "last_name": "Aralar-Analyst",
            "email": "kimberly.aralar+1@gsa.gov",
        },
        {
            "username": "80db923e-ac64-4128-9b6f-e54b2174a09b",
            "first_name": "Kaitlin-Analyst",
            "last_name": "Abbitt-Analyst",
            "email": "kaitlin.abbitt@gwe.cisa.dhs.gov",
        },
        {
            "username": "79b55374-f1a3-4e06-8614-41ba70050cd5",
            "first_name": "Kim-Analyst",
            "last_name": "Allen-Analyst",
            "email": "kim+a@truss.works",
        },
        {
            "username": "acb8e287-9b45-4993-8f76-12648b417b75",
            "first_name": "Daisy-Analyst",
            "last_name": "Gutierrez-Analyst",
            "email": "daisy.gutierrez-ctr@ecstech.com",
        },
        {
            "username": "fa2ea396-0ec1-46e3-a296-a37670996f17",
            "first_name": "Tara-Analyst",
            "last_name": "Kolden-Analyst",
            "email": "tara.kolden+1@contractors.truss.works",
        },
        {
            "username": "25fe3e87-4a20-4709-a0cf-72725e7b1f26",
            "first_name": "Charlie",
            "last_name": "Wells",
            "email": "charles.wells.analyst@ecstech.com",
            "title": "ANALYST",
        },
        {
            "username": "9db645e5-6db1-457a-9a93-abecfb98c5a5",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON",
            "email": "feedback+9@get.gov",
            "title": "ANALYST",
        },
        {
            "username": "1ddd1444-937e-4a0a-9202-e68f2851edde",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON",
            "email": "feedback+10@get.gov",
            "title": "ANALYST",
        },
        {
            "username": "b6a15987-5c88-4e26-8de2-ca71a0bdb2cd",
            "first_name": "Alysia-Analyst",
            "last_name": "Alysia-Analyst",
            "email": "abroddrick+1@truss.works",
        },
        {
            "username": "55b55db0-bb8d-4223-b1df-9482174a3679",
            "first_name": "Samir-Analyst",
            "last_name": "Mishra-Analyst",
            "email": "samir.mishra.gov@ecstech.com",
        },
    ]

    STANDARD_USERS = [
        {
            "username": "e2201529-6901-44ee-9698-0d08bfe7fb01",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON_1",
            "email": "feedback+1@get.gov",
        },
        {
            "username": "74cca338-21d6-4135-910e-4cf9ce179ea6",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON_2",
            "email": "feedback+2@get.gov",
        },
        {
            "username": "22acf459-79d5-43b3-a73e-a81b30cc693c",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON_3",
            "email": "feedback+3@get.gov",
        },
        {
            "username": "f88283cc-0a1f-4c23-b1a8-0cd31411d852",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON_4",
            "email": "feedback+4@get.gov",
        },
        {
            "username": "c2e02542-8cc4-4d95-b153-fb97706a72f1",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON_5",
            "email": "feedback+5@get.gov",
        },
        {
            "username": "fbb06d6c-c58f-49c0-8845-21f0c77b6497",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON_6",
            "email": "feedback+6@get.gov",
        },
        {
            "username": "9e820a1c-c570-465a-9fc3-979c65f3ab17",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON_7",
            "email": "feedback+7@get.gov",
        },
        {
            "username": "b8194c1a-4dec-4b3e-9cc1-829f3dbf78a7",
            "first_name": "FAKEY",
            "last_name": "MCFAKERSON_8",
            "email": "feedback+8@get.gov",
        },
    ]
    # Additional emails to add to the AllowedEmail whitelist.
    ADDITIONAL_ALLOWED_EMAILS: list[str] = []

    @classmethod
    def load_users(cls, users, group_name, are_superusers=False):
        """Loads the users into the database and assigns them to the specified group."""
        logger.info(f"Going to load {len(users)} users for group {group_name}")

        # Step 1: Fetch the group
        group = UserGroup.objects.get(name=group_name)

        # Step 2: Identify new and existing users
        existing_usernames, existing_user_ids = cls._get_existing_users(users)
        new_users = cls._prepare_new_users(users, existing_usernames, existing_user_ids, are_superusers)

        # Step 3: Create new users
        cls._create_new_users(new_users)

        # Step 4: Update existing users
        # Get all users to be updated (both new and existing)
        created_or_existing_users = User.objects.filter(username__in=[user.get("username") for user in users])
        users_to_update = cls._get_users_to_update(created_or_existing_users)
        cls._update_existing_users(users_to_update)

        # Step 5: Assign users to the group
        cls._assign_users_to_group(group, created_or_existing_users)

        logger.info(f"Users loaded for group {group_name}.")

    def load_allowed_emails(cls, users, additional_emails, delete_existing_allowed_emails):
        """Populates a whitelist of allowed emails (as defined in this list)"""

        if delete_existing_allowed_emails:
            logger.info("Deleting all allowed emails")
            AllowedEmail.objects.all().delete()

        logger.info(f"Going to load allowed emails for {len(users)} users")
        if additional_emails:
            logger.info(f"Going to load {len(additional_emails)} additional allowed emails")

        existing_emails = set(AllowedEmail.objects.values_list("email", flat=True))
        new_allowed_emails = []

        for user_data in users:
            user_email = user_data.get("email")
            if user_email and user_email not in existing_emails:
                new_allowed_emails.append(AllowedEmail(email=user_email))

        # Load additional emails, only if they don't exist already
        for email in additional_emails:
            if email not in existing_emails:
                new_allowed_emails.append(AllowedEmail(email=email))

        if new_allowed_emails:
            try:
                AllowedEmail.objects.bulk_create(new_allowed_emails)
                logger.info(f"Loaded {len(new_allowed_emails)} allowed emails")
            except Exception as e:
                logger.error(f"Unexpected error during allowed emails bulk creation: {e}")
        else:
            logger.info("No allowed emails to load")

    @staticmethod
    def _get_existing_users(users):
        # if users match existing users in db by email address, update the users with the username
        # from the db. this will prevent duplicate users (with same email) from being added to db.
        # it is ok to keep the old username in the db because the username will be updated by oidc process during login

        # Extract email addresses from users
        emails = [user.get("email") for user in users]

        # Fetch existing users by email
        existing_users_by_email = User.objects.filter(email__in=emails).values_list("email", "username", "id")

        # Create a dictionary to map emails to existing usernames
        email_to_existing_user = {user[0]: user[1] for user in existing_users_by_email}

        # Update the users list with the usernames from existing users by email
        for user in users:
            email = user.get("email")
            if email and email in email_to_existing_user:
                user["username"] = email_to_existing_user[email]  # Update username with the existing one

        # Get the user identifiers (username, id) for the existing users to query the database
        user_identifiers = [(user.get("username"), user.get("id")) for user in users]

        # Fetch existing users by username or id
        existing_users = User.objects.filter(
            username__in=[user[0] for user in user_identifiers] + [user[1] for user in user_identifiers]
        ).values_list("username", "id")

        # Create sets for usernames and ids that exist
        existing_usernames = set(user[0] for user in existing_users)
        existing_user_ids = set(user[1] for user in existing_users)

        return existing_usernames, existing_user_ids

    @staticmethod
    def _prepare_new_users(users, existing_usernames, existing_user_ids, are_superusers, is_staff=True):
        new_users = []
        for i, user_data in enumerate(users):
            id = user_data.get("id")
            first_name = user_data.get("first_name", "Bob")
            last_name = user_data.get("last_name", "Builder")
            # If username is not provided, create one (must be unique)
            username = user_data.get("username", first_name + last_name + str(id))

            default_email = f"placeholder.{first_name.lower()}.{last_name.lower()}+{i}@igorville.gov"
            email = user_data.get("email", default_email)
            if username not in existing_usernames and id not in existing_user_ids:
                user = User(
                    id=id,
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                    email=email,
                    title=user_data.get("title", "team member"),
                    phone=user_data.get("phone", "2022222222"),
                    is_active=user_data.get("is_active", True),
                    is_staff=is_staff,
                    is_superuser=are_superusers,
                )
                new_users.append(user)
        return new_users

    @staticmethod
    def _create_new_users(new_users):
        if new_users:
            try:
                User.objects.bulk_create(new_users)
                logger.info(f"Created {len(new_users)} new users.")
            except Exception as e:
                logger.error(f"Unexpected error during user bulk creation: {e}")
        else:
            logger.info("No new users to create.")

    @staticmethod
    def _get_users_to_update(users, is_staff=True):
        users_to_update = []
        for user in users:
            updated = False
            if not user.title and is_staff:
                user.title = "Team member"
                updated = True
            if not user.title and not is_staff:
                user.title = "User testing account"
                updated = True
            if not user.phone:
                user.phone = "2022222222"
                updated = True
            if not user.is_staff and is_staff:
                user.is_staff = True
                updated = True
            if updated:
                users_to_update.append(user)
        return users_to_update

    @staticmethod
    def _update_existing_users(users_to_update):
        if users_to_update:
            User.objects.bulk_update(users_to_update, ["is_staff", "title", "phone"])
            logger.info(f"Updated {len(users_to_update)} existing users.")

    @staticmethod
    def _assign_users_to_group(group, users):
        users_not_in_group = users.exclude(groups__id=group.id)
        if users_not_in_group.exists():
            group.user_set.add(*users_not_in_group)

    @classmethod
    def load_standard_users(cls):
        """Loads standard (non-staff) test users without assigning an admin group."""
        logger.info(f"Going to load {len(cls.STANDARD_USERS)} standard users")
        try:
            existing_usernames, existing_user_ids = cls._get_existing_users(cls.STANDARD_USERS)
            new_users = cls._prepare_new_users(
                cls.STANDARD_USERS,
                existing_usernames,
                existing_user_ids,
                are_superusers=False,
                is_staff=False,
            )
            cls._create_new_users(new_users)

            created_or_existing = User.objects.filter(username__in=[u["username"] for u in cls.STANDARD_USERS])
            users_to_update = cls._get_users_to_update(created_or_existing, is_staff=False)
            cls._update_existing_users(users_to_update)
            logger.info("Standard users loaded.")
        except Exception as e:
            logger.warning(e)

    @classmethod
    def load(cls, delete_existing_allowed_emails=False):
        cls.load_users(cls.ADMINS, "full_access_group", are_superusers=True)
        cls.load_users(cls.STAFF, "cisa_analysts_group")
        cls.load_standard_users()

        # Combine ADMINS, STAFF, and STANDARD_USERS lists
        all_users = cls.ADMINS + cls.STAFF + cls.STANDARD_USERS
        cls.load_allowed_emails(
            cls,
            all_users,
            additional_emails=cls.ADDITIONAL_ALLOWED_EMAILS,
            delete_existing_allowed_emails=delete_existing_allowed_emails,
        )
