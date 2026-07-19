# Entity Pages Backend + FX Fix + Frontend Infrastructure — Implementation Plan (Sub-plan B1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the PropertyValuation ViewSet, fix the FX inversion bug and consolidate the remaining duplicated FX loops, add stats/action/auth endpoints, and build all the reusable frontend infrastructure (types, hooks, forms, modals, DataTable) that sub-plan B2 needs for the entity pages.

**Architecture:** Backend additions follow Phase 1's established patterns (DRF ViewSets per-user-scoped, services layer for business logic, TDD with pytest). Frontend infrastructure extends Plan A's foundation (typed API client + React Query) with per-entity hooks, react-hook-form + zod forms, shadcn-based modals, and a TanStack-Table-backed DataTable. No pages are wired yet — B2 consumes this infrastructure.

**Tech Stack:** Django 4.2 + DRF 3.14 (backend); React 19 + TypeScript 6 + Vite 8 + Tailwind v4 + shadcn/ui v4 + TanStack Query v5 + react-hook-form + zod + @tanstack/react-table (frontend); Vitest + Testing Library + MSW (frontend tests); pytest (backend tests).

## Global Constraints

Copied verbatim from the spec (`docs/superpowers/specs/2026-07-19-entity-pages-design.md`):

- **All 5 entity pages** in the combined plan; B1 builds the infra, B2 builds the pages.
- **Delete all replaced legacy views** (the clean cut) — but deletions happen in B2, not B1.
- **Fix FX inversion AND consolidate remaining duplicated FX loops** (the more ambitious scope).
- Decimal fields come through as strings (DRF default) — TypeScript types use `string` for Decimal fields.
- snake_case field names preserved on the TS side (matches DRF serializer output).
- App is **personal / not live** — breaking changes acceptable.
- Phase 1 + Plan A test suites must stay green throughout (114 backend + 15 frontend).
- Git identity (repo-local, configured): `YL-STARDESTROYER <yaroslav.linik@gmail.com>`.
- Working dir: `D:/Developing/Property-rental`. Django project at `D:/Developing/Property-rental/property_rental/`.
- Run pytest from `property_rental/`: `cd property_rental && python -m pytest rentals/tests/ -q`.
- Run frontend tests from `frontend/`: `cd frontend && npm test`.
- Platform: Windows, Git Bash. Use forward slashes in paths.

## File Structure

### Backend (modified/created)

```
property_rental/rentals/api/
├── views.py          (MODIFY: add PropertyCapitalStructureViewSet; add @action vacate on TenantViewSet;
│                      add @action update on FXViewSet; add @action with_stats on Property & Tenant ViewSets)
├── serializers.py    (MODIFY: add PropertyCapitalStructureSerializer — moved from views.py:55)
└── urls.py           (MODIFY: register property-valuations route)
property_rental/rentals/api/auth.py  (MODIFY: extend MeView with PATCH; add ChangePasswordView)
property_rental/rentals/services/fx.py          (MODIFY: remove round(1/fx_rate, 6) tail)
property_rental/rentals/services/financials.py  (MODIFY: consolidate rent_total + pnl_calc loops into convert_transactions)
property_rental/rentals/models.py               (MODIFY: rent_total delegates the FX loop to convert_transactions)
property_rental/rentals/tests/
├── test_api.py                       (MODIFY: add PropertyValuation ViewSet tests)
├── test_auth_api.py                  (MODIFY: add PATCH /me + change-password tests)
├── test_stats_endpoints.py           (NEW: properties/with_stats, tenants/with_stats tests)
├── test_fx_char.py                   (MODIFY: update golden values for FX inversion fix)
├── test_financials_char.py           (MODIFY: update cross-currency rent_total golden value)
└── test_financials_consolidation.py  (NEW: regression tests for loop consolidation)
```

### Frontend (created)

```
frontend/src/
├── types/
│   ├── property.ts
│   ├── tenant.ts
│   ├── transaction.ts
│   ├── fx.ts
│   └── propertyValuation.ts
├── api/
│   ├── keys.ts          (MODIFY: add all entity key factories)
│   ├── properties.ts    (NEW: hooks + mutations)
│   ├── tenants.ts       (NEW: hooks + mutations + vacate)
│   ├── transactions.ts  (NEW: hooks + mutations)
│   ├── fx.ts            (NEW: hooks + update)
│   ├── propertyValuations.ts (NEW: hooks + mutations)
│   └── auth.ts          (MODIFY: add useUpdateMe, useChangePassword)
├── lib/
│   └── format.ts        (MODIFY: extend formatCurrency for 'k' suffix correctness)
├── components/
│   ├── ui/              (shadcn add: select, checkbox, form, dialog, dropdown-menu, table, badge, tooltip, separator)
│   ├── forms/
│   │   ├── PropertyForm.tsx
│   │   ├── TenantForm.tsx
│   │   ├── TransactionForm.tsx
│   │   ├── PropertyValuationForm.tsx
│   │   ├── VacateTenantForm.tsx
│   │   └── ProfileSettingsForm.tsx
│   ├── modals/
│   │   ├── EntityFormDialog.tsx
│   │   ├── ConfirmDialog.tsx
│   │   └── VacateTenantDialog.tsx
│   ├── table/
│   │   └── DataTable.tsx        (TanStack Table wrapper)
│   └── states/
│       ├── SkeletonTable.tsx
│       ├── EmptyState.tsx
│       └── ErrorState.tsx
├── __fixtures__/
│   ├── property.ts
│   ├── tenant.ts
│   ├── transaction.ts
│   ├── fx.ts
│   ├── propertyValuation.ts
│   └── lists.ts
└── test/
    └── handlers.ts     (MODIFY: add MSW handlers for all new endpoints)
```

---

## Task Ordering

Twelve phases, 18 tasks:

1. **FX inversion fix** (Task 1) — the headline backend fix; gated by char tests.
2. **FX loop consolidation** (Tasks 2-4) — rent_total, pnl_calc loops, regression tests.
3. **PropertyValuation ViewSet** (Task 5) — last CRUD endpoint.
4. **Stats endpoints** (Task 6) — properties + tenants with_stats.
5. **Action endpoints** (Task 7) — vacate, FX update.
6. **Auth endpoints** (Task 8) — PATCH /me, change-password.
7. **Frontend types + fixtures** (Task 9).
8. **Frontend API hooks + cache keys** (Task 10).
9. **Frontend forms** (Task 11) — all 6 entity forms with react-hook-form + zod.
10. **Frontend shared components** (Task 12) — modals, DataTable, state components.
11. **Frontend tests** (Tasks 13-17) — hooks, forms, DataTable, MSW handlers.
12. **Verification** (Task 18).

---

## Task 1: Fix FX inversion bug

**Goal:** Remove the `round(1 / fx_rate, 6)` tail in `services/fx.py:get_rate` so it returns the actual rate, not its reciprocal. Update the pinned golden values in the char tests.

