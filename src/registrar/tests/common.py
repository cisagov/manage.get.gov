import os
import logging

from contextlib import contextmanager
import random
from string import ascii_uppercase
from unittest.mock import Mock
from typing import List, Dict

from django.conf import settings
from django.contrib.auth import get_user_model, login

from registrar.models import (
    Contact,
    DraftDomain,
    Website,
    DomainApplication,
    DomainInvitation,
    User,
    DomainInformation,
    Domain,
)

logger = logging.getLogger(__name__)


def get_handlers():
    """Obtain pointers to all StreamHandlers."""
    handlers = {}

    rootlogger = logging.getLogger()
    for h in rootlogger.handlers:
        if isinstance(h, logging.StreamHandler):
            handlers[h.name] = h

    for logger in logging.Logger.manager.loggerDict.values():
        if not isinstance(logger, logging.PlaceHolder):
            for h in logger.handlers:
                if isinstance(h, logging.StreamHandler):
                    handlers[h.name] = h

    return handlers


@contextmanager
def less_console_noise():
    """
    Context manager to use in tests to silence console logging.

    This is helpful on tests which trigger console messages
    (such as errors) which are normal and expected.

    It can easily be removed to debug a failing test.
    """
    restore = {}
    handlers = get_handlers()
    devnull = open(os.devnull, "w")

    # redirect all the streams
    for handler in handlers.values():
        prior = handler.setStream(devnull)
        restore[handler.name] = prior
    try:
        # run the test
        yield
    finally:
        # restore the streams
        for handler in handlers.values():
            handler.setStream(restore[handler.name])
        # close the file we opened
        devnull.close()


class MockUserLogin:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_anonymous:
            user = None
            UserModel = get_user_model()
            username = "Testy"
            args = {
                UserModel.USERNAME_FIELD: username,
            }
            user, _ = UserModel.objects.get_or_create(**args)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            backend = settings.AUTHENTICATION_BACKENDS[-1]
            login(request, user, backend=backend)

        response = self.get_response(request)
        return response


class MockSESClient(Mock):
    EMAILS_SENT: List[Dict] = []

    def send_email(self, *args, **kwargs):
        self.EMAILS_SENT.append({"args": args, "kwargs": kwargs})


