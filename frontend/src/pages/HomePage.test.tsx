import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { fixtureUser } from '@/__fixtures__/user'
import { server } from '@/test/handlers'
import { HomePage } from './HomePage'

vi.mock('@/context/SessionProvider', () => ({
  useSession: () => ({
    user: {
      ...fixtureUser,
      effective_date: '2026-07-29',
      default_currency: 'USD',
      chart_frequency: 'M',
      chart_timeline: '6m',
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
  usePropertiesWithStats: () => ({
    data: [],
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
}))

vi.mock('@/api/tenants', () => ({
  useTenantsWithStats: () => ({
    data: [],
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
}))

vi.mock('@/api/charts', () => ({
  useChartData: () => ({ data: { labels: [], datasets: [], currency: 'USD' } }),
}))

vi.mock('@/components/charts/CashFlowChart', () => ({ CashFlowChart: () => <div>Legacy cash flow chart</div> }))
vi.mock('@/components/charts/ExpenseBreakdownChart', () => ({ ExpenseBreakdownChart: () => <div>Legacy expense chart</div> }))
vi.mock('@/components/charts/NetIncomeTrendChart', () => ({ NetIncomeTrendChart: () => <div>Legacy income chart</div> }))
vi.mock('@/components/charts/OccupancyChart', () => ({ OccupancyChart: () => <div>Legacy occupancy chart</div> }))
vi.mock('@/components/charts/CurrencyExposureChart', () => ({ CurrencyExposureChart: () => <div>Legacy exposure chart</div> }))

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
  it('restores a copied section/filter URL, requests validated summary data, and retains legacy charts', async () => {
    let requestedUrl = ''
    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', ({ request }) => {
        requestedUrl = request.url
        return HttpResponse.json(summary)
      }),
    )

    renderPage('/?section=portfolio&start=2026-01-01&end=2026-07-29&currency=GBP&grain=quarter&comparison=previous_period&property=3&property=1&measure=debt')

    expect(screen.getByRole('heading', { name: 'Portfolio analysis' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Portfolio' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('Legacy cash flow chart')).toBeInTheDocument()

    expect(await screen.findByText('£1,000,000')).toBeInTheDocument()
    expect(screen.getByText('£350,000')).toBeInTheDocument()
    expect(screen.getByText('£650,000')).toBeInTheDocument()
    expect(screen.getByText('£80,000')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()

    const requested = new URL(requestedUrl)
    expect(requested.searchParams.get('comparison')).toBeNull()
    expect(requested.searchParams.getAll('property')).toEqual(['1', '3'])
    expect(requested.searchParams.get('grain')).toBe('quarter')
  })

  it('updates section and filters only through the router URL and resets to session defaults', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', () => HttpResponse.json(summary)),
    )
    renderPage('/?section=risk&start=2026-01-01&end=2026-07-29&currency=GBP&grain=year&comparison=none&property=&measure=property_value')

    await user.click(screen.getByRole('button', { name: 'Income & Costs' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Current dashboard URL')).toHaveTextContent('section=income-costs')
    })

    await user.click(screen.getByRole('button', { name: 'Reset dashboard filters' }))
    const resetUrl = screen.getByLabelText('Current dashboard URL').textContent ?? ''
    const reset = new URLSearchParams(resetUrl)
    expect(reset.get('section')).toBe('overview')
    expect(reset.get('end')).toBe('2026-07-29')
    expect(reset.get('currency')).toBe('USD')
    expect(reset.get('grain')).toBe('month')
    expect(reset.get('comparison')).toBe('none')
  })

  it('distinguishes summary loading, error, and empty states', async () => {
    server.use(
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
})
