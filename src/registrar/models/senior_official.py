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

    state_tribe = models.ForeignKey(
        "registrar.StateTribe",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="senior_official",
        verbose_name="State recognized tribe",
        help_text="The state recognized tribe the senior official is associated with",
    )

    federal_tribe = models.ForeignKey(
        "registrar.FederalTribe",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="senior_official",
        verbose_name="Federally recognized tribe",
        help_text="The federally recognized tribe the senior official is associated with",
    )

    suffix = models.CharField(
        null=True,
        blank=True,
        help_text="Name suffix (ie jr, sr, III)",
    )

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

    # @property
    # def linked_tribe(self):
    #     """The tribe record the SO is associated with, if any"""
    #     return self.federal_tribe or self.state_tribe

    # @property
    # def tribal_leader_is_stale(self):
    #     """
    #     True when the linked tribe record changed after the last sync

    #     This is NOT a manual check - the State/Federal Tribe record is
    #     source of truth, so a sync overwrites whatever is here
    #     """
    #     tribe = self.linked_tribe
    #     if not tribe:
    #         return False
    #     if not self.tribal_leader_updated_at:
    #         return True
    #     return tribe.updated_at > self.tribal_leader_updated_at

    # def _tribal_leader_values(self):
    #     """
    #     Leader values from the linked tribe
    #     (State/Federal diff field name hence if/else)

    #     Returns None when there is no linked tribe
    #     """
    #     if self.federal_tribe:
    #         tribe = self.federal_tribe
    #         values = {
    #             "first_name": tribe.first_name,
    #             "last_name": tribe.last_name,
    #             "title": tribe.job_title,
    #         }
    #     elif self.state_tribe:
    #         tribe = self.state_tribe
    #         values = {
    #             "first_name": tribe.tribal_leader_first_name,
    #             "last_name": tribe.tribal_leader_last_name,
    #             # StateTribe has no title equivalent
    #             "title": None,
    #         }
    #     else:
    #         return None

    #     # email is an ArrayField on both tribe models, only grab first email
    #     values["email"] = tribe.email[0] if tribe.email else None
    #     values["phone"] = tribe.phone or None

    #     return values

    # def sync_from_tribal_leader(self, save=True):
    #     """
    #     Overwrites this record's contact fields from the linked tribe

    #     The Federal/State Tribe record is the source of truth so this always overwrites,
    #     incl clearing any field the tribe no longer has a value for.

    #     Returns True if a sync happened, False if there is no linked tribe
    #     """
    #     values = self._tribal_leader_values()
    #     if values is None:
    #         return False

    #     for field, value in values.items():
    #         setattr(self, field, value)

    #     self.tribal_leader_updated_at = timezone.now()

    #     if save:
    #         self.save(update_fields=[*values.keys(), "tribal_leader_updated_at", "updated_at"])

    #     return True
