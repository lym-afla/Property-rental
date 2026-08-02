"""Deterministic, scheduled-only acquisition of foreign-exchange rates."""

import calendar
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Callable, Collection, Iterable, Protocol, Sequence

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rentals.constants import CURRENCY_CHOICES
from rentals.models import (
    FX,
    Lease_rent,
    Property_capital_structure,
    Tenant,
    Transaction,
)


logger = logging.getLogger(__name__)
RATE_QUANTUM = Decimal("0.0000000001")


@dataclass(frozen=True, order=True)
class CurrencyPair:
    """Canonical FX identity.

    ``FX.rate`` is the direct multiplier from ``from_currency`` to
    ``to_currency`` after this canonicalization. The pair is ordered only for
    uniqueness; callers that need the reverse direction rely on
    ``rentals.services.fx.get_rate`` dividing by the stored rate.
    """

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


@dataclass(frozen=True, order=True)
class RateRequirement:
    effective_date: date
    pair: CurrencyPair


@dataclass
class RefreshReport:
    cached: list[CurrencyPair] = field(default_factory=list)
    fetched: list[CurrencyPair] = field(default_factory=list)
    unavailable: list[CurrencyPair] = field(default_factory=list)
    invalid: list[CurrencyPair] = field(default_factory=list)


@dataclass
class GapRefreshReport:
    cached: list[RateRequirement] = field(default_factory=list)
    fetched: list[RateRequirement] = field(default_factory=list)
    unavailable: list[RateRequirement] = field(default_factory=list)
    invalid: list[RateRequirement] = field(default_factory=list)


def _supported_currency_codes() -> tuple[str, ...]:
    return tuple(code for code, _label in CURRENCY_CHOICES)


def _normalized_currency_codes(currencies: Iterable[str] | None) -> tuple[str, ...]:
    raw_codes = currencies if currencies is not None else _supported_currency_codes()
    codes = []
    for code in raw_codes:
        normalized = (code or "").strip().upper()
        if len(normalized) != 3:
            raise ValueError(f"invalid currency code: {code!r}")
        if normalized not in codes:
            codes.append(normalized)
    return tuple(codes)


def _add_currency_requirements(
    requirements: set[RateRequirement],
    *,
    effective_date: date | None,
    source_currency: str | None,
    target_currencies: Sequence[str],
) -> None:
    if effective_date is None:
        return
    source = (source_currency or "").strip().upper()
    if len(source) != 3:
        return
    for target in target_currencies:
        if source == target:
            continue
        requirements.add(RateRequirement(effective_date, CurrencyPair(source, target)))


def _next_month(month: date) -> date:
    if month.month == 12:
        return month.replace(year=month.year + 1, month=1)
    return month.replace(month=month.month + 1)


def _tenant_due_dates(tenant: Tenant, end: date):
    month = tenant.lease_start.replace(day=1)
    final_month = end.replace(day=1)
    if tenant.lease_end is not None:
        final_month = min(final_month, tenant.lease_end.replace(day=1))
    while month <= final_month:
        payday = tenant.payday or tenant.lease_start.day
        payday = min(payday, calendar.monthrange(month.year, month.month)[1])
        due_date = month.replace(day=payday)
        if (
            tenant.lease_start <= due_date <= end
            and (tenant.lease_end is None or due_date <= tenant.lease_end)
        ):
            yield due_date
        month = _next_month(month)


def _effective_rent(rent_history: Sequence[Lease_rent], due_date: date) -> Lease_rent | None:
    rate = None
    for candidate in rent_history:
        if candidate.date_rent_set > due_date:
            break
        rate = candidate
    return rate