**Files:**
- Modify: `property_rental/rentals/services/fx.py` (the `get_rate` function — find the `round(1 / fx_rate, 6)` line near the tail)
- Modify: `property_rental/rentals/tests/test_fx_char.py` (golden values)
- Modify: `property_rental/rentals/tests/test_financials_char.py` (`test_tenant_rent_total_cross_currency` golden value)

**Interfaces:**
- Produces: `services.fx.get_rate` returns the actual rate (not reciprocal). All downstream consumers (`convert_transactions`, `rent_total`, `pnl_calc`, chart-data) automatically see corrected values.

- [ ] **Step 1: Read the current `get_rate` to find the inversion line**

```bash
cd property_rental && grep -n "round.*1.*fx_rate" rentals/services/fx.py
```
Read the surrounding function to understand the full context. The line is near the end of `get_rate` — it unconditionally does `fx_rate = round(1 / fx_rate, 6)` before returning, which inverts every rate.

- [ ] **Step 2: Run the existing FX char tests to capture current (inverted) values**

```bash
cd property_rental && python -m pytest rentals/tests/test_fx_char.py rentals/tests/test_financials_char.py::test_tenant_rent_total_cross_currency -v
```
Note the current passing values (these are the INVERTED values the tests currently pin). Expected current pinned values per Phase 1 Task 4:
- `get_rate("EUR","USD",_)['FX']` == `Decimal('0.909091')` (stored EURUSD=1.10, inverted)
- `get_rate("USD","EUR",_)['FX']` == `Decimal('1.100000')`
- 2-hop `get_rate("EUR","RUB",_)['FX']` == `Decimal('0.010101')`
- `test_tenant_rent_total_cross_currency` pins a cross-currency value (capture from the test)

- [ ] **Step 3: Apply the fix**

In `property_rental/rentals/services/fx.py`, find the line `fx_rate = round(1 / fx_rate, 6)` (or similar) in `get_rate` and **remove it**. The function should return the accumulated `fx_rate` as-is (the actual Bellman-Ford path product). Leave a comment: `# FX inversion bug fixed <date>: was round(1 / fx_rate, 6) — see docs/superpowers/specs/2026-07-19-entity-pages-design.md §4.2`.

- [ ] **Step 4: Run the char tests — they will FAIL with the new (correct) values**

```bash
cd property_rental && python -m pytest rentals/tests/test_fx_char.py rentals/tests/test_financials_char.py::test_tenant_rent_total_cross_currency -v
```
Read the failure messages — they show the actual (correct) values the tests now produce. Capture:
- Direct EUR→USD: should now be `Decimal('1.10')` or similar (the stored rate, not its reciprocal)
- Reverse USD→EUR: should now be the reciprocal of direct
- 2-hop EUR→RUB: should now be the path product (not its reciprocal)
- Cross-currency rent_total: the new (correct) aggregate

- [ ] **Step 5: Update the pinned golden values**

In `property_rental/rentals/tests/test_fx_char.py`, replace the inverted expected values with the corrected ones captured in Step 4. In `property_rental/rentals/tests/test_financials_char.py`, update `test_tenant_rent_total_cross_currency`'s expected value.

Add a comment in both files: `# Golden values updated <date> for FX inversion fix (Plan B Task 1). Previous values were reciprocals due to the round(1/fx_rate, 6) bug.`

- [ ] **Step 6: Run the char tests — confirm GREEN**

```bash
cd property_rental && python -m pytest rentals/tests/test_fx_char.py rentals/tests/test_financials_char.py -v
```
All FX + financials char tests pass.

- [ ] **Step 7: Run the FULL backend suite — confirm no other golden values drifted**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```
All 114 tests pass (the only changes are the deliberate golden-value updates in Step 5). If any OTHER test fails, the fix drifted behavior unexpectedly — investigate before proceeding.

- [ ] **Step 8: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/services/fx.py property_rental/rentals/tests/test_fx_char.py property_rental/rentals/tests/test_financials_char.py
git commit -m "fix: remove FX rate inversion bug (round(1/fx_rate, 6) tail); update pinned golden values"
```

---

## Task 2: Consolidate `Tenant.rent_total` FX loop

**Goal:** Replace the per-row FX conversion loop in `Tenant.rent_total` with a call to `services.financials.convert_transactions`. The silent-same-currency fallback (sums at face value when `property.currency == target_currency`) is preserved deliberately (pinned by char test).

**Files:**
- Modify: `property_rental/rentals/models.py` (`Tenant.rent_total` ~line 143-177)
- Modify: `property_rental/rentals/services/financials.py` (`convert_transactions` — verify it handles the rent_total case)

**Interfaces:**
- Consumes: `services.financials.convert_transactions(qs, target_currency, as_of)` from Phase 1 Task 11.
- Produces: `Tenant.rent_total` delegates the FX loop to `convert_transactions`. Same output for same input (char tests stay green).

- [ ] **Step 1: Read the current `Tenant.rent_total`**

```bash
cd property_rental && grep -n "def rent_total" rentals/models.py
```
Read the full method. Note the structure:
- If `target_currency is None or property.currency == target_currency`: SQL `aggregate(Sum('amount'))` (the same-currency short-circuit).
- Else: Python loop iterating transactions, calling `FX.get_rate(...)` per row.

- [ ] **Step 2: Read `services.financials.convert_transactions`**

