# Entity Pages + FX Fix — Design Spec (Plan B of 3)

**Date:** 2026-07-19
**Status:** Approved (pending user review of written spec)
**Plan:** B of 3 (sub-plan of the merged Phase 2+3)
**Predecessor:** Plan A (SPA Foundation + Auth, merged at tag `spa-foundation`)
**Successors:** Plan C (Charting overhaul + dashboard)
**Parent spec:** `docs/superpowers/specs/2026-07-19-spa-charting-design.md`

---

## 1. Context

Plan A delivered a bootable React SPA with login + register flows working end-to-end against Django session cookies. The foundation (Vite + React + TS + Tailwind v4 + shadcn/ui + TanStack Query + React Router + Vitest + MSW) is ready to extend. The Django `/api/v1/` layer has 4 entity ViewSets (Property/Tenant/Transaction/FX) + auth endpoints, all per-user-scoped with IDOR structurally closed.

This plan (B) builds the entity pages the SPA currently lacks, adds the missing PropertyValuation ViewSet + stats endpoints + typed action endpoints, fixes the FX inversion bug Phase 1 pinned, consolidates the remaining duplicated FX-conversion loops, and deletes ALL legacy Django templates + views + static JS + forms that the SPA replaces.

**Scope decisions (from brainstorming):**
- **All 5 entity pages** in one plan: Properties, Tenants, Transactions, FX, Profile (plus detail pages for Properties and Tenants).
- **Delete all replaced legacy views** (clean cut — including the orphaned `views.index` that the Plan A review flagged as a Plan B prerequisite).
- **Fix FX inversion AND consolidate remaining duplicated FX loops** (the more ambitious scope, reaching a cleaner end state).

## 2. Goals

1. Render Properties, PropertyDetail, Tenants, TenantDetail, Transactions, FX, Profile pages in the SPA with feature parity to the Django templates they replace.
2. Add PropertyValuation ViewSet, stats endpoints, vacate-tenant action, FX-update action, settings-update + change-password endpoints.
3. Fix the FX inversion bug (`round(1/fx_rate, 6)` tail in `services/fx.py`) and update pinned golden values.
4. Consolidate the 3 remaining duplicated FX-conversion loops into `services.financials.convert_transactions`.
5. Delete every legacy template, view, route, static JS/CSS file, and Django form the SPA replaces.
6. Maintain Phase 1 + Plan A test suites green; add frontend tests for every entity hook, form, and page.

## 3. Non-Goals (out of scope)

- **Charts** — HomePage stays minimal (counts + "coming soon"); PropertyDetail/TenantDetail leave chart placeholders. Plan C fills them.
- **Dashboard** — KPI cards + chart tiles are Plan C.
- **CSV/PNG export** — deferred in the parent spec.
- **Dark mode** — light only.
- **Real-time updates (websockets)** — React Query refetch-on-focus suffices.
- **M2M migration** for User.groups/user_permissions (out of scope since Phase 1).
- **Bulk operations** (bulk delete, bulk assign).
- **Phase 4 architecture debt** (Tenant god-model refactor, `debt`/`debt_advance_payment` dedup).

## 4. Backend additions

### 4.1 PropertyValuation ViewSet

