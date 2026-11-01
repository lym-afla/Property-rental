# Rent Transaction Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver sortable transactions, property currency defaults, optional former tenants, and the selected teal home favicon.

**Architecture:** Reuse TanStack's client sorting and React Hook Form state. Opt transaction tables into accessible sorting; preserve other tables. Serve one public SVG through Vite and Django static files.

**Tech Stack:** React, TypeScript, Vitest, Playwright, Django, pytest, Docker.

**Spec:** `docs/superpowers/specs/2026-11-01-transaction-usability-design.md` (approved).

## Global Constraints

- No schema changes, date-dependent tenant requests, or new dependencies.
- Preserve recorded currencies, manual overrides, historical tenant assignments, and existing filters.
- Current tenant classification matches the existing Tenants page (UTC ISO date).
- Amounts sort as recorded numbers without FX conversion.
- Version 2.2.0 in pyproject, npm manifests, lockfiles and changelog; reconcile before merge.
- Deployment uses exact-commit CI, immutable image promotion, backup, rehearsal, Rent-only deployment and acceptance.

## Review Focus

- Negative and differently sized decimal strings must sort numerically, across pagination (Task 1).
- Missing tenant/name values and identical dates must remain deterministic (Task 1).
- Delayed property data and refetches must not overwrite manual currency choices (Task 2).
- Former tenant retained on edit must not become a hidden selection when toggled off (Task 2).
- Nested production routes must receive a usable static favicon URL (Task 3).

### Task 1: Transaction sorting

**Files:** `frontend/src/components/table/DataTable.tsx`, `frontend/src/pages/TransactionsPage.tsx`, `frontend/src/pages/TransactionsPage.test.tsx`.
**Interfaces:** Add optional `sortableHeaders?: boolean` to DataTable, false by default. Transactions opt in. Use existing `initialSorting` and `ColumnDef<Transaction>`.

- [ ] Add page regression tests: click Date and assert ascending/descending chronological order; sort Amount containing -150, 9, 80, 1000 and assert numeric order; sort property/tenant names instead of IDs; assert aria-sort and keyboard operation, no Actions button; navigate page 2 then sort and assert page 1 of globally sorted data. Include null tenants, ties and empty period/comment values.
- [ ] Run `cd frontend && npm test -- src/pages/TransactionsPage.test.tsx`; expect new tests to fail from missing controls or wrong order.
- [ ] Implement opt-in sortable header buttons, direction icons and aria-sort in DataTable. Set first direction ascending, keep newest date initial order, reset page on sorting. Add accessors for visible property/tenant/category names and numeric amount; compare date strings using basic sorting.
- [ ] Repeat focused tests; expect pass. Commit `feat: add accessible transaction column sorting`.

### Task 2: Transaction defaults and tenant choices

**Files:** `frontend/src/components/forms/TransactionForm.tsx`, new `TransactionForm.test.tsx`, `frontend/src/lib/tenantStatus.ts`, `frontend/src/pages/TenantsPage.tsx`, `frontend/src/pages/TransactionsPage.tsx`.
**Interfaces:** Add `mode?: 'create' | 'edit'` to TransactionForm (default create), pass edit explicitly from edit dialogs. Export `tenantStatus(leaseEnd: string | null | undefined)` with the existing behavior; both pages/forms consume it.

- [ ] Add tests using real Select components: new property sets EUR/GBP; preselected property's delayed data initializes currency; USD override survives rerender/refetch and date changes; edit preserves saved currency and tenant. Current/end-today/future tenants stay selectable, expired tenants require toggle, changing date does not change options, toggling former off clears selection, changing property clears mismatches, no property disables tenant, unassigned submits null. Include delayed tenant data on edit.
- [ ] Run `cd frontend && npm test -- src/components/forms/TransactionForm.test.tsx`; expect failing assertions showing missing defaults/toggle.
- [ ] Extract existing tenantStatus helper. Initialize currency once per selected property unless editing a saved value; property onChange sets native currency. Add optional unassigned item, current-first filtered choices, accessible “Show former tenants” checkbox and former labels; initialize edits so assigned former tenants remain visible. Use explicit mode in page edit callers.
- [ ] Run form tests plus `TransactionsPage.test.tsx` and `TenantsPage.test.tsx`; expect pass. Commit `fix: use property currency and current tenants for transactions`.

### Task 3: Rent browser identity

**Files:** `frontend/public/favicon.svg`, `frontend/index.html`, `property_rental/rentals/templates/spa_index.html`, `property_rental/rentals/tests/test_spa_view.py`, `scripts/container_smoke.py`.
**Interfaces:** Vite public `favicon.svg` builds to `frontend/favicon.svg` in Django static namespace. Django uses `{% static 'frontend/favicon.svg' %}`; base tab title is Rent.

- [ ] Extend rendered nested SPA shell test to assert an icon link using the static URL and Rent title. Run `uv run pytest -q property_rental/rentals/tests/test_spa_view.py`; expect missing icon failure.
- [ ] Replace starter SVG with approved #0f766e rounded square, white house and teal doorway. Wire base-aware Vite href and Django static link; set Rent title in both shells.
- [ ] Extend container smoke to fetch the rendered icon URL and assert an SVG content type/body. Run focused Django tests and production build; expect pass. Inspect 16px/32px rendering in browser. Commit `feat: add Rent browser identity`.

### Task 4: Release verification and review

**Files:** `pyproject.toml`, `uv.lock`, `frontend/package.json`, `frontend/package-lock.json`, `CHANGELOG.md`, release evidence under `docs/superpowers/handoffs/`.
**Interfaces:** Consume Tasks 1–3 as a single 2.2.0 release; no migration or API contract changes.

- [ ] Update version and changelog, run `uv lock` and `npm version 2.2.0 --no-git-tag-version` in frontend.
- [ ] Run full `npm test`, `npm run lint`, `npm run build`, `uv run pytest -q`, Django check, migration drift check, relevant Playwright scenarios and production container smoke; inspect every result, record any environmental limitations.
- [ ] Obtain whole-branch independent review, address substantive findings with failing regression tests followed by passing checks. Commit verified release metadata/evidence.
- [ ] Push review branch and create a draft PR with validation and rollout instructions. Attach PR to chat. Prepare exact release handoff; merge/publish/deploy only with authorization already covering those actions or concrete final approval. Do not misrepresent a prepared release as deployed.

## Execution decision

Proceed inline with one final independent review: user already requested planning and implementation and approved the design. No additional execution-method approval is needed. An isolated managed worktree keeps the source checkout intact.
