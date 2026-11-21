from contextlib import contextmanager

from django.db import connection, transaction


@contextmanager
def repeatable_read():
    if connection.vendor != 'postgresql':
        yield
        return
    nested = connection.in_atomic_block
    with transaction.atomic():
        with connection.cursor() as cursor:
            if nested:
                cursor.execute('SHOW transaction_isolation')
                if cursor.fetchone()[0] not in {'repeatable read', 'serializable'}:
                    raise RuntimeError('FX reports require REPEATABLE READ in an existing transaction')
            else:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        yield
