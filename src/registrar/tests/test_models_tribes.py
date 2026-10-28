"""
Tests overall Federal and State Tribe model functionality

* Tribe dropdown helpers on StateTribe and FederalTribe (get_dropdown_options),
which pulls from TribeHelper.get_dropdown_options() in registrar/models/utility/tribe_helper.py
"""

from django.test import TestCase

from registrar.models import DomainRequest, FederalTribe, StateTribe, User
from registrar.models.portfolio import Portfolio

from api.tests.common import less_console_noise_decorator


class TestTribeDropdownOptions(TestCase):

    def setUp(self):
        super().setUp()
        self.user, _ = User.objects.get_or_create(
            username="tribe@meoward.com",
            email="test-tribe@meoward.com",
            first_name="Meoward",
            last_name="Rules",
        )

    def tearDown(self):
        """
        NOTE: Portfolios MUST go first. The Tribe FKs have PROTECT
        (its like a pokemon power!) so a tribe cannot be deleted
        while a portfolio still points to it
        """
        Portfolio.objects.all().delete()
        StateTribe.objects.all().delete()
        FederalTribe.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    def _make_tribes(self, *names):
        """
        Adding tribes to given tables
        """
        for name in names:
            StateTribe.objects.create(tribe_name=name)
            FederalTribe.objects.create(tribe_full_name=name)

    @less_console_noise_decorator
    def test_state_federal_tribe_options_are_alphabetical(self):
        # Check that we alphabetize the tribal names for both state/federal

        self._make_tribes("Zzzzz Tribe", "Aaaaa Tribe", "Mmmmm Tribe")
        expected = ["Aaaaa Tribe", "Mmmmm Tribe", "Zzzzz Tribe"]

        for model in (StateTribe, FederalTribe):
            with self.subTest(model=model.__name__):
                options = model.get_dropdown_options()

                self.assertEqual([option["name"] for option in options], expected)

    @less_console_noise_decorator
    def test_dropdown_option_returns_correct_keys(self):
        """Make sure we return only 3 fields: id, name, has_existing_portfolio"""
        self._make_tribes("Aaaaa Tribe")

        for model in (StateTribe, FederalTribe):
            with self.subTest(model=model.__name__):
                options = model.get_dropdown_options()

                self.assertEqual(set(options[0].keys()), {"id", "name", "has_existing_portfolio"})

    @less_console_noise_decorator
    def test_state_and_federal_lookups_are_independent(self):
        """
        A State Tribe can have a same name as a Federal Tribe, but we still
        have it as two diff records

        We want to check that a Portfolio for a Federal one should ONLY
        mark the Federal one as "existing" and leave the State one alone

        NOTE: No org name is pass on purpose bc a tribal portfolio
        names itself after the tribe it points to when it saves

        """
        self._make_tribes("Twinning Name Tribe")
        federal = FederalTribe.objects.get(tribe_full_name="Twinning Name Tribe")

        Portfolio.objects.create(
            requester=self.user,
            organization_type=DomainRequest.OrganizationChoices.TRIBAL,
            federal_tribe=federal,
        )

        state_options = StateTribe.get_dropdown_options()
        federal_options = FederalTribe.get_dropdown_options()

        self.assertFalse(state_options[0]["has_existing_portfolio"])
        self.assertTrue(federal_options[0]["has_existing_portfolio"])