Add `/api/v1/property-valuations/` — `ModelViewSet` for `Property_capital_structure`. Same pattern as Phase 1 Task 17:
- `get_queryset()` filters by `property__owned_by__user=request.user`.
- `perform_create()` / `perform_update()` validate the `property` FK belongs to the requester.
- `permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]`.
- Serializer: `PropertyCapitalStructureSerializer` (moved from `views.py:55` where it's currently inline; fields: id, property, capital_structure_date, capital_structure_value, capital_structure_debt).
- Tests: cross-landlord 404, ownership forcing on create, happy-path CRUD.

### 4.2 FX inversion fix + consolidation

**The fix:** remove `fx_rate = round(1 / fx_rate, 6)` at the tail of `services/fx.py:get_rate`. The function should return the actual rate, not its reciprocal.

**Golden-value updates** (the char tests pin the inverted values; they must change):
- `rentals/tests/test_fx_char.py` — direct/reverse/2-hop values now correct.
- `rentals/tests/test_financials_char.py::test_tenant_rent_total_cross_currency` — uses corrected rate.

**Consolidation** of the 3 remaining duplicated FX-conversion loops into `services.financials.convert_transactions`:
- `Tenant.rent_total` (~models.py:143-177) — the silent-same-currency-fallback quirk (sums at face value when `property.currency == target_currency`) is preserved deliberately (pinned by char test); the per-row FX loop becomes a call to `convert_transactions`.
- The two loops in `pnl_calc` (`services/financials.py`) — the `default_currency_for_all_data` gate stays; the per-row FX loop becomes `convert_transactions`.
- `table_data` view's FX loop — deleted with the view (no consolidation needed).

**Regression tests** prove the consolidation preserved behavior: the existing char tests ARE this proof. If any non-FX golden value changes after consolidation, behavior drifted — fix before proceeding. Add focused unit tests for `convert_transactions` covering: same-currency short-circuit, single-row conversion, multi-row aggregation, missing FX rate handling.

### 4.3 Stats endpoints

Two new endpoints providing the aggregated data the SPA tables need (the basic ViewSet list endpoints return raw rows; computed stats depend on per-user `as_of` date and target currency):

- `GET /api/v1/properties/with_stats/?as_of=2024-06-15&currency=USD` — returns properties + P&L aggregates per property (gross_income_all_time, expenses_all_time, net_income_all_time, gross_income_ytd, expenses_ytd, net_income_ytd). Computed via `services.financials.aggregate` and `services.financials.pnl_calc`.
- `GET /api/v1/tenants/with_stats/?as_of=2024-06-15&currency=USD` — returns tenants + rent/debt aggregates (rent_rate, revenue_all_time, revenue_ytd, debt). Computed via `services.financials.convert_transactions` and `services.scheduler.debt`.

Both are `@action(methods=['get'], detail=False)` on their respective ViewSets. Per-user scoped (inherits ViewSet's `get_queryset`). The `as_of` and `currency` come from query params (the SPA reads them from user settings).

### 4.4 Typed action endpoints

- `POST /api/v1/tenants/:id/vacate/` — `@action(detail=True)` on `TenantViewSet`. Body: `{lease_end}`. Sets `tenant.lease_end`, saves, returns serialized tenant. Ownership check is free (ViewSet's `get_object`).
- `POST /api/v1/fx/update/` — `@action(methods=['post'], detail=False)` on `FXViewSet`. Wraps `services.fx.update_rates` (which wraps yfinance). Per-user scoped (already wired in Phase 1 Task 7's `update_fx_view` template view — same logic, now as a typed endpoint). Tests mock yfinance.
- `PATCH /api/v1/auth/me/` — extend the existing `MeView` (or sibling) to accept PATCH. Validates via `UserSerializer`, saves, returns updated user. Used by ProfileSettingsForm.
- `POST /api/v1/auth/change-password/` — new `APIView`. Body: `{old_password, new_password1, new_password2}`. Wraps Django's `password_change` + validators. Returns 200 on success, 400 on validation error.

All covered by tests (happy path + auth + ownership where relevant).

## 5. Frontend infrastructure (shared)

### 5.1 Types

`frontend/src/types/` — one file per entity, matching the DRF serializer field lists (snake_case preserved):
- `property.ts` (id, owned_by, name, location, address, num_bedrooms, area, currency, sold)
- `tenant.ts` (id, user, property, first_name, last_name, phone, email, lease_start, lease_end, payday)
- `transaction.ts` (id, property, tenant, date, category, period, currency, amount, type, comment)
- `fx.ts` (id, date, from_currency, to_currency, rate)
- `propertyValuation.ts` (id, property, capital_structure_date, capital_structure_value, capital_structure_debt)

Decimal fields come through as strings (DRF default). Formatters handle conversion.

### 5.2 API hooks + cache keys

One file per entity in `frontend/src/api/`. Cache invalidation cascade centralized in `api/keys.ts`:

```typescript
export const queryKeys = {
  auth: { me: ['auth', 'me'] as const },
  properties: { all: ['properties'] as const, detail: (id) => ['properties', id] as const,
                withStats: ['properties', 'with-stats'] as const },
  tenants: { all: ['tenants'] as const, detail: (id) => ['tenants', id] as const,
             byProperty: (pid) => ['tenants', { propertyId: pid }] as const,
             withStats: ['tenants', 'with-stats'] as const },
  transactions: { all: ['transactions'] as const,
                  filtered: (f) => ['transactions', f] as const },
  fx: { all: ['fx'] as const },
  propertyValuations: { all: ['property-valuations'] as const,
                        byProperty: (pid) => ['property-valuations', { propertyId: pid }] as const },
  chartData: { all: ['chart-data'] as const, filtered: (f) => ['chart-data', f] as const },
}
```

Any mutation to a Transaction invalidates `['transactions']` AND `['chart-data']` — keeps the dashboard (Plan C) in sync automatically.

Hooks per entity:
- `useProperties()`, `usePropertiesWithStats()`, `useProperty(id)`, `useCreateProperty()`, `useUpdateProperty()`, `useDeleteProperty()`
- `useTenants({property_id?})`, `useTenantsWithStats()`, `useTenant(id)`, `useCreateTenant()`, `useUpdateTenant()`, `useDeleteTenant()`, `useVacateTenant()`
- `useTransactions({property_id?, tenant_id?, category?, from?, to?, period?})`, `useCreateTransaction()`, `useUpdateTransaction()`, `useDeleteTransaction()`
- `useFX()`, `useUpdateFX()`
- `usePropertyValuations({property_id})`, `useCreatePropertyValuation()`, `useUpdatePropertyValuation()`, `useDeletePropertyValuation()`
- `useUpdateMe()`, `useChangePassword()`

### 5.3 Forms (react-hook-form + zod)

Install `react-hook-form @hookform/resolvers zod`. Each entity form follows the pattern: zod schema → `useForm` with `zodResolver` → shadcn `<Form>` components.

Per-entity forms:
- `PropertyForm` — name, location, address, num_bedrooms, area, currency (select), sold (date, optional)
- `TenantForm` — first_name, last_name, phone, email, lease_start, lease_end (opt), payday, property (select filtered to user's own)
- `TransactionForm` — date, property (select), tenant (select, filtered by property — cascade), category, amount, currency, comment
- `PropertyValuationForm` — capital_structure_date, capital_structure_value, capital_structure_debt
- `VacateTenantForm` — lease_end (date picker)
- `ProfileSettingsForm` — default_currency, use_default_currency_for_all_data, chart_frequency, chart_timeline, digits, effective_date

Add shadcn components needed: `npx shadcn@latest add select checkbox form dialog dropdown-menu table badge tooltip separator`.

### 5.4 Modal components

Three reusable patterns on shadcn `<Dialog>`:
- **`<EntityFormDialog>`** — wraps any entity form; opens for create/edit; handles mutation + invalidation + toast + close.
- **`<ConfirmDialog>`** — for delete confirmations; shows dependent counts.
- **`<VacateTenantDialog>`** — specialized, wraps VacateTenantForm.

### 5.5 DataTable component

Reusable `<DataTable>` built on shadcn `<Table>` + `@tanstack/react-table`. Replaces jQuery DataTables. Used by Properties/Tenants/Transactions pages with different column configs. Shared sorting/pagination/filtering state.

Install `@tanstack/react-table`.

### 5.6 Toasts + state components

Toasts already wired (Plan A Task 3). Plan B uses them for all mutations.

State components:
- `<SkeletonTable>` — grey rows while loading.
- `<EmptyState icon title description action>` — friendly empty state with CTA.
- `<ErrorState message onRetry>` — for failed queries.

## 6. Page-by-page design

### 6.1 PropertiesPage (`/properties`)

- Page header + "Create new Property" button.
- `<DataTable>`: columns Name, Location, Rent since, Status, All-time Gross/Expenses/Net, YTD Gross/Expenses/Net.
- Data from `usePropertiesWithStats()` (the `/properties/with_stats/` endpoint).
- Row click → `/properties/:id`.
- Create button → `<EntityFormDialog>` with `PropertyForm`.

### 6.2 PropertyDetailPage (`/properties/:id`)

- Header card (name, location, key stats) + tabs: "Overview" and "Valuations".
- Overview tab: P&L breakdown table (per-category YTD + all-time) + transactions subset (paginated). Chart placeholders (Plan C).
- Valuations tab: `<DataTable>` of `Property_capital_structure` entries. Create/edit/delete via `<EntityFormDialog>` with `PropertyValuationForm`. Exercises the new PropertyValuation ViewSet.
- Actions: Edit property (dialog), Delete property (confirm → navigate to `/properties`).

### 6.3 TenantsPage (`/tenants`)

- `<DataTable>`: columns Tenant, Property, Renting since, Status (Active/Vacated/Will vacate), Rent rate, Revenue (all-time + YTD), Debt, Action (Vacate button).
- Data from `useTenantsWithStats()`.
- Vacate → `<VacateTenantDialog>`.
- Row click → `/tenants/:id`.

### 6.4 TenantDetailPage (`/tenants/:id`)

- Header card (name, property, lease dates, rent rate, debt) + tabs: "Overview" and "Lease timeline".
- Overview tab: transactions subset. Rent chart placeholder (Plan C).
- Lease timeline tab: chronological `Lease_rent` history + lease events (start, vacate).

### 6.5 TransactionsPage (`/transactions`)

- Filter bar (property select, tenant select, category select, date range, search) + `<DataTable>`.
- Columns: Date, Property, Tenant, Category, Period, Amount, Comment.
- **URL-synced filters** — the drill-down target for Plan C's charts. A chart click navigates to `/transactions?property=1&from=2024-01-01&to=2024-01-31&category=rent`; the page reads URL params on mount and pre-populates the filter bar.
- Data from `useTransactions({filters})`.
- Create via `<EntityFormDialog>`. TransactionForm's tenant select filters by selected property (cascade).

### 6.6 FXPage (`/fx`)

- "Update FX" button + `<DataTable>`: Date, From, To, Rate.
- Update button → `useUpdateFX()` mutation. Mocked in tests.
- Rate display shows both stored rate and reciprocal (now CORRECT post-FX-fix).

### 6.7 ProfilePage (`/profile`)

- Tabs: "User details" / "Settings" / "Change password".
- User details: read-only display + "Edit" button → edit dialog.
- Settings: `<ProfileSettingsForm>` → `PATCH /api/v1/auth/me/`. On success: invalidate `['auth', 'me']`, toast.
- Change password: form → `POST /api/v1/auth/change-password/`.

### 6.8 HomePage (minimal placeholder)

- User's properties count + link to `/properties`.
- User's tenants count + link to `/tenants`.
- "Dashboard coming soon" note where charts will go (Plan C).

## 7. Legacy deletion

Once each SPA page is verified working, delete the corresponding legacy view + template + route in the same PR. Per-page ordering keeps each commit reviewable and the app working throughout.

### Templates (`property_rental/rentals/templates/rentals/`)

Delete: `index.html`, `properties.html`, `tenants.html`, `transactions.html`, `fx_list.html`, `profile_page.html`, `edit_profile.html`, `settings.html`, `new_form.html`, `payments_table.html`, snippets `dashboard_card.html`, `timeline-chart.html`.
Keep: `spa_index.html`.

### Views (`property_rental/rentals/views.py`)

Delete: `index`, `logout_view`, `profile_page`, `edit_profile`, `properties`, `tenants`, `transactions`, `new_form`, `table_data`, `handle_element`, `create_element`, `vacate_tenant`, `property_choices`, `chart_data_request`, `property_valuation`, `fx_list`, `update_fx_view`, `chrome_devtools_config`, `well_known_handler`. Also delete the inline serializers (`PropertySerializer`, `TenantSerializer`, `TransactionSerializer`, `PropertyValuationSerializer` at views.py:23-58) — duplicates of `api/serializers.py`.
Keep: `SpaView`, and any helper functions still used by services.

### Routes (`property_rental/rentals/urls.py`)

Delete all page-rendering routes (`/`, `/properties/`, `/tenants/`, `/transactions/`, `/fx/`, `/profile/`, `/edit-profile/`, `/new-form/<type>`, `/table-data/<type>`, `/handling/<type>/<id>`, `/create/<type>`, `/vacate/<id>`, `/property-choices`, `/get_chart_data`, `/properties/valuation/<id>`, `/update-fx/`) + the `# TO BE DELETED` commented routes.
Keep: `/api/v1/`, the SPA catch-all.

### Static JS + CSS (`property_rental/rentals/static/rentals/`)

Delete: `element.js`, `layout.js`, `chart.js`, `settings.js`, `index.js`, `properties_not used.js`, `styles.css`, `fontawesome-minimal.css`.
Keep: SVG icons in `img/` (Plan C may replace with lucide-react).

### Forms (`property_rental/rentals/forms.py`)

Delete all (PropertyForm, TenantForm, TransactionForm, PropertyValuationForm, UserProfileForm, UserSettingsForm, ChangePasswordForm) — the SPA uses react-hook-form + zod. File becomes empty or is deleted.

## 8. Testing

### Frontend (Vitest + Testing Library + MSW)

- **Fixtures** (`frontend/src/__fixtures__/`): `property.ts`, `tenant.ts`, `transaction.ts`, `fx.ts`, `propertyValuation.ts`, `list.ts` (arrays for table tests).
- **MSW handlers**: extend with defaults for every new endpoint (CRUD for all entities + stats + actions + auth-me-patch + change-password).
- **Tests per layer**:
  - `api/{entity}.test.tsx` — hook tests (query returns data, mutation invalidates, etc.)
  - `components/forms/{Entity}Form.test.tsx` — validation (zod errors, submit calls mutation)
  - `components/DataTable.test.tsx` — sorting, pagination, row click
  - `pages/{Page}.test.tsx` — renders table, empty state, error state, create-dialog opens
- **Coverage target**: every entity hook, every form, every page gets at least happy-path + error test.

### Backend (pytest)

- `test_api.py` — extend with PropertyValuation ViewSet tests (CRUD + cross-landlord IDOR).
- `test_auth_api.py` — extend with `PATCH /auth/me/` + `POST /auth/change-password/` tests.
- `test_stats_endpoints.py` (new) — properties/with_stats, tenants/with_stats happy paths.
- `test_fx_char.py` + `test_financials_char.py` — golden-value updates for the FX inversion fix.
- `test_financials_consolidation.py` (new) — regression tests proving loop consolidation preserved behavior.
- Existing Phase 1 + Plan A tests stay green.

### CI

Existing 4-job CI (Plan A Task 12) covers this plan — no new jobs needed. All 4 jobs must stay green.

## 9. Definition of done

Plan B is complete when ALL hold:

1. All 5 entity pages (Properties, PropertyDetail, Tenants, TenantDetail, Transactions, FX, Profile) render in the SPA with feature parity.
2. All legacy views, templates, routes, static JS, CSS, and Django forms deleted. `views.py` contains only `SpaView` (and non-page helpers). `templates/rentals/` contains only `spa_index.html`. `static/rentals/` contains only SVG icons. `forms.py` is empty or gone.
3. PropertyValuation ViewSet live at `/api/v1/property-valuations/` with IDOR-proving tests.
4. FX inversion fixed — `round(1/fx_rate, 6)` removed; golden values updated; consolidation complete; all char tests green.
5. Stats endpoints working and consumed by the SPA tables.
6. Vacate, FX update, settings update, change-password all working via typed endpoints.
7. TransactionsPage supports drill-down filters via URL params (ready for Plan C).
8. Test suites pass: pytest (updated char tests) + Vitest (new entity/form/page tests) + build green.
9. `check --deploy` still reports no critical issues.
10. Manual smoke test: every page works end-to-end.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| FX char-test golden values drift unexpectedly during consolidation | Run char tests after EACH consolidation step (rent_total, then pnl_calc loop 1, then loop 2). If a non-FX golden value changes, bisect to find which consolidation step caused it. |
| PropertyValuation ViewSet IDOR | Reuse Phase 1 Task 17's exact pattern + cross-landlord test. |
| Stats endpoint performance (computes per-row FX for every property/tenant) | The Phase 1 FX graph cache (Task 10) makes this O(1) per FX lookup. If still slow, add per-request memoization. |
| Legacy deletion breaks a hidden dependency | Grep for imports of deleted views/forms BEFORE deleting. Per-page deletion (not bulk) isolates breakage. |
| React Query cache-key typos cause stale UI | Centralized `api/keys.ts` factory + TypeScript on keys. |
| Forms migration: Django validators vs zod schemas | Zod schemas match Django's `clean()` rules; server-side validation still runs (DRF serializers) as a safety net. |
| Session-key removal (Plan A flag) | The SPA never reads Django-session `chart_settings` / `default_currency` / `digits`; settings live in User fields + React state. Legacy views that read those keys are deleted with the views. |

## 11. Open questions

None blocking. (During implementation, the developer may choose exact shadcn component variants, the precise stats-endpoint response shapes, and the DataTable feature set — all local decisions documented in the plan.)
