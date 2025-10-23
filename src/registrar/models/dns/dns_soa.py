from django.db import models
from ..utility.time_stamped_model import TimeStampedModel
from django.core.validators import MaxValueValidator, MinValueValidator


class DnsSoa(TimeStampedModel):
    mname = models.CharField(
        null=True,
        blank=True,
        default=None
    )

    rname = models.CharField(
        blank=True,
        default="dns.cloudflare.com"
    )

    refresh = models.PositiveIntegerField(
        blank=True,
        default=10000,
        validators=[
            MinValueValidator(600),
            MaxValueValidator(86400)
        ]
    )

    retry = models.PositiveIntegerField(
        blank=True,
        default=10000,
        validators=[
            MinValueValidator(600),
            MaxValueValidator(86400)
        ]
    )

    expire = models.PositiveIntegerField(
        blank=True,
        default=604800,
        validators=[
            MinValueValidator(86400),
            MaxValueValidator(2419200)
        ]
    )

    min_ttl = models.PositiveIntegerField(
        blank=True,
        default=1800,
        validators=[
            MinValueValidator(60),
            MaxValueValidator(86400)
        ]
    )

    ttl = models.PositiveIntegerField(
        blank=True,
        default=3600,
        validators=[
            MinValueValidator(300),
            MaxValueValidator(86400)
        ]
    )

    @classmethod
    def get_default_pk(cls):
        soa, _ = cls.objects.get_or_create(
            mname=None,
            rname="dns.cloudflare.com",
            refresh=10000,
            retry=10000,
            expire=604800,
            min_ttl=1800,
            ttl=3600
        )
        return soa.pk

