from waffle.decorators import flag_is_active
from django.test import TestCase, Client, RequestFactory
from registrar.models import (
    WaffleFlag,
    User,
    Contact,
    UserGroup,
)
from registrar.tests.common import create_superuser, create_staffuser, create_user


class TestFeatureFlags(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.factory = RequestFactory()
        self.superuser = create_superuser()

        # For testing purposes, lets set this to false.
        self.superuser.is_staff = False
        self.superuser.save()

        self.staffuser = create_staffuser()
        self.user = create_user()

    def tearDown(self):
        super().tearDown()
        WaffleFlag.objects.all().delete()
        User.objects.all().delete()
        Contact.objects.all().delete()

    def assert_flag_active(self, request_user, flag_name, location="/"):
        """
        Checks if the given `request_user` has `flag_name` active
        using waffles `flag_is_active` function.
        """
        request = self.factory.get(location)
        request.user = request_user
        self.assertTrue(flag_is_active(request, flag_name))

    def assert_flag_not_active(self, request_user, flag_name, location="/"):
        """
        Checks if the given `request_user` has `flag_name` not active
        using waffles `flag_is_active` function.
        """
        request = self.factory.get(location)
        request.user = request_user
        self.assertFalse(flag_is_active(request, flag_name))

    def test_flag_active_for_superuser(self):
        """
        Tests flag_is_active for a flag with `superuser = True`
        """
        flag, _ = WaffleFlag.objects.get_or_create(
            name="test_superuser_flag",
            superusers=True,
            staff=False,
        )
        # Test if superusers can access this flag
        self.assert_flag_active(request_user=self.superuser, flag_name=flag.name)

        # Ensure that regular staff cannot access this flag
        self.assert_flag_not_active(request_user=self.staffuser, flag_name=flag.name)

        # Ensure that a normal user also can't access this flag
        self.assert_flag_not_active(request_user=self.user, flag_name=flag.name)

    def test_flag_active_for_is_staff(self):
        """
        Tests flag_is_active for a flag with `is_staff = True`
        """
        # We should actually expect superusers
        # to not see this feature - otherwise the two distinct booleans aren't useful.
        # In practice, we would usually use groups for toggling features.
        flag, _ = WaffleFlag.objects.get_or_create(
            name="test_superuser_flag",
            superusers=False,
            staff=True,
        )

        # Ensure that regular staff can access this flag
        self.assert_flag_active(request_user=self.staffuser, flag_name=flag.name)

        # Ensure that superusers cannot access this flag
        self.assert_flag_not_active(request_user=self.superuser, flag_name=flag.name)

        # Ensure that a normal user also can't access this flag
        self.assert_flag_not_active(request_user=self.user, flag_name=flag.name)

    def test_flag_active_for_everyone(self):
        """
        Tests flag_is_active for a flag with `everyone = True`
        """
        flag, _ = WaffleFlag.objects.get_or_create(
            name="test_superuser_flag",
            everyone=True,
        )

        # Ensure that regular staff can access this flag
        self.assert_flag_active(request_user=self.staffuser, flag_name=flag.name)

        # Ensure that superusers can access this flag
        self.assert_flag_active(request_user=self.superuser, flag_name=flag.name)

        # Ensure that normal users can access this flag
        self.assert_flag_active(request_user=self.user, flag_name=flag.name)

    def test_flag_active_for_everyone_is_false(self):
        """
        Tests flag_is_active for a flag with `everyone = False`
        """
        flag, _ = WaffleFlag.objects.get_or_create(
            name="test_superuser_flag",
            everyone=False,
        )

        # Ensure that regular staff cannot access this flag
        self.assert_flag_not_active(request_user=self.staffuser, flag_name=flag.name)

        # Ensure that superusers cannot access this flag
        self.assert_flag_not_active(request_user=self.superuser, flag_name=flag.name)

        # Ensure that normal users cannot access this flag
        self.assert_flag_not_active(request_user=self.user, flag_name=flag.name)

    def test_admin_group(self):
        """
        Tests flag_is_active for the admin user group
        """
        flag, _ = WaffleFlag.objects.get_or_create(
            name="test_superuser_flag",
        )

        # Add the full access group to this flag
        group, _ = UserGroup.objects.get_or_create(name="full_access_group")
        flag.groups.set([group])

        # Ensure that regular staff cannot access this flag
        self.assert_flag_not_active(request_user=self.staffuser, flag_name=flag.name)

        # Ensure that superusers can access this flag
        self.assert_flag_active(request_user=self.superuser, flag_name=flag.name)

        # Ensure that normal users cannot access this flag
        self.assert_flag_not_active(request_user=self.user, flag_name=flag.name)

    def test_staff_group(self):
        """
        Tests flag_is_active for the staff user group
        """
        flag, _ = WaffleFlag.objects.get_or_create(
            name="test_superuser_flag",
        )

        # Add the analyst group to this flag
        analyst_group, _ = UserGroup.objects.get_or_create(name="cisa_analysts_group")
        flag.groups.set([analyst_group])

        # Ensure that regular staff can access this flag
        self.assert_flag_active(request_user=self.staffuser, flag_name=flag.name)

        # Ensure that superusers can access this flag.
        # This permission encompasses cisa_analysts_group.
        self.assert_flag_active(request_user=self.superuser, flag_name=flag.name)

        # Ensure that normal users cannot access this flag
        self.assert_flag_not_active(request_user=self.user, flag_name=flag.name)
