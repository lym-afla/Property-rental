# UX Review Follow-up Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved second-round UX review fixes while keeping cost reimbursement as a positive expense-section contra-expense.

**Architecture:** Backend financial semantics remain canonical: Django owns transaction sign normalization, category roles, P&L row construction, yield formulas, valuation start-point interpolation, and tenant FX conversion. React owns display labels, chart/table rendering, accessible controls, responsive behavior, and tooltip filtering without reclassifying financial data.

**Tech Stack:** Python 3.11+, Django 4.2, Django REST Framework, uv, pytest/pytest-django, React 19, TypeScript 6, Vite 8, TanStack Query 5, Recharts 3, shadcn UI, Zod 4, Vitest/Testing Library.

## Global Constraints

- Work only in `D:\Developing\Property-rental\.worktrees\ux-review-followup-20260731` on branch `ux-review-followup-20260731`.
- Cost reimbursement stays in the expense section.
- Cost reimbursement is positive and reduces total expenses.
- Cost reimbursement does not increase revenue.
- Ordinary cost categories save as negative regardless of the sign typed by the user.
- Yield formulas use the same annualized net-income numerator and different denominators.
- The literal `(i)` control becomes a proper circular information affordance.
- Valuation debt defaults to `0` when omitted.
- Sparse valuation timelines use real linear time spacing, not equally spaced categories.
- Tenant rent performance remains in the tenant/property native currency.
- All touched controls keep at least 44px touch targets.
- Negative numbers continue to use accounting format with the currency symbol inside brackets, for example `(£1,234)`.
- Use `uv run` for backend commands.
- Do not make production-deployment changes in this worktree.

---

## Planned File Structure

### Backend

- Create `property_rental/rentals/financial_semantics.py` — shared transaction category role, amount normalization, and analytics signing helpers.
- Create `property_rental/rentals/migrations/0023_normalize_cost_reimbursement_signs.py` — normalize existing reimbursement rows to positive amounts while keeping `type='expense'`.
- Modify `property_rental/rentals/models.py` — use shared helpers in `Transaction.save`.
- Modify `property_rental/rentals/analytics/pnl.py` — remove duplicate YTD column, order rows, and handle positive contra-expense reimbursement.
- Modify `property_rental/rentals/analytics/portfolio.py` — use shared revenue/cost deltas and redefine yield numerator.
- Modify `property_rental/rentals/analytics/property.py` — support optional `start`, interpolated/carried-forward start points, and richer point statuses.
- Modify `property_rental/rentals/analytics/tenant.py` only if RUB/GBP regression tests expose a converter-direction bug.
- Modify `property_rental/rentals/api/serializers.py` — default omitted/blank valuation debt to `0`.
- Modify `property_rental/rentals/api/analytics_views.py` — accept `start` on property valuation analytics.
- Modify `property_rental/rentals/api/analytics_serializers.py` — allow valuation point statuses `interpolated` and `carried_forward`.
- Test with `property_rental/rentals/tests/test_transaction_semantics.py`, `test_api.py`, `test_analytics_pnl.py`, `test_analytics_portfolio.py`, `test_analytics_property.py`, and `test_analytics_tenant.py`.

### Frontend

- Modify `frontend/src/types/analytics.ts` — allow valuation point statuses `interpolated` and `carried_forward`.
- Modify `frontend/src/api/analytics.ts` and `frontend/src/api/keys.ts` — add optional `start` for property valuation analytics.
- Modify `frontend/src/components/analytics/ProfitLossTable.tsx` — render the server order and add a visual gap after `Total revenue`.
- Modify `frontend/src/components/analytics/FinancialDefinitions.tsx` — render circular info affordance and updated yield definitions.
- Modify `frontend/src/features/dashboard/charts/YieldComparisonChart.tsx` — filter non-informative tooltip rows.
- Modify `frontend/src/components/forms/PropertyValuationForm.tsx` — labels and blank debt normalization.
- Modify `frontend/src/features/property/ValuationChart.tsx` — remove subtitle text and pad linear time domain.
- Modify `frontend/src/features/tenant/RentPerformanceChart.tsx` only if chart tests show patterned/dashed mark behavior remains.
- Test with existing focused Vitest files plus a new `frontend/src/components/forms/PropertyValuationForm.test.tsx` if no form test exists.

---

### Task 1: Canonical Transaction Semantics and Cost-Reimbursement Migration

**Files:**
- Create: `property_rental/rentals/financial_semantics.py`
- Create: `property_rental/rentals/migrations/0023_normalize_cost_reimbursement_signs.py`
- Create: `property_rental/rentals/tests/test_transaction_semantics.py`
- Modify: `property_rental/rentals/models.py`
- Modify: `property_rental/rentals/tests/test_api.py`

**Interfaces:**
- Produces: `CONTRA_EXPENSE_CATEGORIES: tuple[str, ...]`
- Produces: `category_kind(category: str, stored_type: str | None = None) -> str`
- Produces: `normalize_transaction_amount(category: str, amount: Decimal) -> Decimal`
- Produces: `signed_analytics_amount(category: str, amount: object, stored_type: str | None = None) -> float`
- Produces: `revenue_cost_deltas(category: str, amount: object, stored_type: str | None = None) -> tuple[float, float]`
- Consumed by P&L and portfolio analytics in Tasks 2 and 3.

- [ ] **Step 1: Write model-level sign-normalization tests**

Add this file:

```python
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
```

- [ ] **Step 2: Add API-level serializer/viewset coverage**

In `property_rental/rentals/tests/test_api.py`, extend the transaction serializer or viewset tests with:

