# Remaining UI/Logic Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix all remaining dashboard, property detail, tenant, transaction, and business-logic issues reported by the user after testing with production data.

**Architecture:** Mix of frontend display fixes (currency, formatting, labels), backend logic fixes (cash-flow calendar vs rolling periods, debt calculation), and data fixes (recategorize "other_income" → expense, remove empty categories from P&L).

**Tech Stack:** React 19 + TypeScript + Recharts + TanStack Query (frontend); Django 4.2 + DRF (backend).

## Global Constraints

- User: Yaroslav. Properties: Анохина (id=95, RUB), Wandsworth (id=96, GBP).
- User's `default_currency` field on the User model drives the display currency for KPIs, charts, and P&L.
- `formatAccounting(value, currency)` exists in `lib/format.ts`.
- Both servers running: Django :8000, Vite :5173.
- `cd frontend && npm run build && npm test` must pass.
- `cd property_rental && python -m pytest rentals/tests/ -q` must pass.
- Git identity: `YL-STARDESTROYER <yaroslav.linik@gmail.com>`.

---

## Task 1: Dashboard — KPI currency uses user's `default_currency`

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/context/SessionProvider.tsx` (expose `user.default_currency`)

**Issue:** KPI revenue/income hardcoded to USD. Must use `user.default_currency` from the session.

- [ ] **Step 1:** In `HomePage.tsx`, read the session user's `default_currency` field (via `useSession()`). Replace the hardcoded `'USD'` in `usePropertiesWithStats(undefined, 'USD')` with the user's currency. If `default_currency` is null/empty, fall back to `'USD'`.

- [ ] **Step 2:** Build + test. Commit.

---

## Task 2: Dashboard — Occupancy chart based on property's first rental date

**Files:**
- Modify: `frontend/src/components/charts/OccupancyChart.tsx`

**Issue:** Occupancy should start from when each property was first put up for rent (earliest tenant lease_start or property acquisition date), not from an arbitrary start.

- [ ] **Step 1:** In OccupancyChart, compute occupancy starting from the earliest `lease_start` across all tenants. For each month from that date to today: occupied = tenants whose `lease_start <= month` and (`lease_end is null` or `lease_end >= month`). Total capacity = number of properties. This means early months when fewer properties existed will show lower capacity — but the user wants to see actual occupancy over time.

Actually simpler: the user says "capacity taking into account when the property was put for renting". So for each month: capacity = count of properties that were active (had at least one tenant whose lease_start <= that month). Occupied = count of tenants with active lease in that month. Occupancy% = occupied/capacity.

- [ ] **Step 2:** Build + test. Commit.

---

## Task 3: Dashboard — Currency Exposure fixes (user currency + data direction)

**Files:**
- Modify: `frontend/src/components/charts/CurrencyExposureChart.tsx`

**Issues:**
a) Chart axis should use user's `default_currency`, not hardcoded USD.
b) "Last 3 months" showing higher than "Last 5 years" — this is actually correct (recent months may have higher net income). But verify the chart values are cumulative within the selected period, not per-period averages. Net income over 3 months CAN be higher than over 5 years if early years had losses. If the user expects cumulative totals (which they should be), then higher recent = good performance. Leave as-is but add a note in the description: "Net income for selected period".
c) Use user's `default_currency` for the USD-converted column instead of hardcoded 'USD'.

- [ ] **Step 1:** Replace all hardcoded 'USD' with user's `default_currency` (read via `useSession()`).

- [ ] **Step 2:** Build + test. Commit.

---

## Task 4: Dashboard — P&L table currency label + format

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`

**Issues:**
a) P&L table says "USD" in subheader regardless of user currency. Fix to show user's `default_currency`.
b) Dollar sign hardcoded. Use the user's currency symbol.
c) Cash flow table (and all chart tables) should show currency sign, negative format `(1,234)`, and `#,###` format.

- [ ] **Step 1:** Read `user.default_currency` via `useSession()`. Use it in the P&L subheader and all `formatAccounting` calls.

- [ ] **Step 2:** Build + test. Commit.

---

## Task 5: Backend — Cash flow yearly data uses calendar periods, not rolling 12m

**Files:**
- Modify: `property_rental/rentals/services/charts.py`

**Issue:** When frequency='Y', the chart data uses rolling 12-month periods, not calendar years. 2026 shows higher because it captures recent months that overlap with 2025's rolling window. Must be calendar: Jan-Dec for each year. The current year (2026) should be YTD (Jan-Jul).

- [ ] **Step 1:** Read `get_chart_data` in `services/charts.py`. Find the yearly frequency branch (`freq='Y'`). Currently it probably does `start_date = d - relativedelta(months=12)` which creates a rolling window. Change to calendar year: `year_start = date(d.year, 1, 1)` and `year_end = date(d.year, 12, 31)`.

