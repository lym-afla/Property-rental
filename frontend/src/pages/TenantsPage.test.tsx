// frontend/src/pages/TenantsPage.test.tsx
//
// Smoke tests for the Tenants list page. The default MSW handlers (see
// `src/test/handlers.ts`) return `fixtureTenantsWithStats` and
// `fixtureProperties`, so the happy path resolves without per-test
// handler registration. The error and empty paths override handlers via
// `server.use(...)` to exercise the `ErrorState` and `EmptyState`
// affordances.
//
// `TenantsPage` uses `useNavigate` for row clicks but no test below
// triggers a click, so the plain `<MemoryRouter>` wrapper is enough
// (no `<Route>` definition needed, unlike the detail page test).
import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'

import { TenantsPage } from './TenantsPage'
import { server } from '@/test/handlers'
import { fixtureTenantWithStats } from '@/__fixtures__/tenant'
import { fixtureTenantsWithStats } from '@/__fixtures__/lists'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <TenantsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TenantsPage', () => {
  it('renders the page title', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: /tenants/i })).toBeInTheDocument()
  })

  it('renders the tenant name from the default fixture', async () => {
    renderPage()
    // The "Tenant" column renders "First Last" — match the full name so
    // the assertion is specific to the fixture.
    const name = `${fixtureTenantWithStats.first_name} ${fixtureTenantWithStats.last_name}`
    expect(await screen.findByText(name)).toBeInTheDocument()
  })

  it('renders the New Tenant button', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: /new tenant/i })).toBeInTheDocument()
  })

  it('renders the Vacate button for an active tenant', async () => {
    renderPage()
    // fixtureTenantWithStats has lease_end '2024-12-31', which is in the
    // past relative to the test runner's clock, so the row would actually
    // render as Vacated and hide the Vacate button. Use the second
    // fixture row (open-ended lease -> Active) to assert the button.
    expect(
      await screen.findByRole('button', { name: /vacate carol doe/i }),
    ).toBeInTheDocument()
  })

  it('renders ErrorState when the with_stats request fails', async () => {
    server.use(
      http.get('/api/v1/tenants/with_stats/', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderPage()
    expect(await screen.findByText(/failed to load tenants/i)).toBeInTheDocument()
  })

  it('renders EmptyState when the list is empty', async () => {
    server.use(
      http.get('/api/v1/tenants/with_stats/', () => HttpResponse.json([])),
    )
    renderPage()
    expect(await screen.findByText(/no tenants yet/i)).toBeInTheDocument()
    // The empty state surfaces its own create affordance.
    expect(
      await waitFor(() => screen.getByRole('button', { name: /new tenant/i })),
    ).toBeInTheDocument()
  })

  it('renders negative debt with accounting brackets and the red class', async () => {
    // debt() returns `paid - due`, so a negative value means the tenant
    // is in arrears. We pin both the bracketed `$(250)` display AND the
    // destructive (red) class so a future regression that flips the
    // sign convention or drops the accounting format is caught.
    server.use(
      http.get('/api/v1/tenants/with_stats/', () =>
        HttpResponse.json([
          {
            ...fixtureTenantsWithStats[0],
            debt: -250,
            stats_currency: 'USD',
          },
        ]),
      ),
    )
    renderPage()
    const debtCell = await screen.findByText('$(250)')
    expect(debtCell).toBeInTheDocument()
    // The cell's <span> carries the destructive class — its parent is
    // the cell wrapper, so we assert on the matched element itself.
    expect(debtCell.className).toContain('text-destructive')
  })

  it('renders positive debt as credit with the green class', async () => {
    // Positive debt = tenant has overpaid (credit balance). Should
    // render without brackets and use the emerald (green) class.
    server.use(
      http.get('/api/v1/tenants/with_stats/', () =>
        HttpResponse.json([
          {
            ...fixtureTenantsWithStats[0],
            debt: 500,
            stats_currency: 'USD',
          },
        ]),
      ),
    )
    renderPage()
    const debtCell = await screen.findByText('$500')
    expect(debtCell).toBeInTheDocument()
    expect(debtCell.className).toContain('text-emerald-600')
  })
})
