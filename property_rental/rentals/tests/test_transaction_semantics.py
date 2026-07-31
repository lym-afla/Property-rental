"""Tests for canonical transaction category/sign semantics."""

from datetime import date
from decimal import Decimal

import pytest

from rentals.financial_semantics import (
    category_kind,
    normalize_transaction_amount,
    revenue_cost_deltas,
    signed_analytics_amount,
)
from rentals.tests.factories import PropertyFactory, TransactionFactory


@pytest.mark.parametrize(
    ("category", "amount", "expected"),
    [
        ("tax", Decimal("250.00"), Decimal("-250.00")),
        ("tax", Decimal("-250.00"), Decimal("-250.00")),
        ("cost_reimbursement", Decimal("250.00"), Decimal("250.00")),
        ("cost_reimbursement", Decimal("-250.00"), Decimal("250.00")),
    ],
)
def test_normalize_transaction_amount_for_expense_categories(category, amount, expected):
    assert normalize_transaction_amount(category, amount) == expected


@pytest.mark.django_db
def test_transaction_save_keeps_cost_reimbursement_positive_expense():
    property_ = PropertyFactory()

    transaction = TransactionFactory(
        property=property_,
        category="cost_reimbursement",
        amount=Decimal("-125.50"),
        date=date(2026, 7, 1),
    )

    transaction.refresh_from_db()
    assert transaction.type == "expense"
    assert transaction.amount == Decimal("125.50")


@pytest.mark.django_db
def test_transaction_save_makes_cost_category_negative_regardless_of_entered_sign():
    property_ = PropertyFactory()

    transaction = TransactionFactory(
        property=property_,
        category="utilities",
        amount=Decimal("75.00"),
        date=date(2026, 7, 1),
    )

    transaction.refresh_from_db()
    assert transaction.type == "expense"
    assert transaction.amount == Decimal("-75.00")


def test_cost_reimbursement_is_positive_expense_section_entry():
    assert category_kind("cost_reimbursement") == "expense"
    assert signed_analytics_amount(
        "cost_reimbursement", Decimal("-250.00"), "expense"
    ) == 250.0
    revenue, costs = revenue_cost_deltas(
        "cost_reimbursement", Decimal("-250.00"), "expense"
    )
    assert revenue == 0.0
    assert costs == -250.0