def discover_rate_requirements(
    *,
    target_currencies: Iterable[str] | None = None,
    through: date | None = None,
) -> tuple[RateRequirement, ...]:
    """Derive missing-rate candidates from dated monetary business records.

    The scheduled production command uses this scan instead of asking providers
    for today's calendar rates. Each run re-derives the full historical set
    through the supplied business date, making the refresh idempotent and able
    to fill gaps introduced by imports or provider outages.
    """

    through = through or timezone.localdate(timezone.now())
    targets = _normalized_currency_codes(target_currencies)
    requirements: set[RateRequirement] = set()

    for transaction_date, currency in (
        Transaction.objects.filter(date__lte=through)
        .exclude(currency__isnull=True)
        .exclude(currency="")
        .values_list("date", "currency")
    ):
        _add_currency_requirements(
            requirements,
            effective_date=transaction_date,
            source_currency=currency,
            target_currencies=targets,
        )

    capital_rows = (
        Property_capital_structure.objects.filter(capital_structure_date__lte=through)
        .filter(
            Q(capital_structure_value__isnull=False)
            | Q(capital_structure_debt__isnull=False)
        )
        .exclude(property__currency__isnull=True)
        .exclude(property__currency="")
        .values_list("capital_structure_date", "property__currency")
    )
    for capital_date, property_currency in capital_rows:
        _add_currency_requirements(
            requirements,
            effective_date=capital_date,
            source_currency=property_currency,
            target_currencies=targets,
        )

    for rent_set_date, currency in (
        Lease_rent.objects.filter(date_rent_set__lte=through)
        .exclude(currency__isnull=True)
        .exclude(currency="")
        .values_list("date_rent_set", "currency")
    ):
        _add_currency_requirements(
            requirements,
            effective_date=rent_set_date,
            source_currency=currency,
            target_currencies=targets,
        )

    tenants = (
        Tenant.objects.filter(lease_start__lte=through)
        .prefetch_related("rent_history")
        .order_by("id")
    )
    for tenant in tenants:
        rent_history = tuple(
            sorted(
                tenant.rent_history.all(),
                key=lambda row: (row.date_rent_set, row.id or 0),
            )
        )
        if not rent_history:
            continue
        for due_date in _tenant_due_dates(tenant, through):
            rent = _effective_rent(rent_history, due_date)
            if rent is None:
                continue
            _add_currency_requirements(
                requirements,
                effective_date=due_date,
                source_currency=rent.currency,
                target_currencies=targets,
            )

    return tuple(sorted(requirements))


def _coerce_provider_rate(raw_rate):
    try:
        rate = Decimal(str(raw_rate))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not rate.is_finite() or rate <= 0:
        return None
    return rate


def _valid_cached_rate_exists(*, effective_date: date, pair: CurrencyPair) -> bool:
    return FX.objects.filter(
        date=effective_date,
        from_currency=pair.from_currency,
        to_currency=pair.to_currency,
        rate__gt=0,
    ).exists()


def refresh_rates(*, as_of: date, pairs: Collection[CurrencyPair], provider: RateProvider) -> RefreshReport:
    report = RefreshReport()
    for pair in dict.fromkeys(CurrencyPair(p.from_currency, p.to_currency) for p in pairs):
        identity = dict(date=as_of, from_currency=pair.from_currency, to_currency=pair.to_currency)
        if _valid_cached_rate_exists(effective_date=as_of, pair=pair):
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
        rate = _coerce_provider_rate(raw_rate)
        if rate is None:
            report.invalid.append(pair)
            continue
        with transaction.atomic():
            FX.objects.update_or_create(**identity, defaults={"rate": rate})
        report.fetched.append(pair)
    return report


def refresh_missing_rates(
    *,
    target_currencies: Iterable[str] | None = None,
    through: date | None = None,
    provider: RateProvider,
) -> GapRefreshReport:
    report = GapRefreshReport()
    for requirement in discover_rate_requirements(
        target_currencies=target_currencies,
        through=through,
    ):
        pair = requirement.pair
        effective_date = requirement.effective_date
        identity = dict(
            date=effective_date,
            from_currency=pair.from_currency,
            to_currency=pair.to_currency,
        )
        if _valid_cached_rate_exists(effective_date=effective_date, pair=pair):
            report.cached.append(requirement)
            continue
        try:
            raw_rate = provider.get_rate(as_of=effective_date, pair=pair)
        except Exception:
            logger.exception(
                "FX provider failed for %s/%s on %s",
                pair.from_currency,
                pair.to_currency,
                effective_date,
            )
            report.unavailable.append(requirement)
            continue
        if raw_rate is None:
            report.unavailable.append(requirement)
            continue
        rate = _coerce_provider_rate(raw_rate)
        if rate is None:
            report.invalid.append(requirement)
            continue
        with transaction.atomic():
            FX.objects.update_or_create(**identity, defaults={"rate": rate})
        report.fetched.append(requirement)
    return report