```bash
cd property_rental && grep -n "def convert_transactions" rentals/services/financials.py
```
Read the function. Verify it: takes a queryset/list of transactions, a target currency, and an as_of date; iterates rows; calls `FX.get_rate` per row when currencies differ; returns the summed Decimal. If it doesn't match `rent_total`'s needs, extend it (but don't change its existing behavior — Phase 1 tests pin it).

- [ ] **Step 3: Refactor `rent_total` to delegate**

Replace the Python FX loop in `Tenant.rent_total` with a call to `services.financials.convert_transactions`. Keep the same-currency short-circuit intact. The method becomes:
```python
def rent_total(self, end_date, start_date=None, target_currency=None, include_post_vacation=False):
    # ... existing queryset filtering (Q(tenant=self) | Q(tenant__isnull=True), date range, etc.) ...
    if target_currency is None or self.property.currency == target_currency:
        return transactions.aggregate(models.Sum('amount'))['amount__sum'] or 0
    from rentals.services.financials import convert_transactions
    return convert_transactions(list(transactions), target_currency, end_date)
```
Adjust the actual call to match `convert_transactions`'s real signature (read it first). Preserve the same-currency short-circuit EXACTLY — it's pinned.

- [ ] **Step 4: Run the char tests — they MUST stay green**

```bash
cd property_rental && python -m pytest rentals/tests/test_financials_char.py -v
```
If `test_tenant_rent_total_same_currency` or `test_tenant_rent_total_cross_currency` fails, the consolidation drifted — fix before proceeding. The cross-currency test was just updated in Task 1; its value should now match the corrected rate.

- [ ] **Step 5: Run the full backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```
All 114 pass.

- [ ] **Step 6: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/models.py property_rental/rentals/services/financials.py
git commit -m "refactor: consolidate Tenant.rent_total FX loop into services.financials.convert_transactions"
```

---

## Task 3: Consolidate `pnl_calc` FX loops

**Goal:** Replace the two per-row FX conversion loops in `services.financials.pnl_calc` with calls to `convert_transactions`. The `default_currency_for_all_data` gate stays.

**Files:**
- Modify: `property_rental/rentals/services/financials.py` (`pnl_calc` — the two loops that iterate transactions per category)

**Interfaces:**
- Produces: `pnl_calc` uses `convert_transactions` for cross-currency aggregation. Same output for same input.

- [ ] **Step 1: Read the current `pnl_calc`**

```bash
cd property_rental && grep -n "def pnl_calc" rentals/services/financials.py
```
Read the full function. Identify the two FX loops:
1. The per-category loop when `default_currency_for_all_data` is True (forces all to default currency).
2. The per-category loop when False (uses each transaction's native currency, converts to target).

Note the `default_currency_for_all_data` gate — it controls whether conversion happens at all.

- [ ] **Step 2: Refactor each loop to use `convert_transactions`**

For each category's transaction set, replace the inline FX loop with:
```python
total = convert_transactions(list(category_transactions), target_currency, as_of)
```
Keep the `default_currency_for_all_data` gate intact — when False and the category's transactions match the target currency, the short-circuit in `convert_transactions` handles it.

**Watch for:** the `pnl_calc` mixed-types quirk (per-category values are `float`, `total` sub-dict is `Decimal`). This is pinned by `test_pnl_calc_portfolio`. Don't "fix" the types — preserve them.

- [ ] **Step 3: Run the char tests — they MUST stay green**

```bash
cd property_rental && python -m pytest rentals/tests/test_financials_char.py -v
```
`test_pnl_calc_portfolio` must pass unchanged (including the mixed-types pin).

- [ ] **Step 4: Run the charts char tests (they derive from pnl_calc)**

```bash
cd property_rental && python -m pytest rentals/tests/test_charts_char.py -v
```
All green — the chart data is unchanged.

- [ ] **Step 5: Run the full backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```
All 114 pass.

- [ ] **Step 6: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/services/financials.py
git commit -m "refactor: consolidate pnl_calc FX loops into services.financials.convert_transactions"
```

---

## Task 4: Consolidation regression tests

**Goal:** Add focused unit tests for `convert_transactions` covering edge cases the char tests don't isolate.

**Files:**
- Create: `property_rental/rentals/tests/test_financials_consolidation.py`

**Interfaces:**
- Consumes: `services.financials.convert_transactions`.
- Produces: regression coverage proving the consolidated helper handles edge cases.

- [ ] **Step 1: Write the tests**

`property_rental/rentals/tests/test_financials_consolidation.py`:
```python
import pytest
from datetime import date
from decimal import Decimal
from rentals.services.financials import convert_transactions
from rentals.tests.factories import (
    PropertyFactory, TransactionFactory, FXFactory, LandlordFactory,
)

@pytest.mark.django_db
def test_convert_transactions_same_currency_short_circuits(db):
    """When all transactions match target currency, no FX lookup happens."""
    property = PropertyFactory(currency="USD")
    txns = [
        TransactionFactory(property=property, amount=Decimal("100.00"), currency="USD", date=date(2024,1,15)),
        TransactionFactory(property=property, amount=Decimal("200.00"), currency="USD", date=date(2024,1,15)),
    ]
    total = convert_transactions(txns, "USD", date(2024,6,1))
    assert total == Decimal("300.00")

@pytest.mark.django_db
def test_convert_transactions_single_cross_currency(db):
    """A single GBP transaction converted to USD uses the FX rate."""
    property = PropertyFactory(currency="GBP")
    FXFactory(date=date(2024,1,1), from_currency="GBP", to_currency="USD", rate=Decimal("1.25"))
    txns = [TransactionFactory(property=property, amount=Decimal("100.00"), currency="GBP", date=date(2024,1,15))]
    total = convert_transactions(txns, "USD", date(2024,6,1))
    assert total == Decimal("125.00")  # 100 * 1.25 (post-FX-fix: actual rate, not reciprocal)

@pytest.mark.django_db
def test_convert_transactions_multi_row_aggregation(db):
    """Multiple transactions in mixed currencies aggregate correctly."""
    property = PropertyFactory(currency="USD")
    FXFactory(date=date(2024,1,1), from_currency="EUR", to_currency="USD", rate=Decimal("1.10"))
    txns = [
        TransactionFactory(property=property, amount=Decimal("100.00"), currency="USD", date=date(2024,1,15)),
        TransactionFactory(property=property, amount=Decimal("100.00"), currency="EUR", date=date(2024,1,15)),
    ]
    total = convert_transactions(txns, "USD", date(2024,6,1))
    # 100 USD + 100 EUR * 1.10 = 100 + 110 = 210
    assert total == Decimal("210.00")

@pytest.mark.django_db
def test_convert_transactions_empty_list_returns_zero(db):
    total = convert_transactions([], "USD", date(2024,6,1))
    assert total == 0
```
**Verify** the expected values match the actual `convert_transactions` behavior by running once and capturing output. Adjust if the function's return type differs (Decimal vs float).

- [ ] **Step 2: Run the tests**

```bash
cd property_rental && python -m pytest rentals/tests/test_financials_consolidation.py -v
```
All 4 pass.

- [ ] **Step 3: Run the full backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```
All 118 pass (114 + 4 new).

- [ ] **Step 4: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/tests/test_financials_consolidation.py
git commit -m "test: add convert_transactions regression tests (FX consolidation safety net)"
```

---

## Task 5: PropertyValuation ViewSet

**Goal:** Add `/api/v1/property-valuations/` — the last CRUD endpoint needed to retire `handle_element`.

**Files:**
- Modify: `property_rental/rentals/api/serializers.py` (add `PropertyCapitalStructureSerializer`)
- Modify: `property_rental/rentals/api/views.py` (add `PropertyCapitalStructureViewSet`)
- Modify: `property_rental/rentals/api/urls.py` (register route)
- Test: `property_rental/rentals/tests/test_api.py` (extend)

**Interfaces:**
- Produces: `GET/POST/PUT/PATCH/DELETE /api/v1/property-valuations/` — per-user-scoped CRUD for `Property_capital_structure`.

- [ ] **Step 1: Move `PropertyValuationSerializer` from views.py to serializers.py**

In `property_rental/rentals/api/serializers.py`, add:
```python
class PropertyCapitalStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Property_capital_structure
        fields = ['id', 'property', 'capital_structure_date', 'capital_structure_value', 'capital_structure_debt']
```
Verify the field names against `property_rental/rentals/models.py` (the `Property_capital_structure` model ~line 123).

- [ ] **Step 2: Write failing tests (TDD)**

In `property_rental/rentals/tests/test_api.py`, extend with:
```python
@pytest.mark.django_db
def test_property_valuation_list_requires_auth(db, client):
    resp = client.get("/api/v1/property-valuations/")
    assert resp.status_code in (401, 403)

@pytest.mark.django_db
def test_property_valuation_list_returns_only_own(auth_client, sample_property):
    from rentals.tests.factories import PropertyCapitalStructureFactory
    val = PropertyCapitalStructureFactory(property=sample_property)
    resp = auth_client.get("/api/v1/property-valuations/")
    assert resp.status_code == 200
    assert any(v["id"] == val.id for v in resp.json())

@pytest.mark.django_db
def test_property_valuation_create_validates_property_ownership(auth_client, sample_property, other_landlord_user):
    from django.test import Client
    from rentals.tests.factories import PropertyFactory
    other_prop = PropertyFactory(owned_by=other_landlord_user.landlord)
    other_client = Client()
    other_client.force_login(other_landlord_user)
    resp = other_client.post("/api/v1/property-valuations/", {
        "property": sample_property.id,
        "capital_structure_date": "2024-01-01",
        "capital_structure_value": "250000.00",
        "capital_structure_debt": "150000.00",
    }, content_type="application/json")
    assert resp.status_code == 400  # property doesn't belong to requester
```

- [ ] **Step 3: Run, confirm fail**

```bash
cd property_rental && python -m pytest rentals/tests/test_api.py -v -k property_valuation
```

- [ ] **Step 4: Implement the ViewSet**

In `property_rental/rentals/api/views.py`, add:
```python
from rest_framework import viewsets
from rentals.models import Property_capital_structure
from .serializers import PropertyCapitalStructureSerializer
from .permissions import IsOwnerOrReadOnly
from rest_framework.permissions import IsAuthenticated

class PropertyCapitalStructureViewSet(viewsets.ModelViewSet):
    serializer_class = PropertyCapitalStructureSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return Property_capital_structure.objects.filter(property__owned_by__user=self.request.user)

    def perform_create(self, serializer):
        # Validate the property belongs to the requester before saving.
        property_id = self.request.data.get('property')
        from rentals.models import Property
        if not Property.objects.filter(id=property_id, owned_by__user=self.request.user).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"property": "This property does not belong to you."})
        serializer.save()

    def perform_update(self, serializer):
        # Same ownership check on the property FK if it's being changed.
        property_id = self.request.data.get('property')
        if property_id is not None:
            from rentals.models import Property
            if not Property.objects.filter(id=property_id, owned_by__user=self.request.user).exists():
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"property": "This property does not belong to you."})
        serializer.save()
```

- [ ] **Step 5: Wire the route**

In `property_rental/rentals/api/urls.py`, add to the router registrations:
```python
from .views import PropertyCapitalStructureViewSet
router.register(r"property-valuations", PropertyCapitalStructureViewSet, basename="property-valuation")
```

- [ ] **Step 6: Run the tests — confirm GREEN**

```bash
cd property_rental && python -m pytest rentals/tests/test_api.py -v -k property_valuation
```

- [ ] **Step 7: Run the full backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```
All pass (118 + new).

- [ ] **Step 8: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/api/ property_rental/rentals/tests/test_api.py
git commit -m "feat(api): add PropertyValuation ViewSet (last CRUD endpoint to retire handle_element)"
```

---

## Task 6: Stats endpoints (properties + tenants with_stats)

**Goal:** Add `GET /api/v1/properties/with_stats/` and `GET /api/v1/tenants/with_stats/` returning entities + their P&L/rent/debt aggregates.

**Files:**
- Modify: `property_rental/rentals/api/views.py` (add `with_stats` `@action` to PropertyViewSet and TenantViewSet)
- Test: `property_rental/rentals/tests/test_stats_endpoints.py` (new)

**Interfaces:**
- Produces:
  - `GET /api/v1/properties/with_stats/?as_of=2024-06-15&currency=USD` → `[{...property fields, gross_income_all_time, expenses_all_time, net_income_all_time, gross_income_ytd, expenses_ytd, net_income_ytd}, ...]`
  - `GET /api/v1/tenants/with_stats/?as_of=2024-06-15&currency=USD` → `[{...tenant fields, rent_rate, revenue_all_time, revenue_ytd, debt}, ...]`

- [ ] **Step 1: Write failing tests**

`property_rental/rentals/tests/test_stats_endpoints.py`:
```python
import pytest
from datetime import date
from decimal import Decimal
from rentals.tests.factories import (
    LandlordFactory, PropertyFactory, TenantFactory, TransactionFactory, LeaseRentFactory,
)

@pytest.mark.django_db
def test_properties_with_stats_requires_auth(db, client):
    resp = client.get("/api/v1/properties/with_stats/")
    assert resp.status_code in (401, 403)

@pytest.mark.django_db
def test_properties_with_stats_returns_aggregates(auth_client, sample_property):
    # Create a transaction so there's data to aggregate
    TransactionFactory(property=sample_property, amount=Decimal("1000.00"), currency="USD", category="rent", date=date(2024,1,15), period="2024-01")
    resp = auth_client.get("/api/v1/properties/with_stats/?as_of=2024-06-15&currency=USD")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    # Verify aggregate fields present
    first = data[0]
    assert "gross_income_all_time" in first
    assert "expenses_all_time" in first
    assert "net_income_all_time" in first

@pytest.mark.django_db
def test_tenants_with_stats_returns_aggregates(auth_client, sample_property):
    from rentals.tests.factories import TenantFactory, LeaseRentFactory
    tenant = TenantFactory(property=sample_property)
    LeaseRentFactory(tenant=tenant, rent=Decimal("1200.00"))
    TransactionFactory(property=sample_property, tenant=tenant, amount=Decimal("1200.00"), currency="USD", category="rent", date=date(2024,1,15), period="2024-01")
    resp = auth_client.get("/api/v1/tenants/with_stats/?as_of=2024-06-15&currency=USD")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    first = data[0]
    assert "rent_rate" in first
    assert "revenue_all_time" in first
    assert "debt" in first
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd property_rental && python -m pytest rentals/tests/test_stats_endpoints.py -v
```

- [ ] **Step 3: Implement the `with_stats` actions**

In `property_rental/rentals/api/views.py`, add `@action` to `PropertyViewSet`:
```python
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import date
from rentals.services.financials import pnl_calc
from rentals.utils import get_currency_symbol  # if needed

class PropertyViewSet(viewsets.ModelViewSet):
    # ... existing code ...

    @action(detail=False, methods=['get'])
    def with_stats(self, request):
        from dateutil.parser import parse as parse_date
        as_of_str = request.query_params.get('as_of')
        currency = request.query_params.get('currency', 'USD')
        try:
            as_of = parse_date(as_of_str).date() if as_of_str else date.today()
        except (ValueError, TypeError):
            as_of = date.today()

        properties = self.get_queryset()
        result = []
        for prop in properties:
            # Compute aggregates via the services layer
            year_start = date(as_of.year, 1, 1)
            income_all = __import__('rentals.services.financials', fromlist=['aggregate']).aggregate(
                end_date=as_of, target_currency=currency, properties=[prop], transaction_type='income')
            expense_all = __import__('rentals.services.financials', fromlist=['aggregate']).aggregate(
                end_date=as_of, target_currency=currency, properties=[prop], transaction_type='expense')
            income_ytd = __import__('rentals.services.financials', fromlist=['aggregate']).aggregate(
                end_date=as_of, start_date=year_start, target_currency=currency, properties=[prop], transaction_type='income')
            expense_ytd = __import__('rentals.services.financials', fromlist=['aggregate']).aggregate(
                end_date=as_of, start_date=year_start, target_currency=currency, properties=[prop], transaction_type='expense')

            data = PropertySerializer(prop).data
            data.update({
                'gross_income_all_time': float(income_all),
                'expenses_all_time': float(expense_all),
                'net_income_all_time': float(income_all + expense_all),  # expense is negative
                'gross_income_ytd': float(income_ytd),
                'expenses_ytd': float(expense_ytd),
                'net_income_ytd': float(income_ytd + expense_ytd),
            })
            result.append(data)
        return Response(result)
```
**Read `services.financials.aggregate`'s actual signature first** — the inline `__import__` is a hack to avoid circular imports; prefer a clean `from rentals.services.financials import aggregate` at the top of the file. Also verify whether `aggregate` takes `transaction_type` as `'income'/'expense'` or filters by category — adjust accordingly.

Add a similar `with_stats` action to `TenantViewSet` using `services.scheduler.debt` and `tenant.rent_total`.

- [ ] **Step 4: Run the tests — confirm GREEN**

```bash
cd property_rental && python -m pytest rentals/tests/test_stats_endpoints.py -v
```
Adjust expected values to match actual output (the test asserts field presence, not exact values — keep it loose for now; exact-value tests are fragile against FX rate changes).

- [ ] **Step 5: Run the full backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```

- [ ] **Step 6: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/api/ property_rental/rentals/tests/test_stats_endpoints.py
git commit -m "feat(api): add properties/with_stats and tenants/with_stats endpoints"
```

---

## Task 7: Action endpoints (vacate + FX update)

**Goal:** Add `POST /api/v1/tenants/:id/vacate/` and `POST /api/v1/fx/update/` as `@action`s.

**Files:**
- Modify: `property_rental/rentals/api/views.py` (add `vacate` to TenantViewSet, `update_rates` to FXViewSet)
- Test: `property_rental/rentals/tests/test_api.py` (extend)

**Interfaces:**
- Produces:
  - `POST /api/v1/tenants/:id/vacate/` body `{lease_end}` → 200 serialized tenant.
  - `POST /api/v1/fx/update/` → 200 `{detail: "FX rates updated"}` (wraps `services.fx.update_rates`).

- [ ] **Step 1: Write failing tests**

In `property_rental/rentals/tests/test_api.py`, extend:
```python
@pytest.mark.django_db
def test_vacate_tenant_sets_lease_end(auth_client, sample_property):
    from rentals.tests.factories import TenantFactory
    from rentals.models import Tenant
    tenant = TenantFactory(property=sample_property)
    resp = auth_client.post(f"/api/v1/tenants/{tenant.id}/vacate/", {"lease_end": "2024-12-31"}, content_type="application/json")
    assert resp.status_code == 200
    tenant.refresh_from_db()
    assert str(tenant.lease_end) == "2024-12-31"

@pytest.mark.django_db
def test_vacate_tenant_other_landlord_404(auth_client, sample_property, other_landlord_user):
    from django.test import Client
    from rentals.tests.factories import TenantFactory, PropertyFactory
    other_prop = PropertyFactory(owned_by=other_landlord_user.landlord)
    other_tenant = TenantFactory(property=other_prop)
    resp = auth_client.post(f"/api/v1/tenants/{other_tenant.id}/vacate/", {"lease_end": "2024-12-31"}, content_type="application/json")
    assert resp.status_code == 404

@pytest.mark.django_db
def test_fx_update_endpoint(auth_client):
    from unittest.mock import patch
    with patch('rentals.services.fx.update_rates') as mock_update:
        resp = auth_client.post("/api/v1/fx/update/")
        assert resp.status_code == 200
        assert mock_update.called
```

- [ ] **Step 2: Run, confirm fail**

- [ ] **Step 3: Implement the actions**

In `property_rental/rentals/api/views.py`:
```python
from rest_framework.decorators import action

class TenantViewSet(viewsets.ModelViewSet):
    # ... existing ...

    @action(detail=True, methods=['post'])
    def vacate(self, request, pk=None):
        tenant = self.get_object()  # ownership-scoped
        lease_end = request.data.get('lease_end')
        if not lease_end:
            return Response({"lease_end": "This field is required."}, status=400)
        tenant.lease_end = lease_end
        tenant.save()
        return Response(TenantSerializer(tenant).data, status=200)

class FXViewSet(viewsets.ModelViewSet):
    # ... existing ...

    @action(detail=False, methods=['post'])
    def update_rates(self, request):
        from rentals.services.fx import update_rates
        update_rates(request.user)
        return Response({"detail": "FX rates updated"}, status=200)
```
**Read `services.fx.update_rates`'s actual signature first** — it may take a user or a property queryset. Adjust the call.

- [ ] **Step 4: Run the tests — confirm GREEN**

- [ ] **Step 5: Run the full backend suite**

- [ ] **Step 6: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/api/ property_rental/rentals/tests/test_api.py
git commit -m "feat(api): add vacate-tenant and fx-update action endpoints"
```

---

## Task 8: Auth endpoints (PATCH /me + change-password)

**Goal:** Add `PATCH /api/v1/auth/me/` for settings updates and `POST /api/v1/auth/change-password/`.

**Files:**
- Modify: `property_rental/rentals/api/auth.py` (extend MeView with PATCH; add ChangePasswordView)
- Modify: `property_rental/rentals/api/urls.py` (add change-password route)
- Test: `property_rental/rentals/tests/test_auth_api.py` (extend)

**Interfaces:**
- Produces:
  - `PATCH /api/v1/auth/me/` — partial update of user settings (default_currency, chart_frequency, etc.).
  - `POST /api/v1/auth/change-password/` body `{old_password, new_password1, new_password2}` → 200 or 400.

- [ ] **Step 1: Write failing tests**

In `property_rental/rentals/tests/test_auth_api.py`, extend:
```python
@pytest.mark.django_db
def test_patch_me_updates_settings(db):
    from rentals.tests.factories import UserFactory
    user = UserFactory(is_landlord=True, chart_frequency='M')
    user.set_password("OldPass123!")
    user.save()
    c = Client()
    c.force_login(user)
    resp = c.patch("/api/v1/auth/me/", {"chart_frequency": "Q"}, content_type="application/json")
    assert resp.status_code == 200
    assert resp.json()["user"]["chart_frequency"] == "Q"
    user.refresh_from_db()
    assert user.chart_frequency == "Q"

@pytest.mark.django_db
def test_change_password_success(db):
    from rentals.tests.factories import UserFactory
    user = UserFactory(is_landlord=True)
    user.set_password("OldPass123!")
    user.save()
    c = Client()
    c.force_login(user)
    resp = c.post("/api/v1/auth/change-password/", {
        "old_password": "OldPass123!",
        "new_password1": "NewPass456!",
        "new_password2": "NewPass456!",
    }, content_type="application/json")
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.check_password("NewPass456!")

@pytest.mark.django_db
def test_change_password_wrong_old_returns_400(db):
    from rentals.tests.factories import UserFactory
    user = UserFactory(is_landlord=True)
    user.set_password("OldPass123!")
    user.save()
    c = Client()
    c.force_login(user)
    resp = c.post("/api/v1/auth/change-password/", {
        "old_password": "WrongPass!",
        "new_password1": "NewPass456!",
        "new_password2": "NewPass456!",
    }, content_type="application/json")
    assert resp.status_code == 400
```

- [ ] **Step 2: Run, confirm fail**

- [ ] **Step 3: Extend MeView with PATCH**

In `property_rental/rentals/api/auth.py`, add a `patch` method to `MeView`:
```python
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"user": UserSerializer(request.user).data})

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"user": serializer.data})
```

- [ ] **Step 4: Add ChangePasswordView**

```python
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        form = PasswordChangeForm(request.user, data={
            'old_password': request.data.get('old_password', ''),
            'new_password1': request.data.get('new_password1', ''),
            'new_password2': request.data.get('new_password2', ''),
        })
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)
            return Response({"detail": "Password changed"}, status=200)
        return Response(form.errors, status=400)
