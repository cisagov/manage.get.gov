from django.test import TestCase

from registrar.models import (
    User,
    Contact,
)

from django.core.management import call_command
from unittest.mock import patch

from registrar.management.commands.copy_names_from_contacts_to_users import Command

class TestOrganizationMigration(TestCase):
    def setUp(self):
        """Defines the file name of migration_json and the folder its contained in"""
    
        
        # self.user1, _ = User.objects.get_or_create(username="user1")
        # self.user2 = User.objects.create(username="user2", first_name="Joey", last_name="")
        # self.user3 = User.objects.create(username="user3", first_name="a special first name", last_name="a special last name")
        # self.userX = User.objects.create(username="emailX@igorville.gov", first_name="firstX", last_name="lastX")
        
        # self.contact1, _ = Contact.objects.get_or_create(user=self.user1, email="email1@igorville.gov", first_name="first1", last_name="last1")
        # self.contact2 = Contact.objects.create(user=self.user2, email="email2@igorville.gov", first_name="first2", last_name="last2")
        # self.contact3 = Contact.objects.create(user=None, email="email3@igorville.gov", first_name="first3", last_name="last3")
        # self.contact4 = Contact.objects.create(user=None, email="email4@igorville.gov", first_name="first4", last_name="last4")
        
        # self.contact1 = Contact.objects.create(email="email1@igorville.gov", first_name="first1", last_name="last1")
        # self.contact2 = Contact.objects.create(email="email2@igorville.gov", first_name="first2", last_name="last2")
        # self.contact3 = Contact.objects.create(email="email3@igorville.gov", first_name="first3", last_name="last3")
        # self.contact4 = Contact.objects.create(email="email4@igorville.gov", first_name="first4", last_name="last4")
        
        # self.user1 = User.objects.create(contact=self.contact1)
        # self.user2 = User.objects.create(contact=self.contact2, username="user2", first_name="Joey", last_name="")
        # self.user3 = User.objects.create(username="user3", first_name="a special first name", last_name="a special last name")
        # self.userX = User.objects.create(username="emailX@igorville.gov", first_name="firstX", last_name="lastX")
        
        
        self.command = Command()

    def tearDown(self):
        """Deletes all DB objects related to migrations"""
        # Delete users
        User.objects.all().delete()
        Contact.objects.all().delete()
        
    def test_script_updates_linked_users(self):
        
        user1, _ = User.objects.get_or_create(username="user1")
        contact1, _ = Contact.objects.get_or_create(user=user1, email="email1@igorville.gov", first_name="first1", last_name="last1")
        
        
        # self.user1.first_name = ""
        # self.user1.last_name = ""
        # self.user2.last_name = ""
        # self.user1.save()
        # self.user2.save()
        
        # users we SKIPPED
        skipped_contacts = []
        # users we found that are linked to contacts
        eligible_users = []
        # users we PROCESSED
        processed_users = []
        (
            skipped_contacts,
            eligible_users,
            processed_users,
        ) = self.command.process_contacts(
            True,
            skipped_contacts,
            eligible_users,
            processed_users,
        )
        
        # self.user1.refresh_from_db()
        # self.user2.refresh_from_db()
        # self.user3.refresh_from_db()
        # self.userX.refresh_from_db()
        
        self.assertEqual(user1.first_name, "first1")
        self.assertEqual(user1.last_name, "last1")
        # self.assertEqual(self.user2.first_name, "first2")
        # self.assertEqual(self.user2.last_name, "last2")
        # self.assertEqual(self.user3.first_name, "a special first name")
        # self.assertEqual(self.user3.last_name, "a special last name")
        # self.assertEqual(self.userX.first_name, "firstX")
        # self.assertEqual(self.userX.last_name, "lastX")
        
        
        
        