class AuditedAdminMockData:
    """Creates simple data mocks for AuditedAdminTest.
    Can likely be more generalized, but the primary purpose of this class is to simplify
    mock data creation, especially for lists of items,
    by making the assumption that for most use cases we don't have to worry about
    data 'accuracy' ('testy 2' is not an accurate first_name for example), we just care about
    implementing some kind of patterning, especially with lists of items.

    Two variables are used across multiple functions:

    *item_name* - Used in patterning. Will be appended en masse to multiple string fields,
    like first_name. For example, item_name 'egg' will return a user object of:

    first_name: 'egg first_name:user',
    last_name: 'egg last_name:user',
    username: 'egg username:user'

    where 'user' is the short_hand

    *short_hand* - Used in patterning. Certain fields will have ':{shorthand}' appended to it,
    as a way to optionally include metadata in the string itself. Can be further expanded on.
    Came from a bug where different querysets used in testing would effectively be 'anonymized', wherein
    it would only display a list of types, but not include the variable name.
    """  # noqa

    # Constants for different domain object types
    INFORMATION = "information"
    APPLICATION = "application"
    INVITATION = "invitation"

    def dummy_user(self, item_name, short_hand):
        """Creates a dummy user object,
        but with a shorthand and support for multiple"""
        user = User.objects.get_or_create(
            first_name="{} first_name:{}".format(item_name, short_hand),
            last_name="{} last_name:{}".format(item_name, short_hand),
            username="{} username:{}".format(item_name, short_hand),
        )[0]
        return user

    def dummy_contact(self, item_name, short_hand):
        """Creates a dummy contact object"""
        contact = Contact.objects.get_or_create(
            first_name="{} first_name:{}".format(item_name, short_hand),
            last_name="{} last_name:{}".format(item_name, short_hand),
            title="{} title:{}".format(item_name, short_hand),
            email="{}testy@town.com".format(item_name),
            phone="(555) 555 5555",
        )[0]
        return contact

    def dummy_draft_domain(self, item_name):
        """Creates a dummy draft domain object"""
        return DraftDomain.objects.get_or_create(name="city{}.gov".format(item_name))[0]

    def dummy_domain(self, item_name):
        """Creates a dummy domain object"""
        return Domain.objects.get_or_create(name="city{}.gov".format(item_name))[0]

    def dummy_alt(self, item_name):
        """Creates a dummy website object for alternates"""
        return Website.objects.get_or_create(website="cityalt{}.gov".format(item_name))[
            0
        ]

    def dummy_current(self, item_name):
        """Creates a dummy website object for current"""
        return Website.objects.get_or_create(website="city{}.com".format(item_name))[0]

    def get_common_domain_arg_dictionary(
        self,
        item_name,
        org_type="federal",
        federal_type="executive",
        purpose="Purpose of the site",
    ):
        """Generates a generic argument list for most domains"""
        common_args = dict(
            organization_type=org_type,
            federal_type=federal_type,
            purpose=purpose,
            organization_name="{} organization".format(item_name),
            address_line1="{} address_line1".format(item_name),
            address_line2="{} address_line2".format(item_name),
            is_policy_acknowledged=True,
            state_territory="NY",
            zipcode="10002",
            type_of_work="e-Government",
            anything_else="There is more",
            authorizing_official=self.dummy_contact(item_name, "authorizing_official"),
            submitter=self.dummy_contact(item_name, "submitter"),
            creator=self.dummy_user(item_name, "creator"),
        )
        return common_args

    def dummy_kwarg_boilerplate(
        self,
        domain_type,
        item_name,
        status,
        org_type="federal",
        federal_type="executive",
        purpose="Purpose of the site",
    ):
        """
        A helper function that returns premade kwargs for easily creating different domain object types.
        There is a decent amount of boilerplate associated with
        creating new domain objects (such as domain_application, or domain_information),
        so for test case purposes, we can make some assumptions and utilize that to simplify
        the object creation process.

        *domain_type* uses constants. Used to identify what kind of 'Domain' object you'd like to make.

        In more detail: domain_type specifies what kind of domain object you'd like to create, i.e.
        domain_application (APPLICATION), or domain_information (INFORMATION).
        """  # noqa
        common_args = self.get_common_domain_arg_dictionary(
            item_name, org_type, federal_type, purpose
        )
        full_arg_list = None
        match domain_type:
            case self.APPLICATION:
                full_arg_list = dict(
                    **common_args,
                    requested_domain=self.dummy_draft_domain(item_name),
                    investigator=self.dummy_user(item_name, "investigator"),
                    status=status,
                )
            case self.INFORMATION:
                domain_app = self.create_full_dummy_domain_application(item_name)
                full_arg_list = dict(
                    **common_args,
                    domain=self.dummy_domain(item_name),
                    domain_application=domain_app,
                )
            case self.INVITATION:
                full_arg_list = dict(
                    email="test_mail@mail.com",
                    domain=self.dummy_domain(item_name),
                    status=DomainInvitation.INVITED,
                )
        return full_arg_list

    def create_full_dummy_domain_application(
        self, object_name, status=DomainApplication.STARTED
    ):
        """Creates a dummy domain application object"""
        domain_application_kwargs = self.dummy_kwarg_boilerplate(
            self.APPLICATION, object_name, status
        )
        application = DomainApplication.objects.get_or_create(
            **domain_application_kwargs
        )[0]
        return application

    def create_full_dummy_domain_information(
        self, object_name, status=DomainApplication.STARTED
    ):
        """Creates a dummy domain information object"""
        domain_application_kwargs = self.dummy_kwarg_boilerplate(
            self.INFORMATION, object_name, status
        )
        application = DomainInformation.objects.get_or_create(
            **domain_application_kwargs
        )[0]
        return application

    def create_full_dummy_domain_invitation(
        self, object_name, status=DomainApplication.STARTED
    ):
        """Creates a dummy domain invitation object"""
        domain_application_kwargs = self.dummy_kwarg_boilerplate(
            self.INVITATION, object_name, status
        )
        application = DomainInvitation.objects.get_or_create(
            **domain_application_kwargs
        )[0]

        return application

    def create_full_dummy_domain_object(
        self,
        domain_type,
        object_name,
        has_other_contacts=True,
        has_current_website=True,
        has_alternative_gov_domain=True,
        status=DomainApplication.STARTED,
    ):
        """A helper to create a dummy domain application object"""
        application = None
        match domain_type:
            case self.APPLICATION:
                application = self.create_full_dummy_domain_application(
                    object_name, status
                )
            case self.INVITATION:
                application = self.create_full_dummy_domain_invitation(
                    object_name, status
                )
            case self.INFORMATION:
                application = self.create_full_dummy_domain_information(
                    object_name, status
                )
            case _:
                raise ValueError("Invalid domain_type, must conform to given constants")

        if has_other_contacts and domain_type != self.INVITATION:
            other = self.dummy_contact(object_name, "other")
            application.other_contacts.add(other)
        if has_current_website and domain_type == self.APPLICATION:
            current = self.dummy_current(object_name)
            application.current_websites.add(current)
        if has_alternative_gov_domain and domain_type == self.APPLICATION:
            alt = self.dummy_alt(object_name)
            application.alternative_domains.add(alt)

        return application