```
Wire `path("auth/change-password/", ChangePasswordView.as_view())` in `urls.py`.

- [ ] **Step 5: Run the tests — confirm GREEN**

- [ ] **Step 6: Run the full backend suite**

- [ ] **Step 7: Commit**

```bash
cd "D:/Developing/Property-rental"
git add property_rental/rentals/api/ property_rental/rentals/tests/test_auth_api.py
git commit -m "feat(api): add PATCH /auth/me/ and POST /auth/change-password/"
```

---

## Task 9: Frontend types + fixtures

**Goal:** Add TypeScript types for all entities + canned fixtures for tests.

**Files:**
- Create: `frontend/src/types/{property,tenant,transaction,fx,propertyValuation}.ts`
- Create: `frontend/src/__fixtures__/{property,tenant,transaction,fx,propertyValuation,lists}.ts`

**Interfaces:**
- Produces: typed entity shapes used by all hooks/forms/pages in B2.

- [ ] **Step 1: Write the types**

Verify each against `property_rental/rentals/api/serializers.py` field lists first. Create:

`frontend/src/types/property.ts`:
```typescript
export type Property = {
  id: number
  owned_by: number
  name: string
  location: string
  address: string
  num_bedrooms: number
  area: string | null
  currency: string
  sold: string | null
}

