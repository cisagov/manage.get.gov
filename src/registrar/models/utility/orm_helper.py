from django.db.models.expressions import Func


class ArrayRemoveNull(Func):
    """Custom Func to use array_remove to remove null values"""

    function = "array_remove"
    template = "%(function)s(%(expressions)s, NULL)"
