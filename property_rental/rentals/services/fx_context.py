"""Context-local resolver and measured behavior selection for read-only reports."""
from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings

BEHAVIORS = ('rent_total_face_value', 'scheduler_rent_denomination',
             'scheduler_rent_selection', 'native_stats_and_pnl')
_selection = ContextVar('fx_calculation_selection', default=None)


def backend():
    selected = _selection.get()
    return selected[0] if selected else getattr(settings, 'FX_BACKEND', 'legacy')


def behavior(name):
    selected = _selection.get()
    return name in selected[1] if selected else backend() == 'mirror'


@contextmanager
def calculation_context(resolver, behaviors=None):
    if resolver not in ('legacy', 'mirror'):
        raise ValueError('Invalid resolver')
    enabled = frozenset(BEHAVIORS if resolver == 'mirror' else ()) if behaviors is None else frozenset(behaviors)
    if not enabled.issubset(BEHAVIORS):
        raise ValueError('Invalid behavior')
    token = _selection.set((resolver, enabled))
    try:
        yield
    finally:
        _selection.reset(token)