export type PropertyWithStats = Property & {
  gross_income_all_time: number
  expenses_all_time: number
  net_income_all_time: number
  gross_income_ytd: number
  expenses_ytd: number
  net_income_ytd: number
}
```

`frontend/src/types/tenant.ts`:
```typescript
export type Tenant = {
  id: number
  user: number | null
  property: number
  first_name: string
  last_name: string
  phone: string
  email: string
  lease_start: string
  lease_end: string | null
  payday: number
}

export type TenantWithStats = Tenant & {
  rent_rate: number | string
  revenue_all_time: number
  revenue_ytd: number
  debt: number
}
```

`frontend/src/types/transaction.ts`:
```typescript
export type Transaction = {
  id: number
  property: number
  tenant: number | null
  date: string
  category: string
  period: string
  currency: string
  amount: string  // Decimal as string
  type: string    // read-only
  comment: string | null
}
```

`frontend/src/types/fx.ts`:
```typescript
export type FX = {
  id: number
  date: string
  from_currency: string
  to_currency: string
  rate: string  // Decimal as string
}
```

`frontend/src/types/propertyValuation.ts`:
```typescript
export type PropertyValuation = {
  id: number
  property: number
  capital_structure_date: string
  capital_structure_value: string
  capital_structure_debt: string
}
```

- [ ] **Step 2: Write the fixtures**

`frontend/src/__fixtures__/property.ts`:
```typescript
import type { Property, PropertyWithStats } from '@/types/property'

