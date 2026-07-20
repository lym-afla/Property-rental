# Entity Pages + Legacy Deletion — Implementation Plan (Sub-plan B2 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the B1 infrastructure into 7 SPA entity pages (Properties, PropertyDetail, Tenants, TenantDetail, Transactions, FX, Profile) + a minimal HomePage, fix the B1 review's two contract mismatches, then delete ALL legacy Django templates/views/routes/static-JS/forms that the SPA replaces.

**Architecture:** Each page consumes the B1 hooks + forms + DataTable + modals. Pages are added to the React Router inside `<AppLayout>`. Legacy deletion happens per-page: once an SPA page is verified working, the corresponding Django template + view + route + static JS are deleted in the same task. The final task is a bulk cleanup of everything remaining.

**Tech Stack:** React 19 + TypeScript 6 + Vite 8 + Tailwind v4 + shadcn/ui v4 + TanStack Query v5 + react-hook-form + zod + @tanstack/react-table (frontend); Django 4.2 + DRF 3.14 (backend, deletion only).

## Global Constraints

Copied verbatim from the spec (`docs/superpowers/specs/2026-07-19-entity-pages-design.md`):

- **All 5 entity pages** in this plan: Properties, Tenants, Transactions, FX, Profile (plus detail pages for Properties and Tenants).
- **Delete all replaced legacy views** (clean cut — including the orphaned `views.index`).
- Decimal fields come through as strings (DRF default) — TypeScript types use `string` for Decimal fields.
- snake_case field names preserved on the TS side.
- App is **personal / not live** — breaking changes acceptable.
- Phase 1 + Plan A + Plan B1 suites must stay green throughout (131 backend + 50 frontend).
- Git identity (repo-local, configured): `YL-STARDESTROYER <yaroslav.linik@gmail.com>`.
- Working dir: `D:/Developing/Property-rental`. Django project at `property_rental/`.
- Run pytest from `property_rental/`: `cd property_rental && python -m pytest rentals/tests/ -q`.
- Run frontend tests from `frontend/`: `cd frontend && npm test`.
- Platform: Windows, Git Bash.

**B1 review's two contract fixes (Task 1 of this plan):**
- Vacate response: backend returns `TenantSerializer`; frontend types it as `{detail, lease_end}` → fix frontend to match.
- Chart-data MSW fixture: returns `{labels, income, expense, net}` but backend returns `{labels, datasets, currency}` → fix MSW handler.

---

## Task Ordering

1. **Fix B1 contract mismatches** (Task 1) — vacate + chart-data MSW.
2. **PropertiesPage + delete legacy** (Task 2).
3. **PropertyDetailPage** (Task 3).
4. **TenantsPage + delete legacy** (Task 4).
5. **TenantDetailPage** (Task 5).
6. **TransactionsPage + delete legacy** (Task 6).
7. **FXPage + delete legacy** (Task 7).
8. **ProfilePage + delete legacy** (Task 8).
9. **HomePage minimal + delete legacy index** (Task 9).
10. **Bulk legacy cleanup** (Task 10) — delete remaining static JS, CSS, Django forms, inline serializers, dead routes.
11. **Frontend page tests** (Task 11).
12. **Verification** (Task 12).

---

## Task 1: Fix B1 contract mismatches

**Goal:** Fix the two frontend contract mismatches the B1 whole-branch review flagged.

**Files:**
- Modify: `frontend/src/api/tenants.ts` (vacate response type)
- Modify: `frontend/src/test/handlers.ts` (vacate + chart-data MSW handlers)
- Modify: `frontend/src/api/tenants.test.tsx` (vacate test assertions)

**Interfaces:**
- Produces: `useVacateTenant` returns `Tenant` (not `{detail, lease_end}`). Chart-data MSW returns `{labels, datasets, currency}`.

- [ ] **Step 1: Fix vacate response type**

