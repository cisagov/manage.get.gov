from django.test import TestCase

from registrar.models import (
    UserGroup,
)
import logging

logger = logging.getLogger(__name__)


class TestGroups(TestCase):
    def test_groups_created(self):
        """The test enviroment contains data that was created in migration,
        so we are able to test groups and permissions.

            - Test cisa_analysts_group and full_access_group created
            - Test permissions on full_access_group
        """

        # Get the UserGroup objects
        cisa_analysts_group = UserGroup.objects.get(name="cisa_analysts_group")
        full_access_group = UserGroup.objects.get(name="full_access_group")

        # Assert that the cisa_analysts_group exists in the database
        self.assertQuerysetEqual(UserGroup.objects.filter(name="cisa_analysts_group"), [cisa_analysts_group])

        # Assert that the full_access_group exists in the database
        self.assertQuerysetEqual(UserGroup.objects.filter(name="full_access_group"), [full_access_group])

        # Test permissions for cisa_analysts_group
        # Verifies permission data migrations ran as expected.
        # Define the expected permission codenames
        expected_permissions = [
            "view_logentry",
            "change_contact",
            "view_domain",
            "add_domaininvitation",
            "view_domaininvitation",
            "change_domainrequest",
            "add_federalagency",
            "change_federalagency",
            "delete_federalagency",
            "analyst_access_permission",
            "change_user",
            "delete_userdomainrole",
            "view_userdomainrole",
            "add_verifiedbystaff",
            "change_verifiedbystaff",
            "delete_verifiedbystaff",
        ]

        # Get the codenames of actual permissions associated with the group
        actual_permissions = [p.codename for p in cisa_analysts_group.permissions.all()]

        # Assert that the actual permissions match the expected permissions
        self.assertListEqual(actual_permissions, expected_permissions)
