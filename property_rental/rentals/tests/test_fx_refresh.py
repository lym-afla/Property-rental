import json
import os
import sys
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction

from rentals.models import FX
from rentals.tests.factories import (
    FXFactory,
    LeaseRentFactory,
    PropertyCapitalStructureFactory,
    PropertyFactory,
    TenantFactory,
    TransactionFactory,
)


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


class CBRResponse:
    def __init__(self, *, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetCursOnDateResponse xmlns="http://web.cbr.ru/">
      <GetCursOnDateResult>
        <diffgr:diffgram xmlns:diffgr="urn:schemas-microsoft-com:xml-diffgram-v1">
          <ValuteData>
            <ValuteCursOnDate diffgr:id="ValuteCursOnDate1">
              <VchCode>USD</VchCode>
              <Vnom>1</Vnom>
              <Vcurs>90,0000</Vcurs>
            </ValuteCursOnDate>
            <ValuteCursOnDate diffgr:id="ValuteCursOnDate2">
              <VchCode>EUR</VchCode>
              <Vnom>1</Vnom>
              <Vcurs>100,0000</Vcurs>
            </ValuteCursOnDate>
          </ValuteData>
        </diffgr:diffgram>
      </GetCursOnDateResult>
    </GetCursOnDateResponse>
  </soap:Body>
</soap:Envelope>"""


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
def test_gap_scan_derives_required_rates_from_business_records():
    from rentals.services.fx_refresh import CurrencyPair, RateRequirement, discover_rate_requirements

    property_ = PropertyFactory(currency="GBP")
    TransactionFactory(
        property=property_,
        date=date(2024, 1, 15),
        currency="EUR",
        amount=Decimal("100.00"),
    )
    PropertyCapitalStructureFactory(
        property=property_,
        capital_structure_date=date(2024, 2, 1),
        capital_structure_value=Decimal("250000.00"),
    )
    tenant = TenantFactory(
        property=property_,
        lease_start=date(2024, 3, 1),
        lease_end=date(2024, 3, 1),
        payday=1,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2024, 3, 1),
        currency="RUB",
        rent=Decimal("75000.00"),
    )

    requirements = discover_rate_requirements(
        target_currencies=("USD",),
        through=date(2024, 3, 31),
    )

    assert set(requirements) == {
        RateRequirement(date(2024, 1, 15), CurrencyPair("EUR", "USD")),
        RateRequirement(date(2024, 2, 1), CurrencyPair("GBP", "USD")),
        RateRequirement(date(2024, 3, 1), CurrencyPair("RUB", "USD")),
    }


@pytest.mark.django_db
def test_gap_scan_includes_tenant_due_dates_when_rent_rate_applies():
    from rentals.services.fx_refresh import CurrencyPair, RateRequirement, discover_rate_requirements

    tenant = TenantFactory(
        lease_start=date(2024, 1, 10),
        lease_end=date(2024, 3, 31),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2024, 1, 10),
        currency="EUR",
        rent=Decimal("1200.00"),
    )

    requirements = discover_rate_requirements(
        target_currencies=("USD",),
        through=date(2024, 3, 31),
    )

    assert set(requirements) == {
        RateRequirement(date(2024, 1, 10), CurrencyPair("EUR", "USD")),
        RateRequirement(date(2024, 2, 5), CurrencyPair("EUR", "USD")),
        RateRequirement(date(2024, 3, 5), CurrencyPair("EUR", "USD")),
    }


@pytest.mark.django_db
def test_refresh_missing_rates_is_idempotent_per_effective_date_and_pair():
    from rentals.services.fx_refresh import CurrencyPair, RateRequirement, refresh_missing_rates

    property_ = PropertyFactory(currency="GBP")
    TransactionFactory(
        property=property_,
        date=date(2024, 1, 15),
        currency="EUR",
        amount=Decimal("100.00"),
    )
    PropertyCapitalStructureFactory(
        property=property_,
        capital_structure_date=date(2024, 2, 1),
        capital_structure_value=Decimal("250000.00"),
    )
    FXFactory(
        date=date(2024, 1, 15),
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("1.10"),
    )

    first_provider = Provider([Decimal("1.25")])
    first = refresh_missing_rates(
        target_currencies=("USD",),
        through=date(2024, 2, 28),
        provider=first_provider,
    )
    second_provider = Provider([])
    second = refresh_missing_rates(
        target_currencies=("USD",),
        through=date(2024, 2, 28),
        provider=second_provider,
    )

    cached_transaction_rate = RateRequirement(date(2024, 1, 15), CurrencyPair("EUR", "USD"))
    fetched_capital_rate = RateRequirement(date(2024, 2, 1), CurrencyPair("GBP", "USD"))
    assert first.cached == [cached_transaction_rate]
    assert first.fetched == [fetched_capital_rate]
    assert first_provider.calls == [(date(2024, 2, 1), CurrencyPair("GBP", "USD"))]
    assert second.cached == [cached_transaction_rate, fetched_capital_rate]
    assert second_provider.calls == []
    assert FX.objects.filter(from_currency="GBP", to_currency="USD").count() == 1


def test_routing_provider_sends_rub_pairs_to_cbr_and_others_to_yahoo():
    from rentals.services.fx_refresh import CurrencyPair, RoutingRateProvider

    yahoo = Provider([Decimal("1.10")])
    cbr = Provider([Decimal("0.0111111111")])
    provider = RoutingRateProvider(yahoo=yahoo, cbr=cbr)

    assert provider.get_rate(as_of=date(2024, 1, 10), pair=CurrencyPair("EUR", "USD")) == Decimal("1.10")
    assert provider.get_rate(as_of=date(2024, 1, 10), pair=CurrencyPair("USD", "RUB")) == Decimal(
        "0.0111111111"
    )
    assert yahoo.calls == [(date(2024, 1, 10), CurrencyPair("EUR", "USD"))]
    assert cbr.calls == [(date(2024, 1, 10), CurrencyPair("RUB", "USD"))]


def test_cbr_provider_returns_direct_multiplier_for_canonical_rub_pairs():
    from rentals.services.fx_refresh import CBRRateProvider, CurrencyPair

    provider = CBRRateProvider(http_post=lambda *args, **kwargs: CBRResponse(), sleep=lambda seconds: None)

    # Stored FX rows use the canonical direct multiplier. USD/RUB canonicalizes
    # to RUB/USD, so CBR's RUB-per-USD quote must be inverted.
    assert provider.get_rate(as_of=date(2024, 1, 10), pair=CurrencyPair("USD", "RUB")) == Decimal(
        "0.0111111111"
    )
    # EUR/RUB canonicalizes to EUR/RUB, matching CBR's RUB-per-EUR direction.
    assert provider.get_rate(as_of=date(2024, 1, 10), pair=CurrencyPair("RUB", "EUR")) == Decimal(
        "100.0000000000"
    )


def test_cbr_provider_retries_transient_errors_and_rate_limits_before_success():
    from rentals.services.fx_refresh import CBRRateProvider, CurrencyPair

    responses = [
        ConnectionError("connection reset by peer"),
        CBRResponse(status_code=429, headers={"Retry-After": "2.5"}),
        CBRResponse(),
    ]
    sleeps = []

    def post(*args, **kwargs):
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    provider = CBRRateProvider(http_post=post, sleep=sleeps.append)
    provider.retry_sleep_seconds = 0.5

    assert provider.get_rate(as_of=date(2024, 1, 10), pair=CurrencyPair("USD", "RUB")) == Decimal(
        "0.0111111111"
    )
    assert responses == []
    assert sleeps == [0.5, 2.5]


def test_cbr_provider_reuses_one_response_for_multiple_pairs_on_same_date():
    from rentals.services.fx_refresh import CBRRateProvider, CurrencyPair

    calls = []

    def post(*args, **kwargs):
        calls.append(kwargs["data"])
        return CBRResponse()

    provider = CBRRateProvider(http_post=post, sleep=lambda seconds: None)

    assert provider.get_rate(as_of=date(2024, 1, 10), pair=CurrencyPair("USD", "RUB")) == Decimal(
        "0.0111111111"
    )
    assert provider.get_rate(as_of=date(2024, 1, 10), pair=CurrencyPair("RUB", "EUR")) == Decimal(
        "100.0000000000"
    )
    assert len(calls) == 1


def test_yahoo_provider_uses_ephemeral_cache_and_walks_back_missing_dates(monkeypatch):
    from rentals.services.fx_refresh import CurrencyPair, YahooRateProvider

    class EmptyData:
        empty = True

    class CloseSeries:
        @property
        def iloc(self):
            return self

        def __getitem__(self, index):
            assert index == 0
            return Decimal("1.20")

    class Data:
        empty = False

        def __getitem__(self, key):
            assert key == "Close"
            return CloseSeries()

    calls = []

    def download(*args, **kwargs):
        calls.append(kwargs)
        return EmptyData() if len(calls) == 1 else Data()

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=download))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    provider = YahooRateProvider()
    provider.lookback_days = 1

    assert provider.get_rate(as_of=date(2024, 1, 1), pair=CurrencyPair("EUR", "USD")) == Decimal("1.20")
    assert os.environ["XDG_CACHE_HOME"] == "/tmp/.cache"
    assert calls[0]["start"] == "2024-01-01"
    assert calls[1]["start"] == "2023-12-31"
    assert calls[0]["auto_adjust"] is False


@pytest.mark.django_db
def test_command_default_runs_gap_scan_not_calendar_refresh(monkeypatch):
    import rentals.management.commands.refresh_fx as command
    from rentals.services.fx_refresh import CurrencyPair, GapRefreshReport, RateRequirement

    seen = {}
    provider = object()
    monkeypatch.setattr(command.timezone, "now", lambda: datetime(2024, 1, 1, 21, 30, tzinfo=dt_timezone.utc))
    monkeypatch.setattr(command, "RoutingRateProvider", lambda: provider)
    monkeypatch.setattr(command, "refresh_rates", lambda **kwargs: pytest.fail("calendar refresh should not run"))

    def capture(**kwargs):
        seen.update(kwargs)
        return GapRefreshReport(
            fetched=[RateRequirement(date(2024, 1, 15), CurrencyPair("EUR", "USD"))]
        )

    monkeypatch.setattr(command, "refresh_missing_rates", capture)

    call_command("refresh_fx")

    assert seen == {
        "target_currencies": None,
        "through": date(2024, 1, 1),
        "provider": provider,
    }


@pytest.mark.django_db
def test_command_default_prints_compact_gap_scan_summary(monkeypatch):
    import rentals.management.commands.refresh_fx as command
    from rentals.services.fx_refresh import CurrencyPair, GapRefreshReport, RateRequirement

    provider = object()
    stdout = StringIO()
    monkeypatch.setattr(command.timezone, "now", lambda: datetime(2024, 1, 1, 21, 30, tzinfo=dt_timezone.utc))
    monkeypatch.setattr(command, "RoutingRateProvider", lambda: provider)
    monkeypatch.setattr(
        command,
        "refresh_missing_rates",
        lambda **kwargs: GapRefreshReport(
            cached=[
                RateRequirement(date(2024, 1, 1), CurrencyPair("EUR", "USD")),
                RateRequirement(date(2024, 1, 2), CurrencyPair("GBP", "USD")),
            ],
            fetched=[RateRequirement(date(2024, 1, 3), CurrencyPair("EUR", "GBP"))],
        ),
    )

    call_command("refresh_fx", stdout=stdout)

    payload = json.loads(stdout.getvalue())
    assert payload == {
        "cached_count": 2,
        "fetched_count": 1,
        "invalid_count": 0,
        "mode": "gap_scan",
        "through": "2024-01-01",
        "unavailable_count": 0,
    }


@pytest.mark.django_db
@pytest.mark.parametrize("option", [{"json_report": True}, {"verbose": True}])
def test_command_explicit_full_output_prints_gap_scan_json(monkeypatch, option):
    import rentals.management.commands.refresh_fx as command
    from rentals.services.fx_refresh import CurrencyPair, GapRefreshReport, RateRequirement

    stdout = StringIO()
    monkeypatch.setattr(command.timezone, "now", lambda: datetime(2024, 1, 1, 21, 30, tzinfo=dt_timezone.utc))
    monkeypatch.setattr(command, "refresh_missing_rates", lambda **kwargs: GapRefreshReport(
        cached=[RateRequirement(date(2024, 1, 1), CurrencyPair("EUR", "USD"))],
        fetched=[RateRequirement(date(2024, 1, 2), CurrencyPair("GBP", "USD"))],
    ))

    call_command("refresh_fx", stdout=stdout, **option)

    payload = json.loads(stdout.getvalue())
    assert payload == {
        "cached": [{"date": "2024-01-01", "pair": "EUR/USD"}],
        "fetched": [{"date": "2024-01-02", "pair": "GBP/USD"}],
        "invalid": [],
        "mode": "gap_scan",
        "through": "2024-01-01",
        "unavailable": [],
    }


@pytest.mark.django_db
def test_command_default_prints_compact_date_pair_summary(monkeypatch):
    import rentals.management.commands.refresh_fx as command
    from rentals.services.fx_refresh import CurrencyPair, RefreshReport

    stdout = StringIO()
    monkeypatch.setattr(command, "refresh_rates", lambda **kwargs: RefreshReport(
        cached=[CurrencyPair("EUR", "USD")],
        fetched=[CurrencyPair("GBP", "USD")],
    ))

    call_command("refresh_fx", as_of="2024-01-05", pair=["EUR/USD"], stdout=stdout)

    payload = json.loads(stdout.getvalue())
    assert payload == {
        "as_of": "2024-01-05",
        "cached_count": 1,
        "fetched_count": 1,
        "invalid_count": 0,
        "mode": "date_pair",
        "unavailable_count": 0,
    }


@pytest.mark.django_db
def test_command_uses_business_timezone_date_and_fails_for_missing_rate(monkeypatch):
    import rentals.management.commands.refresh_fx as command

    seen = {}
    monkeypatch.setattr(command.timezone, "now", lambda: datetime(2024, 1, 1, 21, 30, tzinfo=dt_timezone.utc))
    monkeypatch.setattr(command, "RoutingRateProvider", lambda: Provider([None]))
    real_refresh = command.refresh_rates

    def capture(**kwargs):
        seen["as_of"] = kwargs["as_of"]
        return real_refresh(**kwargs)

    monkeypatch.setattr(command, "refresh_rates", capture)
    with pytest.raises(CommandError):
        call_command("refresh_fx", pair=["EUR/USD"])
    assert seen["as_of"] == date(2024, 1, 1)


def test_command_reports_malformed_date_as_command_error():
    with pytest.raises(CommandError, match="Invalid date"):
        call_command("refresh_fx", as_of="not-a-date", pair=["EUR/USD"])