```python
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("category", "submitted", "stored", "stored_type"),
    [
        ("utilities", "75.00", Decimal("-75.00"), "expense"),
        ("utilities", "-75.00", Decimal("-75.00"), "expense"),
        ("cost_reimbursement", "75.00", Decimal("75.00"), "expense"),
        ("cost_reimbursement", "-75.00", Decimal("75.00"), "expense"),
    ],
)
def test_transaction_api_normalizes_cost_signs(
    auth_client, sample_property, category, submitted, stored, stored_type
):
    response = auth_client.post(
        "/api/v1/transactions/",
        {
            "date": "2026-07-15",
            "property": sample_property.id,
            "tenant": None,
            "category": category,
            "period": "2026-07",
            "currency": "USD",
            "amount": submitted,
            "comment": "",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert Decimal(body["amount"]) == stored
    assert body["type"] == stored_type
```

- [ ] **Step 3: Run focused tests and confirm failure before implementation**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_transaction_semantics.py property_rental/rentals/tests/test_api.py::test_transaction_api_normalizes_cost_signs -q
```

Expected before implementation: imports fail because `rentals.financial_semantics` does not exist, or assertions fail because `Transaction.save` does not normalize signs.

- [ ] **Step 4: Implement shared financial semantics**

Create `property_rental/rentals/financial_semantics.py`:

```python
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
```

- [ ] **Step 5: Wire `Transaction.save` to the shared helpers**

In `property_rental/rentals/models.py`, replace the current transaction type/amount logic:

```python
from .financial_semantics import category_kind, normalize_transaction_amount
```

Then update `Transaction.save`:

```python
def save(self, *args, **kwargs):
    self.type = category_kind(self.category)
    self.amount = normalize_transaction_amount(self.category, self.amount)
    self.comment = "–" if not self.comment else self.comment
    super(Transaction, self).save(*args, **kwargs)
```

- [ ] **Step 6: Add data migration for existing reimbursements**

Create `property_rental/rentals/migrations/0023_normalize_cost_reimbursement_signs.py`:

```python
from decimal import Decimal

from django.db import migrations


def normalize_cost_reimbursements(apps, schema_editor):
    Transaction = apps.get_model("rentals", "Transaction")
    for transaction in Transaction.objects.filter(category="cost_reimbursement"):
        transaction.amount = abs(transaction.amount or Decimal("0"))
        transaction.type = "expense"
        transaction.save(update_fields=["amount", "type"])


def reverse_normalize_cost_reimbursements(apps, schema_editor):
    Transaction = apps.get_model("rentals", "Transaction")
    Transaction.objects.filter(category="cost_reimbursement").update(type="expense")


class Migration(migrations.Migration):
    dependencies = [
        ("rentals", "0022_migrate_legacy_other_income"),
    ]

    operations = [
        migrations.RunPython(
            normalize_cost_reimbursements,
            reverse_normalize_cost_reimbursements,
        ),
    ]
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_transaction_semantics.py property_rental/rentals/tests/test_api.py::test_transaction_api_normalizes_cost_signs -q
```

Expected after implementation: all selected tests pass.

- [ ] **Step 8: Run migration and API smoke tests**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_migration_command.py property_rental/rentals/tests/test_api.py -q
```

Expected: all selected tests pass. If existing `test_api.py` assertions expected non-normalized signs, update those expectations to the canonical behavior from this task.

- [ ] **Step 9: Commit Task 1**

Run:

```powershell
git add property_rental/rentals/financial_semantics.py property_rental/rentals/models.py property_rental/rentals/migrations/0023_normalize_cost_reimbursement_signs.py property_rental/rentals/tests/test_transaction_semantics.py property_rental/rentals/tests/test_api.py
git commit -m "fix: normalize transaction category signs"
```

### Task 2: Backend P&L Columns, Ordering, and Contra-Expense Totals

**Files:**
- Modify: `property_rental/rentals/analytics/pnl.py`
- Modify: `property_rental/rentals/tests/test_analytics_pnl.py`
- Modify: `frontend/src/components/analytics/ProfitLossTable.tsx`
- Modify: `frontend/src/components/analytics/ProfitLossTable.test.tsx`

**Interfaces:**
- Consumes: `category_kind` and `signed_analytics_amount` from `rentals.financial_semantics`.
- Produces: P&L response with no standalone `ytd` column.
- Produces: current-year column label such as `2026YTD`.
- Produces: backend row order `income rows`, `total_revenue`, `expense rows`, `total_expenses`, `net_income`.

- [ ] **Step 1: Update backend P&L tests for columns and row order**

In `property_rental/rentals/tests/test_analytics_pnl.py`, update `test_profit_and_loss_builds_reconciling_annual_and_ytd_columns`:

```python
assert [column.key for column in result.columns] == ["2023", "2024", "2025"]
assert [column.label for column in result.columns] == ["2023", "2024", "2025YTD"]
assert result.columns[-1].start == date(2025, 1, 1)
assert result.columns[-1].end == date(2025, 7, 30)
assert result.rows_by_key["rent"].values["2025"] == pytest.approx(7_000)
assert [row.key for row in result.rows] == [
    "rent",
    "total_revenue",
    "capex",
    "tax",
    "management",
    "total_expenses",
    "net_income",
]
```

Update the property-scope loop:

```python
for key in ("2023", "2024", "2025"):
    assert result.total_revenue[key] + result.total_expenses[key] == pytest.approx(
        result.net_income[key]
    )
```

- [ ] **Step 2: Add a contra-expense P&L test**

Append:

