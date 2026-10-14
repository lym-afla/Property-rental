# Tenant security deposits: handoff brief

**Date:** 2026-10-13
**From:** the Wealth (three statements) design session, `D:\Developing\Wealth-statements`
**Status:** Requirement brief, not a design. Run the normal Rent design process with the owner (brainstorm, spec, plan) before implementing.

## Problem

Leases in reality take security deposits: the tenant pays one at the start of a lease and gets it back at the end, or part of it is withheld against unpaid rent or damage. Rent has no way to record them:

- `TRANSACTION_CATEGORIES` has no deposit category.
- `financial_semantics.category_kind()` classifies every category as either income or expense.

A deposit recorded as a `rent` transaction is counted as rental income. That overstates revenue, yields and the property P&L until the deposit is returned, and the return then shows up as an expense.

## What a deposit is

- A liability of the landlord to the tenant. It is neither income nor expense.
- **Received:** cash in, liability up. P&L unaffected.
- **Returned:** cash out, liability down. P&L unaffected.
- **Withheld (applied):** liability down. The withheld amount becomes income of the kind it settles: rent (reduces arrears) or a cost reimbursement (e.g. damage repair).
- It belongs to a tenant and property, and is denominated in its own currency.

## Requirements

1. Record a deposit received, returned and applied (withheld), per tenant and property, dated, with currency. Partial returns and partial application must work.
2. Analytics exclude deposits from revenue, costs, P&L, yields and expense drivers. An applied amount counts as rent or cost reimbursement on the date it is applied.
3. An amount applied against arrears reduces outstanding rent.
4. Cash-flow analytics show deposit movements distinctly: they are real cash, but not income or expense.
5. The deposit held is available per tenant and property at any date, and visible in the tenant and property views.
6. Historical deposits already recorded as `rent` are found and reclassified by the owner through a reviewable, reversible step. No automatic guessing.
7. Follow the existing currency-of-record rules: convert only for reporting.
8. Model deposits so that "deposit held per tenant and property at a date" and "deposit movements in a period" are straightforward reads. Wealth will later read them through Rent's read-only export API, which is a separate task.

## Pointers

- `rentals/constants.py`: `TRANSACTION_CATEGORIES`, `INCOME_CATEGORIES`.
- `rentals/financial_semantics.py`: `category_kind()` returns only income or expense. Deposits need a third kind, a balance-sheet movement that never reaches P&L.
- `rentals/models.py`: `Transaction.save()` derives `type` and normalises the amount's sign through `category_kind()` and `normalize_transaction_amount()`.
- `rentals/analytics/`: `pnl.py`, `cash_flow.py`, `portfolio.py`, and `tenant.py` (outstanding rent).
- Characterisation tests (`test_financials_char.py`, `test_charts_char.py`) pin analytics output. Expect intentional differences only where deposits leave income.

## Questions for the owner

- Is a deposit ever applied to anything other than rent arrears or damage costs?
- Can a deposit be returned in a different currency from the one received?
- Are there deposits held from past leases that were never returned or applied?

## Indicative acceptance

- Recording a deposit leaves revenue, P&L and yield figures unchanged. Cash flow shows it as a deposit movement.
- An applied deposit reduces outstanding rent or costs and appears as income on the date applied.
- The deposit-held balance is correct at any date.
- Tests cover receive, return, full and partial application, and multiple currencies.
- Reclassifying historical items is owner-confirmed and reversible.
