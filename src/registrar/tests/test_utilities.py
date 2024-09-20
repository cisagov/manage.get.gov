from django.test import TestCase
from django.contrib.auth.models import User
from waffle.testutils import override_flag
from registrar.utility.waffle import flag_is_active_for_user

class FlagIsActiveForUserTest(TestCase):

    def setUp(self):
        # Set up a test user
        self.user = User.objects.create_user(username="testuser", password="testpassword")

    @override_flag("test_flag", active=True)
    def test_flag_active_for_user(self):
        # Test that the flag is active for the user
        is_active = flag_is_active_for_user(self.user, "test_flag")
        self.assertTrue(is_active)

    @override_flag("test_flag", active=False)
    def test_flag_inactive_for_user(self):
        # Test that the flag is inactive for the user
        is_active = flag_is_active_for_user(self.user, "test_flag")
        self.assertFalse(is_active)
