from django.test import TestCase

from registrar.models import (
    User,
    Contact,
)

from registrar.management.commands.copy_names_from_contacts_to_users import Command


class TestDataUpdates(TestCase):
    def setUp(self):
        """We cannot setup the user details because contacts will override the first and last names in its save method
        so we will initiate the users, setup the contacts and link them, and leave the rest of the setup for the test(s).
        """

        self.user1 = User.objects.create(username="user1")
        self.user2 = User.objects.create(username="user2")
        self.user3 = User.objects.create(username="user3")
        self.userX = User.objects.create(username="user4")
        # The last user created triggers the creation of a contact and attaches itself to it. @Neil wth is going on?
        # This bs_user defuses that situation so we can test the code.
        self.bs_user = User.objects.create()

        self.contact1 = Contact.objects.create(
            user=self.user1, email="email1@igorville.gov", first_name="first1", last_name="last1"
        )
        self.contact2 = Contact.objects.create(
            user=self.user2, email="email2@igorville.gov", first_name="first2", last_name="last2"
        )
        self.contact3 = Contact.objects.create(
            user=self.user3, email="email3@igorville.gov", first_name="first3", last_name="last3"
        )
        self.contact4 = Contact.objects.create(email="email4@igorville.gov", first_name="first4", last_name="last4")

        self.command = Command()

    def tearDown(self):
        """Clean up"""
        # Delete users and contacts
        User.objects.all().delete()
        Contact.objects.all().delete()

    def test_script_updates_linked_users(self):
        """Test the script that copies contacts' first and last names into associated users that
        are eligible (first or last are blank or undefined)"""

        # Set up the users' first and last names here so
        # they that they don't get overwritten by Contact's save()
        # User with no first or last names
        self.user1.first_name = ""
        self.user1.last_name = ""
        self.user1.save()

        # User with a first name but no last name
        self.user2.last_name = ""
        self.user2.save()

        # User with a first and last name
        self.user3.first_name = "An existing first name"
        self.user3.last_name = "An existing last name"
        self.user3.save()

        # Unlinked user
        # To make this test useful, we will set the last_name to ""
        self.userX.first_name = "Unlinked user's first name"
        self.userX.last_name = ""
        self.userX.save()

        # Call the parent method the same way we do it in the script
        skipped_contacts = []
        eligible_users = []
        processed_users = []
        (
            skipped_contacts,
            eligible_users,
            processed_users,
        ) = self.command.process_contacts(
            # Set debugging to False
            False,
            skipped_contacts,
            eligible_users,
            processed_users,
        )

        # Trigger DB refresh
        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.user3.refresh_from_db()
        self.userX.refresh_from_db()

        # Asserts
        self.assertEqual(self.user1.first_name, "first1")
        self.assertEqual(self.user1.last_name, "last1")
        self.assertEqual(self.user2.first_name, "first2")
        self.assertEqual(self.user2.last_name, "last2")
        self.assertEqual(self.user3.first_name, "An existing first name")
        self.assertEqual(self.user3.last_name, "An existing last name")
        self.assertEqual(self.userX.first_name, "Unlinked user's first name")
        self.assertEqual(self.userX.last_name, "")
