from django.db import models


class DomainField(models.CharField):
    """Subclass of CharField to enforce domain name specific requirements."""

    def to_python(self, value):
        """Convert to lowercase during deserialization and during form `clean`."""
        if value is None:
            return value
        if isinstance(value, str):
            return value.lower()
        return str(value).lower()
