import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import { fixtureUser } from '@/__fixtures__/user'
import { server } from '@/test/handlers'
import { HomePage } from './HomePage'

let savedChartTimeline = '6m'
let savedChartFrequency = 'M'

afterEach(() => {
  savedChartTimeline = '6m'
  savedChartFrequency = 'M'
})

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  }
})

vi.mock('@/context/SessionProvider', () => ({
  useSession: () => ({
    user: {
      ...fixtureUser,
      effective_date: '2026-07-29',
      default_currency: 'USD',
      chart_frequency: savedChartFrequency,
      chart_timeline: savedChartTimeline,
    },
    isLoading: false,
  }),
}))

vi.mock('@/api/properties', () => ({
  useProperties: () => ({
    data: [
      { id: 1, name: 'Birch House' },
      { id: 3, name: 'Canal Court' },
    ],
    isLoading: false,
    isError: false,
  }),
}))

const summary = {
  currency: 'GBP',
  scale: 1,
  start: '2026-01-01',
  end: '2026-07-29',
  property_count: 2,
  rental_inventory_count: 2,
  occupied: 1,
  occupancy_rate: 50,
  revenue: 125000,
  costs: 45000,
  net_income: 80000,
  property_value: 1000000,
  debt: 350000,
  equity: 650000,
  valuation_status: 'ok',
  property_value_status: 'ok',
  debt_status: 'ok',
} as const

const cashFlow = {
  metric: 'portfolio_cash_flow', grain: 'month', currency: 'USD', scale: 1,
  start: '2026-01-01', end: '2026-07-29',
  series: [
    { key: 'rent', label: 'Rent', kind: 'income_category' },
    { key: 'utilities', label: 'Utilities', kind: 'expense_category' },
    { key: 'total_income', label: 'Total income', kind: 'income_total' },
    { key: 'total_expenses', label: 'Total expenses', kind: 'expense_total' },
    { key: 'net_income', label: 'Net income', kind: 'net' },
    { key: 'cumulative_net_income', label: 'Cumulative net income', kind: 'cumulative' },
  ],
  points: [{ period_start: '2026-01-01', period_end: '2026-01-31', rent: 1500, utilities: -250, total_income: 1500, total_expenses: -250, net_income: 1250, cumulative_net_income: 1250 }],
} as const

const expenses = { ...cashFlow, metric: 'expense_drivers', series: [{ key: 'utilities', label: 'Utilities', kind: 'expense_category' }], points: [{ period_start: '2026-01-01', period_end: '2026-01-31', utilities: -250 }] } as const

const propertyBreakdown = {
  metric: 'property_breakdown', grain: 'month', currency: 'USD', scale: 1,
  start: '2026-01-01', end: '2026-07-29', measure: 'property_value', measure_label: 'Property value',
  series: [{ key: 'property_1', label: 'Anokhina', kind: 'property' }],
  points: [{ period_start: '2026-01-01', period_end: '2026-01-31', property_1: 1000 }],
  coverage: [{ period_start: '2026-01-01', period_end: '2026-01-31', property_id: 1, status: 'ok' }],
} as const

const profitLoss = {
  metric: 'profit_and_loss', currency: 'USD', scale: 1, end: '2026-07-29',
  columns: [
    { key: '2025', label: '2025', start: '2025-01-01', end: '2025-12-31' },
    { key: '2026', label: '2026', start: '2026-01-01', end: '2026-07-29' },
    { key: 'ytd', label: 'YTD', start: '2026-01-01', end: '2026-07-29' },
  ],
  rows: [
    { key: 'rent', label: 'Rent', kind: 'income', values: { '2025': 12000, '2026': 7000, ytd: 7000 } },
    { key: 'total_revenue', label: 'Total revenue', kind: 'total_revenue', values: { '2025': 12000, '2026': 7000, ytd: 7000 } },
    { key: 'total_expenses', label: 'Total expenses', kind: 'total_expenses', values: { '2025': 0, '2026': 0, ytd: 0 } },
    { key: 'net_income', label: 'Net income', kind: 'net_income', values: { '2025': 12000, '2026': 7000, ytd: 7000 } },
  ],
} as const

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="Current dashboard URL">{location.search}</output>
}

