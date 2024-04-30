from unittest import skip
from waffle.decorators import flag_is_active
from django.test import TestCase, Client, RequestFactory
from registrar.models import (
    WaffleFlag,
    User,
    Contact
)
from registrar.tests.common import create_superuser, create_staffuser, create_user

class TestFeatureFlags(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST="localhost:8080")
        self.factory = RequestFactory()
        self.superuser = create_superuser()
        self.staffuser = create_staffuser()
        self.user = create_user()

    def tearDown(self):
        super().tearDown()
        WaffleFlag.objects.all().delete()
        User.objects.all().delete()
        Contact.objects.all().delete()

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
        request = self.factory.get("/")
        request.user = self.superuser
        self.assertTrue(flag_is_active(request, flag.name))

        # Ensure that regular staff cannot access this flag
        request_staff = self.factory.get("/")
        request_staff.user = self.staffuser
        self.assertFalse(flag_is_active(request_staff, flag.name))

        # Ensure that a normal user also can't access this flag
        request_normal = self.factory.get("/")
        request_normal.user = self.user
        self.assertFalse(flag_is_active(request_normal, flag.name))
    
    @skip("not implemented yet")
    def test_flag_active_for_is_staff(self):
        """
        Tests flag_is_active for a flag with `is_staff = True`
        """
        # Test if staff can access this flag
        # Ensure that superusers cannot
        raise
    
    @skip("not implemented yet")
    def test_flag_active_for_everyone(self):
        """
        Tests flag_is_active for a flag with `everyone = True`
        """
        # Test if superuser, analyst, and a normal user can access
        raise
    
    @skip("not implemented yet")
    def test_flag_active_for_everyone_is_false(self):
        """
        Tests flag_is_active for a flag with `everyone = False`
        """
        # Test if no user type can access
        raise

    @skip("not implemented yet")
    def test_admin_group(self):
        """
        Tests flag_is_active for the admin user group
        """
        # Test if no user type can access
        raise

    @skip("not implemented yet")
    def test_staff_group(self):
        """
        Tests flag_is_active for the staff user group
        """
        # Test if no user type can access
        raise