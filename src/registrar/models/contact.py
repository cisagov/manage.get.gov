from django.db import models

from .utility.time_stamped_model import TimeStampedModel

from phonenumber_field.modelfields import PhoneNumberField  # type: ignore


class Contact(TimeStampedModel):
    """
    Contact information follows a similar pattern for each contact.
    """

    class Meta:
        """Contains meta information about this class"""

        indexes = [
            models.Index(fields=["email"]),
        ]

    first_name = models.CharField(
        null=True,
        blank=True,
        verbose_name="first name",
    )
    middle_name = models.CharField(
        null=True,
        blank=True,
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
    email = models.EmailField(
        null=True,
        blank=True,
        max_length=320,
    )
    phone = PhoneNumberField(
        null=True,
        blank=True,
    )

    def _get_all_relations(self):
        """Returns an array of all fields which are relations"""
        return [f.name for f in self._meta.get_fields() if f.is_relation]

    def has_more_than_one_join(self, expected_relation):
        """Helper for finding whether an object is joined more than once.
        expected_relation is the one relation with one expected join"""
        # all_relations is the list of all_relations (from contact) to be checked for existing joins
        all_relations = self._get_all_relations()
        return any(self._has_more_than_one_join_per_relation(rel, expected_relation) for rel in all_relations)

    def _has_more_than_one_join_per_relation(self, relation, expected_relation):
        """Helper for finding whether an object is joined more than once."""
        # threshold is the number of related objects that are acceptable
        # when determining if related objects exist. threshold is 0 for most
        # relationships. if the relationship is expected_relation, we know that
        # there is already exactly 1 acceptable relationship (the one we are
        # attempting to delete), so the threshold is 1
        threshold = 1 if relation == expected_relation else 0

        # Raise a KeyError if rel is not a defined field on the db_obj model
        # This will help catch any errors in relation passed.
        if relation not in [field.name for field in self._meta.get_fields()]:
            raise KeyError(f"{relation} is not a defined field on the {self._meta.model_name} model.")

        # if attr rel in db_obj is not None, then test if reference object(s) exist
        if getattr(self, relation) is not None:
            field = self._meta.get_field(relation)
            if isinstance(field, models.OneToOneField):
                # if the rel field is a OneToOne field, then we have already
                # determined that the object exists (is not None)
                # so return True unless the relation being tested is the expected_relation
                is_not_expected_relation = relation != expected_relation
                return is_not_expected_relation
            elif isinstance(field, models.ForeignObjectRel):
                # if the rel field is a ManyToOne or ManyToMany, then we need
                # to determine if the count of related objects is greater than
                # the threshold
                return getattr(self, relation).count() > threshold
        return False

    def get_formatted_name(self):
        """Returns the contact's name in Western order."""
        names = [n for n in [self.first_name, self.middle_name, self.last_name] if n]
        return " ".join(names) if names else "Unknown"

    def has_contact_info(self):
        return bool(self.title or self.email or self.phone)

    def __str__(self):
        if self.first_name or self.last_name:
            return self.get_formatted_name()
        elif self.email:
            return self.email
        elif self.pk:
            return str(self.pk)
        else:
            return ""
