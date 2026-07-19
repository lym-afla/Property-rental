# SPA + Charting Modernization — Design Spec

**Date:** 2026-07-19
**Status:** Approved (pending user review of written spec)
**Phases:** Merged Phase 2 (charting overhaul) + Phase 3 (frontend reshape)
**Predecessor:** Phase 1 Foundation (`docs/superpowers/specs/2026-07-17-foundation-modernization-design.md`, merged to `main` at tag `phase-1-foundation`)
**Successors:** Phase 4 (architecture debt: `Tenant` god-model refactor, `debt`/`debt_advance_payment` dedup, full FX cache hardening)

---

## 1. Context

Phase 1 closed the security holes, extracted a service layer, migrated `FX` to normalized long format, cached the graph, stood up the `/api/v1/` DRF layer (per-user-scoped, IDOR-structurally-closed), and pinned every financial calculation with characterization tests (103/103 green, smoke-tested). The frontend is unchanged — still Django templates + Bootstrap 5 + jQuery + Chart.js.

This phase replaces that frontend with a **React SPA** and rebuilds the charting layer in **Recharts** as the centerpiece. The strategic direction was chosen during Phase 1's brainstorming:

- **Stack:** Django + DRF backend, React + TypeScript + Vite + shadcn/ui + Recharts + TanStack Query frontend.
- **Scope:** Merged Phase 2 + Phase 3 (full SPA rewrite with charts as headline) — chosen over "React islands" or "stay in Chart.js" to do the charting work exactly once and reach the cleanest end state.
- **Auth:** Keep Django session cookies (no token/JWT layer).
- **Deploy:** Django serves the built SPA — same origin, no CORS.
- **Login:** Login + register move into the SPA.
- **Legacy:** Django templates + template-view code deleted as the SPA replaces each page.

## 2. Goals

1. Replace every user-facing Django template page with a React SPA route, with feature parity.
2. Rebuild the 3 existing charts in Recharts and add 5 new high-value charts (Section 5).
3. Deliver 3 interactive chart features: click-to-drill-down, legend toggle, time-range brush.
4. Fix the FX inversion bug (`round(1/fx_rate, 6)` tail in `services/fx.py`) that becomes visible in the new Currency Exposure chart.
5. Delete all legacy template + template-view + jQuery + DataTables + Chart.js code as the SPA takes over each page.
6. Maintain the Phase 1 characterization-test safety net; update pinned FX golden values to reflect the bug fix.
7. Establish a frontend test scaffold (Vitest + Testing Library + MSW) plus a light Playwright smoke suite.

## 3. Non-Goals (out of scope for this phase)

