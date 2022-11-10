from django.db import models


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
