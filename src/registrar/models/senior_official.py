from django.db import models
from django.db.models import Q

# from django.utils import timezone

from .utility.time_stamped_model import TimeStampedModel
from phonenumber_field.modelfields import PhoneNumberField  # type: ignore


class SeniorOfficial(TimeStampedModel):
    """
    Senior Official is a distinct Contact-like entity (NOT to be inherited
    from Contacts) developed for the unique role these individuals have in
    managing Portfolios.
    """

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(state_tribe__isnull=True) | Q(federal_tribe__isnull=True),
                name="senior_official_single_tribe_reference",
            ),
        ]

    first_name = models.CharField(
        null=True,
        blank=True,
        verbose_name="first name",
    )

    last_name = models.CharField(
        null=True,
        blank=True,
        verbose_name="last name",
    )

    title = models.CharField(
        null=True,
        blank=True,
        verbose_name="title / role",
    )

    phone = PhoneNumberField(
        null=True,
        blank=True,
    )

    email = models.EmailField(
        null=True,
        blank=True,
        max_length=320,
    )

    federal_agency = models.ForeignKey(
        "registrar.FederalAgency",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="so_federal_agency",
        help_text="The federal agency this user is associated with",
    )

    # QUESTION: Do we want PROTECT instead of SET_NULL?
    # If the Tribe goes away, PROTECT would block the delete
    # Do we want the the tribe <> senior official link to not be able to be borked?
    state_tribe = models.ForeignKey(
        "registrar.StateTribe",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="senior_official",
        verbose_name="State recognized tribe",
        help_text="The state recognized tribe the senior official is associated with",
    )

    # QUESTION: Do we want PROTECT instead of SET_NULL?
    # If the Tribe goes away, PROTECT would block the delete
    # Do we want the the tribe <> senior official link to not be able to be borked?
    federal_tribe = models.ForeignKey(
        "registrar.FederalTribe",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="senior_official",
        verbose_name="Federally recognized tribe",
        help_text="The federally recognized tribe the senior official is associated with",
    )

    # QUESTION: What model type would we want this to be? See below
    tribal_leader_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Tribal leader last updated",
        help_text="When this record was last updated from the linked tribe's leader information",
    )

    def get_formatted_name(self):
        """Returns the contact's name in Western order."""
        names = [n for n in [self.first_name, self.last_name] if n]
        return " ".join(names) if names else "Unknown"

    def __str__(self):
        if self.federal_agency and (self.first_name or self.last_name):
            return self.get_formatted_name() + " of " + self.federal_agency.__str__()
        elif self.first_name or self.last_name:
            return self.get_formatted_name()
        elif self.pk:
            return str(self.pk)
        else:
            return ""

    @property
    def linked_tribe(self):
        """The tribe record the SO is associated with, if any"""
        return self.federal_tribe or self.state_tribe

    """
    QUESITION:
    We want to update the tribal leader contact info if there are any updates to the record
    1. Will/should Analysts be able to edit these records?
    (Iirc currently Federal Tribes Analysts cannot edit, State Tribes Analysts can)
    2. If not, what if we have tribal_leader_updated_at be a JSON blob so it can compare per field
    (maybe we rename that variable too)
    3. We should just always overwrite bc they should be editing it on the Federal/State Tribe field
    anyway which is our source of truth
    """

    # @property
    # def tribal_leader_is_stale(self):
    #     """True when the linked tribe record changed after the last sync"""
    #     tribe = self.linked_tribe
    #     if not tribe or not self.tribal_leader_updated_at:
    #         return False
    #     return tribe.updated_at > self.tribal_leader_updated_at

    # def sync_from_tribal_leader(self, save=True):
    #     """
    #     Copies tribal leader contact info from the linked tribe record

    #     NOTE: Nothing triggers this yet, these are just possible dummy functions
    #     that can be edited.
    #     Do we even want this? Bc if an Analyst were to come in and manually edit,
    #     whenever we have another sync this would overwrite it
    #     """
    #     if self.federal_tribe:
    #         tribe = self.federal_tribe
    #         self.first_name = tribe.first_name
    #         self.last_name = tribe.last_name
    #         if tribe.job_title:
    #             self.title = tribe.job_title
    #     elif self.state_tribe:
    #         tribe = self.state_tribe
    #         self.first_name = tribe.tribal_leader_first_name
    #         self.last_name = tribe.tribal_leader_last_name
    #     else:
    #         return

    #     if tribe.email:
    #         self.email = tribe.email[0]

    #     if tribe.phone:
    #         self.phone = tribe.phone

    #     self.tribal_leader_updated_at = timezone.now()

    #     if save:
    #         self.save()