export const fixtureProperty: Property = {
  id: 1, owned_by: 1, name: 'Riverside Flat', location: 'Berlin, DE',
  address: 'Hauptstrasse 1', num_bedrooms: 2, area: '75.50',
  currency: 'EUR', sold: null,
}

export const fixturePropertyWithStats: PropertyWithStats = {
  ...fixtureProperty,
  gross_income_all_time: 7200, expenses_all_time: 1680, net_income_all_time: 8880,
  gross_income_ytd: 3600, expenses_ytd: 840, net_income_ytd: 4440,
}
```

Similarly for tenant, transaction, fx, propertyValuation, and a `lists.ts` with arrays.

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/src/types/ frontend/src/__fixtures__/
git commit -m "feat(frontend): add entity types + test fixtures"
```

---

## Task 10: Frontend API hooks + cache keys

**Goal:** Add React Query hooks for all entities + extend the centralized key factory.

**Files:**
- Modify: `frontend/src/api/keys.ts`
- Create: `frontend/src/api/{properties,tenants,transactions,fx,propertyValuations}.ts`
- Modify: `frontend/src/api/auth.ts` (add `useUpdateMe`, `useChangePassword`)
- Modify: `frontend/src/test/handlers.ts` (add MSW defaults for all new endpoints)

**Interfaces:**
- Produces: all entity hooks + the cascade invalidation pattern.

- [ ] **Step 1: Extend `keys.ts`**

Replace `frontend/src/api/keys.ts` with the full key factory from the spec §5.2 (properties, tenants, transactions, fx, propertyValuations, chartData — each with `all` / `detail(id)` / `byProperty(pid)` / `withStats` / `filtered(f)` as appropriate).

- [ ] **Step 2: Write each entity's hooks**

One file per entity. Pattern (example for properties):
```typescript
// frontend/src/api/properties.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'
import type { Property, PropertyWithStats } from '@/types/property'

export function useProperties() {
  return useQuery<Property[]>({
    queryKey: queryKeys.properties.all,
    queryFn: () => apiFetch<Property[]>('/properties/'),
  })
}

export function usePropertiesWithStats(asOf?: string, currency?: string) {
  return useQuery<PropertyWithStats[]>({
    queryKey: queryKeys.properties.withStats,
    queryFn: () => apiFetch<PropertyWithStats[]>('/properties/with_stats/', { query: { as_of: asOf, currency } }),
  })
}

export function useProperty(id: number) {
  return useQuery<Property>({
    queryKey: queryKeys.properties.detail(id),
    queryFn: () => apiFetch<Property>(`/properties/${id}/`),
  })
}

export function useCreateProperty() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<Property>) => apiFetch<Property>('/properties/', { method: 'POST', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.properties.all })
      qc.invalidateQueries({ queryKey: queryKeys.properties.withStats })
    },
  })
}

export function useUpdateProperty() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Property> }) =>
      apiFetch<Property>(`/properties/${id}/`, { method: 'PATCH', body: data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.properties.all })
      qc.invalidateQueries({ queryKey: queryKeys.properties.withStats })
    },
  })
}

export function useDeleteProperty() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/properties/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.properties.all })
      qc.invalidateQueries({ queryKey: queryKeys.properties.withStats })
    },
  })
}
```

