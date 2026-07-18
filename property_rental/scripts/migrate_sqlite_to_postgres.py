"""Backward-compat shim that delegates to the management command.

The brief listed ``scripts/migrate_sqlite_to_postgres.py`` as the
expected file. We moved the real implementation into
``rentals/management/commands/migrate_sqlite_to_postgres.py`` so the
verification logic is unit-testable and the script gains proper arg
parsing / ``--dry-run`` / idempotency. This file exists so the brief's
documented invocation still works::

    DJANGO_SETTINGS_MODULE=property_rental.settings.prod \
        python manage.py shell < scripts/migrate_sqlite_to_postgres.py

It just shells out to the management command via ``call_command``.
"""

from django.core.management import call_command

if __name__ == "__main__":
    # When piped into ``python manage.py shell``, ``__name__`` is
    # ``__main__`` and Django is already set up. Forward to the command.
    call_command("migrate_sqlite_to_postgres")