def mock_user():
    """A simple user."""
    user_kwargs = dict(
        id=4,
        first_name="Rachid",
        last_name="Mrad",
    )
    mock_user, _ = User.objects.get_or_create(**user_kwargs)
    return mock_user


def create_superuser():
    User = get_user_model()
    p = "adminpass"
    return User.objects.create_superuser(
        username="superuser",
        email="admin@example.com",
        password=p,
    )


def create_user():
    User = get_user_model()
    p = "userpass"
    return User.objects.create_user(
        username="staffuser",
        email="user@example.com",
        password=p,
    )


def completed_application(
    has_other_contacts=True,
    has_current_website=True,
    has_alternative_gov_domain=True,
    has_type_of_work=True,
    has_anything_else=True,
    status=DomainApplication.STARTED,
    user=False,
):
    """A completed domain application."""
    if not user:
        user = get_user_model().objects.create(username="username")
    ao, _ = Contact.objects.get_or_create(
        first_name="Testy",
        last_name="Tester",
        title="Chief Tester",
        email="testy@town.com",
        phone="(555) 555 5555",
    )
    domain, _ = DraftDomain.objects.get_or_create(name="city.gov")
    alt, _ = Website.objects.get_or_create(website="city1.gov")
    current, _ = Website.objects.get_or_create(website="city.com")
    you, _ = Contact.objects.get_or_create(
        first_name="Testy2",
        last_name="Tester2",
        title="Admin Tester",
        email="mayor@igorville.gov",
        phone="(555) 555 5556",
    )
    other, _ = Contact.objects.get_or_create(
        first_name="Testy",
        last_name="Tester",
        title="Another Tester",
        email="testy2@town.com",
        phone="(555) 555 5557",
    )
    domain_application_kwargs = dict(
        organization_type="federal",
        federal_type="executive",
        purpose="Purpose of the site",
        is_policy_acknowledged=True,
        organization_name="Testorg",
        address_line1="address 1",
        address_line2="address 2",
        state_territory="NY",
        zipcode="10002",
        authorizing_official=ao,
        requested_domain=domain,
        submitter=you,
        creator=user,
        status=status,
    )
    if has_type_of_work:
        domain_application_kwargs["type_of_work"] = "e-Government"
    if has_anything_else:
        domain_application_kwargs["anything_else"] = "There is more"

    application, _ = DomainApplication.objects.get_or_create(
        **domain_application_kwargs
    )

    if has_other_contacts:
        application.other_contacts.add(other)
    if has_current_website:
        application.current_websites.add(current)
    if has_alternative_gov_domain:
        application.alternative_domains.add(alt)

    return application


def multiple_unalphabetical_domain_objects(
    domain_type=AuditedAdminMockData.APPLICATION,
):
    """Returns a list of generic domain objects for testing purposes"""
    applications = []
    list_of_letters = list(ascii_uppercase)
    random.shuffle(list_of_letters)

    mock = AuditedAdminMockData()
    for object_name in list_of_letters:
        application = mock.create_full_dummy_domain_object(domain_type, object_name)
        applications.append(application)
    return applications