```python
@pytest.mark.django_db
def test_profit_and_loss_keeps_cost_reimbursement_as_positive_expense(
    landlord_user,
):
    property_ = PropertyFactory(owned_by=landlord_user.landlord)
    TransactionFactory(
        property=property_,
        category="rent",
        amount=Decimal("1000.00"),
        date=date(2026, 1, 1),
    )
    TransactionFactory(
        property=property_,
        category="tax",
        amount=Decimal("-300.00"),
        date=date(2026, 1, 2),
    )
    TransactionFactory(
        property=property_,
        category="cost_reimbursement",
        amount=Decimal("-125.00"),
        date=date(2026, 1, 3),
    )

    result = profit_and_loss(
        landlord_user,
        end=date(2026, 7, 31),
        currency="USD",
    )

    assert result.rows_by_key["cost_reimbursement"].kind == "expense"
    assert result.rows_by_key["cost_reimbursement"].values["2026"] == pytest.approx(125)
    assert result.total_revenue["2026"] == pytest.approx(1000)
    assert result.total_expenses["2026"] == pytest.approx(-175)
    assert result.net_income["2026"] == pytest.approx(825)
    assert [row.key for row in result.rows] == [
        "rent",
        "total_revenue",
        "tax",
        "cost_reimbursement",
        "total_expenses",
        "net_income",
    ]
```

Update the legacy `other_income` test:

```python
assert row.kind == "expense"
assert row.values["2025"] == pytest.approx(250)
assert result.total_revenue["2025"] == pytest.approx(0)
assert result.total_expenses["2025"] == pytest.approx(250)
```

- [ ] **Step 3: Run P&L tests and confirm failure**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_analytics_pnl.py -q
```

Expected before implementation: failures show extra `ytd` column, old row order, and negative reimbursement behavior.

- [ ] **Step 4: Implement P&L column changes**

In `property_rental/rentals/analytics/pnl.py`, replace `_columns` with:

```python
def _columns(first_year: int, end: date):
    return tuple(
        ProfitLossColumn(
            key=str(year),
            label=f"{year}YTD" if year == end.year else str(year),
            start=date(year, 1, 1),
            end=end if year == end.year else date(year, 12, 31),
        )
        for year in range(first_year, end.year + 1)
    )
```

Remove all writes to `values[category]["ytd"]`.

- [ ] **Step 5: Implement P&L signing, totals, and row order**

Import:

```python
from rentals.financial_semantics import category_kind, signed_analytics_amount
```

Use `category_kind(category, transaction.type)` when determining row kind. Use `signed_analytics_amount(category, converted, transaction.type)` for every transaction.

Build rows with:

```python
income_rows = []
expense_rows = []
for key in category_keys:
    if not any(values[key].values()):
        continue
    row = ProfitLossRow(
        key=key,
        label=_category_label(key),
        kind=category_kinds[key],
        values=values[key],
    )
    if row.kind == "income":
        income_rows.append(row)
    else:
        expense_rows.append(row)


def _row_impact(row):
    return sum(abs(value) for value in row.values.values())


