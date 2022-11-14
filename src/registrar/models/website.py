import re

from django.db import models


class Website(models.Model):

    """Keep domain names in their own table so that applications can refer to
    many of them."""

    # domain names have strictly limited lengths, 255 characters is more than
    # enough.
    website = models.CharField(
        max_length=255,
        null=False,
        help_text="",
    )

    # a domain name is alphanumeric or hyphen, up to 63 characters, doesn't
    # begin or end with a hyphen, followed by a TLD of 2-6 alphabetic characters
    DOMAIN_REGEX = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.[A-Za-z]{2,6}")

    @classmethod
    def string_could_be_domain(cls, domain: str) -> bool:
        """Return True if the string could be a domain name, otherwise False.

        TODO: when we have a Domain class, this could be a classmethod there.
        """
        if cls.DOMAIN_REGEX.match(domain):
            return True
        return False

    def could_be_domain(self) -> bool:
        """Could this instance be a domain?"""
        # short-circuit if self.website is null/None
        if not self.website:
            return False
        return self.string_could_be_domain(str(self.website))

    def __str__(self) -> str:
        return str(self.website)
