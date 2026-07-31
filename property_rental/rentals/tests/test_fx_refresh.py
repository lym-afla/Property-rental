from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction

from rentals.models import FX


class Provider:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def get_rate(self, *, as_of, pair):
        self.calls.append((as_of, pair))
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value


def test_legacy_synchronous_acquisition_entry_points_are_removed():
    from rentals import utils
    from rentals.services import fx

    assert not hasattr(utils, "update_FX_database")
    assert not hasattr(fx, "update_rates")


@pytest.mark.django_db
def test_canonical_pair_and_cached_rate_avoid_provider_call():
    from rentals.services.fx_refresh import CurrencyPair, refresh_rates

    FX.objects.create(date=date(2024, 1, 2), from_currency="EUR", to_currency="USD", rate=Decimal("1.1"))
    provider = Provider([])
    report = refresh_rates(as_of=date(2024, 1, 2), pairs=[CurrencyPair("usd", "eur")], provider=provider)
    assert report.cached == [CurrencyPair("EUR", "USD")]
    assert provider.calls == []


@pytest.mark.django_db
def test_refresh_is_idempotent_and_rejects_duplicate_identity():
    from rentals.services.fx_refresh import CurrencyPair, refresh_rates

    provider = Provider([Decimal("1.25")])
    pair = CurrencyPair("GBP", "USD")
    first = refresh_rates(as_of=date(2024, 2, 1), pairs=[pair], provider=provider)
    second = refresh_rates(as_of=date(2024, 2, 1), pairs=[pair], provider=provider)
    assert first.fetched == [pair]
    assert second.cached == [pair]
    assert FX.objects.filter(date=date(2024, 2, 1), from_currency="GBP", to_currency="USD").count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        FX.objects.create(date=date(2024, 2, 1), from_currency="GBP", to_currency="USD", rate=2)


@pytest.mark.django_db
@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")])
def test_invalid_provider_values_are_reported_without_writes(value):
    from rentals.services.fx_refresh import CurrencyPair, refresh_rates

    pair = CurrencyPair("EUR", "USD")
    report = refresh_rates(as_of=date(2024, 3, 1), pairs=[pair], provider=Provider([value]))
    assert report.invalid == [pair]
    assert not FX.objects.exists()


@pytest.mark.django_db
def test_provider_error_is_bounded_and_existing_rates_are_retained():
    from rentals.services.fx_refresh import CurrencyPair, refresh_rates

    old = FX.objects.create(date=date(2024, 2, 28), from_currency="EUR", to_currency="USD", rate=Decimal("1.09"))
    pair = CurrencyPair("EUR", "USD")
    provider = Provider([TimeoutError("bounded timeout")])
    report = refresh_rates(as_of=date(2024, 3, 1), pairs=[pair], provider=provider)
    assert report.unavailable == [pair]
    assert len(provider.calls) == 1
    old.refresh_from_db()
    assert old.rate == Decimal("1.0900000000")


@pytest.mark.django_db
def test_non_positive_cached_row_is_replaced_by_valid_provider_value():
    from rentals.services.fx_refresh import CurrencyPair, refresh_rates

    pair = CurrencyPair("EUR", "USD")
    FX.objects.create(
        date=date(2024, 3, 1),
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("0"),
    )

    report = refresh_rates(
        as_of=date(2024, 3, 1), pairs=[pair], provider=Provider([Decimal("1.08")])
    )

    assert report.fetched == [pair]
    assert FX.objects.get().rate == Decimal("1.0800000000")


@pytest.mark.django_db
def test_command_uses_business_timezone_date_and_fails_for_missing_rate(monkeypatch):
    import rentals.management.commands.refresh_fx as command

    seen = {}
    monkeypatch.setattr(command.timezone, "now", lambda: datetime(2024, 1, 1, 21, 30, tzinfo=dt_timezone.utc))
    monkeypatch.setattr(command, "YahooRateProvider", lambda: Provider([None]))
    real_refresh = command.refresh_rates

    def capture(**kwargs):
        seen["as_of"] = kwargs["as_of"]
        return real_refresh(**kwargs)

    monkeypatch.setattr(command, "refresh_rates", capture)
    with pytest.raises(CommandError):
        call_command("refresh_fx", pair=["EUR/USD"])
    assert seen["as_of"] == date(2024, 1, 1)