expense_rows.sort(key=_row_impact, reverse=True)
rows = [
    *income_rows,
    ProfitLossRow("total_revenue", "Total revenue", "total_revenue", total_revenue),
    *expense_rows,
    ProfitLossRow("total_expenses", "Total expenses", "total_expenses", total_expenses),
    ProfitLossRow("net_income", "Net income", "net_income", net_income),
]
```

Compute totals from row kinds:

```python
total_revenue = {
    column.key: sum(
        values[key][column.key] for key in category_keys if category_kinds[key] == "income"
    )
    for column in columns
}
total_expenses = {
    column.key: sum(
        values[key][column.key] for key in category_keys if category_kinds[key] == "expense"
    )
    for column in columns
}
```

- [ ] **Step 6: Update frontend P&L table tests**

In `frontend/src/components/analytics/ProfitLossTable.test.tsx`, remove the `ytd` column from the fixture and assert:

```tsx
expect(within(table).getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
  'Category', '2024', '2025', '2026YTD',
])
expect(screen.queryByRole('columnheader', { name: 'YTD' })).not.toBeInTheDocument()
```

Add a row-order/gap test:

```tsx
it('renders the backend P&L order with a visual gap before expenses', () => {
  render(<ProfitLossTable data={statement} />)
  const table = screen.getByRole('table', { name: 'Profit and Loss statement' })
  const rowNames = within(table).getAllByRole('row').slice(1).map((row) => row.textContent)
  expect(rowNames[0]).toContain('Rental revenue')
  expect(rowNames[1]).toContain('Total revenue')
  expect(rowNames[2]).toContain('Property tax')
  expect(within(table).getByRole('row', { name: /Property tax/ })).toHaveClass('border-t-8')
})
```

- [ ] **Step 7: Implement frontend P&L gap styling**

In `ProfitLossTable.tsx`, compute the previous row:

```tsx
{data.rows.map((row, index) => {
  const previous = data.rows[index - 1]
  const isTotal = !['income', 'expense'].includes(row.kind)
  const startsExpenseBlock = row.kind === 'expense' && previous?.kind === 'total_revenue'
  return (
    <TableRow
      key={row.key}
      className={cn(
        isTotal && 'border-t font-semibold',
        startsExpenseBlock && 'border-t-8 border-t-muted',
      )}
    >
```

- [ ] **Step 8: Run focused backend and frontend tests**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_analytics_pnl.py -q
npm test -- src/components/analytics/ProfitLossTable.test.tsx --run
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit Task 2**

Run:

```powershell
git add property_rental/rentals/analytics/pnl.py property_rental/rentals/tests/test_analytics_pnl.py frontend/src/components/analytics/ProfitLossTable.tsx frontend/src/components/analytics/ProfitLossTable.test.tsx
git commit -m "fix: align profit loss statement layout"
```

### Task 3: Net-Income Yield Formula, Info Affordance, and Tooltip Cleanup

**Files:**
- Modify: `property_rental/rentals/analytics/portfolio.py`
- Modify: `property_rental/rentals/tests/test_analytics_portfolio.py`
- Modify: `frontend/src/components/analytics/FinancialDefinitions.tsx`
- Modify: `frontend/src/components/analytics/FinancialDefinitions.test.tsx`
- Modify: `frontend/src/features/dashboard/charts/YieldComparisonChart.tsx`
- Modify: `frontend/src/features/dashboard/charts/YieldComparisonChart.test.tsx`

**Interfaces:**
- Consumes: `revenue_cost_deltas` from `rentals.financial_semantics`.
- Produces: `_transaction_totals(properties, reporting_currency) -> dict[int, list[float, float]]` where the second item is net costs, allowing cost reimbursements to reduce costs.
- Produces: `gross_yield = (annualized_revenue - annualized_costs) / property_value * 100`.
- Produces: `equity_yield = (annualized_revenue - annualized_costs) / equity * 100`.

- [ ] **Step 1: Add backend yield formula test**

In `property_rental/rentals/tests/test_analytics_portfolio.py`, add:

```python
@pytest.mark.django_db
def test_yields_use_net_income_numerator_for_value_and_equity(
    landlord_user, sample_property
):
    from rentals.analytics.portfolio import property_yields

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )
    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("12000.00"),
        date=date(2026, 1, 15),
    )
    TransactionFactory(
        property=sample_property,
        category="utilities",
        amount=Decimal("-2000.00"),
        date=date(2026, 1, 20),
    )

    result = property_yields(
        landlord_user,
        filters_for("2026-01-01", "2026-12-31"),
    )
    row = next(row for row in result.rows if row.property_id == sample_property.id)

    assert row.annualized_revenue == pytest.approx(12000)
    assert row.annualized_costs == pytest.approx(2000)
    assert row.gross_yield == pytest.approx(10.0)
    assert row.equity_yield == pytest.approx(16.666666)
```

Add reimbursement coverage:

```python
@pytest.mark.django_db
def test_portfolio_totals_treat_cost_reimbursement_as_contra_expense(
    landlord_user, sample_property
):
    from rentals.analytics.portfolio import portfolio_summary

    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("1000.00"),
        date=date(2026, 1, 1),
    )
    TransactionFactory(
        property=sample_property,
        category="tax",
        amount=Decimal("-300.00"),
        date=date(2026, 1, 2),
    )
    TransactionFactory(
        property=sample_property,
        category="cost_reimbursement",
        amount=Decimal("-125.00"),
        date=date(2026, 1, 3),
    )

    result = portfolio_summary(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.revenue == pytest.approx(1000)
    assert result.costs == pytest.approx(175)
    assert result.net_income == pytest.approx(825)
```

- [ ] **Step 2: Run backend portfolio tests and confirm failure**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_analytics_portfolio.py::test_yields_use_net_income_numerator_for_value_and_equity property_rental/rentals/tests/test_analytics_portfolio.py::test_portfolio_totals_treat_cost_reimbursement_as_contra_expense -q
```

Expected before implementation: gross yield still uses revenue-only numerator, or reimbursement does not reduce net costs.

- [ ] **Step 3: Implement portfolio revenue/cost deltas and yield formula**

In `property_rental/rentals/analytics/portfolio.py`, import:

```python
from rentals.financial_semantics import revenue_cost_deltas
```

Update `_transaction_totals`:

```python
revenue_delta, cost_delta = revenue_cost_deltas(
    transaction.category,
    converted,
    transaction.type,
)
totals[transaction.property_id][0] += revenue_delta
totals[transaction.property_id][1] += cost_delta
```

Update `_rental_income_by_property` only if this chart should stay rent-only. For this scope, leave it filtered by `INCOME_CATEGORIES` so property breakdown rental income remains rent income, not reimbursements.

Update `property_yields`:

```python
annualized_net_income = annualized_revenue - annualized_costs
gross_yield=(
    annualized_net_income / property_value * 100.0
    if has_value_denominator
    else None
),
equity_yield=(
    annualized_net_income / equity * 100.0
    if has_equity_denominator
    else None
),
```

- [ ] **Step 4: Update FinancialDefinitions tests**

In `frontend/src/components/analytics/FinancialDefinitions.test.tsx`, replace copy assertions:

```tsx
expect(trigger).toHaveClass('min-h-11', 'min-w-11')
expect(trigger.querySelector('[aria-hidden="true"]')).toHaveTextContent('i')
expect(screen.getByText('Gross yield — annualized rental income net of costs divided by the latest property value.')).toBeVisible()
expect(screen.getByText('Equity yield — annualized rental income net of costs divided by equity.')).toBeVisible()
expect(screen.getByText('Equity — latest property value less latest debt, using records available as of the selected date.')).toBeVisible()
```

- [ ] **Step 5: Implement circular info affordance and copy**

In `FinancialDefinitions.tsx`, update the trigger:

```tsx
<Button
  type="button"
  variant="ghost"
  size="icon"
  className="min-h-11 min-w-11 rounded-full"
  aria-label="Yield definitions"
>
  <span
    aria-hidden="true"
    className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-muted text-sm font-semibold text-muted-foreground"
  >
    i
  </span>
</Button>
```

Update dialog text:

```tsx
<span className="block">Gross yield — annualized rental income net of costs divided by the latest property value.</span>
<span className="block">Equity yield — annualized rental income net of costs divided by equity.</span>
```

- [ ] **Step 6: Update yield tooltip test**

In `YieldComparisonChart.tsx`, export a small pure helper so tooltip filtering is testable without relying on Recharts hover behavior in jsdom:

```tsx
export function yieldTooltipRows(payload: readonly TooltipPayload[]): ChartTooltipRow[] {
  return payload
    .filter((item) => item.dataKey === 'yield' && typeof item.value === 'number')
    .map((item) => ({ label: String(item.name), value: formatYield(item.value) }))
}
```

In `YieldComparisonChart.test.tsx`, add:

```tsx
it('filters non-yield rows from the tooltip', () => {
  expect(yieldTooltipRows([
    { name: 'Property', dataKey: 'property_name', value: 'Anokhina' },
    { name: 'Gross yield', dataKey: 'yield', value: 8.5 },
  ] as never)).toEqual([
    { label: 'Gross yield', value: '8.5%' },
  ])
})
```

- [ ] **Step 7: Implement yield tooltip filtering**

In `YieldComparisonChart.tsx`, build tooltip rows from only numeric `yield` payload items:

```tsx
const rows = (payload ?? [])
  .filter((item) => item.dataKey === 'yield' && isFiniteNumber(item.value))
  .map((item) => ({ label: String(item.name), value: formatYield(item.value) }))
return active && propertyName ? <ChartTooltip label={propertyName} rows={rows} /> : null
```

- [ ] **Step 8: Run focused tests**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_analytics_portfolio.py -q
npm test -- src/components/analytics/FinancialDefinitions.test.tsx src/features/dashboard/charts/YieldComparisonChart.test.tsx --run
```

Expected: selected tests pass.

- [ ] **Step 9: Commit Task 3**

Run:

```powershell
git add property_rental/rentals/analytics/portfolio.py property_rental/rentals/tests/test_analytics_portfolio.py frontend/src/components/analytics/FinancialDefinitions.tsx frontend/src/components/analytics/FinancialDefinitions.test.tsx frontend/src/features/dashboard/charts/YieldComparisonChart.tsx frontend/src/features/dashboard/charts/YieldComparisonChart.test.tsx
git commit -m "fix: redefine yield analytics and tooltip"
```

### Task 4: Property Valuation Debt Defaults, Interpolated Start, and Chart Polish

**Files:**
- Modify: `property_rental/rentals/api/serializers.py`
- Modify: `property_rental/rentals/api/analytics_views.py`
- Modify: `property_rental/rentals/api/analytics_serializers.py`
- Modify: `property_rental/rentals/analytics/property.py`
- Modify: `property_rental/rentals/tests/test_analytics_property.py`
- Modify: `property_rental/rentals/tests/test_api.py`
- Modify: `frontend/src/types/analytics.ts`
- Modify: `frontend/src/api/analytics.ts`
- Modify: `frontend/src/api/keys.ts`
- Modify: `frontend/src/components/forms/PropertyValuationForm.tsx`
- Create: `frontend/src/components/forms/PropertyValuationForm.test.tsx`
- Modify: `frontend/src/features/property/ValuationChart.tsx`
- Modify: `frontend/src/features/property/ValuationChart.test.tsx`

**Interfaces:**
- Produces: `property_valuation_history(user, property_id, end, start=None)`.
- Produces valuation point statuses: `ok`, `missing_value`, `missing_debt`, `missing_value_and_debt`, `interpolated`, `carried_forward`.
- Produces API support for `GET /api/v1/analytics/properties/{id}/valuation/?start=YYYY-MM-DD&end=YYYY-MM-DD`.
- Produces `usePropertyValuationAnalytics(propertyId: number, params?: { start?: string; end?: string })`.

- [ ] **Step 1: Add backend API test for omitted debt default**

In `property_rental/rentals/tests/test_api.py`, add:

```python
@pytest.mark.django_db
def test_property_valuation_api_defaults_blank_debt_to_zero(auth_client, sample_property):
    response = auth_client.post(
        "/api/v1/property-valuations/",
        {
            "property": sample_property.id,
            "capital_structure_date": "2026-07-31",
            "capital_structure_value": "250000.00",
            "capital_structure_debt": "",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert Decimal(response.json()["capital_structure_debt"]) == Decimal("0.00")
```

- [ ] **Step 2: Add backend valuation start interpolation tests**

In `property_rental/rentals/tests/test_analytics_property.py`, add:

```python
@pytest.mark.django_db
def test_property_valuation_history_interpolates_requested_start(
    landlord_user, sample_property
):
    from rentals.analytics.property import property_valuation_history

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2020, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2022, 1, 1),
        capital_structure_value=Decimal("200000.00"),
        capital_structure_debt=Decimal("80000.00"),
    )

    result = property_valuation_history(
        landlord_user,
        sample_property.id,
        start=date(2021, 1, 1),
        end=date(2022, 12, 31),
    )

    assert result.start == date(2021, 1, 1)
    assert result.points[0]["period_start"] == date(2021, 1, 1)
    assert result.points[0]["status"] == "interpolated"
    assert result.points[0]["total_value"] == pytest.approx(150000, rel=0.01)
    assert result.points[0]["debt"] == pytest.approx(60000, rel=0.01)
    assert result.points[0]["equity"] == pytest.approx(90000, rel=0.01)
    assert result.points[1]["period_start"] == date(2022, 1, 1)
    assert result.points[1]["status"] == "ok"
```

Add a carried-forward test:

```python
@pytest.mark.django_db
def test_property_valuation_history_carries_forward_start_after_last_prior_record(
    landlord_user, sample_property
):
    from rentals.analytics.property import property_valuation_history

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2020, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )

    result = property_valuation_history(
        landlord_user,
        sample_property.id,
        start=date(2021, 1, 1),
        end=date(2021, 12, 31),
    )

    assert result.points[0]["period_start"] == date(2021, 1, 1)
    assert result.points[0]["status"] == "carried_forward"
    assert result.points[0]["total_value"] == 100000.0
    assert result.points[0]["debt"] == 40000.0
```

- [ ] **Step 3: Run backend valuation tests and confirm failure**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_api.py::test_property_valuation_api_defaults_blank_debt_to_zero property_rental/rentals/tests/test_analytics_property.py -q
```

Expected before implementation: serializer rejects blank debt, analytics function does not accept `start`, or synthetic status values are not supported.

- [ ] **Step 4: Implement serializer debt default**

In `PropertyCapitalStructureSerializer`, override validation:

```python
def validate(self, attrs):
    if attrs.get("capital_structure_debt") in ("", None):
        attrs["capital_structure_debt"] = Decimal("0")
    return attrs
```

Add `from decimal import Decimal` at the top of `serializers.py` if not present.

- [ ] **Step 5: Implement valuation start support**

In `property_rental/rentals/analytics/property.py`, change signature:

```python
def property_valuation_history(user, property_id, end, start=None):
```

Add helper functions:

```python
def _valuation_point(period, total_value, debt, status):
    return {
        "period_start": period,
        "period_end": period,
        "total_value": float(total_value) if total_value is not None else None,
        "debt": float(debt) if debt is not None else None,
        "equity": (
            float(total_value - debt)
            if total_value is not None and debt is not None
            else None
        ),
        "status": status,
    }


def _interpolate_value(before_value, after_value, before_date, after_date, target_date):
    if before_value is None or after_value is None:
        return None
    span = (after_date - before_date).days
    if span <= 0:
        return before_value
    elapsed = (target_date - before_date).days
    return before_value + (after_value - before_value) * elapsed / span
```

When `start` is provided:

- query all valuations through `end`;
- find `before = latest record <= start`;
- find `after = earliest record > start`;
- if `before` and `after`, prepend an interpolated start point unless `before.capital_structure_date == start`;
- if only `before`, prepend a carried-forward start point unless `before.capital_structure_date == start`;
- include actual records with `capital_structure_date >= start`.

Set response `start` to the requested `start` when provided; otherwise preserve the current first-record behavior.

- [ ] **Step 6: Update analytics view and serializers**

In `_ValuationEndSerializer`, add:

```python
start = ISODateField(required=False)
```

In `PropertyValuationAnalyticsView.get`, allow `{"start", "end"}` and pass both:

```python
start = query.validated_data.get("start")
end = query.validated_data.get("end", get_effective_date(request.user))
if start is not None and end < start:
    raise serializers.ValidationError({"end": "end must be on or after start"})
result = property_valuation_history(request.user, property_id, start=start, end=end)
```

Update `PropertyValuationPointSerializer` status choices and `frontend/src/types/analytics.ts` status enum to include `interpolated` and `carried_forward`.

- [ ] **Step 7: Update frontend valuation hook and key**

In `frontend/src/api/keys.ts`, change the analytics key:

```ts
propertyValuation: (propertyId: number, params?: { start?: string; end?: string }) =>
  ['analytics', 'property-valuation', propertyId, params] as const,
```

In `frontend/src/api/analytics.ts`:

```ts
export function usePropertyValuationAnalytics(
  propertyId: number,
  params: { start?: string; end?: string } = {},
) {
  const search = new URLSearchParams()
  if (params.start !== undefined) search.set('start', params.start)
  if (params.end !== undefined) search.set('end', params.end)
  const query = search.toString()
  const path = `/analytics/properties/${propertyId}/valuation/${query ? `?${query}` : ''}`

  return useQuery({
    queryKey: queryKeys.analytics.propertyValuation(propertyId, params),
    queryFn: () => fetchValidated(path, propertyValuationSchema),
    enabled: propertyId > 0,
  })
}
```

Existing callers can keep calling `usePropertyValuationAnalytics(propertyId)` because the second argument defaults to `{}`.

- [ ] **Step 8: Add PropertyValuationForm tests**

Create `frontend/src/components/forms/PropertyValuationForm.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PropertyValuationForm } from './PropertyValuationForm'

describe('PropertyValuationForm', () => {
  it('uses plain valuation labels and defaults blank debt to zero on submit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<PropertyValuationForm onSubmit={onSubmit} />)

    expect(screen.getByLabelText('Date')).toBeInTheDocument()
    expect(screen.getByLabelText('Total value')).toBeInTheDocument()
    expect(screen.getByLabelText('Debt')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Date'), '2026-07-31')
    await user.type(screen.getByLabelText('Total value'), '250000')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(onSubmit).toHaveBeenCalledWith({
      capital_structure_date: '2026-07-31',
      capital_structure_value: '250000',
      capital_structure_debt: '0',
    }, expect.anything())
  })
})
```

- [ ] **Step 9: Implement PropertyValuationForm labels and blank debt normalization**

In `PropertyValuationForm.tsx`, change schema:

```ts
const schema = z.object({
  capital_structure_date: z.string().min(1, 'Required'),
  capital_structure_value: z.string().min(1, 'Required'),
  capital_structure_debt: z.string().optional().default(''),
}).transform((values) => ({
  ...values,
  capital_structure_debt: values.capital_structure_debt?.trim() || '0',
}))
```

Change labels to `Date`, `Total value`, and `Debt`.

- [ ] **Step 10: Update ValuationChart tests**

In `ValuationChart.test.tsx`, assert removed subtitle:

```tsx
expect(screen.queryByText(/Server-provided valuation records/i)).not.toBeInTheDocument()
```

Assert status text for synthetic rows is visible in table mode or screen-reader list:

```tsx
render(<ValuationChart data={{
  ...data,
  points: [
    { period_start: '2021-01-01', period_end: '2021-01-01', total_value: 150000, debt: 60000, equity: 90000, status: 'interpolated' },
    ...data.points,
  ],
}} />)
expect(screen.getByText(/All time: 2021-01-01 to 2026-07-29/)).toBeInTheDocument()
```

- [ ] **Step 11: Implement ValuationChart subtitle and time-domain padding**

In `ValuationChart.tsx`, replace subtitle:

```tsx
subtitle={data ? `All time: ${data.start} to ${data.end}` : undefined}
```

Add helper:

```tsx
function paddedTimeDomain(points: readonly { timestamp: number }[]) {
  if (points.length === 0) return ['dataMin', 'dataMax'] as const
  const values = points.map((point) => point.timestamp)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = Math.max(max - min, 1000 * 60 * 60 * 24 * 30)
  const padding = span * 0.04
  return [min - padding, max + padding] as [number, number]
}
```

Use:

```tsx
<XAxis
  dataKey="timestamp"
  type="number"
  scale="time"
  domain={paddedTimeDomain(chartPoints)}
  tickFormatter={(value) => formatDate(new Date(Number(value)))}
  minTickGap={24}
/>
```

- [ ] **Step 12: Run focused backend and frontend tests**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_api.py::test_property_valuation_api_defaults_blank_debt_to_zero property_rental/rentals/tests/test_analytics_property.py -q
npm test -- src/components/forms/PropertyValuationForm.test.tsx src/features/property/ValuationChart.test.tsx src/api/analytics.test.tsx --run
```

Expected: selected tests pass.

- [ ] **Step 13: Commit Task 4**

Run:

```powershell
git add property_rental/rentals/api/serializers.py property_rental/rentals/api/analytics_views.py property_rental/rentals/api/analytics_serializers.py property_rental/rentals/analytics/property.py property_rental/rentals/tests/test_analytics_property.py property_rental/rentals/tests/test_api.py frontend/src/types/analytics.ts frontend/src/api/analytics.ts frontend/src/api/keys.ts frontend/src/components/forms/PropertyValuationForm.tsx frontend/src/components/forms/PropertyValuationForm.test.tsx frontend/src/features/property/ValuationChart.tsx frontend/src/features/property/ValuationChart.test.tsx
git commit -m "fix: improve property valuation entry and timeline"
```

### Task 5: Tenant Rent Performance RUB/GBP Regression and Native-Currency Guard

**Files:**
- Modify: `property_rental/rentals/tests/test_analytics_tenant.py`
- Modify: `property_rental/rentals/analytics/tenant.py` only if focused tests fail.
- Modify: `frontend/src/features/tenant/RentPerformanceChart.test.tsx`
- Modify: `frontend/src/features/tenant/RentPerformanceChart.tsx` only if focused tests fail.

**Interfaces:**
- Consumes: `tenant_rent_performance(user, tenant_id, filters)`.
- Produces: regression coverage for RUB/GBP direct and reverse paths.
- Preserves response `currency = tenant.property.currency.upper()`.

- [ ] **Step 1: Add RUB/GBP same-currency and cross-currency tests**

In `property_rental/rentals/tests/test_analytics_tenant.py`, add:

```python
@pytest.mark.django_db
def test_rent_performance_rub_native_rows_do_not_use_fx(landlord_user):
    from rentals.analytics.tenant import tenant_rent_performance

    property_ = PropertyFactory(owned_by=landlord_user.landlord, currency="RUB")
    tenant = TenantFactory(
        property=property_,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("100000.00"),
        currency="RUB",
    )
    TransactionFactory(
        property=property_,
        tenant=tenant,
        category="rent",
        amount=Decimal("50000.00"),
        currency="RUB",
        date=date(2026, 1, 10),
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31", currency="GBP"),
    )

    assert result.currency == "RUB"
    assert result.points[0]["expected"] == 100000.0
    assert result.points[0]["received"] == 50000.0
    assert result.points[0]["variance"] == -50000.0
```

Add cross-currency path tests:

```python
@pytest.mark.django_db
def test_rent_performance_converts_gbp_to_rub_without_inverse_rate(
    landlord_user,
):
    from rentals.analytics.tenant import tenant_rent_performance

    property_ = PropertyFactory(owned_by=landlord_user.landlord, currency="RUB")
    tenant = TenantFactory(property=property_, lease_start=date(2026, 1, 1), payday=5)
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="GBP",
    )
    FXFactory(date=date(2026, 1, 5), from_currency="GBP", to_currency="USD", rate=Decimal("1.25"))
    FXFactory(date=date(2026, 1, 5), from_currency="USD", to_currency="RUB", rate=Decimal("90.00"))

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.currency == "RUB"
    assert result.points[0]["expected"] == pytest.approx(112500)