Follow the same pattern for tenants (+ `useVacateTenant`), transactions (with filter support), fx (+ `useUpdateFX`), propertyValuations (with `byProperty`).

- [ ] **Step 3: Extend `auth.ts`**

Add `useUpdateMe()` (PATCH /auth/me/) and `useChangePassword()` (POST /auth/change-password/).

- [ ] **Step 4: Extend MSW handlers**

In `frontend/src/test/handlers.ts`, add default handlers for every new endpoint (CRUD for all entities + stats + actions + auth patches). Use the fixtures from Task 9.

- [ ] **Step 5: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 6: Verify existing frontend tests still pass**

```bash
cd frontend && npm test
```
All 15 prior tests pass (MSW handler additions shouldn't break them).

- [ ] **Step 7: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/src/api/ frontend/src/test/handlers.ts
git commit -m "feat(frontend): add entity React Query hooks + cache keys + MSW handlers"
```

---

## Task 11: Frontend forms (react-hook-form + zod)

**Goal:** Build all 6 entity forms with validation.

**Files:**
- Create: `frontend/src/components/forms/{PropertyForm,TenantForm,TransactionForm,PropertyValuationForm,VacateTenantForm,ProfileSettingsForm}.tsx`
- Install: `react-hook-form @hookform/resolvers zod`
- shadcn add: `select checkbox form dropdown-menu`

**Interfaces:**
- Produces: validated forms callable as `<PropertyForm defaultValues={...} onSubmit={...} />`.

- [ ] **Step 1: Install deps + shadcn components**

```bash
cd frontend
npm install react-hook-form @hookform/resolvers zod
npx shadcn@latest add select checkbox form dropdown-menu
```

- [ ] **Step 2: Write each form**

Each form follows this pattern (PropertyForm example):
```tsx
// frontend/src/components/forms/PropertyForm.tsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'

const schema = z.object({
  name: z.string().min(1, 'Required'),
  location: z.string().min(1, 'Required'),
  address: z.string().optional().default(''),
  num_bedrooms: z.coerce.number().min(0),
  area: z.string().optional().default(''),
  currency: z.enum(['USD', 'EUR', 'GBP', 'RUB']),
  sold: z.string().optional().nullable(),
})
type Values = z.infer<typeof schema>

type Props = {
  defaultValues?: Partial<Values>
  onSubmit: (values: Values) => void
  isSubmitting?: boolean
}

export function PropertyForm({ defaultValues, onSubmit, isSubmitting }: Props) {
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues })
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField name="name" render={({ field }) => (
          <FormItem><FormLabel>Name</FormLabel><FormControl><Input {...field} /></FormControl><FormMessage /></FormItem>
        )} />
        {/* ... other fields ... */}
        <Button type="submit" disabled={isSubmitting}>Save</Button>
      </form>
    </Form>
  )
}
```

Write all 6 forms. The TenantForm's `property` field and TransactionForm's `tenant` field are Selects populated from the user's own properties/tenants (passed as props or fetched inside the form). The TransactionForm's tenant select filters by the selected property (cascade — watch the selected property, filter tenants accordingly).

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "feat(frontend): add entity forms (react-hook-form + zod)"
```

---

## Task 12: Frontend shared components (modals + DataTable + states)

**Goal:** Build the reusable modal patterns, DataTable, and loading/empty/error state components.

**Files:**
- shadcn add: `dialog table badge tooltip separator`
- Install: `@tanstack/react-table`
- Create: `frontend/src/components/modals/{EntityFormDialog,ConfirmDialog,VacateTenantDialog}.tsx`
- Create: `frontend/src/components/table/DataTable.tsx`
- Create: `frontend/src/components/states/{SkeletonTable,EmptyState,ErrorState}.tsx`

**Interfaces:**
- Produces:
  - `<EntityFormDialog open onOpenChange entity mode onSuccess />`
  - `<ConfirmDialog open onOpenChange title description onConfirm />`
  - `<DataTable columns data onRowClick />`
  - `<SkeletonTable />`, `<EmptyState />`, `<ErrorState />`

- [ ] **Step 1: Install deps + shadcn components**

```bash
cd frontend
npm install @tanstack/react-table
npx shadcn@latest add dialog table badge tooltip separator
```

- [ ] **Step 2: Write the DataTable component**

`frontend/src/components/table/DataTable.tsx`:
```tsx
import { useState } from 'react'
import {
  ColumnDef, flexRender, getCoreRowModel, getSortedRowModel,
  getPaginationRowModel, SortingState, useReactTable,
} from '@tanstack/react-table'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'

type Props<T> = {
  columns: ColumnDef<T, any>[]
  data: T[]
  onRowClick?: (row: T) => void
  pageSize?: number
}

export function DataTable<T extends { id: number }>({ columns, data, onRowClick, pageSize = 10 }: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const table = useReactTable({
    data, columns, state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  })

  return (
    <div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map(hg => (
              <TableRow key={hg.id}>
                {hg.headers.map(header => (
                  <TableHead key={header.id}>
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map(row => (
              <TableRow
                key={row.id}
                onClick={() => onRowClick?.(row.original)}
                className={onRowClick ? 'cursor-pointer' : ''}
              >
                {row.getVisibleCells().map(cell => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end space-x-2 py-4">
        <Button variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>Previous</Button>
        <Button variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>Next</Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Write the modals**

`EntityFormDialog` wraps a form in shadcn `<Dialog>`, calls the appropriate mutation, invalidates, toasts, closes. `ConfirmDialog` shows a title + description + confirm/cancel buttons. `VacateTenantDialog` wraps VacateTenantForm.

- [ ] **Step 4: Write the state components**

`SkeletonTable` renders grey placeholder rows. `EmptyState` renders an icon + title + description + optional CTA button. `ErrorState` renders an error message + retry button.

- [ ] **Step 5: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 6: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "feat(frontend): add DataTable, modal patterns, state components"
```

---

## Task 13: Frontend tests — entity hooks

**Goal:** Test the React Query hooks for all entities.

**Files:**
- Create: `frontend/src/api/{properties,tenants,transactions,fx,propertyValuations}.test.tsx`

- [ ] **Step 1: Write hook tests**

