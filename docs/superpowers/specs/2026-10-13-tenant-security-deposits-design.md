# Tenant security deposits — design

Date: 2026-10-13
Status: design approved by owner in brainstorming; written spec awaiting review
Source: `docs/superpowers/handoffs/2026-10-13-tenant-security-deposits-handoff.md` (from the Wealth three-statements design session)

## Context

Leases take security deposits. Rent has no way to record them: `TRANSACTION_CATEGORIES` has no deposit category and `financial_semantics.category_kind()` knows only income and expense. Deposits booked as `rent` overstate revenue, yields and property P&L from receipt until the lease ends, and make the tenant look ahead on rent for the whole lease.

A deposit is a landlord liability to the tenant. Receipt: cash in, liability up. Return: cash out, liability down. Application (withholding): liability down, and the applied amount becomes income of the kind it settles. None of the three movements is itself income or expense.

## Owner decisions

| Question | Answer |
|---|---|
| What can a deposit be applied to? | Only rent arrears (`rent`) or damage costs (`cost_reimbursement`). |
| Can a deposit be returned/applied in another currency? | No. One currency per tenant deposit. |
| Deposits from past leases still unsettled? | No. All historical deposits were settled. |
| How were historical deposits recorded? | Booked as `rent` at lease start; refund not recorded; the deposit covered the final month, for which no rent row exists. |
| Reclassification of history | Done manually by the owner through the normal UI (three deposits to add; one deposit covers an already-existing rent row). No reclassification feature is built. Brief requirement 6 is met by ordinary, reversible edits. |
| Applying a deposit to an existing rent row | Supported: the application attaches to the existing row instead of creating a new one. |
| Where deposits are entered | On the tenant detail page; read-only totals on the property detail page. No new top-level page. |
| Model approach | Separate `DepositMovement` ledger (chosen over deposit categories on `Transaction` and over a general double-entry ledger). |

## Data model

New model `DepositMovement` in `rentals/models.py`, migration `0028_depositmovement`:

| Field | Definition |
|---|---|
| `tenant` | `ForeignKey(Tenant, on_delete=CASCADE, related_name="deposit_movements")`. The property is `tenant.property`; it is not stored separately, so it cannot drift. |
| `date` | `DateField()` |
| `kind` | `CharField`, choices `received` / `returned` / `applied` |
| `currency` | `CharField(max_length=3, choices=CURRENCY_CHOICES)`, required |
| `amount` | `DecimalField(max_digits=10, decimal_places=2)`, stored positive (`> 0`); sign comes from `kind` |
| `applied_to` | `CharField`, choices `rent` / `cost_reimbursement`; required iff `kind == "applied"`, otherwise null |
| `transaction` | `OneToOneField(Transaction, null=True, blank=True, on_delete=RESTRICT, related_name="deposit_movement")`; set iff `kind == "applied"` |
| `owns_transaction` | `BooleanField(default=False)`; true when the movement created its transaction |
| `comment` | `TextField(max_length=250, blank=True, null=True)` |

Database constraints: `amount > 0`; `applied_to` null iff kind is not `applied`. Ordering: `("date", "id")`.

New constants in `rentals/constants.py`: `DEPOSIT_MOVEMENT_KINDS`, `DEPOSIT_APPLICATION_CATEGORIES = ("rent", "cost_reimbursement")`.

New helper in `rentals/financial_semantics.py`:

```python
def deposit_signed_amount(kind: str, amount) -> Decimal:
    # received: +amount (liability up); returned / applied: -amount (liability down)
```

This defines the third, balance-sheet-only kind of money movement alongside `category_kind()`. Deposits never reach `category_kind()` because they are not transactions.

## Service: `rentals/services/deposits.py`

All writes go through this module inside `transaction.atomic()`. The API calls it; nothing else writes `DepositMovement` rows.

Functions: `create_movement(tenant, **fields)`, `update_movement(movement, **fields)`, `delete_movement(movement)`, `deposit_held(*, as_of, tenant=None, property=None)`, `movements_for_user(user, start=None, end=None, property_ids=None, tenant_id=None)`.

Rules (each raises `DepositRuleError(field, message)`, mapped to HTTP 400):