function renderPage(initialEntry = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <HomePage />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('HomePage dashboard shell', () => {
  it('keeps a scoped annual and YTD P&L visible below Income & Costs charts', async () => {
    let pnlSearch = ''
    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', () => HttpResponse.json(summary)),
      http.get('/api/v1/analytics/portfolio/cash-flow/', () => HttpResponse.json(cashFlow)),
      http.get('/api/v1/analytics/portfolio/expenses/', () => HttpResponse.json(expenses)),
      http.get('/api/v1/analytics/portfolio/profit-loss/', ({ request }) => {
        pnlSearch = new URL(request.url).searchParams.toString()
        return HttpResponse.json(profitLoss)
      }),
    )

    renderPage('/?section=income-costs&start=2026-04-01&end=2026-07-29&currency=USD&grain=month&property=3&property=1&measure=property_value')

    expect(await screen.findByRole('table', { name: 'Profit and Loss statement' })).toBeVisible()
    expect(screen.getByText('Revenue and expenses')).toBeVisible()
    expect(screen.getByText('Expense drivers')).toBeVisible()
    expect(screen.getByText('2025')).toBeVisible()
    expect(screen.getByText('YTD')).toBeVisible()
    expect(pnlSearch).toBe('end=2026-07-29&currency=USD&property=1&property=3')
  })

  it('normalizes a saved all-history monthly dashboard to a bounded request grain', async () => {
    savedChartTimeline = 'All'
    savedChartFrequency = 'M'
    const requestedQueries: URLSearchParams[] = []
    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', ({ request }) => {
        requestedQueries.push(new URL(request.url).searchParams)
        return HttpResponse.json(summary)
      }),
      http.get('/api/v1/analytics/portfolio/cash-flow/', ({ request }) => {
        requestedQueries.push(new URL(request.url).searchParams)
        return HttpResponse.json({ ...cashFlow, grain: 'year', start: '1900-01-01' })
      }),
    )

    const page = renderPage()

    expect(await screen.findByText('Portfolio value')).toBeInTheDocument()
    await waitFor(() => expect(requestedQueries).toHaveLength(2))
    expect(requestedQueries.map((query) => [query.get('start'), query.get('grain')])).toEqual([
      ['1900-01-01', 'year'],
      ['1900-01-01', 'year'],
    ])
    page.unmount()
  })

  it('restores a copied URL and requests only overview analytics for every selected property', async () => {
    const user = userEvent.setup()
    let requestedUrl = ''
    let cashFlowRequests = 0
    let irrelevantRequests = 0
    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json(summary)
      }),
      http.get('/api/v1/analytics/portfolio/cash-flow/', () => {
        cashFlowRequests += 1
        return HttpResponse.json(cashFlow)
      }),
      http.get('/api/v1/analytics/portfolio/expenses/', () => {
        irrelevantRequests += 1
        return HttpResponse.json(expenses)
      }),
      http.get('/api/v1/analytics/portfolio/property-contribution/', () => {
        irrelevantRequests += 1
        return HttpResponse.json({})
      }),
      http.get('/api/v1/analytics/portfolio/yields/', () => {
        irrelevantRequests += 1
        return HttpResponse.json({})
      }),
      http.get('/api/v1/analytics/portfolio/property-breakdown/', () => {
        irrelevantRequests += 1
        return HttpResponse.json(propertyBreakdown)
      }),
      http.get('/api/v1/analytics/portfolio/occupancy/', () => {
        irrelevantRequests += 1
        return HttpResponse.json({})
      }),
    )

    renderPage('/?section=overview&start=2026-01-01&end=2026-07-29&currency=GBP&grain=quarter&comparison=previous_period&property=3&property=1&measure=debt')

    expect(screen.getByRole('heading', { name: 'Investment dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByText('Net cash flow')).toBeInTheDocument()
    expect(screen.queryByText('Portfolio breakdown by property')).not.toBeInTheDocument()

    expect(await screen.findByText('£1,000,000')).toBeInTheDocument()
    expect(screen.getByText('£350,000')).toBeInTheDocument()
    expect(screen.getByText('£650,000')).toBeInTheDocument()
    expect(screen.getByText('£80,000')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()

    const requested = new URL(requestedUrl)
    expect(requested.searchParams.get('comparison')).toBeNull()
    expect(requested.searchParams.getAll('property')).toEqual(['1', '3'])
    expect(requested.searchParams.get('grain')).toBe('quarter')
    expect(cashFlowRequests).toBe(1)
    expect(irrelevantRequests).toBe(0)

    await user.click(screen.getByText('Drill down to transactions'))
    await user.click(screen.getByRole('button', { name: 'View Rent transactions for Jan 1, 2026' }))
    expect(screen.getByLabelText('Current dashboard URL')).toHaveTextContent(
      'from=2026-01-01&to=2026-01-31&category=rent&currency=USD&property=1&property=3',
    )
  })

  it('updates router URL and analytics request from filter interactions, then fully serializes reset defaults', async () => {
    const user = userEvent.setup()
    const requestedUrls: string[] = []
    const breakdownUrls: string[] = []
    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', ({ request }) => {
        requestedUrls.push(request.url)
        return HttpResponse.json(summary)
      }),
      http.get('/api/v1/analytics/portfolio/cash-flow/', () => HttpResponse.json(cashFlow)),
      http.get('/api/v1/analytics/portfolio/expenses/', () => HttpResponse.json(expenses)),
      http.get('/api/v1/analytics/portfolio/profit-loss/', () => HttpResponse.json(profitLoss)),
      http.get('/api/v1/analytics/portfolio/property-breakdown/', ({ request }) => {
        breakdownUrls.push(request.url)
        return HttpResponse.json(propertyBreakdown)
      }),
    )
    renderPage('/?section=portfolio&start=2026-01-01&end=2026-07-29&currency=GBP&grain=year&property=&measure=property_value')

    expect(screen.getByText('Portfolio breakdown by property')).toBeInTheDocument()
    expect(screen.queryByText('Occupancy risk')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Portfolio breakdown measure'), 'debt')
    await waitFor(() => {
      const currentUrl = screen.getByLabelText('Current dashboard URL').textContent ?? ''
      expect(new URLSearchParams(currentUrl).get('measure')).toBe('debt')
      expect(new URL(breakdownUrls.at(-1) ?? 'http://invalid').searchParams.get('measure')).toBe('debt')
    })

    await user.click(screen.getByRole('button', { name: 'Income & Costs' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Current dashboard URL')).toHaveTextContent('section=income-costs')
    })

    await user.click(screen.getByRole('button', { name: 'Show settings' }))
    await user.click(screen.getByLabelText('Reporting currency'))
    await user.click(screen.getByRole('option', { name: 'EUR' }))
    await waitFor(() => {
      const currentUrl = screen.getByLabelText('Current dashboard URL').textContent ?? ''
      expect(new URLSearchParams(currentUrl).get('currency')).toBe('EUR')
      expect(new URL(requestedUrls.at(-1) ?? 'http://invalid').searchParams.get('currency')).toBe('EUR')
    })

    await user.click(screen.getByRole('button', { name: 'Reset dashboard filters' }))
    const resetUrl = screen.getByLabelText('Current dashboard URL').textContent ?? ''
    expect(resetUrl).toBe(
      '?section=overview&start=2026-01-29&end=2026-07-29&currency=USD&grain=month&property=&measure=property_value',
    )
  })

  it('distinguishes summary loading, error, and empty states', async () => {
    server.use(
      http.get('/api/v1/analytics/portfolio/cash-flow/', () => HttpResponse.json(cashFlow)),
      http.get('/api/v1/analytics/portfolio/expenses/', () => HttpResponse.json(expenses)),
      http.get('/api/v1/analytics/portfolio/summary/', async () => {
        await delay('infinite')
        return HttpResponse.json(summary)
      }),
    )
    const loadingPage = renderPage('/?section=overview&start=2026-01-01&end=2026-07-29&currency=USD&grain=month&comparison=none&property=&measure=property_value')
    expect(screen.getByLabelText('Loading portfolio summary')).toBeInTheDocument()
    loadingPage.unmount()

    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', () => new HttpResponse(null, { status: 500 })),
    )
    const { unmount } = renderPage('/?section=overview&start=2026-01-01&end=2026-07-29&currency=USD&grain=month&comparison=none&property=&measure=property_value')
    expect(await screen.findByText('Failed to load portfolio summary')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Retry' }).at(0)).toHaveClass('min-h-11')
    unmount()

    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', () =>
        HttpResponse.json({
          ...summary,
          currency: 'USD',
          property_count: 0,
          rental_inventory_count: 0,
          occupied: 0,
          occupancy_rate: 0,
          revenue: 0,
          costs: 0,
          net_income: 0,
          property_value: null,
          debt: null,
          equity: null,
          valuation_status: 'missing_valuation',
          property_value_status: 'missing_valuation',
          debt_status: 'missing_valuation',
        }),
      ),
    )
    renderPage('/?section=overview&start=2026-01-01&end=2026-07-29&currency=USD&grain=month&comparison=none&property=&measure=property_value')
    expect(await screen.findByText('No portfolio data for this selection.')).toBeInTheDocument()
  })

  it('formats occupancy to one decimal place', async () => {
    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', () =>
        HttpResponse.json({ ...summary, occupancy_rate: 50.123456 }),
      ),
    )
    renderPage('/?section=overview&start=2026-01-01&end=2026-07-29&currency=GBP&grain=month&comparison=none&property=&measure=property_value')
    expect(await screen.findByText('50.1%')).toBeInTheDocument()
    expect(screen.queryByText('50.123456%')).not.toBeInTheDocument()
  })
})
