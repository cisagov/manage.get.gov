from django.test import TestCase

from registrar.models import (
    User,
    Domain,
    DomainInvitation,
    TransitionDomain,
    DomainInformation,
    UserDomainRole,
)

from registrar.management.commands.master_domain_migrations import Command as master_migration_command

from registrar.management.commands.utility.terminal_helper import (
    TerminalHelper,
)

class TestLogins(TestCase):

    """Test ......"""

    def setUp(self):
        """ """
        # self.user, _ = User.objects.get_or_create(email=self.email)

        # # clean out the roles each time
        # UserDomainRole.objects.all().delete()
    
    def tearDown(self):
        super().tearDown()
        TransitionDomain.objects.all().delete()
        Domain.objects.all().delete()
        DomainInvitation.objects.all().delete()
        DomainInformation.objects.all().delete()

    def compare_tables(self,
                       expected_total_transition_domains,
                       expected_total_domains,
                       expected_total_domain_informations,
                       expected_total_domain_invitations,
                       expected_missing_domains,
                       expected_duplicate_domains,
                       expected_missing_domain_informations,
                       expected_missing_domain_invitations):
        """Does a diff between the transition_domain and the following tables: 
        domain, domain_information and the domain_invitation. 
        Verifies that the data loaded correctly."""

        missing_domains = []
        duplicate_domains = []
        missing_domain_informations = []
        missing_domain_invites = []
        for transition_domain in TransitionDomain.objects.all():# DEBUG:
            transition_domain_name = transition_domain.domain_name
            transition_domain_email = transition_domain.username

            # Check Domain table
            matching_domains = Domain.objects.filter(name=transition_domain_name)
            # Check Domain Information table
            matching_domain_informations = DomainInformation.objects.filter(domain__name=transition_domain_name)
            # Check Domain Invitation table
            matching_domain_invitations = DomainInvitation.objects.filter(email=transition_domain_email.lower(), 
                                                                          domain__name=transition_domain_name)

            if len(matching_domains) == 0:
                missing_domains.append(transition_domain_name)
            elif len(matching_domains) > 1:
                duplicate_domains.append(transition_domain_name)
            if len(matching_domain_informations) == 0:
                missing_domain_informations.append(transition_domain_name)
            if len(matching_domain_invitations) == 0:
                missing_domain_invites.append(transition_domain_name)

        total_missing_domains = len(missing_domains)
        total_duplicate_domains = len(duplicate_domains)
        total_missing_domain_informations = len(missing_domain_informations)
        total_missing_domain_invitations = len(missing_domain_invites)

        total_transition_domains = len(TransitionDomain.objects.all())
        total_domains = len(Domain.objects.all())
        total_domain_informations = len(DomainInformation.objects.all())
        total_domain_invitations = len(DomainInvitation.objects.all())

        print(f"""
        total_missing_domains = {len(missing_domains)}
        total_duplicate_domains = {len(duplicate_domains)}
        total_missing_domain_informations = {len(missing_domain_informations)}
        total_missing_domain_invitations = {len(missing_domain_invites)}

        total_transition_domains = {len(TransitionDomain.objects.all())}
        total_domains = {len(Domain.objects.all())}
        total_domain_informations = {len(DomainInformation.objects.all())}
        total_domain_invitations = {len(DomainInvitation.objects.all())}
        """)

        self.assertTrue(total_missing_domains == expected_missing_domains)
        self.assertTrue(total_duplicate_domains == expected_duplicate_domains)
        self.assertTrue(total_missing_domain_informations == expected_missing_domain_informations)
        self.assertTrue(total_missing_domain_invitations == expected_missing_domain_invitations)

        self.assertTrue(total_transition_domains == expected_total_transition_domains)
        self.assertTrue(total_domains == expected_total_domains)
        self.assertTrue(total_domain_informations == expected_total_domain_informations)
        self.assertTrue(total_domain_invitations == expected_total_domain_invitations)
     
    def test_master_migration_functions(self):
        """ Run the full master migration script using local test data.
         NOTE: This is more of an integration test and so far does not
         follow best practice of limiting the number of assertions per test.
         But for now, this will double-check that the script
         works as intended. """
        
        migration_directory = "/app/registrar/tests/data/"
        contacts_filename = "test_contacts.txt"
        domain_contacts_filename = "test_domain_contacts.txt"
        domain_statuses_filename = "test_domain_statuses.txt"

        # STEP 1: Run the master migration script using local test data
        master_migration_command.run_load_transition_domain_script(master_migration_command(),
                                                                migration_directory,
                                                                domain_contacts_filename,
                                                                contacts_filename,
                                                                domain_statuses_filename,
                                                                "|",
                                                                False,
                                                                False,
                                                                False,
                                                                0)

        # run_master_script_command = "./manage.py master_domain_migrations" 
        # run_master_script_command += " --runMigrations"
        # run_master_script_command += " --migrationDirectory /app/registrar/tests/data"
        # run_master_script_command += " --migrationFilenames test_contacts.txt,test_domain_contacts.txt,test_domain_statuses.txt"
        # TerminalHelper.execute_command(run_master_script_command)

        # STEP 2: (analyze the tables just like the migration script does, but add assert statements)
        expected_total_transition_domains = 8
        expected_total_domains = 4
        expected_total_domain_informations = 0
        expected_total_domain_invitations = 7

        expected_missing_domains = 0
        expected_duplicate_domains = 0
         # we expect 8 missing domain invites since the migration does not auto-login new users
        expected_missing_domain_informations = 8
        # we expect 1 missing invite from anomaly.gov (an injected error)
        expected_missing_domain_invitations = 1
        self.compare_tables(expected_total_transition_domains,
                            expected_total_domains,
                            expected_total_domain_informations,
                            expected_total_domain_invitations,
                            expected_missing_domains,
                            expected_duplicate_domains,
                            expected_missing_domain_informations,
                            expected_missing_domain_invitations,
                            )

    def test_load_transition_domains():
        """ """

    def test_user_logins(self):
        """A new user's first_login callback retrieves their invitations."""
        # self.user.first_login()
        # self.assertTrue(UserDomainRole.objects.get(user=self.user, domain=self.domain))
