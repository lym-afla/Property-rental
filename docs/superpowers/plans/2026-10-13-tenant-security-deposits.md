# Tenant Security Deposits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record tenant security deposits (received / returned / applied) as a liability ledger that never reaches income, with applied amounts landing as rent or cost-reimbursement income, deposits shown distinctly in cash flow, and add/edit UI on the tenant page.

**Architecture:** New `DepositMovement` model with all writes through `rentals/services/deposits.py`. Applications create (or attach to) an ordinary `Transaction`, so P&L, yields and arrears need no code change. Only `portfolio_cash_flow` gains deposit keys, and only when movements exist in scope. React UI adds a Security deposit card on the tenant page, a read-only summary on the property page and a deposit series in the net cash flow chart.

**Tech Stack:** Django 4.2, DRF 3.14, pytest + pytest-django + factory-boy (`uv run pytest`); React + TypeScript, React Query, react-hook-form + zod, vitest (`npm test` in `frontend/`).

**Spec:** `docs/superpowers/specs/2026-10-13-tenant-security-deposits-design.md`

## Global Constraints

- Movement kinds: `received`, `returned`, `applied`. Application categories: `rent`, `cost_reimbursement` only.
- `amount` stored positive (`> 0`); signed value: received `+amount`, returned/applied `-amount`.
- One currency per tenant deposit; no FX between movements; conversion only for reporting.
- Running balance per tenant, replayed in `(date, received-before-outflows, id)` order, never below zero.
- Auto-created transaction comment is exactly `"Applied from security deposit"`.
- Linked transaction FK: `OneToOneField(..., on_delete=models.RESTRICT, related_name="deposit_movement")`.
- Cash-flow series exactly: `SeriesDefinition("deposits", "Security deposits", "deposit_movement")`, `SeriesDefinition("net_cash_flow", "Net cash flow", "net_cash")`, appended after `cumulative_net_income`, present only when a movement is in scope.
- 409 message for linked transaction delete/edit: `"Edit the security deposit movement instead."`
- Existing tests (incl. `test_financials_char.py`, `test_fx_char.py`, `test_analytics_cash_flow.py`) must pass unchanged.
- Run backend tests from the repo root: `uv run pytest property_rental/rentals/tests/<file> -q`.

## Review Focus

1. **Shrinking a receipt below what was already applied/returned** (edit, not delete) — expected: 400 overdraw. Test in Task 2.
2. **Receipt and application on the same date** — expected: allowed (receipt replays first). Test in Task 2.
3. **Changing currency of a tenant's only movement** — expected: allowed (rule 1 compares against *other* movements). Test in Task 2.
4. **Cash flow filtered to property A while property B's tenant has deposits** — expected: no deposit keys for A. Test in Task 5.
5. **Editing an attach-mode movement in the form** — expected: its current linked transaction remains selectable even though it is "already linked". Test in Task 8.

## File Structure

| File | Responsibility |
|---|---|
| `property_rental/rentals/constants.py` | add kind / application-category constants |
| `property_rental/rentals/financial_semantics.py` | add `deposit_signed_amount` |
| `property_rental/rentals/models.py` | add `DepositMovement` |
| `property_rental/rentals/migrations/0028_depositmovement.py` | generated |
| `property_rental/rentals/admin.py` | read-only admin |
| `property_rental/rentals/services/deposits.py` | write rules + balance reads (new) |
| `property_rental/rentals/api/serializers.py` | `DepositMovementSerializer`; `deposit_movement` on `TransactionSerializer` |
| `property_rental/rentals/api/views.py` | `DepositMovementViewSet` (+ `balance` action); 409 guards in `TransactionViewSet` |
| `property_rental/rentals/api/urls.py` | register `deposit-movements` |
| `property_rental/rentals/analytics/cash_flow.py` | deposit keys/series |
| `frontend/src/types/deposit.ts`, `frontend/src/api/deposits.ts` | types + hooks (new) |
| `frontend/src/components/forms/DepositMovementForm.tsx` | form (new) |
| `frontend/src/features/tenant/SecurityDepositCard.tsx` | tenant page card (new) |
| `frontend/src/features/property/DepositsHeldSummary.tsx` | property page summary (new) |

