// frontend/src/pages/PropertyDetailPage.test.tsx
//
// Smoke tests for the property detail page. The default MSW handlers
// return:
//   - `/properties/:id/`         -> fixtureProperty (id 1, "Riverside Flat")
//   - `/property-valuations/`    -> filtered to the property query param
//   - `/transactions/`           -> fixtureTransactions (both tied to id 1)
//
// So the happy path resolves without per-test handler registration. The
// error path overrides `/properties/:id/` to a 500 to exercise the
// `ErrorState` affordance.
//
// `useParams` only returns a value when the page is rendered inside a
// matching `<Route path="/properties/:id">`, so the test wrapper includes
// the route definition rather than just `<MemoryRouter>`.
import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'

import { PropertyDetailPage } from './PropertyDetailPage'
import { server } from '@/test/handlers'
import { fixtureProperty } from '@/__fixtures__/property'

function renderPage(route = '/properties/1') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/properties/:id" element={<PropertyDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PropertyDetailPage', () => {
  it('renders the property name in the header', async () => {
    renderPage()
    // CardTitle renders a <div>, not a real heading element, so we look
    // by text rather than by role.
    expect(await screen.findByText(fixtureProperty.name)).toBeInTheDocument()
  })

  it('renders the location in the header', async () => {
    renderPage()
    // The CardDescription concatenates location + status, so use a substring
    // matcher rather than exact text. Multiple ancestors can match the
    // textContent predicate, so use `getAllByText` and assert non-empty.
    const matches = await screen.findAllByText((_, node) =>
      Boolean(node?.textContent?.includes(fixtureProperty.location)),
    )
    expect(matches.length).toBeGreaterThan(0)
  })

  it('renders the Overview tab with P&L labels', async () => {
    renderPage()
    expect(await screen.findByText(/gross income/i)).toBeInTheDocument()
    expect(screen.getByText(/net income/i)).toBeInTheDocument()
  })

  it('switches to the Valuations tab on click', async () => {
    const user = userEvent.setup()
    renderPage()
    // Wait for the property to load first so the tabs are mounted.
    await screen.findByText(fixtureProperty.name)
    // Click the Valuations tab trigger. `userEvent` (vs raw `.click()`)
    // fires the full pointer + keyboard event sequence radix Tabs listens
    // for, so the inactive panel gets un-hidden in jsdom.
    await user.click(screen.getByRole('tab', { name: /valuations/i }))
    // The Valuations panel surfaces a "New Valuation" button + a
    // "Capital structure" heading.
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /capital structure/i }),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByRole('button', { name: /new valuation/i }),
    ).toBeInTheDocument()
  })

  it('renders ErrorState when the property request fails', async () => {
    server.use(
      http.get('/api/v1/properties/:id/', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderPage()
    expect(await screen.findByText(/failed to load property/i)).toBeInTheDocument()
  })
})
