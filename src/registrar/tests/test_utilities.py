from django.test import TestCase
from registrar.models import User
from waffle.testutils import override_flag
from waffle.models import get_waffle_flag_model
from registrar.utility.waffle import flag_is_active_for_user, flag_is_active_anywhere


class FlagIsActiveForUserTest(TestCase):

    def setUp(self):
        # Set up a test user
        self.user = User.objects.create_user(username="testuser")

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


class TestFlagIsActiveAnywhere(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        self.flag_name = "test_flag"
    
    @override_flag("test_flag", active=True)
    def test_flag_active_for_everyone(self):
        """Test when flag is active for everyone"""
        is_active = flag_is_active_anywhere("test_flag")
        self.assertTrue(is_active)
    
    @override_flag("test_flag", active=False)
    def test_flag_inactive_for_everyone(self):
        """Test when flag is inactive for everyone"""
        is_active = flag_is_active_anywhere("test_flag")
        self.assertFalse(is_active)
    
    def test_flag_active_for_some_users(self):
        """Test when flag is active for specific users"""
        flag, _ = get_waffle_flag_model().objects.get_or_create(name="test_flag")
        flag.everyone = None
        flag.save()
        flag.users.add(self.user)
        
        is_active = flag_is_active_anywhere("test_flag")
        self.assertTrue(is_active)
    
    def test_flag_inactive_with_no_users(self):
        """Test when flag has no users and everyone is None"""
        flag, _ = get_waffle_flag_model().objects.get_or_create(name="test_flag")
        flag.everyone = None
        flag.save()

        is_active = flag_is_active_anywhere("test_flag")
        self.assertFalse(is_active)
