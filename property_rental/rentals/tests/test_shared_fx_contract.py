from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.test import override_settings


def test_vendored_resolver_hash():
    import hashlib
    from pathlib import Path
    from rentals.services import shared_fx_resolver
    assert hashlib.sha256(Path(shared_fx_resolver.__file__).read_bytes()).hexdigest() == 'feee2baef84e3d44ba369facfd0a83142f1fb681905b44a55d014a37c419b86d'


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_mirror_adapter_uses_shared_resolution_and_preserves_shape(monkeypatch):
    from rentals.models import FXAnchor
    from rentals.services import fx_mirror, shared_fx_resolver
    FXAnchor.objects.create(date=date(2026, 1, 6), currency='USD', value='1', snapshot_id='s')
    FXAnchor.objects.create(date=date(2026, 1, 6), currency='EUR', value='0.9', snapshot_id='s')
    calls = []
    def resolve(values, base, quote, requested, **kwargs):
        calls.append((values, base, quote, requested, kwargs))
        return SimpleNamespace(multiplier=Decimal('0.7'), effective_date=requested,
                               source_date=requested, provisional=False, cacheable=True)
    monkeypatch.setattr(shared_fx_resolver, 'resolve', resolve)
    result = fx_mirror.get_rate('USD', 'EUR', date(2026, 1, 6))
    assert result['FX'] == Decimal('0.7')
    assert result['conversions'] == 1 and result['dates_async'] is False
    assert result['dates'] == result['FX dates used'] == [date(2026, 1, 6)]
    assert calls[0][1:4] == ('USD', 'EUR', date(2026, 1, 6))