class RoutingRateProvider:
    """Route RUB pairs to CBR and all other supported pairs to Yahoo."""

    def __init__(
        self,
        *,
        yahoo: RateProvider | None = None,
        cbr: RateProvider | None = None,
    ):
        self.yahoo = yahoo or YahooRateProvider()
        self.cbr = cbr or CBRRateProvider()

    def get_rate(self, *, as_of: date, pair: CurrencyPair):
        provider = (
            self.cbr
            if "RUB" in (pair.from_currency, pair.to_currency)
            else self.yahoo
        )
        return provider.get_rate(as_of=as_of, pair=pair)


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


class CBRRateProvider:
    """Central Bank of Russia SOAP adapter for RUB-related pairs.

    CBR publishes foreign-currency quotes as RUB per nominal foreign unit.
    This adapter converts that provider convention into the rental app's
    canonical stored convention: a direct multiplier from
    ``pair.from_currency`` to ``pair.to_currency``.
    """

    endpoint = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
    timeout_seconds = 10
    max_attempts = 3
    lookback_days = 7
    retry_sleep_seconds = 1

    def __init__(
        self,
        *,
        http_post: Callable | None = None,
        sleep: Callable[[float], None] | None = None,
    ):
        if http_post is None:
            import requests

            http_post = requests.post
        self.http_post = http_post
        self.sleep = sleep or time.sleep

    def get_rate(self, *, as_of: date, pair: CurrencyPair):
        if "RUB" not in (pair.from_currency, pair.to_currency):
            return None

        foreign_currency = (
            pair.to_currency if pair.from_currency == "RUB" else pair.from_currency
        )
        if foreign_currency == "RUB":
            return None

        for offset in range(self.lookback_days + 1):
            lookup_date = as_of - timedelta(days=offset)
            rub_per_foreign = self._fetch_rub_per_foreign(
                as_of=lookup_date,
                foreign_currency=foreign_currency,
            )
            if rub_per_foreign is None:
                continue
            if pair.to_currency == "RUB":
                return rub_per_foreign.quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)
            return (Decimal("1") / rub_per_foreign).quantize(
                RATE_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
        return None

    def _fetch_rub_per_foreign(self, *, as_of: date, foreign_currency: str) -> Decimal | None:
        payload = _cbr_soap_payload(as_of)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "http://web.cbr.ru/GetCursOnDate",
            "User-Agent": "property-rental-fx-refresh/1.0",
        }
        for attempt in range(self.max_attempts):
            try:
                response = self.http_post(
                    self.endpoint,
                    data=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except Exception:
                logger.exception("CBR FX request failed for %s", as_of)
                return None

            status_code = getattr(response, "status_code", None)
            if status_code == 429 and attempt < self.max_attempts - 1:
                self.sleep(self.retry_sleep_seconds * (attempt + 1))
                continue
            if status_code != 200:
                logger.warning(
                    "CBR FX request returned HTTP %s for %s",
                    status_code,
                    as_of,
                )
                return None

            text = getattr(response, "text", "")
            return _parse_cbr_rate(text, foreign_currency)
        return None


def _cbr_soap_payload(as_of: date) -> str:
    formatted_date = as_of.strftime("%Y-%m-%dT00:00:00")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetCursOnDate xmlns="http://web.cbr.ru/">
      <On_date>{formatted_date}</On_date>
    </GetCursOnDate>
  </soap:Body>
</soap:Envelope>"""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(node: ET.Element, name: str) -> str | None:
    for child in node:
        if _local_name(child.tag) == name:
            return child.text
    return None


def _parse_cbr_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value.strip().replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return parsed


def _parse_cbr_rate(xml_text: str, foreign_currency: str) -> Decimal | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("CBR FX response was not valid XML")
        return None

    target = foreign_currency.strip().upper()
    for element in root.iter():
        if _local_name(element.tag) != "ValuteCursOnDate":
            continue
        code = (_child_text(element, "VchCode") or "").strip().upper()
        if code != target:
            continue
        nominal = _parse_cbr_decimal(_child_text(element, "Vnom"))
        value = _parse_cbr_decimal(_child_text(element, "Vcurs"))
        if nominal is None or value is None:
            return None
        return value / nominal
    return None