---

### Task 1: Model, constants, semantics helper

**Files:**
- Modify: `property_rental/rentals/constants.py`, `property_rental/rentals/financial_semantics.py`, `property_rental/rentals/models.py`, `property_rental/rentals/admin.py`
- Create: `property_rental/rentals/migrations/0028_depositmovement.py` (via `makemigrations`)
- Test: `property_rental/rentals/tests/test_deposit_semantics.py`

**Interfaces:**
- Produces: `constants.DEPOSIT_MOVEMENT_KINDS = (("received","Received"),("returned","Returned"),("applied","Applied"))`; `constants.DEPOSIT_APPLICATION_CATEGORIES = ("rent", "cost_reimbursement")`; `financial_semantics.deposit_signed_amount(kind: str, amount: Decimal) -> Decimal`; model `DepositMovement` with fields exactly as the spec's Data model table (`tenant`, `date`, `kind`, `currency`, `amount`, `applied_to`, `transaction`, `owns_transaction`, `comment`), `Meta.ordering = ("date", "id")`, check constraints `deposit_amount_positive` (`amount__gt=0`) and `deposit_applied_to_iff_applied` (`Q(kind="applied", applied_to__isnull=False) | (~Q(kind="applied") & Q(applied_to__isnull=True))`).

- [ ] **Step 1: Write failing tests**

```python
from decimal import Decimal
import pytest
from django.db import IntegrityError
from rentals.financial_semantics import deposit_signed_amount

@pytest.mark.parametrize("kind,expected", [("received", Decimal("500")), ("returned", Decimal("-500")), ("applied", Decimal("-500"))])
def test_deposit_signed_amount(kind, expected):
    assert deposit_signed_amount(kind, Decimal("500")) == expected

def test_deposit_signed_amount_rejects_unknown_kind():
    with pytest.raises(ValueError):
        deposit_signed_amount("rent", Decimal("1"))

@pytest.mark.django_db
def test_amount_must_be_positive():
    from rentals.models import DepositMovement
    from rentals.tests.factories import TenantFactory
    with pytest.raises(IntegrityError):
        DepositMovement.objects.create(tenant=TenantFactory(), date="2026-01-01", kind="received", currency="GBP", amount=Decimal("0"))

@pytest.mark.django_db
def test_applied_requires_applied_to():
    from rentals.models import DepositMovement
    from rentals.tests.factories import TenantFactory
    with pytest.raises(IntegrityError):
        DepositMovement.objects.create(tenant=TenantFactory(), date="2026-01-01", kind="applied", currency="GBP", amount=Decimal("10"))
```

- [ ] **Step 2: Run** `uv run pytest property_rental/rentals/tests/test_deposit_semantics.py -q` — Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** constants, `deposit_signed_amount` (raises `ValueError` on unknown kind), and `DepositMovement`. Register in admin with a `ModelAdmin` whose `has_add/change/delete_permission` return `False`.
- [ ] **Step 4: Generate migration** `uv run python property_rental/manage.py makemigrations rentals -n depositmovement` — Expected: creates `0028_depositmovement.py`.
- [ ] **Step 5: Run** the test file, then `uv run pytest -q` — Expected: all PASS.
- [ ] **Step 6: Commit** `feat: add DepositMovement model and signed-amount semantics`

### Task 2: Deposit service — rules and reads