@pytest.mark.django_db
def test_rent_performance_converts_rub_to_gbp_without_inverse_rate(
    landlord_user,
):
    from rentals.analytics.tenant import tenant_rent_performance

    property_ = PropertyFactory(owned_by=landlord_user.landlord, currency="GBP")
    tenant = TenantFactory(property=property_, lease_start=date(2026, 1, 1), payday=5)
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("112500.00"),
        currency="RUB",
    )
    FXFactory(date=date(2026, 1, 5), from_currency="GBP", to_currency="USD", rate=Decimal("1.25"))
    FXFactory(date=date(2026, 1, 5), from_currency="USD", to_currency="RUB", rate=Decimal("90.00"))

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31", currency="RUB"),
    )

    assert result.currency == "GBP"
    assert result.points[0]["expected"] == pytest.approx(1000)
```

- [ ] **Step 2: Run focused tenant tests**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_analytics_tenant.py::test_rent_performance_rub_native_rows_do_not_use_fx property_rental/rentals/tests/test_analytics_tenant.py::test_rent_performance_converts_gbp_to_rub_without_inverse_rate property_rental/rentals/tests/test_analytics_tenant.py::test_rent_performance_converts_rub_to_gbp_without_inverse_rate -q
```

Expected: pass if the current converter direction is already correct; fail if the RUB/GBP defect is in this code path.