- **Phase 4 architecture debt**: `Tenant` god-model refactor, `debt`/`debt_advance_payment` dedup, `pnl_calc` mixed-types normalization.
- **FX cache hardening**: signals-based invalidation, per-cluster cache, LRU (Phase 1's deferred items).
- **Internationalization (i18n)** — English only.
- **Dark mode** — light only (shadcn supports it later).
- **Mobile-native app** — responsive web only.
- **Real-time updates (websockets)** — React Query refetch-on-focus is enough.
- **CSV/PNG export of charts** — deferred (not selected in brainstorming).
- **Admin-style bulk operations** (bulk delete, bulk assign).
- **Multi-currency input on transactions** beyond today's behavior.
- **Migration of every existing DRF template endpoint** — only the auth + property-valuations additions needed to retire templates (Section 7).

## 4. Architecture & project layout

```
property-rental/                         <- repo root
├── property_rental/                     <- Django project (existing)
│   ├── manage.py
│   ├── property_rental/settings/        <- Phase 1 settings package
│   └── rentals/                         <- Django app (slims down)
│       ├── api/                         <- DRF (extended in Section 7)
│       ├── models.py, services/         <- (existing)
│       └── templates/rentals/           <- SHRINKS as SPA replaces pages
│
└── frontend/                            <- NEW: the React SPA
    ├── package.json
    ├── vite.config.ts                   <- dev proxy → Django :8000
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── components.json                  <- shadcn/ui config
    ├── index.html
    └── src/
        ├── main.tsx                     <- entry, mounts <App/>
        ├── App.tsx                      <- router + providers
        ├── api/                         <- typed client + React Query hooks
        │   ├── client.ts                <- fetch wrapper (CSRF, JSON, 401 handling)
        │   ├── properties.ts            <- useProperties(), useProperty(id), mutations
        │   ├── tenants.ts, transactions.ts, fx.ts, propertyValuations.ts
        │   ├── auth.ts                  <- useLogin/useLogout/useRegister/useSession
        │   └── charts.ts                <- useChartData(type, params)
        ├── components/
        │   ├── ui/                      <- shadcn/ui generated components
        │   ├── charts/                  <- Recharts wrappers (Section 5)
        │   ├── layout/                  <- AppLayout, Navbar, ProtectedRoute
        │   └── forms/                   <- react-hook-form + zod entity forms
        ├── pages/                       <- one per route (Section 6)
        ├── hooks/                       <- domain hooks (useDebounce, etc.)
        ├── lib/                         <- utils, formatters, currency
        ├── context/                     <- ThemeContext, SettingsContext
        └── types/                       <- shared TS types (Property, Tenant...)
```

### Key architecture decisions

1. **`frontend/` is a sibling of `property_rental/`**, not nested. Clean separation; the Django app doesn't need Node/Vite.
2. **Dev: Vite dev server proxies API calls to Django.** `vite.config.ts` sets `server.proxy` for `/api`, `/login`, `/logout` → `http://127.0.0.1:8000`. Cookies (CSRF + sessionid) forward through.
3. **Prod: Vite builds to `frontend/dist/`.** Django's `prod.py` adds `'DIRS': [BASE_DIR.parent / 'frontend' / 'dist']` to `TEMPLATES`; a catch-all Django view serves `index.html` for any non-`/api/`, non-`/admin/`, non-`/static/` path. Same origin → cookies "just work."
4. **The DRF API is the single contract.** The SPA never touches Django templates, never reads Django-session `chart_settings`. Chart state is React state (URL-synced for shareable views).
5. **CSRF on mutations.** The SPA reads the `csrftoken` cookie and sends it as the `X-CSRFToken` header on POST/PUT/PATCH/DELETE. A single `api/client.ts` wrapper handles this once.

### Legacy deletion strategy

For each page the SPA takes over, the same PR deletes:
- The template (`templates/rentals/<page>.html`)
- The view function (or `path()` entry in `urls.py`)
- The static JS handlers for that page (chunks of `element.js`, `layout.js`, `chart.js`, `settings.js`, `index.js`)
- Eventually all of `static/rentals/` (except SVG icons if not migrated) and the inline DRF serializers in `views.py` (Phase 1 left these as legacy template-view helpers; Phase 2 retires them once `handle_element` is deleted).

## 5. Charting design (the headline)

### The 8 charts

| # | Page | Chart | Type | Data source | Why this type |
|---|---|---|---|---|---|
| **1** | Home | **Portfolio Cash Flow** | Diverging stacked bar (income split above, expenses split below axis) | `/api/v1/chart-data?type=homePage` | Shows income vs expenses vs net in one frame; the old "everything above zero" stacked bar hid profitability at a glance |
| **2** | Home | **Net Income Trend** | Line + area (toggle) | Derived from #1 (sum of categories per period) | Companion to #1: the *trajectory* |
| **3** | Home | **Expense Breakdown** | Donut | Aggregated transactions (last 12 mo, by category) | "Where does the money go" — proportions a stacked bar can't show |
| **4** | Home | **Portfolio Occupancy** | Stacked area (occupied vs vacant units over time) | Tenants' lease_start/lease_end + properties | #1 landlord KPI; absent today |
| **5** | Home | **Currency Exposure** | Horizontal stacked bar (current value at-risk by currency) | Properties × currency + FX (corrected rates) | Multi-currency is core; shows FX exposure at a glance |
| **6** | Property detail | **Property Valuation** | Stacked bar (Debt + Equity) + line overlay (value trajectory) | `/api/v1/chart-data?type=property` | Replaces stale/hardcoded chart; combo shows snapshot split and trend |
| **7** | Property detail | **Rent Yield** | Line (rent / value %, per period) | Derived: rent_total ÷ property_value, per period | Universal property-investment metric; absent today |
| **8** | Tenant detail | **Tenant Rent History** | Bar + Brush | `/api/v1/chart-data?type=tenant` | Replaces existing chart; Brush handles long tenancies |

### Interactivity

- **Click-to-drill-down** (charts 1, 6, 8): clicking a bar/segment navigates to `/transactions?from=...&to=...&category=...`. TransactionsPage reads URL params on mount and pre-filters.
- **Legend toggle** (charts 1, 3, 5, 6): Recharts `<Legend/>` is interactive by default — click a legend item to hide that series.
- **Time-range brush** (charts 1, 2, 8): Recharts `<Brush/>` under the chart.

### Bugs fixed by the rewrite

All Phase-1-deferred charting bugs are addressed by the rewrite:

| Bug | Fix |
|---|---|
| `aspectRatio: 1\|3` bitwise-OR typo (home chart renders too short) | Eliminated — Recharts uses `<ResponsiveContainer>` with explicit height |
| Property valuation chart never refreshes after edits | Eliminated — React Query auto-invalidates on mutation success |
| Currency axis label `$k` confusion | Eliminated — proper `formatCurrency()` formatter in `lib/format.ts` |
| Not accessible (no aria-labels, no fallback) | Each chart wrapped in `<ChartCard>` with title + SR-only summary + "view data table" toggle |
| Not responsive in tab panes | Eliminated — `<ResponsiveContainer>` listens to parent resize |
| N+1 perf (per-call FX graph rebuild) | Already fixed in Phase 1 Task 10 |

### FX inversion bug fix

Phase 1 pinned a latent bug: `services/fx.py:get_rate` ends with `fx_rate = round(1 / fx_rate, 6)`, returning the reciprocal. Today it's hidden because chart math uses the rate twice (canceling the inversion), but the new Currency Exposure chart and rent-yield calc display raw FX-derived numbers — making the bug visible.

**Fix:** remove the unconditional inversion in `services/fx.py`. Update the pinned golden values in `rentals/tests/test_fx_char.py` and `rentals/tests/test_financials_char.py` to the corrected (non-inverted) values. The char tests are the proof the fix is complete.

## 6. Page-by-page SPA design

### Route map (React Router)

| Route | Page | Content | Legacy deleted |
|---|---|---|---|
| `/login` | LoginPage | React form → POST `/api/v1/auth/login/` | `login.html` + `login_view` |
| `/register` | RegisterPage | React form → POST `/api/v1/auth/register/` | `register.html` + `register_view` |
| `/` | HomePage | Dashboard — KPI cards + 5 charts (1–5) + P&L table | `index.html`, `index.js` |
| `/properties` | PropertiesPage | Table with inline P&L, sort/filter, click→detail | `properties.html` |
| `/properties/:id` | PropertyDetailPage | Header card + 2 charts (6, 7) + valuation history + transactions subset | (was modal in `handle_element`) |
| `/tenants` | TenantsPage | Table with debt calc, vacate action, click→detail | `tenants.html` |
| `/tenants/:id` | TenantDetailPage | Header card + rent chart (8) + lease timeline + transactions subset | (was modal) |
| `/transactions` | TransactionsPage | Filterable table (replaces DataTables) with drill-down from charts | `transactions.html` + jQuery + DataTables |
| `/fx` | FXPage | Long-format table + Update FX button + rate-history mini-chart | `fx_list.html` |
| `/profile` | ProfilePage | Tabs: User details / Settings (incl. `effective_date`) / Change password | `profile_page.html`, `edit_profile.html`, `settings.js` |
| `*` | NotFoundPage | 404 | (new) |

### Detail-page promotion (UX improvement)

Property/Tenant detail are currently modals from the table. The SPA promotes them to real routes (`/properties/:id`, `/tenants/:id`). Three benefits: bookmarkable URLs, back-button works, mobile-friendly. The table's row-click navigates instead of opening a modal.

### HomePage dashboard layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  Navbar (Property rental · Home/Properties/Tenants/Transactions · ⚙) │
├──────────────────────────────────────────────────────────────────────┤
│  [KPI: 2 Properties]  [KPI: $10,204 Rev YTD]  [KPI: $12,400 Net]   │
│  [KPI: 100% Occupancy]  [KPI: $X at-risk EUR / $Y GBP / $Z RUB]    │
├──────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────┐  ┌─────────────────────────────┐ │
│  │ Chart 1: Cash Flow (stacked)   │  │ Chart 3: Expense Breakdown  │ │
│  │ [M|Q|Y] [Last 6mo ▼]  [brush]  │  │ (donut, last 12mo)          │ │
│  └────────────────────────────────┘  └─────────────────────────────┘ │
│  ┌────────────────────────────────┐  ┌─────────────────────────────┐ │
│  │ Chart 2: Net Income Trend      │  │ Chart 4: Occupancy          │ │
│  │ (line + area toggle)           │  │ (stacked area)              │ │
│  └────────────────────────────────┘  └─────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Chart 5: Currency Exposure (horizontal stacked bar)            │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ P&L table (per-category YTD + all-time)                        │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

Responsive: stacks to single column under `lg`. Each chart lives in a `<ChartCard>` with title, controls, and the accessibility "view as table" toggle.

### Settings move

Currently chart settings (`frequency`, `timeline`, `default_currency`, etc.) live in `request.session` and `User` fields. The SPA keeps the `User` fields (persisted via `PATCH /api/v1/auth/me/`) but **drops the session-based `chart_settings` dict** — chart state becomes React state, URL-synced via query params for shareable views. The session-stored version was a workaround for server-rendered templates.

## 7. Components, forms, UX patterns

### Component organization

- **`components/ui/`** — shadcn/ui generated primitives: `button`, `input`, `select`, `checkbox`, `dialog`, `tabs`, `dropdown-menu`, `table`, `card`, `badge`, `tooltip`, `sonner` (toasts), `skeleton`, `separator`.
- **`components/layout/`** — `AppLayout.tsx` (navbar + `<Outlet/>`), `Navbar.tsx`, `ProtectedRoute.tsx` (redirects to `/login` if `useSession()` null).
- **`components/charts/`** — Recharts wrappers, one file per chart. Each takes `data` + `params` and renders inside a `<ChartCard>`. Plus `_chartFormatters.ts` (currency/number/date axis+tooltip formatters — the "fix `$k`" lives here) and `_chartTheme.ts` (palette per category).

### Forms

Every form is shadcn/ui driven by `react-hook-form` + `zod`:

| Form | Fields | API |
|---|---|---|
| `PropertyForm` | name, location, address, num_bedrooms, area, currency, sold (opt) | POST/PATCH `/api/v1/properties/` |
| `TenantForm` | first_name, last_name, phone, email, lease_start, lease_end (opt), payday, property (select owned) | POST/PATCH `/api/v1/tenants/` |
| `TransactionForm` | date, property (select owned), tenant (select filtered by property), category, amount, currency, comment | POST/PATCH `/api/v1/transactions/` |
| `PropertyValuationForm` | capital_structure_date, capital_structure_value, capital_structure_debt | POST/PATCH `/api/v1/property-valuations/` (new — Section 8) |
| `VacateTenantForm` | lease_end | PATCH `/api/v1/tenants/:id/` |
| `ProfileSettingsForm` | default_currency, default_currency_for_all_data, chart_frequency, chart_timeline, digits, effective_date | PATCH `/api/v1/auth/me/` |
| `LoginForm`, `RegisterForm`, `ChangePasswordForm` | standard | `/api/v1/auth/*` |

### Modals (replacing Django ones)

All built on shadcn `<Dialog>`:
- **EntityFormDialog** — `<EntityFormDialog entity="property" mode="create" />`. Triggered by navbar "New Entry" dropdown or row action button. On success: invalidate React Query key, toast "Created", close.
- **ConfirmDialog** — `<ConfirmDialog title="Delete property?" description="This will also delete N tenants and M transactions." onConfirm={...} />`. Dependent-count computed from query data.
- **VacateTenantDialog** — specialized; date picker for `lease_end` + warning copy.

### Toasts (replacing `alert()`)

`sonner` (via shadcn) — toasts for all mutations: success and error paths. Auto-invalidates React Query caches so UI updates without manual refetch. Closes the Phase 1 audit finding of `alert()` blocking the UI thread.

### Data fetching & cache (TanStack Query)

```ts
useProperties(), useProperty(id)
useCreateProperty(), useUpdateProperty(), useDeleteProperty()
useTenants({property_id?}), useTenant(id), useVacateTenant()
useTransactions({property_id?, tenant_id?, category?, from?, to?, period?})  // supports drill-down
useChartData({type, element_id?, freq, start, end, currency})
useFX(), useUpdateFX()
useSession(), useLogin(), useLogout(), useRegister()
```

- **Hierarchical keys**: `['properties']`, `['properties', id]`, `['properties', id, 'valuations']`. Creating a transaction invalidates `['transactions']` AND `['chart-data']` (since charts derive from transactions) — one `queryClient.invalidateQueries({queryKey: ['chart-data']})` covers all chart variants.
- **Stale times**: 60 seconds for list/detail; 0 for charts (always refetch on mount — cheap with the FX cache).

### Drill-down flow

```ts
<CashFlowChart
  data={chartData}
  onBarClick={(period, category) => {
    navigate(`/transactions?from=${period.start}&to=${period.end}&category=${category}`);
  }}
/>
```

TransactionsPage reads URL search params on mount and pre-populates its filter UI.

### Loading / empty / error states

Uniform triad per data-bound view:
- **Loading**: shadcn `<Skeleton>` placeholders (grey rows in tables, skeleton cards for charts).
- **Empty**: friendly empty-state with icon + CTA ("No properties yet. Create your first property →").
- **Error**: `<ErrorState>` with message + "Try again" (calls `queryClient.invalidateQueries`).

No more silent `console.error` (Phase 1 audit finding).

## 8. Backend additions (small)

### Auth endpoints (new — needed to retire template login views)

Add to `rentals/api/`:

- `POST /api/v1/auth/login/` — `{username, password}` → sets session cookie, returns `{user: {...}}`.
- `POST /api/v1/auth/logout/` — clears session.
- `GET /api/v1/auth/me/` — returns current user or 401 (SPA uses on app boot).
- `POST /api/v1/auth/register/` — wraps existing registration logic.

These reuse Django's `authenticate`/`login`/`logout` (same session-cookie mechanism Phase 1's template views use), just exposed as JSON endpoints. The existing template login/register views are deleted once the SPA login is live.

