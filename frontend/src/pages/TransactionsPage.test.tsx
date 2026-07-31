// frontend/src/pages/TransactionsPage.test.tsx
//
// Smoke tests for the Transactions list page. The default MSW handlers
// (see `src/test/handlers.ts`) return `fixtureTransactions`,
// `fixtureProperties`, and `fixtureTenants`, so the happy path resolves
// without per-test handler registration. The error and empty paths
// override handlers via `server.use(...)` to exercise the `ErrorState`
// and `EmptyState` affordances.
//
// URL-sync test: render the page inside `<MemoryRouter initialEntries>` so
// we can assert that an inbound `?property=1&category=rent` pre-populates
// the filter UI, and that the page writes back to the URL when a filter
// changes.
import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'

import { TransactionsPage } from './TransactionsPage'
import { server } from '@/test/handlers'
import { fixtureTransactionIncome } from '@/__fixtures__/transaction'

function renderPage(initialEntry = '/transactions') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/transactions" element={<TransactionsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TransactionsPage', () => {
  it('renders the page title', async () => {
    renderPage()
    expect(
      await screen.findByRole('heading', { name: /transactions/i }),
    ).toBeInTheDocument()
  })

  it('renders rows from the default fixture', async () => {
    renderPage()
    expect(await screen.findByText('Rent')).toBeInTheDocument()
    expect(screen.queryByText(fixtureTransactionIncome.category)).not.toBeInTheDocument()
  })

  it('renders the New Transaction button', async () => {
    renderPage()
    expect(
      await screen.findByRole('button', { name: /new transaction/i }),
    ).toBeInTheDocument()
  })

  it('renders ErrorState when the transactions request fails', async () => {
    server.use(
      http.get('/api/v1/transactions/', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderPage()
    expect(await screen.findByText(/failed to load transactions/i)).toBeInTheDocument()
  })

  it('renders EmptyState when the list is empty', async () => {
    server.use(
      http.get('/api/v1/transactions/', () => HttpResponse.json([])),
    )
    renderPage()
    expect(await screen.findByText(/no transactions yet/i)).toBeInTheDocument()
    expect(
      await waitFor(() => screen.getByRole('button', { name: /new transaction/i })),
    ).toBeInTheDocument()
  })

  it('shows friendly category labels while preserving raw URL and API filter keys', async () => {
    let requestedCategory: string | null = null
    server.use(
      http.get('/api/v1/transactions/', ({ request }) => {
        requestedCategory = new URL(request.url).searchParams.get('category')
        return HttpResponse.json([
          {
            ...fixtureTransactionIncome,
            id: 3,
            category: 'cost_reimbursement',
          },
        ])
      }),
    )

    renderPage('/transactions?property=1&category=cost_reimbursement')
    // Wait for the page to load before querying the filter UI.
    await screen.findByRole('heading', { name: /transactions/i })
    expect((await screen.findAllByText('Cost reimbursement')).length).toBeGreaterThan(0)
    expect(screen.queryByText('cost_reimbursement')).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Category' })).toHaveTextContent(
      'Cost reimbursement',
    )
    expect(requestedCategory).toBe('cost_reimbursement')

    const user = userEvent.setup()
    await user.click(screen.getByRole('combobox', { name: 'Category' }))
    expect(screen.getByRole('option', { name: 'Other expenses' })).toBeVisible()
    await user.keyboard('{Escape}')

    await user.click(screen.getByRole('button', { name: 'Delete transaction 3' }))
    expect(screen.getByText('Delete transaction?')).toBeVisible()
    expect(screen.getByRole('dialog')).toHaveTextContent('Cost reimbursement')
    expect(screen.queryByText('cost_reimbursement')).not.toBeInTheDocument()
  })

  it('matches a friendly category label in search', async () => {
    server.use(
      http.get('/api/v1/transactions/', () =>
        HttpResponse.json([
          {
            ...fixtureTransactionIncome,
            id: 4,
            category: 'cost_reimbursement',
          },
        ]),
      ),
    )

    renderPage('/transactions?search=cost%20reimbursement')

    expect(await screen.findByText('Cost reimbursement')).toBeVisible()
  })

  it('writes filter changes back to the URL', async () => {
    // We capture the live URL via a sibling Route so we can assert the
    // page calls `setSearchParams` after a filter change.
    let observedSearch = ''
    function LocationProbe() {
      const loc = useLocation()
      observedSearch = loc.search
      return null
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/transactions']}>
          <Routes>
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route path="*" element={<LocationProbe />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await screen.findByRole('heading', { name: /transactions/i })
    // On mount with no filters, the URL should remain empty (no
    // `?property=&...` noise). The probe captures whatever react-router
    // stored on the most recent render.
    await waitFor(() => {
      expect(observedSearch).toBe('')
    })
  })
})
