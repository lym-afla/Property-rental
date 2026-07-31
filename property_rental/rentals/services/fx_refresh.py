"""Deterministic, scheduled-only acquisition of foreign-exchange rates."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Collection, Protocol

from django.db import transaction

from rentals.models import FX


@dataclass(frozen=True, order=True)
class CurrencyPair:
    from_currency: str
    to_currency: str

    def __post_init__(self):
        left = self.from_currency.strip().upper()
        right = self.to_currency.strip().upper()
        if len(left) != 3 or len(right) != 3 or left == right:
            raise ValueError("currency pairs require two distinct three-letter codes")
        left, right = sorted((left, right))
        object.__setattr__(self, "from_currency", left)
        object.__setattr__(self, "to_currency", right)


class RateProvider(Protocol):
    def get_rate(self, *, as_of: date, pair: CurrencyPair): ...


@dataclass
class RefreshReport:
    cached: list[CurrencyPair] = field(default_factory=list)
    fetched: list[CurrencyPair] = field(default_factory=list)
    unavailable: list[CurrencyPair] = field(default_factory=list)
    invalid: list[CurrencyPair] = field(default_factory=list)


def refresh_rates(*, as_of: date, pairs: Collection[CurrencyPair], provider: RateProvider) -> RefreshReport:
    report = RefreshReport()
    for pair in dict.fromkeys(CurrencyPair(p.from_currency, p.to_currency) for p in pairs):
        identity = dict(date=as_of, from_currency=pair.from_currency, to_currency=pair.to_currency)
        if FX.objects.filter(**identity, rate__gt=0).exists():
            report.cached.append(pair)
            continue
        try:
            raw_rate = provider.get_rate(as_of=as_of, pair=pair)
        except Exception:
            report.unavailable.append(pair)
            continue
        if raw_rate is None:
            report.unavailable.append(pair)
            continue
        try:
            rate = Decimal(str(raw_rate))
        except (InvalidOperation, TypeError, ValueError):
            report.invalid.append(pair)
            continue
        if not rate.is_finite() or rate <= 0:
            report.invalid.append(pair)
            continue
        with transaction.atomic():
            FX.objects.update_or_create(**identity, defaults={"rate": rate})
        report.fetched.append(pair)
    return report


class YahooRateProvider:
    """Yahoo adapter with a finite request timeout and no internal retry loop."""

    timeout_seconds = 10

    def get_rate(self, *, as_of: date, pair: CurrencyPair):
        import yfinance as yf

        data = yf.download(
            f"{pair.from_currency}{pair.to_currency}=X",
            start=as_of.isoformat(),
            end=(as_of + timedelta(days=1)).isoformat(),
            progress=False,
            timeout=self.timeout_seconds,
        )
        if data.empty:
            return None
        close = data["Close"].iloc[0]
        return close.iloc[0] if hasattr(close, "iloc") else close