### PropertyValuation ViewSet (new — needed to retire `handle_element`)

The legacy `handle_element` view (Phase 1 left it for `data_type='propertyValuation'`) is the only CRUD path for capital-structure entries. To delete `handle_element` entirely, add:

- `/api/v1/property-valuations/` — `ModelViewSet` for `Property_capital_structure`. Same pattern as Phase 1's Task 17: `get_queryset()` filters by `property__owned_by__user=request.user`; `perform_create()`/`perform_update()` validate the `property` FK belongs to the requester. `permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]`. Covered by the same IDOR-proving test pattern (cross-landlord 404, ownership forcing on create).

### FX inversion fix

In `rentals/services/fx.py`, remove the unconditional `round(1 / fx_rate, 6)` tail in `get_rate`. Update `FX.get_rate`'s delegates and the pinned golden values in:
- `rentals/tests/test_fx_char.py` — direct/reverse/2-hop values invert (now correct rather than inverted).
- `rentals/tests/test_financials_char.py` — `test_tenant_rent_total_cross_currency` golden value updates to reflect non-inverted FX.

## 9. Testing & verification

### Frontend tests — Vitest + Testing Library

**Stack:** Vitest, `@testing-library/react`, `@testing-library/jest-dom`, MSW (Mock Service Worker).