- [ ] **Step 3: If focused tenant tests fail, normalize currency codes before conversion**

If the failure is due to case or whitespace in persisted currency codes, add this helper to `property_rental/rentals/analytics/tenant.py`:

```python
def _currency_code(currency):
    return currency.upper().strip() if currency else currency
```

Use it in:

```python
currency = _currency_code(tenant.property.currency)
```

and when creating `_ConvertibleAmount` rows:

```python
_ConvertibleAmount(rate.rent, _currency_code(rate.currency), due_date)
```

and when converting transactions:

```python
value, error = _converted(
    converter,
    transaction.amount,
    _currency_code(transaction.currency),
    currency,
    transaction.date,
)
```

If the failure is due to `PreloadedConverter` direction, fix `property_rental/rentals/services/fx.py::PreloadedConverter.convert` to match the already-characterized `get_rate` direction:

```python
if fx.from_currency == source and fx.to_currency == target:
    fx_rate *= fx.rate
else:
    fx_rate /= fx.rate
```

Do not change tenant analytics to ignore stored lease-rent currencies; that would hide data issues and contradict existing cross-currency tests.

- [ ] **Step 4: Add frontend native-currency chart test**

In `frontend/src/features/tenant/RentPerformanceChart.test.tsx`, assert native currency is visible:

