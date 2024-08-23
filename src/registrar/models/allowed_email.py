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

        if not email:
            return False

        # Split the email into a local part and a domain part
        local, domain = email.split("@")

        # If the email exists within the whitelist, then do nothing else.
        email_exists = cls.objects.filter(email__iexact=email).exists()
        if email_exists:
            return True

        # Check if there's a '+' in the local part
        if "+" in local:
            base_local = local.split("+")[0]
            base_email_exists = cls.objects.filter(Q(email__iexact=f"{base_local}@{domain}")).exists()

            # Given an example email, such as "joe.smoe+1@igorville.com"
            # The full regex statement will be: "^joe.smoe\\+\\d+@igorville.com$"
            pattern = f"^{re.escape(base_local)}\\+\\d+@{re.escape(domain)}$"
            return base_email_exists and re.match(pattern, email)
        else:
            # Edge case, the +1 record exists but the base does not,
            # and the record we are checking is the base record.
            pattern = f"^{re.escape(local)}\\+\\d+@{re.escape(domain)}$"
            plus_email_exists = cls.objects.filter(Q(email__iregex=pattern)).exists()
            return plus_email_exists

    def __str__(self):
        return str(self.email)