| Layer | Examples |
|---|---|
| `lib/format.ts`, `lib/validate.ts` | `formatCurrency(1234, 'USD', {compact: true})` → `'$1.2k'`; zod schemas accept/reject shapes |
| `api/client.ts` | CSRF header attached on POST; 401 clears session; query params serialized |
| React Query hooks | `useProperties()` calls the right endpoint; mutations invalidate the right keys |
| `components/charts/*` | Renders correct bar/donut/line for fixture data; legend click hides series; brush changes range; click-drill fires navigate |
| `components/forms/*` | Submits with valid data; shows zod errors; server-error path toasts |
| `pages/*` | One happy-path + one error-state per page |

**Coverage target:** every chart, every form, every API hook. Pages get one happy + one error test. Fixtures in `src/__fixtures__/` (canned API responses).

### Visual regression — Playwright (light)

8–12 tests covering the manual smoke-test happy paths: login, dashboard renders, navigate each page, click chart bar → drill-down, toggle legend, create entity via modal, logout. Run against a running Django+Vite dev stack. Separate CI workflow (slower).

### Backend tests — extend Phase 1's pytest

- **4 auth endpoints** → happy-path + invalid-creds + 401-when-unauthenticated.
- **PropertyValuation ViewSet** → same IDOR-proving pattern as Phase 1 Task 17.
- **FX inversion fix** → golden-value updates in `test_fx_char.py` + `test_financials_char.py`.