**Files:**
- Create: `property_rental/rentals/services/deposits.py`
- Test: `property_rental/rentals/tests/test_deposits_service.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `class DepositRuleError(Exception)` with attributes `field: str`, `message: str`.
  - `create_movement(tenant, *, date, kind, currency, amount, applied_to=None, transaction=None, comment=None) -> DepositMovement`
  - `update_movement(movement, **fields) -> DepositMovement` (fields: any of `date, currency, amount, applied_to, transaction, comment`; `kind` change to/from `applied` raises `DepositRuleError("kind", ...)`)
  - `delete_movement(movement) -> None`
  - `deposit_held(*, as_of, tenant=None, property=None) -> dict[str, Decimal]` (exactly one of tenant/property, else `ValueError`)
  - `deposit_held_by_tenant(*, property, as_of) -> list[tuple[Tenant, str, Decimal]]` (tenants with a non-empty history, ordered by tenant id)
  - `movements_for_user(user, *, start=None, end=None, property_ids=(), tenant_id=None) -> QuerySet[DepositMovement]` (`select_related("tenant__property")`)
- All writes in `transaction.atomic()`. Validation runs on the post-change list of the tenant's movements (built in memory) before any DB write.

Replay ordering key (not determined by the signature):

```python
def _replay_key(m):
    return (m.date, 0 if m.kind == "received" else 1, m.id or 0)
