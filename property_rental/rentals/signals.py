"""Cache-invalidation signal handlers for the ``FX`` model.

Phase 4 Task 3 (2026-07-19) moved FX graph cache invalidation off of
the ``FX.save`` / ``FX.delete`` model overrides and onto Django
``post_save`` / ``post_delete`` signals. The previous model-override
pattern missed writes that bypass ``save()`` (e.g. ``QuerySet.update()``
and ``QuerySet.bulk_create()``) — and ``bulk_create`` is exactly the
call path the yfinance back-fill in ``services.fx.update_rates`` uses
indirectly through ``update_or_create``, which already exercises
``save()`` but a future bulk path would not.

The handlers are registered in ``RentalsConfig.ready`` (see ``apps.py``)
so they fire for every ORM write to ``FX``: single-row ``save`` /
``delete``, ``QuerySet.bulk_create``, ``QuerySet.update``, and
``QuerySet.delete``.

Catching ``bulk_create`` is the central motivation: ``post_save`` fires
once per created row (so a 360-row back-fill emits 360 signals, each
invalidating the cache) which is acceptable for a personal app. A
version-counter pattern (see ``services.fx`` module docstring) would be
the right optimization once the cache backend moves to Redis.

Why a single ``invalidate_fx_cache`` receiver on both signals
------------------------------------------------------------

The cache key is the ``as_of`` date (only thing the graph depends on).
Invalidating the whole cache on any write is the conservative choice
that matches the old ``save`` / ``delete`` override behavior — we don't
need to inspect the row to know it might affect any cached graph. If
later we want finer-grained invalidation, the signal handler is the
single place to refine it.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from rentals.models import FX


@receiver(post_save, sender=FX)
def _invalidate_fx_cache_on_save(sender, instance, **kwargs):
    """Invalidate the FX graph cache after any ``FX`` row is saved.

    Fires on every ``FX.objects.create(...)``, ``fx.save()`` (insert or
    update), and per-row ``bulk_create`` writes (Django 4.0+ emits
    ``post_save`` per row created via ``bulk_create`` when the model
    has a signal handler registered).
    """
    # Lazy import: ``rentals.services.fx`` imports ``rentals.models``
    # (the lazy-imported ``FX`` reference), and ``rentals.models`` is
    # imported at module load by ``rentals.signals`` (this module) —
    # so importing ``services.fx`` at module scope here would close a
    # circular import. Deferring it to call time keeps the graph a DAG.
    from rentals.services.fx import invalidate_cache
    invalidate_cache()


@receiver(post_delete, sender=FX)
def _invalidate_fx_cache_on_delete(sender, instance, **kwargs):
    """Invalidate the FX graph cache after any ``FX`` row is deleted."""
    from rentals.services.fx import invalidate_cache
    invalidate_cache()