- [ ] **Step 2:** The chart char tests (`test_charts_char.py`) pin yearly output — they may need updating if the date windows change. Run the tests; if they fail because the windows shifted from rolling to calendar, update the golden values.

- [ ] **Step 3:** Run full backend suite. Commit.

---

## Task 6: Property Detail — Gross yield is zero (valuation data issue)

**Files:**
- Modify: `frontend/src/components/charts/RentYieldChart.tsx`

**Issue:** Gross yield shows zero because the chart can't find property valuation data. The yield calculation needs `property_value` from the latest `Property_capital_structure` entry. The chart might not be fetching valuations, or the valuation data is empty for the selected period.

- [ ] **Step 1:** Read `RentYieldChart.tsx`. Check how it gets property values. It likely uses `useChartData({type:'property', elementId})` which returns Debt + Equity datasets — value = debt + equity. If equity is 0 or datasets are empty, yield = 0/0.

- [ ] **Step 2:** Also fetch valuations directly via `usePropertyValuations({property_id: id})` to get the latest value. Use the latest valuation's `capital_structure_value` as the denominator.

- [ ] **Step 3:** Build + test. Commit.

---

## Task 7: Property Detail — P&L YTD revenue discrepancy

**Issue:** P&L shows YTD revenue £11,400 for Wandsworth, but tenant page shows £9,950. This might be correct — P&L sums ALL income categories (rent + other), while the tenant page only shows `rent_total`. Or there might be unassigned transactions (tenant=null) counted in P&L but not in tenant stats.

- [ ] **Step 1:** Check the DB for transactions on property 96 (Wandsworth) with `category='rent'` and date >= 2026-01-01. Sum them. Compare with both the P&L and tenant stats figures.

- [ ] **Step 2:** If the discrepancy is due to unassigned transactions or non-rent income categories, document the difference. The P&L should show total revenue (all income categories); the tenant stats show only rent. This is correct behavior.

---

## Task 8: Tenants — Debt format (accounting brackets for negatives)

**Files:**
- Modify: `frontend/src/pages/TenantsPage.tsx`

**Issue:** Negative debt (credit/overpayment) shows in green but without accounting brackets. Should show `£(250)` not `£-250`.

- [ ] **Step 1:** In the Debt column cell renderer, use `formatAccounting(debt, currency)` instead of a plain format. This adds brackets for negatives.

- [ ] **Step 2:** Build + test. Commit.

---

## Task 9: Tenants — Remove "Net income" column

**Files:**
- Modify: `frontend/src/pages/TenantsPage.tsx`

**Issue:** "Net income" is non-informative on the tenants list. Remove the column.

- [ ] **Step 1:** Remove the Net income column definition from the columns array.

- [ ] **Step 2:** Build + test. Commit.

---

## Task 10: Transactions — Fix broken filters (Category, From, To)

**Files:**
- Modify: `frontend/src/pages/TransactionsPage.tsx`
- Modify: `property_rental/rentals/api/views.py` (TransactionViewSet)

**Issue:** The category, from-date, and to-date filters don't work. The backend may not be filtering on these query params, or the frontend isn't sending them correctly.

- [ ] **Step 1:** Check TransactionViewSet's `get_queryset` — does it handle `?category=`, `?date__gte=`, `?date__lte=` (or `?from=`, `?to=`)?

- [ ] **Step 2:** Add filtering for category and date range in the ViewSet:
```python
def get_queryset(self):
    qs = super().get_queryset()  # or the existing scoped queryset
    category = self.request.query_params.get('category')
    if category:
        qs = qs.filter(category=category)
    date_from = self.request.query_params.get('from') or self.request.query_params.get('date__gte')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    date_to = self.request.query_params.get('to') or self.request.query_params.get('date__lte')
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs
```

- [ ] **Step 3:** Check the frontend — does `useTransactions({category, from, to})` pass these as query params to `apiFetch`?

- [ ] **Step 4:** Build + test. Commit.

---

## Task 11: Backend — Debt calculation logic review

**Issue:** User changed Jose's rent to £1,700. Payment day is 1st. Today is 23-Jul. User expects debt = £1,700 (one month due). Current logic might be counting partial months differently.

- [ ] **Step 1:** Read `services/scheduler.py` — the `debt()` function. Understand how it counts "due" months. For the standard method: a month is "due" if `check_date >= due_date + grace_period_days`. With payday=1, the July payment is due on Jul 1. On Jul 23, that's 22 days past due — well within any reasonable grace period (3 days). So July should be counted as due.

