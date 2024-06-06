from django.db import models

from .utility.time_stamped_model import TimeStampedModel


class Portfolio(TimeStampedModel):
    """
    TODO: 
    """

    class Meta:
        """Contains meta information about this class"""

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["email"]),
        ]
        
    # NOTE: This will be specified in a future ticket
    # class PortfolioTypes(models.TextChoices):
    #     TYPE1 = "foo", "foo"
    #     TYPE2 = "foo", "foo"
    #     TYPE3 = "foo", "foo"
    #     TYPE4 = "foo", "foo"


    # creator- user foreign key- stores who created this model should get the user who is adding 
    # it via django admin if there is a user (aka not done via commandline/ manual means)"""
    # TODO: auto-populate
    creator = models.ForeignKey(
        "registrar.User",
        on_delete=models.PROTECT,
        help_text="Associated user",
        unique=False
    )

    # NOTE: This will be specified in a future ticket
    # portfolio_type = models.TextField(
    #     choices=PortfolioTypes.choices,
    #     null=True,
    #     blank=True,
    # )

    # notes- text field (copy what is done on requests/domains)
    notes = models.TextField(
        null=True,
        blank=True,
    )

    # domains- many to many to Domain field (nullable)
    domains = models.ManyToManyField(
        "registrar.Domain",
        null=True,
        blank=True,
        related_name="portfolio domains",
        verbose_name="portfolio domains",
        # on_delete=models.PROTECT, # TODO: protect this?
    )

    # domain_requests- Many to many to Domain Request field (nullable)
    domain_requests = models.ManyToManyField(
        "registrar.DomainRequest",
        null=True,
        blank=True,
        related_name="portfolio domain requests",
        verbose_name="portfolio domain requests",
        # on_delete=models.PROTECT, # TODO: protect this?
    )

    # organization
    organization = models.OneToOneField(
        "registrar.Organization",
        null=True,
        blank=True,
        # on_delete=models.PROTECT, # TODO: protect this?
    )
   

    # def save(self, *args, **kwargs):
    #     # Call the parent class's save method to perform the actual save
    #     super().save(*args, **kwargs)

    #     if self.user:
    #         updated = False

    #         # Update first name and last name if necessary
    #         if not self.user.first_name or not self.user.last_name:
    #             self.user.first_name = self.first_name
    #             self.user.last_name = self.last_name
    #             updated = True

    #         # Update phone if necessary
    #         if not self.user.phone:
    #             self.user.phone = self.phone
    #             updated = True

    #         # Save user if any updates were made
    #         if updated:
    #             self.user.save()

    # def __str__(self):
    #     if self.first_name or self.last_name:
    #         return self.get_formatted_name()
    #     elif self.email:
    #         return self.email
    #     elif self.pk:
    #         return str(self.pk)
    #     else:
    #         return ""
