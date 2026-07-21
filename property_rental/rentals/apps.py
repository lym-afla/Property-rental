from django.apps import AppConfig


class RentalsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rentals'

    def ready(self):
        # Phase 4 Task 3 (2026-07-19): import the ``FX`` cache-invalidation
        # signal handlers so they are registered with Django's signal
        # dispatcher at app-load time. The module body is the registration
        # (``@receiver`` decorators at import time); importing it is the
        # whole point. ``# noqa: F401`` because the import is for its side
        # effects, not because anything here uses the symbol.
        from . import signals  # noqa: F401