For each entity, write tests covering: query returns data, mutation invalidates the right keys. Example:
```typescript
// frontend/src/api/properties.test.tsx
import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useProperties, useCreateProperty } from './properties'
import type { ReactNode } from 'react'

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

describe('useProperties', () => {
  it('returns properties', async () => {
    const { result } = renderHook(() => useProperties(), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.length).toBeGreaterThan(0)
  })
})

describe('useCreateProperty', () => {
  it('invalidates the properties cache on success', async () => {
    const qc = new QueryClient()
    const w = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    const { result } = renderHook(() => useCreateProperty(), { wrapper: w })
    result.current.mutate({ name: 'New', location: 'X', currency: 'USD' } as any)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // Cache was invalidated; verify by checking the query is stale
    expect(qc.getQueryState(['properties'])?.isInvalidated).toBe(true)
  })
})
```

- [ ] **Step 2: Run the tests**

```bash
cd frontend && npm test
```

- [ ] **Step 3: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/src/api/
git commit -m "test(frontend): entity React Query hook tests"
```

---

## Task 14: Frontend tests — forms

**Goal:** Test the zod validation + submit behavior of each form.

**Files:**
- Create: `frontend/src/components/forms/{PropertyForm,TenantForm,TransactionForm}.test.tsx`

- [ ] **Step 1: Write form tests**

For each form: renders, shows zod errors on invalid input, calls onSubmit with valid values. Example:
```typescript
// PropertyForm.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PropertyForm } from './PropertyForm'

describe('PropertyForm', () => {
  it('shows validation error on empty name', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<PropertyForm onSubmit={onSubmit} />)
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(await screen.findByText(/required/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('calls onSubmit with valid values', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<PropertyForm onSubmit={onSubmit} />)
    await user.type(screen.getByLabelText(/name/i), 'Test Property')
    await user.type(screen.getByLabelText(/location/i), 'Berlin')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: 'Test Property' })))
  })
})
```

- [ ] **Step 2: Run + commit**

---

## Task 15: Frontend tests — DataTable

**Goal:** Test sorting, pagination, row click.

**Files:**
- Create: `frontend/src/components/table/DataTable.test.tsx`

- [ ] **Step 1: Write DataTable tests**

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DataTable } from './DataTable'
import type { Property } from '@/types/property'
import { fixtureProperty } from '@/__fixtures__/property'

const columns = [
  { accessorKey: 'name', header: 'Name' },
  { accessorKey: 'location', header: 'Location' },
]

describe('DataTable', () => {
  it('renders rows', () => {
    render(<DataTable columns={columns} data={[fixtureProperty]} />)
    expect(screen.getByText('Riverside Flat')).toBeInTheDocument()
  })

  it('calls onRowClick when row clicked', async () => {
    const onRowClick = vi.fn()
    render(<DataTable columns={columns} data={[fixtureProperty]} onRowClick={onRowClick} />)
    await userEvent.setup().click(screen.getByText('Riverside Flat'))
    expect(onRowClick).toHaveBeenCalledWith(fixtureProperty)
  })
})
```

- [ ] **Step 2: Run + commit**

---

## Task 16: Frontend tests — MSW handler coverage

**Goal:** Verify all new MSW handlers intercept correctly (no unhandled requests).

**Files:**
- Modify: `frontend/src/test/handlers.ts` (verify completeness)
- Verify: existing tests still pass after handler additions

- [ ] **Step 1: Run the full frontend suite with strict mode**

```bash
cd frontend && npm test
```
MSW is in `onUnhandledRequest: 'error'` mode — if any test triggers an unhandled request, it fails. Fix by adding the missing handler.

- [ ] **Step 2: Commit any handler fixes**

---

## Task 17: Frontend tests — auth hooks extension

**Goal:** Test `useUpdateMe` and `useChangePassword`.

**Files:**
- Modify: `frontend/src/api/auth.test.tsx` (extend)

- [ ] **Step 1: Write tests for the new auth hooks**

```typescript
describe('useUpdateMe', () => {
  it('updates settings and refetches me', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useUpdateMe(), { wrapper })
    result.current.mutate({ chart_frequency: 'Q' } as any)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(qc.getQueryState(['auth', 'me'])?.isInvalidated).toBe(true)
  })
})
```

- [ ] **Step 2: Run + commit**

---

## Task 18: Definition-of-done verification

This task runs the full verification checklist. No code changes unless a check fails.

- [ ] **Step 1: Backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```
Confirm all green (should be ~125+ depending on additions).

- [ ] **Step 2: Frontend suite**

```bash
cd frontend && npm test
```
All green.

- [ ] **Step 3: Frontend build**

```bash
cd frontend && npm run build
```
No errors.

- [ ] **Step 4: `check --deploy`**

```bash
cd property_rental && python manage.py check --deploy
```
No new critical issues.

- [ ] **Step 5: `makemigrations --check`**

```bash
cd property_rental && python manage.py makemigrations --check --dry-run
```
No pending migrations.

- [ ] **Step 6: Commit + tag**

```bash
cd "D:/Developing/Property-rental"
git commit --allow-empty -m "chore: Plan B1 (backend + FX fix + frontend infra) verification complete"
git tag plan-b1-complete
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task(s) | Covered? |
|---|---|---|
| §4.1 PropertyValuation ViewSet | Task 5 | ✅ |
| §4.2 FX inversion fix | Task 1 | ✅ |
| §4.2 FX consolidation (rent_total) | Task 2 | ✅ |
| §4.2 FX consolidation (pnl_calc) | Task 3 | ✅ |
| §4.2 Consolidation regression tests | Task 4 | ✅ |
| §4.3 Stats endpoints | Task 6 | ✅ |
| §4.4 Vacate + FX update actions | Task 7 | ✅ |
| §4.4 PATCH /me + change-password | Task 8 | ✅ |
| §5.1 Types | Task 9 | ✅ |
| §5.2 API hooks + cache keys | Task 10 | ✅ |
| §5.3 Forms | Task 11 | ✅ |
| §5.4-5.7 Modals + DataTable + states + toasts | Task 12 | ✅ |
| §8 Frontend tests (hooks) | Task 13 | ✅ |
| §8 Frontend tests (forms) | Task 14 | ✅ |
| §8 Frontend tests (DataTable) | Task 15 | ✅ |
| §8 MSW handler coverage | Task 16 | ✅ |
| §8 Auth hooks tests | Task 17 | ✅ |

**Spec sections NOT in B1** (covered by B2):
- §6 page-by-page wiring → B2
- §7 legacy deletion → B2
- §9 DoD items about pages rendering → B2

**2. Placeholder scan:** Searched for TBD/TODO/etc. — the inline `__import__` hack in Task 6 Step 3 is flagged as a hack with instruction to use a clean import. The stats-endpoint response shapes depend on reading `services.financials.aggregate`'s actual signature — the task says "read it first." Acceptable.

**3. Type consistency:**
- `Property` / `Tenant` / `Transaction` / `FX` / `PropertyValuation` types: defined Task 9, consumed Tasks 10-15. Consistent.
- `queryKeys` factory: extended Task 10, consumed Tasks 10-15. Consistent.
- `convert_transactions(qs, target_currency, as_of)`: defined Phase 1, consumed Tasks 2-4. Consistent.
- `apiFetch<T>(path, options)`: defined Plan A, consumed all hooks. Consistent.

All consistent.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-entity-backend-infra.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
