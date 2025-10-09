from contextlib import contextmanager
from django.db import connection, transaction


@contextmanager
def pg_timeouts(*, statement_ms=None, lock_ms=None, idle_tx_ms=None):
    with transaction.atomic():
        with connection.cursor() as cur:
            if statement_ms is not None:
                cur.execute("SET LOCAL statement_timeout = %s", [statement_ms])
            if lock_ms is not None:
                cur.execute("SET LOCAL lock_timeout = %s", [lock_ms])
            if idle_tx_ms is not None:
                cur.execute("SET LOCAL idle_in_transaction_session_timeout = %s", [idle_tx_ms])
        yield