### CI

Extend `.github/workflows/ci.yml`:

```yaml
jobs:
  backend-test:    # existing — pytest on Python 3.11/3.12
  frontend-lint:   # NEW — npm run lint (ESLint + tsc --noEmit)
  frontend-test:   # NEW — npm run test (Vitest)
  frontend-build:  # NEW — npm run build
```

All four jobs green on PR. Matrix: Python 3.11/3.12, Node 20.

## 10. Definition of done

The phase is complete when ALL hold:

1. Every route in Section 6 renders in the SPA with feature parity to the Django template version.
2. All 8 charts in Section 5 render correctly, with the 3 interactive features (drill-down, legend, brush) working.
3. Django templates + template-view code deleted for every replaced page. `templates/rentals/` is empty or contains only the SPA-shell `layout.html` (likely empty). `views.py` no longer has `index`, `properties`, `tenants`, `transactions`, `fx_list`, `profile_page`, `handle_element`, `create_element`, `chart_data_request`, `property_choices`, `new_form`, `update_fx_view`, `property_valuation`, `login_view`, `register_view`.
4. FX inversion bug fixed; pinned char tests reflect corrected values.
5. Old static JS deleted (`element.js`, `layout.js`, `chart.js`, `settings.js`, `index.js`, `properties_not used.js`). `static/rentals/` is gone or contains only SVG icons (which the SPA can also replace).
6. Test suites pass: pytest (with updated char tests) + Vitest + Playwright smoke. All green on `main`.
7. `manage.py check --deploy` still reports no critical issues.
8. Manual smoke test: log in, view dashboard, click a chart bar, edit an entity, see it update — no console errors.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| FX char-test updates drift from real corrected values | Compute new golden values by running the corrected `get_rate` once, capture verbatim. Re-verify with the cross-currency rent_total test. |
| Recharts data-shape mismatch (`{labels, datasets}` vs Recharts' flat-object-per-x) | A small transform in `api/charts.ts` converts the API shape to Recharts' expected `[{x, series1, series2, ...}]`. Tested in isolation. |
| Session cookie not sent in dev (Vite proxy) | Verified pattern; if it breaks, `server.proxy.cookieDomainRewrite` + `changeOrigin: true` in `vite.config.ts`. |
| Catch-all Django view shadows `/api/` or `/admin/` | URL ordering: `/api/`, `/admin/`, `/static/` routes listed BEFORE the catch-all. Tests cover each prefix. |
| React Query cache-key typos cause stale UI | Centralized key factory (`api/keys.ts`); TypeScript on keys. |
| Modal UX regressions vs Django templates | The 3 modal patterns (Section 7) cover what exists; smoke-test the create/edit/delete flows. |
| PropertyValuation ViewSet IDOR | Reuse Phase 1 Task 17's exact pattern + cross-landlord test. |
| Bulk of work in one phase | Sequenced plan (next step): auth → skeleton → entity pages → dashboard → charts → legacy delete. Each step produces a deployable state. |

## 12. Open questions

None blocking. (During implementation, the developer may choose exact shadcn component variants, the precise Recharts version, and the chart color palette — all local decisions.)
