from contextlib import contextmanager
from django.db import transaction, IntegrityError
from psycopg2 import errorcodes


def get_portfolio_from_session(session):
    """Return the Portfolio instance stored in the session, or None."""
    from registrar.models import Portfolio

    portfolio_id = session.get("portfolio")
    return Portfolio.objects.get(id=portfolio_id) if portfolio_id else None


@contextmanager
def lock_domain_row_for_update(domain_id):
    """Yield a fresh Domain instance while locking its row in database"""
    from registrar.models import Domain

    with transaction.atomic():
        yield Domain.objects.select_for_update().get(pk=domain_id)


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