- [ ] **Step 2:** The debt should be: (months due × rent) - (payments made). If rent is £1,700 and the rent was just changed, the question is: when was the rent changed? If changed today (Jul 23), the new rate applies from today forward. Previous months were at the old rate. The debt calc uses the rent rate as of the `as_of_date`, which might be the NEW rate (£1,700) applied retroactively to all months. This could cause the discrepancy.

- [ ] **Step 3:** Read how `debt()` gets the rent rate — does it use `tenant.lease_rent(as_of_date)` which returns the rate as of that date? If so, it uses the CURRENT rate for all calculations, which is wrong for historical months. This is a known limitation. For now, verify the logic is: count months from lease_start to as_of_date where month is "due", multiply each by the rent rate AS OF THAT MONTH (not the current rate). If the code uses a single rate for all months, that's the bug.

- [ ] **Step 4:** This may be complex to fix properly (rent rate history). For now, document the limitation and ensure the calculation at least produces £1,700 for a tenant with 0 payments and 1 month due at the new rate. Run the DB query to verify.

---

## Task 12: Data — Recategorize "other_income" to expense category

**Issue:** "Other income" should be recategorized as "cost reimbursement" under expenses (positive entry reducing total expenses).

- [ ] **Step 1:** Run a DB migration to change category:
```python
from rentals.models import Transaction
Transaction.objects.filter(category='other_income').update(category='cost_reimbursement')
# Also need to flip the sign: other_income was positive (income), cost_reimbursement as expense should also be positive (reducing expenses)
# But wait — in this app, expenses are stored as NEGATIVE amounts. So cost_reimbursement should be... the user says "positive entry to Expenses". 
# This means: the amount stays positive (it's a reimbursement that offsets expenses), and it's categorized as an expense.
# Actually the user says "positive entry to Expenses" — meaning the reimbursement REDUCES total expenses.
# In the current sign convention: income = positive, expenses = negative.
# A cost reimbursement is income-like (positive) but the user wants it under expenses.
# As a positive entry in expenses, it would REDUCE the total (negative) expense figure. E.g., expenses = -5000 + 200 reimbursement = -4800.
# So: keep the amount POSITIVE, set category='cost_reimbursement', and classify it as expense type.
# The Transaction.save() auto-derives type from category. Need to ensure 'cost_reimbursement' maps to 'expense'.
```

- [ ] **Step 2:** Update `Transaction.save()` or the category→type mapping to classify `cost_reimbursement` as expense.

- [ ] **Step 3:** Run the recategorization in the DB.

- [ ] **Step 4:** Ensure empty categories (like "other_income" after migration) don't appear in P&L tables. The frontend should filter out categories with zero total.

- [ ] **Step 5:** Build + test. Commit.

---

## Task 13: Tenant Detail — Remove "Currency shown in..." text + net income fix

**Files:**
- Modify: `frontend/src/pages/TenantDetailPage.tsx`

**Issues:**
a) Remove the "Currency shown in GBP..." text (already requested before — verify it's gone).
b) Net income still wrong — verify the computation uses ONLY this tenant's transactions.

- [ ] **Step 1:** Read `TenantDetailPage.tsx`. Find and remove the duplicate currency text.

- [ ] **Step 2:** Verify net income computation: `useTransactions({tenant: id})` must filter to this tenant. Sum amounts.

- [ ] **Step 3:** Build + test. Commit.

---

## Self-Review

**Spec coverage:**

| User item | Task | Covered? |
|---|---|---|
| Dashboard 1: KPI user currency | Task 1 | ✅ |
| Dashboard 2: Occupancy capacity | Task 2 | ✅ |
| Dashboard 3: Currency exposure user currency | Task 3 | ✅ |
| Dashboard 4: P&L labels/format | Task 4 | ✅ |
| Dashboard 5: Cash flow calendar periods | Task 5 | ✅ |
| Property 1: Gross yield zero | Task 6 | ✅ |
| Property 2: YTD revenue discrepancy | Task 7 | ✅ |
| Tenants 1: Debt brackets | Task 8 | ✅ |
| Tenants 2: Remove net income | Task 9 | ✅ |
| Transactions 1: Broken filters | Task 10 | ✅ |
| Additional 1: Debt logic | Task 11 | ✅ |
| Additional 2: Recategorize other_income | Task 12 | ✅ |
| Tenant detail: Remove text + net income | Task 13 | ✅ |

**Placeholder scan:** Tasks 7 and 11 are investigation/debugging tasks without fixed code — they require reading the DB/code and making decisions. Acceptable for this type of work.

**Type consistency:** `default_currency` field name consistent across User model, UserSerializer, and TypeScript User type.
