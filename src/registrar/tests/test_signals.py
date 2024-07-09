from django.test import TestCase
from django.contrib.auth import get_user_model
from registrar.models import Contact, User


class TestUserPostSave(TestCase):
    def setUp(self):
        Contact.objects.all().delete()
        self.username = "test_signal_user"
        self.first_name = "First"
        self.last_name = "Last"
        self.email = "signal@example.com"
        self.phone = "202-555-0133"

        self.preferred_first_name = "One"
        self.preferred_last_name = "Two"
        self.preferred_email = "front_desk@example.com"
        self.preferred_phone = "202-555-0134"
    
    def tearDown(self):
        Contact.objects.all().delete()
        User.objects.all().delete()

    def test_user_created_without_matching_contact(self):
        """Expect 1 Contact containing data copied from User."""
        self.assertEqual(len(Contact.objects.all()), 0)
        user = get_user_model().objects.create(
            username=self.username,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            phone=self.phone,
        )
        actual = Contact.objects.get(user=user)
        self.assertEqual(actual.first_name, self.first_name)
        self.assertEqual(actual.last_name, self.last_name)
        self.assertEqual(actual.email, self.email)
        self.assertEqual(actual.phone, self.phone)

    def test_user_created_with_matching_contact(self):
        """Expect 1 Contact associated, but with no data copied from User."""
        self.assertEqual(len(Contact.objects.all()), 0)
        Contact.objects.create(
            first_name=self.preferred_first_name,
            last_name=self.preferred_last_name,
            email=self.email,  # must be the same, to find the match!
            phone=self.preferred_phone,
        )
        user = get_user_model().objects.create(
            username=self.username,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
        )
        actual = Contact.objects.get(user=user)
        self.assertEqual(actual.first_name, self.preferred_first_name)
        self.assertEqual(actual.last_name, self.preferred_last_name)
        self.assertEqual(actual.email, self.email)
        self.assertEqual(actual.phone, self.preferred_phone)

    def test_user_updated_without_matching_contact(self):
        """Expect 1 Contact containing data copied from User."""
        # create the user
        self.assertEqual(len(Contact.objects.all()), 0)
        user = get_user_model().objects.create(username=self.username, first_name="", last_name="", email="", phone="")
        # delete the contact
        Contact.objects.all().delete()
        self.assertEqual(len(Contact.objects.all()), 0)
        # modify the user
        user.username = self.username
        user.first_name = self.first_name
        user.last_name = self.last_name
        user.email = self.email
        user.phone = self.phone
        user.save()
        # test
        actual = Contact.objects.get(user=user)
        self.assertEqual(actual.first_name, self.first_name)
        self.assertEqual(actual.last_name, self.last_name)
        self.assertEqual(actual.email, self.email)
        self.assertEqual(actual.phone, self.phone)

    def test_user_updated_with_matching_contact(self):
        """Expect 1 Contact associated, but with no data copied from User."""
        # create the user
        self.assertEqual(len(Contact.objects.all()), 0)
        user = get_user_model().objects.create(
            username=self.username,
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            phone=self.phone,
        )
        # modify the user
        user.first_name = self.preferred_first_name
        user.last_name = self.preferred_last_name
        user.email = self.preferred_email
        user.phone = self.preferred_phone
        user.save()
        # test
        actual = Contact.objects.get(user=user)
        self.assertEqual(actual.first_name, self.first_name)
        self.assertEqual(actual.last_name, self.last_name)
        self.assertEqual(actual.email, self.email)
        self.assertEqual(actual.phone, self.phone)