```tsx
it('states the native currency in the subtitle', () => {
  render(<RentPerformanceChart data={{ ...data, currency: 'RUB' }} />)
  expect(screen.getByText(/Native currency: RUB/)).toBeInTheDocument()
})
```

Assert no dashed/patterned bar semantics by checking received and variance bars use color tokens only through existing render output or snapshots supported by the current tests. If the test harness cannot inspect Recharts SVG internals reliably, keep the native-currency test and rely on the existing source-level implementation where bars already use solid fills.

- [ ] **Step 5: Run focused tenant tests**

Run:

```powershell
uv run pytest property_rental/rentals/tests/test_analytics_tenant.py -q
npm test -- src/features/tenant/RentPerformanceChart.test.tsx --run
```

Expected: selected tests pass.

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git add property_rental/rentals/tests/test_analytics_tenant.py property_rental/rentals/analytics/tenant.py frontend/src/features/tenant/RentPerformanceChart.test.tsx frontend/src/features/tenant/RentPerformanceChart.tsx
git commit -m "test: cover tenant rent fx direction"
```

If `analytics/tenant.py` and `RentPerformanceChart.tsx` were not modified because the focused tests passed, omit those files from `git add`.

### Task 6: Integration Verification and Final Polish

**Files:**
- Modify only files with demonstrated failures from the verification commands.
- Update: `docs/superpowers/specs/2026-07-31-ux-review-followup-design.md` only if implementation reveals a design correction that changes accepted behavior.

**Interfaces:**
- Consumes all prior tasks.
- Produces a verified branch ready for review/merge.

- [ ] **Step 1: Check working tree before full verification**

Run:

```powershell
git status --short
```

Expected: only intentional source/test changes since the last task commit, or a clean tree.

- [ ] **Step 2: Run backend suite**

Run:

```powershell
uv run pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 3: Build frontend assets before Django system check**

