from contextlib import contextmanager
from django.db import transaction, IntegrityError
from psycopg2 import errorcodes


@contextmanager
def ignore_unique_violation():
    """
    Execute within an atomic transaction so that if a unique constraint violation occurs,
    the individual transaction is rolled back without invalidating any larger transaction.
    """
    with transaction.atomic():
        try:
            yield
        except IntegrityError as e:
            if e.__cause__.pgcode == errorcodes.UNIQUE_VIOLATION:
                # roll back to the savepoint, effectively ignoring this transaction
                pass
            else:
                raise e

def object_is_being_created(object):
    """ returns true if the object is new and hasn't been saved in the db
        To use this inside a class just pass 'self' as the parameter
    """
    # _state and _state.adding are django specifc more information at:
    # https://docs.djangoproject.com/en/4.2/ref/models/instances/#django.db.models.Model.from_db
    #  _state exists on object after initialization
    # `adding` is set to True by django
    # only when the object hasn't been saved to the db
    # django automagically changes this to false after db-save
    return getattr(object, "_state", None) and object._state.adding
    