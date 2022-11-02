from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import AbstractUser
from django.db import models

from django_fsm import FSMField, transition

from ..api.views.available import string_could_be_domain


class User(AbstractUser):
    """
    A custom user model that performs identically to the default user model
    but can be customized later.
    """

    def __str__(self):
        try:
            return self.userprofile.display_name
        except ObjectDoesNotExist:
            return self.username


class TimeStampedModel(models.Model):
    """
    An abstract base model that provides self-updating
    `created_at` and `updated_at` fields.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class AddressModel(models.Model):
    """
    An abstract base model that provides common fields
    for postal addresses.
    """

    # contact's street (null ok)
    street1 = models.TextField(blank=True)
    # contact's street (null ok)
    street2 = models.TextField(blank=True)
    # contact's street (null ok)
    street3 = models.TextField(blank=True)
    # contact's city
    city = models.TextField(blank=True)
    # contact's state or province (null ok)
    sp = models.TextField(blank=True)
    # contact's postal code (null ok)
    pc = models.TextField(blank=True)
    # contact's country code
    cc = models.TextField(blank=True)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class ContactInfo(models.Model):
    """
    An abstract base model that provides common fields
    for contact information.
    """

    voice = models.TextField(blank=True)
    fax = models.TextField(blank=True)
    email = models.TextField(blank=True)

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored


class UserProfile(TimeStampedModel, ContactInfo, AddressModel):
    user = models.OneToOneField(User, null=True, on_delete=models.CASCADE)
    display_name = models.TextField()

    def __str__(self):
        if self.display_name:
            return self.display_name
        else:
            try:
                return self.user.username
            except ObjectDoesNotExist:
                return "No username"


class Website(models.Model):

    """Keep domain names in their own table so that applications can refer to
    many of them."""

    # domain names have strictly limited lengths, 255 characters is more than
    # enough.
    website = models.CharField(max_length=255, null=False, help_text="")


class Contact(models.Model):

    """Contact information follows a similar pattern for each contact."""

    first_name = models.TextField(null=True, help_text="First name")
    middle_name = models.TextField(null=True, help_text="Middle name")
    last_name = models.TextField(null=True, help_text="Last name")
    title = models.TextField(null=True, help_text="Title")
    email = models.TextField(null=True, help_text="Email")
    phone = models.TextField(null=True, help_text="Phone")


class DomainApplication(TimeStampedModel):

    STARTED = "started"
    SUBMITTED = "submitted"
    INVESTIGATING = "investigating"
    APPROVED = "approved"
    STATUS_CHOICES = [
        (STARTED, STARTED),
        (SUBMITTED, SUBMITTED),
        (INVESTIGATING, INVESTIGATING),
        (APPROVED, APPROVED),
    ]
    status = FSMField(
        choices=STATUS_CHOICES,  # possible states as an array of constants
        default=STARTED,  # sensible default
        protected=True,  # cannot change state directly, must use methods!
    )
    creator = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="applications_created"
    )
    investigator = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="applications_investigating",
    )

    # data fields from the initial form

    FEDERAL = "federal"
    INTERSTATE = "interstate"
    STATE_OR_TERRITORY = "state_or_territory"
    TRIBAL = "tribal"
    COUNTY = "county"
    CITY = "city"
    SPECIAL_DISTRICT = "special_district"
    ORGANIZATION_CHOICES = [
        (FEDERAL, "a federal agency"),
        (INTERSTATE, "an organization of two or more states"),
        (
            STATE_OR_TERRITORY,
            "one of the 50 U.S. states, the District of "
            "Columbia, American Samoa, Guam, Northern Mariana Islands, "
            "Puerto Rico, or the U.S. Virgin Islands",
        ),
        (
            TRIBAL,
            "a tribal government recognized by the federal or " "state government",
        ),
        (COUNTY, "a county, parish, or borough"),
        (CITY, "a city, town, township, village, etc."),
        (SPECIAL_DISTRICT, "an independent organization within a single state"),
    ]
    organization_type = models.CharField(
        max_length=255, choices=ORGANIZATION_CHOICES, help_text="Type of Organization"
    )

    EXECUTIVE = "Executive"
    JUDICIAL = "Judicial"
    LEGISLATIVE = "Legislative"
    BRANCH_CHOICES = [(x, x) for x in (EXECUTIVE, JUDICIAL, LEGISLATIVE)]
    federal_branch = models.CharField(
        max_length=50,
        choices=BRANCH_CHOICES,
        null=True,
        help_text="Branch of federal government",
    )

    is_election_office = models.BooleanField(
        null=True, help_text="Is your ogranization an election office?"
    )

    organization_name = models.TextField(null=True, help_text="Organization name")
    street_address = models.TextField(null=True, help_text="Street Address")
    unit_type = models.CharField(max_length=15, null=True, help_text="Unit type")
    unit_number = models.CharField(max_length=255, null=True, help_text="Unit number")
    state_territory = models.CharField(
        max_length=2, null=True, help_text="State/Territory"
    )
    zip_code = models.CharField(max_length=10, null=True, help_text="ZIP code")

    authorizing_official = models.ForeignKey(
        Contact,
        null=True,
        related_name="authorizing_official",
        on_delete=models.PROTECT,
    )

    # "+" means no reverse relation to lookup applications from Website
    current_websites = models.ManyToManyField(Website, related_name="current+")

    requested_domain = models.ForeignKey(
        Website,
        null=True,
        help_text="The requested domain",
        related_name="requested+",
        on_delete=models.PROTECT,
    )
    alternative_domains = models.ManyToManyField(Website, related_name="alternatives+")

    submitter = models.ForeignKey(
        Contact, null=True, related_name="submitted_applications", on_delete=models.PROTECT
    )

    purpose = models.TextField(null=True, help_text="Purpose of the domain")

    other_contacts = models.ManyToManyField(
        Contact, related_name="contact_applications"
    )

    security_email = models.CharField(
        max_length=320, null=True, help_text="Security email for public use"
    )

    anything_else = models.TextField(
        null=True, help_text="Anything else we should know?"
    )

    acknowledged_policy = models.BooleanField(
        null=True,
        help_text="Acknowledged .gov acceptable use policy"
    )

    def can_submit(self):
        """Return True if this instance can be marked as submitted."""
        if not string_could_be_domain(requested_domain):
            return False
        return True

    @transition(
        field="status", source=STARTED, target=SUBMITTED, conditions=[can_submit]
    )
    def submit(self):
        """Submit an application that is started."""
        # don't need to do anything inside this method although we could
        pass