1. **Single currency.** Every movement for a tenant uses the same currency as the tenant's other movements.
2. **No overdraw.** Replaying the tenant's movements in `(date, received-before-outflows, id)` order, the running balance never goes below zero. Checked against the post-change set on create, update and delete (deleting a receipt that later outflows depend on is rejected).
3. **Apply, create mode** (`transaction` not given): create a `Transaction` with `property=tenant.property`, `tenant=tenant`, `category=applied_to`, same date, currency and amount, comment `"Applied from security deposit"`; set `owns_transaction=True`. `Transaction.save()` normalises the sign as usual (`rent` positive, `cost_reimbursement` positive contra-expense).
4. **Apply, attach mode** (`transaction` given): the transaction must belong to the same tenant (`transaction.tenant == tenant`), have `category == applied_to`, `currency == deposit currency`, `date == movement date`, `abs(amount) >= movement amount`, and not already be linked to another movement. Set `owns_transaction=False`.
5. **Edits.** Updating an owning movement updates its transaction's date, amount, category and currency to match. Changing `kind` between applied and non-applied is rejected; delete and re-add instead. Attach-mode movements re-validate rule 4 on edit.
6. **Deletes.** Deleting an owning movement deletes its transaction; deleting an attach-mode movement only unlinks it.
7. **Non-applied movements** must not carry `applied_to` or `transaction`.

Reads:

- `deposit_held(as_of, tenant=...)` → `{currency: Decimal}` (at most one key) summing `deposit_signed_amount` over movements with `date <= as_of`.
- `deposit_held(as_of, property=...)` → `{currency: Decimal}` summed over the property's tenants, grouped by currency.
- Values are native-currency; conversion happens only for reporting (brief requirement 7). These two reads plus `movements_for_user` are the shapes the future Wealth export API will reuse.

## Linked transactions

A `Transaction` with a `deposit_movement` is a deposit-funded row:

- `TransactionSerializer` gains read-only `deposit_movement` (id or null).
- `TransactionViewSet` rejects `DELETE` with 409 and rejects updates to `date`, `amount`, `category`, `currency`, `tenant` or `property` with 409 ("Edit the security deposit movement instead"). Comment edits are allowed.
- `on_delete=RESTRICT` backs this at the ORM level: a linked transaction cannot be deleted on its own, but deleting a tenant or property (which cascades to both the movement and the transaction in one operation) still works. `PROTECT` is deliberately not used because it would block those cascades. Covered by a test.

## Analytics impact

Income and expense analytics read only `Transaction`, so receipts and returns are invisible to them and need no code change: `analytics/pnl.py`, `analytics/portfolio.py` (summary, yields, contribution, rental-income breakdown), `services/financials.py` (`aggregate`, `pnl_calc`), the `type="income"` stats in `api/views.py`, and `expense_drivers`.

Applications are ordinary `rent` / `cost_reimbursement` rows dated on the application date, so:

- they count as income (or contra-expense) on that date in P&L, yields and summaries (brief requirement 2);
- applied-to-rent rows are picked up by `Tenant.rent_total` → `services.scheduler.debt` and by `analytics.tenant.tenant_rent_performance`, reducing arrears (brief requirement 3).

**Cash flow** (`analytics/cash_flow.portfolio_cash_flow`) is the only analytics change (brief requirement 4). When at least one deposit movement for the scoped properties falls in the date range:

- each point gains `deposits`: the sum of `deposit_signed_amount` for that period, converted to the reporting currency using the same converter and as-of convention as the category totals;
- each point gains `net_cash_flow = net_income + deposits`;
- series gain `SeriesDefinition("deposits", "Security deposits", "deposit_movement")` and `SeriesDefinition("net_cash_flow", "Net cash flow", "net_cash")`.

`net_income` and `cumulative_net_income` keep their existing meaning. Applications net to zero new cash: `+amount` in the `rent`/`cost_reimbursement` series and `-amount` in `deposits`. This also handles an application attached to an existing row for less than the row amount.

When no movements are in scope the response is identical to today, so existing `points ==` assertions and characterisation tests do not change. `expense_drivers` never includes deposits.

## API

`/api/v1/deposit-movements/`, `DepositMovementViewSet(ModelViewSet)`, modelled on `LeaseRentViewSet`:

- queryset scoped by `tenant__property__owned_by__user`; optional `?tenant=` and `?property=` filters;
- tenant and `transaction` ownership validated on create/update (IDOR defence; a foreign id yields 400);
- writes delegated to `services.deposits`; `DepositRuleError` → 400 with a field error.

