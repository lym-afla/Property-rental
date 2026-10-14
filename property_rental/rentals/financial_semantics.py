"""Canonical category roles and signed-value helpers for transactions."""

from decimal import Decimal

from rentals.constants import INCOME_CATEGORIES, TRANSACTION_CATEGORIES

TRANSACTION_CATEGORY_KEYS = tuple(key for key, _label in TRANSACTION_CATEGORIES)
CONTRA_EXPENSE_CATEGORIES = ("cost_reimbursement",)


def _decimal_abs(value: Decimal) -> Decimal:
    return value.copy_abs()


def category_kind(category: str, stored_type: str | None = None) -> str:
    if category in INCOME_CATEGORIES:
        return "income"
    if category in TRANSACTION_CATEGORY_KEYS:
        return "expense"
    return "income" if stored_type == "income" else "expense"


def normalize_transaction_amount(category: str, amount: Decimal) -> Decimal:
    if category in CONTRA_EXPENSE_CATEGORIES:
        return _decimal_abs(amount)
    if category in INCOME_CATEGORIES:
        return amount
    return -_decimal_abs(amount)


def signed_analytics_amount(
    category: str,
    amount: object,
    stored_type: str | None = None,
) -> float:
    value = float(amount)
    kind = category_kind(category, stored_type)
    if kind == "income":
        return value
    if category in CONTRA_EXPENSE_CATEGORIES:
        return abs(value)
    return -abs(value)


def revenue_cost_deltas(
    category: str,
    amount: object,
    stored_type: str | None = None,
) -> tuple[float, float]:
    kind = category_kind(category, stored_type)
    signed = signed_analytics_amount(category, amount, stored_type)
    if kind == "income":
        return signed, 0.0
    return 0.0, -signed


def deposit_signed_amount(kind: str, amount: Decimal) -> Decimal:
    """Signed effect of a deposit movement on the deposit liability.

    Balance-sheet only: deposits are not transactions and never reach
    ``category_kind()``. received raises the liability; returned and applied
    lower it.
    """
    if kind == "received":
        return amount
    if kind in ("returned", "applied"):
        return -amount
    raise ValueError(f"Unknown deposit movement kind: {kind!r}")
