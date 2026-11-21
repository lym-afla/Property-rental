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
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'

import { PropertyDetailPage } from './PropertyDetailPage'
import { server } from '@/test/handlers'
import { fixtureProperty } from '@/__fixtures__/property'

vi.mock('@/context/SessionProvider', () => ({
  useSession: () => ({
    user: { effective_date: '2026-07-29' },
    isLoading: false,
  }),
}))

beforeEach(() => {
  server.use(
    http.get('/api/v1/analytics/portfolio/profit-loss/', () =>
      HttpResponse.json({
        metric: 'profit_and_loss', currency: 'EUR', scale: 1, end: '2026-07-29',
        columns: [
          { key: '2026', label: '2026YTD', start: '2026-01-01', end: '2026-07-29' },
        ],
        rows: [
          { key: 'total_revenue', label: 'Total revenue', kind: 'total_revenue', values: { '2026': 0 } },
          { key: 'total_expenses', label: 'Total expenses', kind: 'total_expenses', values: { '2026': 0 } },
          { key: 'net_income', label: 'Net income', kind: 'net_income', values: { '2026': 0 } },
        ],
      }),
    ),
    http.get('/api/v1/analytics/properties/:id/valuation/', () =>
      HttpResponse.json({
        metric: 'property_valuation', grain: 'record', currency: 'EUR', scale: 1,
        start: '2026-01-01', end: '2026-07-29', status: 'missing_valuation',
        series: [
          { key: 'total_value', label: 'Total value', kind: 'total' },
          { key: 'debt', label: 'Debt', kind: 'debt' },
          { key: 'equity', label: 'Equity', kind: 'equity' },
        ],
        points: [],
      }),
    ),
  )
})

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
    let pnlSearch = ''
    server.use(
      http.get('/api/v1/analytics/portfolio/profit-loss/', ({ request }) => {
        pnlSearch = new URL(request.url).searchParams.toString()
        return (
        HttpResponse.json({
          metric: 'profit_and_loss', currency: 'EUR', scale: 1, end: '2026-07-29',
          columns: [
            { key: '2024', label: '2024', start: '2024-01-01', end: '2024-12-31' },
            { key: '2025', label: '2025', start: '2025-01-01', end: '2025-12-31' },
            { key: '2026', label: '2026YTD', start: '2026-01-01', end: '2026-07-29' },
          ],
          rows: [
            { key: 'rent', label: 'Rent', kind: 'income', values: { '2024': 12000, '2025': 13000, '2026': 7000 } },
            { key: 'total_revenue', label: 'Total revenue', kind: 'total_revenue', values: { '2024': 12000, '2025': 13000, '2026': 7000 } },
            { key: 'total_expenses', label: 'Total expenses', kind: 'total_expenses', values: { '2024': 0, '2025': 0, '2026': 0 } },
            { key: 'net_income', label: 'Net income', kind: 'net_income', values: { '2024': 12000, '2025': 13000, '2026': 7000 } },
          ],
        })
        )
      }),
    )
    renderPage()
    expect(await screen.findByText(/profit & loss/i)).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Profit and Loss statement' })
    expect(table).toBeVisible()
    expect(screen.getByText('2024')).toBeInTheDocument()
    expect(screen.getByText('2025')).toBeInTheDocument()
    expect(screen.getByText('2026YTD')).toBeInTheDocument()
    expect(screen.getAllByText('€12,000').length).toBeGreaterThan(0)
    expect(pnlSearch).toBe('end=2026-07-29&currency=EUR&property=1')
    expect(screen.queryByText(/Server-calculated year-to-date performance/)).not.toBeInTheDocument()
  })

  it('rounds the area and renders a friendly recent-transaction category', async () => {
    server.use(
      http.get('/api/v1/properties/:id/', () =>
        HttpResponse.json({ ...fixtureProperty, area: '85.49' }),
      ),
      http.get('/api/v1/transactions/', () =>
        HttpResponse.json([
          {
            id: 42,
            property: 1,
            tenant: null,
            date: '2026-07-01',
            category: 'cost_reimbursement',
            period: '2026-07',
            currency: 'EUR',
            amount: '-125.00',
            type: 'expense',
            comment: 'Utility refund',
          },
        ]),
      ),
    )

    renderPage()

    expect(await screen.findByText('85 m²')).toBeVisible()
    expect(screen.getByText('Cost reimbursement')).toBeVisible()
    expect(screen.queryByText('cost_reimbursement')).not.toBeInTheDocument()
    expect(screen.queryByText(/Server-calculated year-to-date/)).not.toBeInTheDocument()
  })

  it('uses the latest non-null property value for the header', async () => {
    server.use(
      http.get('/api/v1/property-valuations/', () =>
        HttpResponse.json([
          {
            id: 1,
            property: 1,
            capital_structure_date: '2026-01-01',
            capital_structure_value: '250000.00',
            capital_structure_debt: null,
          },
          {
            id: 2,
            property: 1,
            capital_structure_date: '2026-02-01',
            capital_structure_value: null,
            capital_structure_debt: '100000.00',
          },
        ]),
      ),
    )

    renderPage()

    expect(await screen.findByText('€250,000')).toBeVisible()
  })

  it('renders partial capital snapshots without fabricating zero or equity', async () => {
    server.use(
      http.get('/api/v1/property-valuations/', () =>
        HttpResponse.json([
          {
            id: 1,
            property: 1,
            capital_structure_date: '2026-01-01',
            capital_structure_value: '250000.00',
            capital_structure_debt: null,
          },
          {
            id: 2,
            property: 1,
            capital_structure_date: '2026-02-01',
            capital_structure_value: null,
            capital_structure_debt: '100000.00',
          },
        ]),
      ),
    )
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(fixtureProperty.name)

    await user.click(screen.getByRole('tab', { name: /valuations/i }))

    const valueOnlyRow = screen.getByRole('button', { name: 'Edit valuation 1' }).closest('tr')
    const debtOnlyRow = screen.getByRole('button', { name: 'Edit valuation 2' }).closest('tr')
    expect(valueOnlyRow).toHaveTextContent('€250,000——')
    expect(debtOnlyRow).toHaveTextContent('—€100,000—')
    expect(screen.queryByText('€0')).not.toBeInTheDocument()
  })

  it('orders valuation history by date when older entries are added later', async () => {
    server.use(
      http.get('/api/v1/property-valuations/', () =>
        HttpResponse.json([
          { id: 1, property: 1, capital_structure_date: '2026-12-31', capital_structure_value: '300000.00', capital_structure_debt: null },
          { id: 2, property: 1, capital_structure_date: '2024-12-31', capital_structure_value: '250000.00', capital_structure_debt: null },
          { id: 3, property: 1, capital_structure_date: '2025-04-01', capital_structure_value: null, capital_structure_debt: '150000.00' },
        ]),
      ),
    )
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(fixtureProperty.name)
    await user.click(screen.getByRole('tab', { name: /valuations/i }))

    const editButtons = await screen.findAllByRole('button', { name: /^Edit valuation / })
    expect(editButtons.map((button) => button.getAttribute('aria-label'))).toEqual([
      'Edit valuation 2',
      'Edit valuation 3',
      'Edit valuation 1',
    ])
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

  it('opens valuation history from the empty valuation chart action', async () => {
    server.use(
      http.get('/api/v1/analytics/properties/:id/valuation/', () =>
        HttpResponse.json({
          metric: 'property_valuation', grain: 'record', currency: 'EUR', scale: 1,
          start: '2026-01-01', end: '2026-07-29', status: 'missing_valuation',
          series: [
            { key: 'total_value', label: 'Total value', kind: 'total' },
            { key: 'debt', label: 'Debt', kind: 'debt' },
            { key: 'equity', label: 'Equity', kind: 'equity' },
          ], points: [],
        }),
      ),
    )
    const user = userEvent.setup()
    renderPage()
    await screen.findByText(fixtureProperty.name)
    expect(screen.queryByRole('heading', { name: /capital structure/i })).not.toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: /view valuation history/i }))
    expect(screen.getByRole('heading', { name: /capital structure/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /new valuation/i })).toBeInTheDocument()
  })

  it('shows deposits held for the property as of the effective date', async () => {
    let search = ''
    server.use(
      http.get('/api/v1/deposit-movements/balance/', ({ request }) => {
        search = new URL(request.url).searchParams.toString()
        return HttpResponse.json({
          as_of: '2026-07-29',
          balances: [{ currency: 'EUR', amount: '800.00' }],
          by_tenant: [{ tenant: 1, currency: 'EUR', amount: '800.00' }],
        })
      }),
    )
    renderPage()
    expect(await screen.findByText('Deposits held')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Bob Jones' })).toHaveAttribute(
      'href',
      '/tenants/1',
    )
    expect(search).toBe('property=1&as_of=2026-07-29')
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

describe('valuation mortgage product history', () => {
  const product = { id: 1, loan: 1, name: 'Original deal', lender: 'Historic Bank', start_date: '2012-08-15', end_date: '2015-01-31', interest_rate: null, rate_type: '', opening_balance: null, notes: '', created_at: '', updated_at: '' }
  const products = [product, { ...product, id: 2, lender: 'Renewal Bank', name: 'Tracker renewal', start_date: '2015-02-01', end_date: null }, { ...product, id: 3, loan: 2, lender: 'Other loan bank', name: 'Unrelated mortgage' }]
  beforeEach(() => {
    server.use(
      http.get('/api/v1/loans/', () => HttpResponse.json([{ id: 1, property: 1, lender: 'Current lender', reference: 'CURRENT-ACCOUNT', currency: 'EUR' }])),
      http.get('/api/v1/property-valuations/', () => HttpResponse.json([
        { id: 1, property: 1, loan: 1, capital_structure_date: '2012-08-15', capital_structure_value: '200000', capital_structure_debt: '100000' },
        { id: 2, property: 1, loan: 1, capital_structure_date: '2015-01-31', capital_structure_value: '200000', capital_structure_debt: '100000' },
        { id: 3, property: 1, loan: 1, capital_structure_date: '2015-02-01', capital_structure_value: '200000', capital_structure_debt: '100000' },
        { id: 4, property: 1, loan: 1, capital_structure_date: '2012-08-14', capital_structure_value: '200000', capital_structure_debt: '100000' },
        { id: 5, property: 1, loan: null, capital_structure_date: '2012-08-13', capital_structure_value: '200000', capital_structure_debt: null },
      ])),
    )
  })
  const row = (id: number) => within(screen.getByRole('button', { name: `Edit valuation ${id}` }).closest('tr')!)
  it('uses the linked loan product on inclusive boundary dates and leaves gaps explicit', async () => {
    let propertyFilter = ''
    server.use(http.get('/api/v1/loan-products/', ({ request }) => {
      propertyFilter = new URL(request.url).searchParams.get('property') ?? ''
      return HttpResponse.json(products)
    }))
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Valuations' }))
    expect(await row(1).findByText('Historic Bank')).toBeInTheDocument()
    expect(row(1).getByText('Original deal')).toBeInTheDocument()
    expect(row(2).getByText('Historic Bank')).toBeInTheDocument()
    expect(row(3).getByText('Renewal Bank')).toBeInTheDocument()
    expect(row(3).getByText('Tracker renewal')).toBeInTheDocument()
    expect(row(4).getByText('Product not recorded')).toBeInTheDocument()
    expect(row(5).queryByText('Product not recorded')).not.toBeInTheDocument()
    expect(screen.queryByText('Other loan bank')).not.toBeInTheDocument()
    expect(screen.queryByText('Current lender')).not.toBeInTheDocument()
    expect(screen.queryByText('CURRENT-ACCOUNT')).not.toBeInTheDocument()
    expect(propertyFilter).toBe('1')
  })
  it('shows fetch failure and supports retry instead of displaying the current lender', async () => {
    server.use(http.get('/api/v1/loan-products/', () => HttpResponse.json({}, { status: 500 })))
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Valuations' }))
    const retry = await row(1).findByRole('button', { name: 'Product unavailable — retry' })
    expect(screen.queryByText('Current lender')).not.toBeInTheDocument()
    server.use(http.get('/api/v1/loan-products/', () => HttpResponse.json(products)))
    await userEvent.click(retry)
    expect(await row(1).findByText('Historic Bank')).toBeInTheDocument()
  })
})