```

Field names used in `DepositRuleError`: `currency` (rule 1), `amount` (rule 2 overdraw, rule 4 amount), `transaction` (rule 4 other mismatches / already linked), `applied_to` (rule 7, missing on applied), `kind`.

- [ ] **Step 1: Write failing tests.** Use a `tenant` fixture (`TenantFactory(property=sample_property, lease_start=date(2025,1,1))`) and `rcv = lambda amt, d="2025-01-01": create_movement(tenant, date=date.fromisoformat(d), kind="received", currency="GBP", amount=Decimal(amt))`. Tests and key assertions:
  - `test_receive_partial_return_balance`: rcv 1500 on 2025-01-01; returned 500 on 2025-06-01 → `deposit_held(tenant=t, as_of=date(2025,5,31)) == {"GBP": Decimal("1500")}`, at 2025-06-01 `== {"GBP": Decimal("1000")}`, at 2024-12-31 `== {}`.
  - `test_currency_locked_to_existing_movements`: rcv GBP then received EUR → `DepositRuleError` with `field == "currency"`.
  - `test_currency_of_only_movement_can_change` (Review Focus 3): `update_movement(m, currency="EUR")` succeeds.
  - `test_return_cannot_exceed_held`: rcv 1000; returned 1000.01 → `field == "amount"`.
  - `test_outflow_before_receipt_rejected`: rcv on 2025-03-01; returned 100 on 2025-02-01 → `field == "amount"`.
  - `test_same_day_receipt_and_application_allowed` (Review Focus 2): rcv 1000 and applied 1000 (rent) both 2025-01-01, applied created first → succeeds.
  - `test_shrinking_receipt_below_applied_rejected` (Review Focus 1): rcv 1000; applied 800; `update_movement(receipt, amount=Decimal("700"))` → `field == "amount"`; receipt still 1000 in DB.
  - `test_deleting_receipt_needed_by_later_outflow_rejected`.
  - `test_apply_create_mode_creates_owned_rent_transaction`: applied 1500 rent on 2025-12-01 → `m.owns_transaction`, `m.transaction.category == "rent"`, `.amount == Decimal("1500")`, `.tenant == tenant`, `.property == tenant.property`, `.currency == "GBP"`, `.comment == "Applied from security deposit"`.
  - `test_apply_cost_reimbursement_creates_positive_contra_expense`: `m.transaction.amount == Decimal("200")`, `.type == "expense"`.
  - `test_apply_attach_mode_links_existing_row`: rent `TransactionFactory(property=p, tenant=t, category="rent", amount=1500, currency="GBP", date=2025-12-01)`; applied 500 with `transaction=row` → `not m.owns_transaction`, `Transaction.objects.count()` unchanged.
  - `test_attach_rejects_mismatch` (parametrize: other tenant / category `utilities` / currency `EUR` / different date / amount above row / row already linked) → `field` as listed above.
  - `test_update_owned_application_syncs_transaction`: change amount 1500→1200 and date → transaction matches.
  - `test_delete_owned_application_deletes_transaction` and `test_delete_attached_application_keeps_transaction`.
  - `test_kind_change_to_or_from_applied_rejected`.
  - `test_non_applied_rejects_applied_to_and_transaction`.
  - `test_linked_transaction_cannot_be_deleted_directly`: `row.delete()` raises `django.db.models.RestrictedError`.
  - `test_tenant_delete_cascades_movements_and_owned_transactions`: `tenant.delete()` succeeds; both tables empty for that tenant.
  - `test_property_balance_groups_currencies`: tenant A GBP 1500, tenant B (same property) EUR 900 → `deposit_held(property=p, as_of=...) == {"GBP": Decimal("1500"), "EUR": Decimal("900")}`; `deposit_held_by_tenant` returns both rows.
  - `test_movements_for_user_is_owner_scoped`: another landlord's movements excluded; `property_ids` and date bounds filter.
- [ ] **Step 2: Run** `uv run pytest property_rental/rentals/tests/test_deposits_service.py -q` — Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `services/deposits.py` per the Interfaces block and spec rules 1–7.
- [ ] **Step 4: Run** the file — Expected: PASS. Then `uv run pytest -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: add deposit service with balance rules and reads`

### Task 3: Guard deposit-linked transactions in the Transaction API

**Files:**
- Modify: `property_rental/rentals/api/serializers.py` (`TransactionSerializer`), `property_rental/rentals/api/views.py` (`TransactionViewSet`)
- Test: `property_rental/rentals/tests/test_deposits_api.py` (new; Task 4 extends it)

**Interfaces:**
- Consumes: `create_movement` (Task 2).
- Produces: `TransactionSerializer` field `deposit_movement` (read-only PK or `null`). `TransactionViewSet.destroy` and `perform_update`/`update` return `409` with `{"detail": "Edit the security deposit movement instead."}` when the instance has a `deposit_movement` and the request deletes it or changes any of `date, amount, category, currency, tenant, property`. A comment-only PATCH succeeds.

- [ ] **Step 1: Write failing tests** using `auth_client`, `sample_property`, a tenant and an applied movement:
  - `test_transaction_payload_exposes_deposit_movement`: GET `/api/v1/transactions/<id>/` → `["deposit_movement"] == movement.id`; unlinked row → `None`.
  - `test_delete_linked_transaction_returns_409` → status 409, detail exact, row still exists.
  - `test_patch_amount_on_linked_transaction_returns_409`.
  - `test_patch_comment_on_linked_transaction_allowed` → 200.
- [ ] **Step 2: Run** `uv run pytest property_rental/rentals/tests/test_deposits_api.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** the serializer field and the guards (compare `serializer.validated_data` against the instance for the guarded fields; raise a DRF `APIException` subclass with `status_code = 409`).
- [ ] **Step 4: Run** the file and `uv run pytest property_rental/rentals/tests/test_api.py -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: protect deposit-funded transactions from direct edits`

### Task 4: Deposit movements API and balance endpoint

**Files:**
- Modify: `property_rental/rentals/api/serializers.py`, `property_rental/rentals/api/views.py`, `property_rental/rentals/api/urls.py`
- Test: `property_rental/rentals/tests/test_deposits_api.py`