In `frontend/src/api/tenants.ts`, find `useVacateTenant`. The mutation's return type is `{ detail: string; lease_end: string }` — change it to `Tenant` (import from `@/types/tenant`):
```typescript
export function useVacateTenant() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, lease_end }: { id: number; lease_end: string }) =>
      apiFetch<Tenant>(`/tenants/${id}/vacate/`, { method: 'POST', body: { lease_end } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tenants.all })
      qc.invalidateQueries({ queryKey: queryKeys.tenants.withStats })
    },
  })
}
```

- [ ] **Step 2: Fix vacate MSW handler**

In `frontend/src/test/handlers.ts`, find the vacate handler. Change the response from `{detail: 'Tenant vacated', lease_end: ...}` to return the full tenant shape using the fixture:
```typescript
http.post('/api/v1/tenants/:id/vacate/', async ({ request, params }) => {
  const body = await request.json() as { lease_end: string }
  return HttpResponse.json({ ...fixtureTenant, lease_end: body.lease_end })
}),
```

- [ ] **Step 3: Fix chart-data MSW handler**

In `frontend/src/test/handlers.ts`, find the chart-data handler. Change from `{labels: [], income: [], expense: [], net: []}` to the real shape:
```typescript
http.get('/api/v1/chart-data/', () => HttpResponse.json({
  labels: ['Jan-24', 'Feb-24', 'Mar-24'],
  datasets: [{ label: 'rent', data: [1000, 1000, 1000] }],
  currency: 'USD',
})),
```

- [ ] **Step 4: Fix vacate test assertions**

In `frontend/src/api/tenants.test.tsx`, find the vacate test. Change assertions from checking `.detail` and `.lease_end` to checking the returned `Tenant` shape (e.g., `result.current.data?.id`).

- [ ] **Step 5: Run tests + build**

```bash
cd frontend && npm test && npm run build
```
All 50 tests pass, build green.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/tenants.ts frontend/src/test/handlers.ts frontend/src/api/tenants.test.tsx
git commit -m "fix(frontend): vacate response type + chart-data MSW fixture (B1 review findings)"
```

---

## Task 2: PropertiesPage + delete legacy properties view

**Goal:** Build the Properties list page consuming B1 hooks, then delete the legacy template + view + route.

**Files:**
- Create: `frontend/src/pages/PropertiesPage.tsx`
- Create: `frontend/src/pages/PropertiesPage.test.tsx`
- Modify: `frontend/src/App.tsx` (add route)
- Delete: `property_rental/rentals/templates/rentals/properties.html`
- Modify: `property_rental/rentals/views.py` (delete `properties` function)
- Modify: `property_rental/rentals/urls.py` (delete `/properties/` route)

**Interfaces:**
- Consumes: `usePropertiesWithStats`, `useProperties`, `useDeleteProperty`, `<DataTable>`, `<EntityFormDialog>`, `<PropertyForm>`, `<SkeletonTable>`, `<EmptyState>`, `<ErrorState>` from B1.

- [ ] **Step 1: Write PropertiesPage**

`frontend/src/pages/PropertiesPage.tsx`:
```tsx
import { useNavigate } from 'react-router-dom'
import { usePropertiesWithStats, useDeleteProperty } from '@/api/properties'
import { DataTable } from '@/components/table/DataTable'
import type { ColumnDef } from '@tanstack/react-table'
import type { PropertyWithStats } from '@/types/property'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { PropertyForm } from '@/components/forms/PropertyForm'
import { ConfirmDialog } from '@/components/modals/ConfirmDialog'
import { SkeletonTable } from '@/components/states/SkeletonTable'
import { EmptyState } from '@/components/states/EmptyState'
import { ErrorState } from '@/components/states/ErrorState'
import { useState } from 'react'
import { toast } from 'sonner'
import { formatCurrency } from '@/lib/format'