Run:

```powershell
npm run build
```

Expected: Vite build succeeds and creates frontend static assets for Django.

- [ ] **Step 4: Run Django system check**

Run:

```powershell
uv run python property_rental/manage.py check
```

Expected: no warnings from the project. The fresh-worktree static directory warning should be gone after `npm run build`.

- [ ] **Step 5: Run frontend lint and tests**

Run:

```powershell
npm run lint
npm test -- --run
```

Expected: lint passes and all Vitest tests pass.

- [ ] **Step 6: Inspect key changed UX surfaces manually from source**

Use source inspection for these checks:

```powershell
rg -n "2026YTD|total_revenue|border-t-8|Gross yield|annualized rental income net of costs|Server-provided valuation records|cost_reimbursement|normalize_transaction_amount" frontend/src property_rental/rentals
```

Expected:

- `Gross yield` definition says net of costs.
- Removed valuation subtitle text does not appear in frontend source.
- `cost_reimbursement` sign semantics are centralized.
- P&L table has a visual gap after `Total revenue`.

- [ ] **Step 7: Commit any verification-only fixes**

If verification required source/test changes:

```powershell
git add <changed-files>
git commit -m "fix: complete UX review follow-up verification"
```

If no changes were needed, do not create an empty commit.

- [ ] **Step 8: Record final branch state**

Run:

```powershell
git status --short --branch
git log --oneline --decorate -n 8
```

Expected: clean working tree on `ux-review-followup-20260731` with the task commits visible.

---

## Self-Review Checklist

- [ ] Task 1 covers transaction save behavior, API writes, and existing data normalization.
- [ ] Task 2 covers Dashboard and Property detail P&L because both consume the shared backend P&L response and `ProfitLossTable`.
- [ ] Task 3 covers yield formula, definition affordance, and tooltip cleanup.
- [ ] Task 4 covers valuation field labels, omitted debt, subtitle removal, linear time padding, and start-point approximation.
- [ ] Task 5 covers the tenant RUB/GBP failure mode without hiding persisted currency data.
- [ ] Task 6 covers full backend/frontend verification and static asset ordering for `manage.py check`.
- [ ] No task moves cost reimbursement into revenue.
- [ ] No task uses frontend code to reclassify backend financial categories.