**Interfaces:**
- Consumes: Task 2 service.
- Produces:
  - `/api/v1/deposit-movements/` (router basename `deposit-movement`), fields `id, tenant, date, kind, currency, amount, applied_to, transaction, owns_transaction (read-only), comment`; `?tenant=` and `?property=` filters; writes call `create_movement` / `update_movement` / `delete_movement`; `DepositRuleError` → 400 `{error.field: [error.message]}`; `tenant` or `transaction` not owned by the requester → 400 (same message style as `LeaseRentViewSet`).
  - `GET /api/v1/deposit-movements/balance/?tenant=<id>` or `?property=<id>` [`&as_of=YYYY-MM-DD`] → `{"as_of": "...", "balances": [{"currency": "GBP", "amount": "1500.00"}], "by_tenant": [{"tenant": 7, "currency": "GBP", "amount": "1500.00"}]}`. `by_tenant` is present only for `property=` (feeds the property page per-tenant lines; an addition to the spec's shape, which the Wealth reads do not depend on). Amounts are 2-dp strings. Neither or both params → 400; unowned id → 404. `as_of` parsed with existing `_parse_as_of`.

- [ ] **Step 1: Write failing tests:** create received (201), list filtered by tenant, PATCH amount, DELETE (204); `test_overdraw_returns_400_with_amount_error`; `test_cannot_create_for_other_landlords_tenant` (400, nothing created); `test_cannot_attach_other_landlords_transaction` (400); `test_list_excludes_other_landlords_movements`; `test_balance_by_tenant` (`balances == [{"currency": "GBP", "amount": "1000.00"}]` after 1500 received / 500 returned); `test_balance_by_property_includes_by_tenant`; `test_balance_requires_exactly_one_scope` (400); `test_balance_unowned_tenant_404`; `test_balance_respects_as_of` (receipt after `as_of` excluded).
- [ ] **Step 2: Run** the file — Expected: new tests FAIL (404 route).
- [ ] **Step 3: Implement** serializer, viewset (`perform_create`/`perform_update`/`perform_destroy` delegating to the service), `@action(detail=False, methods=["get"]) balance`, router registration.
- [ ] **Step 4: Run** the file and `uv run pytest -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: add deposit movements API and balance endpoint`

### Task 5: Cash-flow deposit series

**Files:**
- Modify: `property_rental/rentals/analytics/cash_flow.py`
- Test: `property_rental/rentals/tests/test_deposits_analytics.py` (new; Task 6 extends it)

**Interfaces:**
- Consumes: `movements_for_user` (Task 2), `deposit_signed_amount` (Task 1), existing `preload_converter` / `convert_transactions`.
- Produces: `portfolio_cash_flow` points gain `deposits: float` and `net_cash_flow: float` (`net_income + deposits`) and the two series from Global Constraints, only when `movements_for_user(user, start=filters.start, end=filters.end, property_ids=filters.property_ids)` is non-empty. Convert each movement as a signed `_ConvertibleAmount(amount, currency, date)` (same shape as `analytics/tenant.py`) through the same converter and `period_end` as-of used by `_category_total`. `expense_drivers` unchanged.

- [ ] **Step 1: Write failing tests** (reuse `filters_for` from `test_analytics_cash_flow.py` by copying it locally):
  - `test_cash_flow_shows_receipt_as_deposit_not_income`: rent 1000 on 2026-01-10; received 1500 on 2026-01-05 → Jan point `rent == 1000.0`, `total_income == 1000.0`, `net_income == 1000.0`, `deposits == 1500.0`, `net_cash_flow == 2500.0`; series keys end with `("deposits","deposit_movement"), ("net_cash_flow","net_cash")`.
  - `test_cash_flow_application_nets_to_zero_cash`: received 1500 in Jan, applied 1500 rent in Feb → Feb `rent == 1500.0`, `deposits == -1500.0`, `net_cash_flow == 0.0`.
  - `test_cash_flow_attached_partial_application`: rent row 1500 in Mar + applied 500 attached → Mar `net_cash_flow == 1000.0`.
  - `test_cash_flow_without_movements_has_no_deposit_keys`: only a rent row → no `deposits` key, series identical to the existing six.
  - `test_cash_flow_excludes_deposits_of_unselected_property` (Review Focus 4): movement on property B, `property_ids=(A.id,)` → no `deposits` key.
  - `test_cash_flow_converts_deposits_to_reporting_currency`: GBP receipt with an `FXFactory` GBP→USD rate → `deposits` equals the converted value.
  - `test_expense_drivers_ignore_deposits`.
- [ ] **Step 2: Run** `uv run pytest property_rental/rentals/tests/test_deposits_analytics.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** in `cash_flow.py`.
- [ ] **Step 4: Run** the file and `uv run pytest property_rental/rentals/tests/test_analytics_cash_flow.py property_rental/rentals/tests/test_financials_char.py -q` — Expected: PASS, no edits to those files.
- [ ] **Step 5: Commit** `feat: show security deposit movements in portfolio cash flow`

### Task 6: Pin income, P&L, yield and arrears behaviour

Tests only; they should pass on arrival because those paths read `Transaction` only. If one fails, stop and report — do not change analytics code to fit.

**Files:**
- Test: `property_rental/rentals/tests/test_deposits_analytics.py`

**Interfaces:**
- Consumes: `create_movement` (Task 2); `profit_and_loss(user, end, currency, property_ids=())`; `portfolio_summary(user, filters)`; `property_yields(user, filters)`; `Tenant.debt(as_of)`; `tenant_rent_performance(user, tenant_id, filters)`.

Scenario helper `build_lease(book_deposit_as)` with `book_deposit_as in {"rent", "deposit"}`: GBP property, tenant lease 2025-01-01 → 2025-06-30, payday 1, `LeaseRentFactory` 1000 GBP from 2025-01-01; rent rows 1000 on the 1st of Jan–May; deposit 1000 on 2025-01-01 either as a `rent` row (old way) or as a received movement plus an applied-to-rent movement on 2025-06-01 (new way).

- [ ] **Step 1: Write the tests:**
  - `test_receipt_and_return_leave_pnl_unchanged`: P&L, portfolio summary revenue/costs/net and property yields are equal with and without a received + returned pair.
  - `test_old_booking_overstates_january_income` vs `test_new_booking_moves_income_to_application_date`: Jan rent revenue 2000 (old) vs 1000 (new); Jun rent revenue 0 (old) vs 1000 (new); full-lease total 6000 in both.
  - `test_application_reduces_arrears`: new way, `tenant.debt(date(2025,6,30)) == Decimal("0")`; without the applied movement (receipt only), `== Decimal("-1000")`.
  - `test_rent_performance_counts_application_as_received`: Jun point `received == 1000.0`.
- [ ] **Step 2: Run** the file — Expected: PASS.
- [ ] **Step 3: Commit** `test: pin deposit effects on income, yields and arrears`

### Task 7: Frontend data layer

**Files:**
- Create: `frontend/src/types/deposit.ts`, `frontend/src/api/deposits.ts`, `frontend/src/api/deposits.test.tsx`
- Modify: `frontend/src/api/keys.ts`, `frontend/src/types/transaction.ts`, `frontend/src/types/analytics.ts`, `frontend/src/api/transactions.ts` (invalidate deposits on transaction mutations)

**Interfaces:**
- Produces:
  - `type DepositKind = 'received' | 'returned' | 'applied'`; `type DepositAppliedTo = 'rent' | 'cost_reimbursement'`; `type DepositMovement = { id: number; tenant: number; date: string; kind: DepositKind; currency: string; amount: string; applied_to: DepositAppliedTo | null; transaction: number | null; owns_transaction: boolean; comment: string | null }`; `type DepositBalance = { as_of: string; balances: { currency: string; amount: string }[]; by_tenant?: { tenant: number; currency: string; amount: string }[] }`.
  - `queryKeys.deposits = { all, byTenant(tenantId), balance({ tenantId?, propertyId?, asOf? }) }`.
  - Hooks: `useDepositMovements(tenantId)`, `useDepositBalance({ tenantId?, propertyId?, asOf? })`, `useCreateDepositMovement()`, `useUpdateDepositMovement()` (`{ id, data }`), `useDeleteDepositMovement()`; every mutation invalidates `deposits.all`, `transactions.all`, `tenants.all`, `analytics.all`.
  - `Transaction` type gains `deposit_movement: number | null`.
  - `cashFlowSeriesDefinitionSchema` kind enum gains `'deposit_movement'` and `'net_cash'`.

- [ ] **Step 1: Write failing tests** in `deposits.test.tsx` following `api/transactions.test.tsx`: list hook hits `/deposit-movements/?tenant=3`; balance hook hits `/deposit-movements/balance/?property=2&as_of=2026-10-13`; create mutation POSTs and invalidates the four key roots. Add a case to `api/analytics.test.tsx`: a cash-flow payload containing the two new series parses.
- [ ] **Step 2: Run** `npm test -- src/api` (in `frontend/`) — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test -- src/api` and `npx tsc -b` — Expected: PASS, no type errors.
- [ ] **Step 5: Commit** `feat(frontend): add deposit types, keys and hooks`

### Task 8: DepositMovementForm

**Files:**
- Create: `frontend/src/components/forms/DepositMovementForm.tsx`, `frontend/src/components/forms/DepositMovementForm.test.tsx`

**Interfaces:**
- Consumes: Task 7 types.
- Produces: `DepositMovementForm(props: { tenantId: number; defaultCurrency: string; lockedCurrency: string | null; candidateTransactions: Transaction[]; initial?: DepositMovement; onSubmit: (data: DepositMovementInput) => Promise<void>; onCancel: () => void })` where `DepositMovementInput = Omit<DepositMovement, 'id' | 'owns_transaction'>`. Follows `LeaseRentForm` (react-hook-form + zod). Server 400 field errors (thrown by `apiFetch`) are mapped onto fields with `setError`.
- Copy: kind labels `Received`, `Returned`, `Applied`; applies-to labels `Rent`, `Cost reimbursement`; transaction select default option `Create new transaction`.
- Candidate filter: `candidateTransactions` where `category === applied_to`, `currency === currency`, and (`deposit_movement === null` or `deposit_movement === initial?.id`). Choosing a candidate sets `date` and disables the date input.

- [ ] **Step 1: Write failing tests:** applies-to and transaction fields hidden for Received, shown for Applied; currency input read-only showing `lockedCurrency` when set, editable when `null`; candidate list filters by category and hides rows linked elsewhere; **Review Focus 5:** with `initial` attached to transaction 42 (`deposit_movement: initial.id`), option 42 is listed and selected; submit sends `transaction: null` for "Create new transaction"; a rejected `onSubmit` with `{ amount: ['...'] }` shows the message under Amount.
- [ ] **Step 2: Run** `npm test -- DepositMovementForm` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(frontend): add deposit movement form`

### Task 9: Security deposit card and funded-row badge on the tenant page

**Files:**
- Create: `frontend/src/features/tenant/SecurityDepositCard.tsx`, `frontend/src/features/tenant/SecurityDepositCard.test.tsx`
- Modify: `frontend/src/pages/TenantDetailPage.tsx`, `frontend/src/pages/TenantDetailPage.test.tsx`

**Interfaces:**
- Consumes: Task 7 hooks, Task 8 form, `EntityFormDialog`, `ConfirmDialog`, `formatCurrency`-style helper from `lib/format.ts`.
- Produces: `SecurityDepositCard(props: { tenantId: number; propertyCurrency: string; asOf: string; transactions: Transaction[] })`. Card title `Security deposit`; balance line `Held` + formatted amount (or `None held` when `balances` is empty); table columns Date, Kind, Amount, Applies to, Comment, actions (Edit, Delete). `lockedCurrency` = currency of any existing movement other than the one being edited, else `null`; `defaultCurrency` = `propertyCurrency`. `TenantDetailPage` renders it after the "Rent & debt" card with `asOf = user?.effective_date ?? today`. In "Recent transactions", rows with `deposit_movement !== null` show a `From deposit` badge and a disabled delete with tooltip `Funded by the security deposit — edit the deposit movement instead.`

- [ ] **Step 1: Write failing tests:** card renders balance and movements from mocked hooks; `None held` empty state; Add opens dialog titled `New Security deposit movement`; Delete confirms then calls the delete mutation; tenant page shows the badge and disabled delete for a funded row only.
- [ ] **Step 2: Run** `npm test -- SecurityDepositCard TenantDetailPage` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(frontend): manage security deposits on the tenant page`

### Task 10: Deposits held on the property page

**Files:**
- Create: `frontend/src/features/property/DepositsHeldSummary.tsx`, `frontend/src/features/property/DepositsHeldSummary.test.tsx`
- Modify: `frontend/src/pages/PropertyDetailPage.tsx`

**Interfaces:**
- Consumes: `useDepositBalance({ propertyId, asOf })`, tenants already loaded by the page.
- Produces: `DepositsHeldSummary(props: { propertyId: number; asOf: string; tenants: { id: number; name: string }[] })`; heading `Deposits held`; one line per `by_tenant` entry linking to `/tenants/<id>`, then a `Total` line per currency; renders nothing when `balances` is empty.

- [ ] **Step 1: Write failing tests:** per-tenant lines with links; two currencies give two total lines; empty balance renders nothing.
- [ ] **Step 2: Run** `npm test -- DepositsHeldSummary` — Expected: FAIL.
- [ ] **Step 3: Implement** and place it on `PropertyDetailPage` near the tenants section, `asOf` = the page's existing `performanceEnd`.
- [ ] **Step 4: Run** `npm test -- DepositsHeldSummary PropertyDetailPage` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(frontend): show deposits held on the property page`

### Task 11: Deposit series in the net cash flow chart

**Files:**
- Modify: `frontend/src/features/dashboard/charts/NetCashFlowChart.tsx`, `frontend/src/features/dashboard/charts/chartUtils.ts` (visual token for `deposit_movement`), `frontend/src/features/dashboard/charts/NetCashFlowChart.test.tsx`

**Interfaces:**
- Consumes: Task 7 schema kinds.
- Produces: `CASH_FLOW_CATEGORY_KINDS` includes `'deposit_movement'`; the deposit series gets its own visual token distinct from every category token; the data table includes `net_cash_flow` when present; the drill-down button for the deposit series reads `View deposit movements for <period>` and is not wired to the transactions drill-down (no `onDrillDown` call for key `deposits`).

- [ ] **Step 1: Write failing tests:** with the two new series, the legend lists `Security deposits`; the table has a `Net cash flow` column; the deposit drill-down does not call `onDrillDown`; existing tests unchanged and still pass.
- [ ] **Step 2: Run** `npm test -- NetCashFlowChart` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test -- charts` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(frontend): chart security deposit movements in net cash flow`

### Task 12: Full verification

- [ ] **Step 1:** `uv run pytest -q` — Expected: all PASS; `git diff main --stat -- property_rental/rentals/tests/test_financials_char.py property_rental/rentals/tests/test_fx_char.py property_rental/rentals/tests/test_analytics_cash_flow.py` shows no changes.
- [ ] **Step 2:** `uv run python property_rental/manage.py check` and `uv run python property_rental/manage.py makemigrations --check --dry-run` — Expected: no issues, no pending migrations.
- [ ] **Step 3:** In `frontend/`: `npm test`, `npm run lint`, `npm run build` — Expected: all succeed.
- [ ] **Step 4:** Run the app (`run` skill) and, as a smoke test with a throwaway tenant, add a receipt, an application attached to an existing rent row, and a return; confirm tenant card balance, property summary and the dashboard cash-flow chart. Delete the throwaway data.
- [ ] **Step 5:** Commit any fixes; report results to the owner, including that pinned characterisation output is unchanged.