const columns: ColumnDef<PropertyWithStats>[] = [
  { accessorKey: 'name', header: 'Property' },
  { accessorKey: 'location', header: 'Location' },
  {
    accessorKey: 'net_income_all_time',
    header: 'Net (All-time)',
    cell: ({ row }) => formatCurrency(row.original.net_income_all_time, 'USD'),
  },
  {
    accessorKey: 'net_income_ytd',
    header: 'Net (YTD)',
    cell: ({ row }) => formatCurrency(row.original.net_income_ytd, 'USD'),
  },
]

export function PropertiesPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, refetch } = usePropertiesWithStats()
  const deleteProperty = useDeleteProperty()
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<PropertyWithStats | null>(null)

  if (isLoading) return <SkeletonTable />
  if (isError) return <ErrorState message="Failed to load properties" onRetry={() => refetch()} />
  if (!data || data.length === 0) return (
    <EmptyState
      title="No properties yet"
      description="Create your first property to start tracking."
      action={<Button onClick={() => setCreateOpen(true)}><Plus className="mr-2 h-4 w-4" />New Property</Button>}
    />
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Properties</h1>
        <Button onClick={() => setCreateOpen(true)}><Plus className="mr-2 h-4 w-4" />New Property</Button>
      </div>
      <DataTable
        columns={columns}
        data={data}
        onRowClick={(row) => navigate(`/properties/${row.id}`)}
      />
      <EntityFormDialog open={createOpen} onOpenChange={setCreateOpen} title="Create Property">
        {(props) => <PropertyForm {...props} onSubmit={(values) => {
          // Wire to useCreateProperty mutation — the dialog handles close/toast
        }} />}
      </EntityFormDialog>
      {deleteTarget && (
        <ConfirmDialog
          open={!!deleteTarget}
          onOpenChange={() => setDeleteTarget(null)}
          title={`Delete ${deleteTarget.name}?`}
          description="This action cannot be undone."
          onConfirm={() => {
            deleteProperty.mutate(deleteTarget.id, {
              onSuccess: () => { toast.success('Property deleted'); setDeleteTarget(null) },
              onError: () => toast.error('Failed to delete property'),
            })
          }}
        />
      )}
    </div>
  )
}
```
**Note:** The `EntityFormDialog` interface from B1 uses `title`/`children` (not `entity`/`onSuccess` — see B1 review). The page wires the mutation inside the form's `onSubmit`. Read `EntityFormDialog.tsx` first to confirm its actual props.

- [ ] **Step 2: Add the route**

In `frontend/src/App.tsx`, add inside `<AppLayout>`:
```tsx
import { PropertiesPage } from '@/pages/PropertiesPage'
// in <Routes>:
<Route path="/properties" element={<PropertiesPage />} />
```

- [ ] **Step 3: Write a basic page test**

`frontend/src/pages/PropertiesPage.test.tsx`:
```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PropertiesPage } from './PropertiesPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><PropertiesPage /></MemoryRouter>
    </QueryClientProvider>
  )
}