`GET /api/v1/deposit-movements/balance/?tenant=<id>` or `?property=<id>`, optional `as_of` (via the existing `_parse_as_of`), returns:

```json
{"as_of": "2026-10-13", "balances": [{"currency": "GBP", "amount": "1500.00"}]}
```

Exactly one of `tenant` / `property` is required (400 otherwise); an id the user does not own returns 404.

Django admin: `DepositMovement` registered read-only, for inspection.

## Frontend

- `src/types/deposit.ts`; `src/api/deposits.ts` with React Query hooks `useDepositMovements(tenantId)`, `useDepositBalance({tenantId | propertyId, asOf})`, `useCreateDepositMovement`, `useUpdateDepositMovement`, `useDeleteDepositMovement`. Mutations invalidate deposits, transactions, tenants and analytics (the lease-rents cascade pattern). Query keys added to `src/api/keys.ts`.
- `src/components/forms/DepositMovementForm.tsx`, used inside `EntityFormDialog`: date, kind (Received / Returned / Applied), amount, currency (locked to the deposit currency once one exists), comment. When kind is Applied: "Applies to" (Rent / Cost reimbursement) and "Transaction" (default "Create new transaction", or one of the tenant's rows with matching category, currency and no existing link). Server field errors are shown inline.
- `TenantDetailPage`: new "Security deposit" card with the balance held at the user's effective date and a movements table (date, kind, amount, applies to, comment) with Add, Edit and Delete (`ConfirmDialog`). In "Recent transactions", deposit-funded rows show a "From deposit" badge, and their delete action is disabled with an explanatory tooltip.
- `PropertyDetailPage`: read-only "Deposits held" per tenant and in total, per currency, each tenant linking to its page.
- `NetCashFlowChart` / `chartUtils`: the `deposit_movement` kind renders as its own series with a distinct visual token; `net_cash_flow` appears in the data table. Drill-down on the deposit series links to tenant pages rather than the transactions list.
- `src/types/transaction.ts` gains `deposit_movement: number | null`.

## Testing

Backend (pytest, TDD):

- `test_deposit_semantics.py`: `deposit_signed_amount`.
- `test_deposits_service.py`: currency lock; overdraw on create, edit and delete; create-mode and attach-mode application (each attach validation); owning versus attached delete; kind change rejected; balance at dates covering receive, partial return, partial and full application; property balance over two tenants in different currencies; tenant deletion cascade.
- `test_deposits_analytics.py`: the same scenario booked the old way (deposit as `rent`) and the new way, pinning that receipt and return leave P&L, portfolio summary, yields and expense drivers unchanged; applied amounts land as income on the application date; arrears (`Tenant.debt`, `tenant_rent_performance`) fall by the applied amount; cash flow adds `deposits` / `net_cash_flow` only when movements exist and nets applications to zero.
- `test_deposits_api.py`: CRUD, scoping, IDOR on tenant and transaction, balance endpoint, 409 on deleting or editing a linked transaction.
- The full existing suite, including `test_financials_char.py`, `test_fx_char.py` and `test_analytics_cash_flow.py`, passes unchanged. Any diff in pinned output is a defect unless it is a deposit leaving income and the owner has reviewed it.

Frontend (vitest): `DepositMovementForm` (applied fields appear and disappear, currency lock), the tenant deposit card (balance, movements, add/edit/delete flows), the "From deposit" badge with delete disabled, and `NetCashFlowChart` rendering the deposit series.

## Out of scope

- Wealth's read-only export API (separate task; this design keeps its reads to `deposit_held` and `movements_for_user`).
- A reclassification tool for historical rows (the owner rebooks three deposits manually).
- Deposits in a currency other than the one received; deposits applied to anything except rent or cost reimbursement.
- A portfolio-wide deposits page.

## Acceptance

- Recording a receipt or return leaves revenue, P&L, yield and expense-driver figures unchanged; cash flow shows it under Security deposits.
- An application reduces outstanding rent (or offsets costs) and appears as income on the date applied, whether it creates a new row or attaches to an existing one.
- Deposit held is correct at any date per tenant and per property.
- Tests cover receive, return, full and partial application, and multiple currencies.
- The owner can add, edit and delete movements from the tenant page; every edit is reversible by another edit.
