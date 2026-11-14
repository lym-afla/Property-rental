from datetime import date
from decimal import Decimal

import pytest

from rentals.analytics.cash_flow import expense_drivers, portfolio_cash_flow
from rentals.analytics.filters import AnalyticsFilters, Grain
from rentals.analytics.pnl import profit_and_loss
from rentals.analytics.portfolio import portfolio_summary
from rentals.financial_semantics import normalize_transaction_amount, revenue_cost_deltas
from rentals.models import Loan, Transaction
from rentals.services.financials import pnl_calc
from rentals.tests.factories import TenantFactory, TransactionFactory

pytestmark = pytest.mark.django_db
END = date(2026, 1, 31)


def filters_for():
    return AnalyticsFilters(
        start=date(2026, 1, 1), end=END, grain=Grain.MONTH,
        currency="USD", comparison=None, property_ids=(),
    )


@pytest.fixture
def repayment(sample_property):
    loan = Loan.objects.create(
        property=sample_property, lender="Bank", currency="USD", start_date=date(2026, 1, 1),
    )
    for category, amount in (("rent", "1000"), ("loan_interest", "120"), ("loan_principal", "300")):
        TransactionFactory(
            property=sample_property, category=category, amount=Decimal(amount),
            currency="USD", date=date(2026, 1, 10),
            loan=loan if category.startswith("loan_") else None,
        )


@pytest.mark.parametrize("category", ["loan_interest", "loan_principal"])
def test_loan_components_store_positive_paid_amounts(category):
    assert normalize_transaction_amount(category, Decimal("-120")) == Decimal("120")


def test_principal_has_no_revenue_or_cost_effect():
    assert revenue_cost_deltas("loan_principal", Decimal("300"), "expense") == (0, 0)


def test_pnl_counts_only_interest(landlord_user, repayment):
    result = profit_and_loss(landlord_user, END, "USD")
    assert "loan_principal" not in result.rows_by_key
    assert result.rows_by_key["loan_interest"].values == {"2026": -120}
    assert result.total_expenses == {"2026": -120}
    assert result.net_income == {"2026": 880}


def test_portfolio_costs_exclude_principal(landlord_user, repayment):
    result = portfolio_summary(landlord_user, filters_for())
    assert result.costs == 120
    assert result.net_income == 880


def test_cash_flow_includes_principal_without_changing_profit(landlord_user, repayment):
    result = portfolio_cash_flow(landlord_user, filters_for())
    point = result.points[0]
    assert point["loan_principal"] == -300
    assert point["loan_interest"] == -120
    assert point["total_expenses"] == -120
    assert point["net_income"] == 880
    assert point["cumulative_net_income"] == 880
    assert point["net_cash_flow"] == 580
    assert dict((series.key, series.kind) for series in result.series)["loan_principal"] == "balance_sheet"


def test_cash_flow_combines_principal_and_deposits(landlord_user, sample_property, repayment):
    from rentals.services.deposits import create_movement

    tenant = TenantFactory(property=sample_property, lease_start=date(2026, 1, 1))
    create_movement(tenant, date=date(2026, 1, 5), kind="received", currency="USD", amount=Decimal("500"))
    point = portfolio_cash_flow(landlord_user, filters_for()).points[0]
    assert point["deposits"] == 500
    assert point["net_cash_flow"] == 1080
    assert point["net_income"] == 880


def test_expense_drivers_exclude_principal(landlord_user, repayment):
    result = expense_drivers(landlord_user, filters_for())
    assert [series.key for series in result.series] == ["loan_interest"]
    assert result.points[0]["loan_interest"] == -120


def test_legacy_financials_counts_interest_as_negative_cost(sample_property, repayment):
    assert Transaction.financials(
        END, target_currency="USD", properties=[sample_property], transaction_type="expense",
    ) == Decimal("-120")
    assert Transaction.financials(
        END, target_currency="USD", properties=[sample_property],
    ) == Decimal("880")


@pytest.mark.parametrize("convert_currency", [False, True])
def test_legacy_pnl_excludes_principal_and_signs_interest(sample_property, repayment, convert_currency):
    expenses, rent_ytd, rent_all_time, categories = pnl_calc(
        [sample_property], "USD", convert_currency, 2, as_of=END,
    )
    assert "loan_principal" not in categories
    assert expenses["Loan interest"] == {"ytd": -120, "all_time": -120}
    assert expenses["total"] == {"ytd": -120, "all_time": -120}
    assert rent_ytd == rent_all_time == 1000


@pytest.mark.parametrize("with_deposit", [False, True])
def test_cumulative_cash_includes_principal_across_periods(
    landlord_user, sample_property, repayment, with_deposit,
):
    from dataclasses import replace
    from rentals.services.deposits import create_movement

    loan = sample_property.loans.get()
    TransactionFactory(
        property=sample_property, loan=loan, category="loan_principal",
        amount=Decimal("200"), currency="USD", date=date(2026, 2, 10),
    )
    if with_deposit:
        tenant = TenantFactory(property=sample_property, lease_start=date(2026, 1, 1))
        create_movement(
            tenant, date=date(2026, 1, 5), kind="received",
            currency="USD", amount=Decimal("500"),
        )
    result = portfolio_cash_flow(
        landlord_user, replace(filters_for(), end=date(2026, 2, 28)),
    )
    jan, feb = result.points
    assert jan["cumulative_net_cash_flow"] == (1080 if with_deposit else 580)
    assert feb["cumulative_net_cash_flow"] == (880 if with_deposit else 380)
    assert feb["net_cash_flow"] == -200
    assert jan["cumulative_net_income"] == feb["cumulative_net_income"] == 880
    assert next(
        series.kind for series in result.series if series.key == "cumulative_net_cash_flow"
    ) == "cumulative_cash"
