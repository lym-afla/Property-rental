"""Shared daily FX resolution and snapshot integrity contract; stdlib only."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import (
    Context, Decimal, DecimalException, DivisionByZero, InvalidOperation,
    Overflow, Underflow, localcontext,
)
from types import MappingProxyType


class ContractError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PathRule:
    parent: str
    coverage_start: date = date(2008, 1, 1)
    coverage_end: date | None = None
    excluded_intervals: tuple = ()
    observed: bool = True


@dataclass(frozen=True)
class Selection:
    effective_date: date
    provisional: bool


@dataclass(frozen=True)
class Resolution:
    multiplier: Decimal
    requested_date: date
    effective_date: date
    provisional: bool
    cacheable: bool
    source_date: date


INITIAL_PATH_RULES = MappingProxyType({
    currency: PathRule('USD' if currency in {'RUB', 'EUR', 'USDT', 'USDC'} else 'EUR',
                       observed=currency not in {'USDT', 'USDC'})
    for currency in ('RUB', 'EUR', 'GBP', 'CHF', 'PLN', 'CNY', 'USDT', 'USDC')
})


def decimal_context(significant_digits=38, fractional_digits=18):
    if type(significant_digits) is not int or significant_digits < 38 or type(fractional_digits) is not int or fractional_digits != 18:
        raise ContractError('invalid_precision', 'Use at least 38 significant digits and 18 places')
    return Context(prec=significant_digits, rounding='ROUND_HALF_UP', Emin=-999999, Emax=999999,
                   capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow, Underflow])


def positive(value, name):
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ContractError('invalid_rate', f'{name} must be a finite positive Decimal')
    return value


def observation_date(value, on):
    if type(value) is not date:
        raise ContractError('invalid_date', 'Observation date must be a calendar date')
    if value > on:
        raise ContractError('future_observation', 'Observation date is after the effective date')
    return value


def multiplier(values, base, quote, *, significant_digits=38, fractional_digits=18):
    if base not in values or quote not in values:
        raise ContractError('missing_rate', f'Missing anchors for {base}/{quote}')
    numerator, denominator = positive(values[quote], quote), positive(values[base], base)
    try:
        with localcontext(decimal_context(significant_digits, fractional_digits)):
            result = (numerator / denominator).quantize(Decimal(1).scaleb(-fractional_digits))
            return positive(result, f'{base}/{quote}')
    except DecimalException as error:
        raise ContractError('unrepresentable_rate', 'Multiplier overflow or underflow') from error


def convert_amount(amount, rate):
    try:
        with localcontext(decimal_context()):
            return amount * positive(rate, 'multiplier')
    except DecimalException as error:
        raise ContractError('unrepresentable_rate', 'Converted amount overflow or underflow') from error


def select_date(requested_date, latest_completed_date):
    if type(requested_date) is not date or (latest_completed_date is not None and type(latest_completed_date) is not date):
        raise ContractError('invalid_date', 'Valuation and completed dates must be calendar dates')
    if latest_completed_date is None:
        return Selection(requested_date, False)
    return Selection(min(requested_date, latest_completed_date), requested_date > latest_completed_date)


def require_applicable(currency, day, *, path_rules=INITIAL_PATH_RULES, root='USD', coverage_start=date(2008, 1, 1)):
    if type(day) is not date:
        raise ContractError('invalid_date', 'Valuation date must be a calendar date')
    if currency != root and currency not in path_rules:
        raise ContractError('unsupported_currency', f'Unsupported currency {currency}')
    if day < coverage_start:
        raise ContractError('before_coverage', f'{currency} predates policy coverage')
    seen, observed = set(), False
    while currency != root:
        if currency in seen or currency not in path_rules:
            raise ContractError('invalid_policy', 'The tree must be connected and acyclic')
        seen.add(currency)
        rule = path_rules[currency]
        if day < rule.coverage_start:
            raise ContractError('before_coverage', f'{currency} predates path coverage')
        if (rule.coverage_end is not None and day > rule.coverage_end) or any(start <= day <= end for start, end in rule.excluded_intervals):
            raise ContractError('outside_applicability', f'{currency} is outside path applicability')
        observed |= rule.observed
        currency = rule.parent
    return observed


def resolve(values, base, quote, requested_date, *, latest_completed_date, business_today,
            observation_dates, statuses=None, max_fiat_age_days=14, path_rules=INITIAL_PATH_RULES,
            root='USD', coverage_start=date(2008, 1, 1), significant_digits=38, fractional_digits=18):
    selection = select_date(requested_date, latest_completed_date)
    if type(business_today) is not date:
        raise ContractError('invalid_date', 'Business date must be a calendar date')
    if latest_completed_date is not None and latest_completed_date >= business_today:
        raise ContractError('invalid_completed_date', 'Latest completed day must precede business today')
    if requested_date > business_today:
        raise ContractError('future_date', 'Valuation date is after business today')
    applicability = dict(path_rules=path_rules, root=root, coverage_start=coverage_start)
    for currency in (base, quote):
        require_applicable(currency, requested_date, **applicability)
    if latest_completed_date is None:
        raise ContractError('missing_rate', 'FX mirror has no release')
    effective = selection.effective_date
    held = any((statuses or {}).get(currency) == 'held' for currency in (base, quote))
    provisional = selection.provisional or held
    for currency in (base, quote):
        observed_path = require_applicable(currency, effective, **applicability)
        observed = observation_dates.get(currency)
        if observed is not None:
            observation_date(observed, effective)
        if not provisional or base == quote or not observed_path:
            continue
        if observed is None:
            raise ContractError('missing_rate', f'Missing observation date for {currency}')
        if (requested_date - observed).days > max_fiat_age_days:
            raise ContractError('stale', f'{currency} path observation exceeds the provisional ceiling')
    rate = multiplier(values, base, quote, significant_digits=significant_digits, fractional_digits=fractional_digits)
    source = min((observation_dates[c] for c in (base, quote) if c in observation_dates), default=effective) if held else effective
    return Resolution(rate, requested_date, effective, provisional, not provisional, source)


def _day(value):
    return value if type(value) is date else date.fromisoformat(value)


def normalize_statuses(values, observation_dates, on, statuses=None, *, hash_version=None):
    version = hash_version if hash_version is not None else (2 if statuses is not None else 1)
    if type(version) is not int or version not in (1, 2):
        raise ValueError('Unsupported snapshot hash version')
    on = _day(on)
    derived = {currency: 'carried' if _day(observation_dates.get(currency, on)) < on else 'completed' for currency in values}
    if statuses is None:
        if version == 2:
            raise ValueError('Missing anchor statuses')
        return derived
    if not isinstance(statuses, Mapping) or set(statuses) != set(values) or any(state not in ('completed', 'carried', 'held') for state in statuses.values()):
        raise ValueError('Invalid anchor statuses')
    if version == 1 and dict(statuses) != derived:
        raise ValueError('Legacy snapshot statuses disagree with observation dates')
    return dict(statuses)


def _encode(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, 'f')
    raise TypeError(type(value).__name__)


def _canonical_snapshot(item):
    canonical = {field: item[field] for field in ('date', 'policy_id', 'policy_hash', 'values', 'observation_ids', 'coverage', 'observation_dates')}
    statuses = normalize_statuses(item['values'], item['observation_dates'], item['date'], item.get('statuses'), hash_version=item.get('hash_version'))
    if item.get('hash_version', 2 if 'statuses' in item else 1) == 2:
        canonical['statuses'] = statuses
    return canonical, statuses


def snapshot_hash(item):
    canonical, _ = _canonical_snapshot(item)
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=True, default=_encode).encode()).hexdigest()


def check_snapshot(item, expected_hash=None):
    try:
        canonical, statuses = _canonical_snapshot(item)
        if list(item['coverage']) != sorted(set(item['coverage'])) or sorted(item['coverage']) != sorted(item['values']):
            raise ValueError('Invalid FX coverage')
        if list(item['observation_ids']) != sorted(set(item['observation_ids'])):
            raise ValueError('Invalid FX observations')
        for currency, value in item['values'].items():
            positive(Decimal(value), currency)
        expected = item['content_hash'] if expected_hash is None else expected_hash
        if snapshot_hash(canonical) != expected:
            raise ValueError('Snapshot hash mismatch')
        return {**item, 'statuses': statuses}
    except (KeyError, TypeError, DecimalException) as error:
        raise ValueError('Invalid FX snapshot') from error