describe('PropertiesPage', () => {
  it('renders the page title', async () => {
    renderPage()
    expect(await screen.findByText(/properties/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 4: Run tests + build**

```bash
cd frontend && npm test && npm run build
```

- [ ] **Step 5: Manual smoke test (both servers)**

Both servers running. Navigate to `/properties` in the SPA. Confirm: table renders with data, "New Property" button opens dialog, row click navigates to detail (not built yet — will 404, that's OK for now).

- [ ] **Step 6: Delete legacy properties view**

```bash
cd "D:/Developing/Property-rental"
git rm property_rental/rentals/templates/rentals/properties.html
```
In `property_rental/rentals/views.py`, delete the `properties` function. In `property_rental/rentals/urls.py`, delete the `path('properties/', ...)` route. Grep first to find them:
```bash
cd property_rental && grep -n "def properties\b\|path.*properties/" rentals/views.py rentals/urls.py
```

- [ ] **Step 7: Run backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```
If any test referenced the deleted view, update or delete it.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(frontend): PropertiesPage + delete legacy properties view/template"
```

---

## Task 3: PropertyDetailPage

**Goal:** Build the property detail page with Overview + Valuations tabs.

**Files:**
- Create: `frontend/src/pages/PropertyDetailPage.tsx`
- Modify: `frontend/src/App.tsx` (add `/properties/:id` route)

**Interfaces:**
- Consumes: `useProperty`, `usePropertyValuations`, `useTransactions`, `<DataTable>`, `<EntityFormDialog>`, `<PropertyForm>`, `<PropertyValuationForm>`, `<ConfirmDialog>`.

- [ ] **Step 1: Write PropertyDetailPage**

The page has:
- Header card (property name, location, currency).
- Tabs: "Overview" (P&L breakdown + transactions subset) and "Valuations" (DataTable of `Property_capital_structure` entries with create/edit/delete).
- Edit/Delete actions for the property itself.
- Chart placeholders (Plan C fills them).

Use shadcn `<Tabs>` (add via `npx shadcn@latest add tabs` if not present).

Read the B1 hooks first to confirm their exact signatures.

- [ ] **Step 2: Add the route**

```tsx
<Route path="/properties/:id" element={<PropertyDetailPage />} />
```

- [ ] **Step 3: Run build + manual smoke test**

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(frontend): PropertyDetailPage with Overview + Valuations tabs"
```

---

## Task 4: TenantsPage + delete legacy tenants view

**Goal:** Build the Tenants list page, then delete legacy.

**Files:**
- Create: `frontend/src/pages/TenantsPage.tsx`
- Create: `frontend/src/pages/TenantsPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Delete: `property_rental/rentals/templates/rentals/tenants.html`
- Modify: `property_rental/rentals/views.py` (delete `tenants` function)
- Modify: `property_rental/rentals/urls.py` (delete `/tenants/` route)

- [ ] **Step 1: Write TenantsPage**

Columns: Tenant name, Property, Renting since, Status (Active/Vacated/Will vacate), Rent rate, Revenue (all-time + YTD), Debt, Action (Vacate button). Data from `useTenantsWithStats()`. Row click → `/tenants/:id`. Vacate button → `<VacateTenantDialog>`.

- [ ] **Step 2: Add route + basic test + smoke test**

- [ ] **Step 3: Delete legacy tenants view + template + route**

- [ ] **Step 4: Run backend suite + commit**

```bash
git add -A
git commit -m "feat(frontend): TenantsPage + delete legacy tenants view/template"
```

---

## Task 5: TenantDetailPage

**Goal:** Build the tenant detail page.

**Files:**
- Create: `frontend/src/pages/TenantDetailPage.tsx`
- Modify: `frontend/src/App.tsx` (add `/tenants/:id` route)

- [ ] **Step 1: Write TenantDetailPage**

Header card (name, property, lease dates, rent rate, debt) + tabs: "Overview" (transactions subset) and "Lease timeline" (Lease_rent history + lease events). Chart placeholder (Plan C).

- [ ] **Step 2: Add route + build + smoke test**

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat(frontend): TenantDetailPage with Overview + Lease timeline"
```

---

## Task 6: TransactionsPage + delete legacy transactions view

**Goal:** Build the Transactions page with URL-synced filters (drill-down ready), then delete legacy (including jQuery + DataTables).

**Files:**
- Create: `frontend/src/pages/TransactionsPage.tsx`
- Create: `frontend/src/pages/TransactionsPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Delete: `property_rental/rentals/templates/rentals/transactions.html`
- Modify: `property_rental/rentals/views.py` (delete `transactions` function)
- Modify: `property_rental/rentals/urls.py` (delete `/transactions/` route)

- [ ] **Step 1: Write TransactionsPage**

Filter bar (property select, tenant select, category select, date range, search) + `<DataTable>`. URL-synced filters: reads `useSearchParams()` on mount, pre-populates filter UI. Data from `useTransactions({property_id, tenant_id, category, from, to})`.

Create via `<EntityFormDialog>` with `TransactionForm` (property→tenant cascade).

- [ ] **Step 2: Add route + basic test + smoke test**

- [ ] **Step 3: Delete legacy transactions view + template + route**

- [ ] **Step 4: Run backend suite + commit**

```bash
git add -A
git commit -m "feat(frontend): TransactionsPage with URL-synced filters; delete legacy transactions view"
```

---

## Task 7: FXPage + delete legacy FX view

**Goal:** Build the FX page, then delete legacy.

**Files:**
- Create: `frontend/src/pages/FXPage.tsx`
- Modify: `frontend/src/App.tsx`
- Delete: `property_rental/rentals/templates/rentals/fx_list.html`
- Modify: `property_rental/rentals/views.py` (delete `fx_list` function)
- Modify: `property_rental/rentals/urls.py` (delete `/fx/` route)

- [ ] **Step 1: Write FXPage**

"Update FX" button (calls `useUpdateFX()` mutation) + `<DataTable>` of FX rates (Date, From, To, Rate).

- [ ] **Step 2: Add route + build + smoke test**

- [ ] **Step 3: Delete legacy FX view + template + route**

- [ ] **Step 4: Run backend suite + commit**

```bash
git add -A
git commit -m "feat(frontend): FXPage; delete legacy fx_list view/template"
```

---

## Task 8: ProfilePage + delete legacy profile views

**Goal:** Build the Profile page with 3 tabs, then delete legacy.

**Files:**
- Create: `frontend/src/pages/ProfilePage.tsx`
- Modify: `frontend/src/App.tsx`
- Delete: `property_rental/rentals/templates/rentals/profile_page.html`, `edit_profile.html`
- Modify: `property_rental/rentals/views.py` (delete `profile_page`, `edit_profile` functions)
- Modify: `property_rental/rentals/urls.py` (delete `/profile/`, `/edit-profile/` routes)

- [ ] **Step 1: Write ProfilePage**

Tabs: "User details" (read-only display + edit dialog), "Settings" (`<ProfileSettingsForm>` → `PATCH /auth/me/`), "Change password" (form → `POST /auth/change-password/`).

- [ ] **Step 2: Add route + build + smoke test**

- [ ] **Step 3: Delete legacy profile views + templates + routes**

- [ ] **Step 4: Run backend suite + commit**

```bash
git add -A
git commit -m "feat(frontend): ProfilePage with 3 tabs; delete legacy profile views/templates"
```

---

## Task 9: HomePage minimal + delete legacy index view

**Goal:** Replace the Plan A HomePage placeholder with a minimal dashboard (counts + links), then delete the legacy `views.index` — the B1 review's #1 prerequisite.

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Delete: `property_rental/rentals/templates/rentals/index.html`
- Modify: `property_rental/rentals/views.py` (delete `index` function)
- Modify: `property_rental/rentals/urls.py` (delete `path('', views.index, ...)` — the SPA catch-all now serves `/`)

- [ ] **Step 1: Update HomePage**

Minimal content:
- Properties count (from `useProperties()`) + link to `/properties`.
- Tenants count (from `useTenants()`) + link to `/tenants`.
- "Dashboard coming soon" note where charts will go (Plan C).

- [ ] **Step 2: Delete legacy index view + template + route**

```bash
git rm property_rental/rentals/templates/rentals/index.html
```
In `views.py`, delete the `index` function. In `urls.py`, delete `path('', views.index, name='index')`. The `path('', SpaView.as_view())` from Task 6 of Plan A now wins (it was dead code until now).

- [ ] **Step 3: Run backend suite — verify no session-key KeyError**

The B1 review flagged that `views.index` read session keys (`default_currency`, `chart_settings`, `digits`) that the SPA login doesn't populate. Deleting `index` eliminates the latent 500. Verify the backend suite passes.

- [ ] **Step 4: Manual smoke test (prod mode)**

Build the SPA (`npm run build`), then load `http://127.0.0.1:8000/` directly (NOT via Vite proxy). Confirm the SPA loads — no 500.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(frontend): minimal HomePage; delete legacy views.index (B1 review prerequisite)"
```

---

## Task 10: Bulk legacy cleanup

**Goal:** Delete everything remaining — static JS, CSS, Django forms, inline serializers in views.py, remaining legacy routes.

**Files:**
- Delete: `property_rental/rentals/static/rentals/element.js`, `layout.js`, `chart.js`, `settings.js`, `index.js`, `properties_not used.js`
- Delete: `property_rental/rentals/static/rentals/styles.css`, `fontawesome-minimal.css`
- Delete or empty: `property_rental/rentals/forms.py` (all form classes — SPA uses react-hook-form + zod)
- Modify: `property_rental/rentals/views.py` — delete remaining legacy functions: `new_form`, `table_data`, `handle_element`, `create_element`, `vacate_tenant`, `property_choices`, `chart_data_request`, `property_valuation`, `update_fx_view`, `chrome_devtools_config`, `well_known_handler`, `logout_view`. Also delete the inline serializers at the top of views.py (`PropertySerializer`, `TenantSerializer`, `TransactionSerializer`, `PropertyValuationSerializer` — duplicates of `api/serializers.py`). Keep ONLY `SpaView`.
- Modify: `property_rental/rentals/urls.py` — delete ALL remaining legacy routes (everything except `/api/v1/`, `/admin/`, and the SPA catch-all).
- Delete: remaining templates (`dashboard_card.html`, `timeline-chart.html`, `new_form.html`, `payments_table.html`, `settings.html`, `layout.html` if no longer needed).

- [ ] **Step 1: Grep for all remaining legacy views + routes**

```bash
cd property_rental && grep -n "^def \|^class " rentals/views.py
```
Everything except `SpaView` gets deleted.

- [ ] **Step 2: Delete views.py legacy content**

Delete all functions/classes except `SpaView`. Delete the inline serializer imports/definitions at the top. Keep `SpaView` and its imports.

- [ ] **Step 3: Delete urls.py legacy routes**

Keep ONLY: `path('api/v1/', include(...))`, the SPA catch-all (`path('', SpaView...)` and `re_path(...)`), and `app_name`. Delete everything else.

- [ ] **Step 4: Delete static JS + CSS**

```bash
cd "D:/Developing/Property-rental"
git rm property_rental/rentals/static/rentals/element.js
git rm property_rental/rentals/static/rentals/layout.js
git rm property_rental/rentals/static/rentals/chart.js
git rm property_rental/rentals/static/rentals/settings.js
git rm property_rental/rentals/static/rentals/index.js
git rm property_rental/rentals/static/rentals/properties_not\ used.js
git rm property_rental/rentals/static/rentals/styles.css
git rm property_rental/rentals/static/rentals/fontawesome-minimal.css
```

- [ ] **Step 5: Delete Django forms**

Empty or delete `property_rental/rentals/forms.py`. Grep first to confirm no remaining imports:
```bash
cd property_rental && grep -rn "from .forms\|from rentals.forms" rentals/
```
If anything imports from forms.py, remove that import (it's legacy code being deleted).

- [ ] **Step 6: Delete remaining templates**

```bash
git rm property_rental/rentals/templates/rentals/dashboard_card.html
git rm property_rental/rentals/templates/rentals/timeline-chart.html
git rm property_rental/rentals/templates/rentals/new_form.html
git rm property_rental/rentals/templates/rentals/payments_table.html
git rm property_rental/rentals/templates/rentals/settings.html
```
Keep `spa_index.html`. Check if `layout.html` is still referenced anywhere — if not, delete it too.

- [ ] **Step 7: Run backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```
Fix any test that referenced deleted views/forms/routes. Some tests in `test_api.py` may reference `handle_element` — delete those (the SPA's `/api/v1/` endpoints replace `handle_element`).

- [ ] **Step 8: Run frontend tests + build**

```bash
cd frontend && npm test && npm run build
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor: bulk delete all legacy templates, views, routes, static JS/CSS, Django forms"
```

---

## Task 11: Frontend page tests

**Goal:** Add basic page tests for all new pages.

**Files:**
- Create: `frontend/src/pages/{TenantsPage,TransactionsPage,FXPage,ProfilePage,HomePage}.test.tsx`

- [ ] **Step 1: Write a basic test per page**

Each test follows the pattern: render with `QueryClientProvider` + `MemoryRouter`, assert the page title renders. Don't test complex interactions (those are Playwright's job in Plan C).

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npm test
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/
git commit -m "test(frontend): basic page tests for all entity pages"
```

---

## Task 12: Definition-of-done verification

- [ ] **Step 1: Backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```

- [ ] **Step 2: Frontend suite + build**

```bash
cd frontend && npm test && npm run build
```

- [ ] **Step 3: `views.py` contains ONLY `SpaView`**

```bash
cd property_rental && grep -n "^def \|^class " rentals/views.py
```
Expected: only `SpaView` (plus any non-page utility functions that services still need).

- [ ] **Step 4: `templates/rentals/` contains ONLY `spa_index.html`**

```bash
ls property_rental/rentals/templates/rentals/
```

- [ ] **Step 5: `static/rentals/` is empty or contains only SVG icons**

```bash
ls property_rental/rentals/static/rentals/
```

- [ ] **Step 6: `forms.py` is empty or gone**

```bash
cat property_rental/rentals/forms.py 2>/dev/null || echo "DELETED"
```

- [ ] **Step 7: `check --deploy`**

```bash
cd property_rental && python manage.py check --deploy
```

- [ ] **Step 8: Manual smoke test (both servers)**

Walk through every page: properties list, property detail, tenants list, tenant detail, transactions (with filters), FX, profile settings, change password. Create/edit/delete at least one entity per type. Confirm no console errors.

- [ ] **Step 9: Commit + tag**

```bash
git commit --allow-empty -m "chore: Plan B2 (entity pages + legacy deletion) verification complete"
git tag plan-b2-complete
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task(s) | Covered? |
|---|---|---|
| §6.1 PropertiesPage | Task 2 | ✅ |
| §6.2 PropertyDetailPage | Task 3 | ✅ |
| §6.3 TenantsPage | Task 4 | ✅ |
| §6.4 TenantDetailPage | Task 5 | ✅ |
| §6.5 TransactionsPage | Task 6 | ✅ |
| §6.6 FXPage | Task 7 | ✅ |
| §6.7 ProfilePage | Task 8 | ✅ |
| §6.8 HomePage minimal | Task 9 | ✅ |
| §7 Legacy deletion (templates) | Tasks 2,4,6,7,8,9,10 | ✅ |
| §7 Legacy deletion (views) | Tasks 2,4,6,7,8,9,10 | ✅ |
| §7 Legacy deletion (static JS/CSS) | Task 10 | ✅ |
| §7 Legacy deletion (Django forms) | Task 10 | ✅ |
| B1 review: vacate contract fix | Task 1 | ✅ |
| B1 review: chart-data MSW fix | Task 1 | ✅ |
| B1 review: views.index deletion | Task 9 | ✅ |

**2. Placeholder scan:** The page code (Tasks 2-9) uses abbreviated implementations with the instruction to "read B1 hooks first to confirm signatures." This is deliberate — the B1 hooks' exact signatures were established in B1's plan and verified in reviews; repeating full code for every page would bloat the plan to 2000+ lines. The implementer reads the actual files. Acceptable for a plan at this complexity level.

**3. Type consistency:** All pages consume the B1 types/hooks/components whose names were verified in B1's reviews. The vacate contract fix (Task 1) aligns the frontend type with the backend's actual return shape.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-20-entity-pages-legacy.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
