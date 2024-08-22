from django.db import models
from django.db.models import Q
import re
from .utility.time_stamped_model import TimeStampedModel


class AllowedEmail(TimeStampedModel):
    """
    AllowedEmail is a whitelist for email addresses that we can send to
    in non-production environments.
    """

    email = models.EmailField(
        unique=True,
        null=False,
        blank=False,
        max_length=320,
    )

    @classmethod
    def is_allowed_email(cls, email):
        """Given an email, check if this email exists within our AllowEmail whitelist"""
        print(f"the email is: {email}")
        if not email:
            return False

        # Split the email into a local part and a domain part
        local, domain = email.split('@')

        # Check if there's a '+' in the local part
        if "+" in local:
            base_local = local.split("+")[0]
            base_email = f"{base_local}@{domain}"
            allowed_emails = cls.objects.filter(email__iexact=base_email)

            # The string must start with the local, and the plus must be a digit
            # and occur immediately after the local. The domain should still exist in the email.
            pattern = f'^{re.escape(base_local)}\\+\\d+@{re.escape(domain)}$'

            # If the base email exists AND the email matches our expected regex,
            # then we can let the email through.
            return allowed_emails.exists() and re.match(pattern, email)
        else:
            # If no '+' exists in the email, just do an exact match
            allowed_emails = cls.objects.filter(email__iexact=email)
            return allowed_emails.exists()

    def __str__(self):
        return str(self.email)
