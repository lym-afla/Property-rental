import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

import { fixtureUser } from '@/__fixtures__/user'
import { server } from '@/test/handlers'
import { HomePage } from './HomePage'

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
}))

vi.mock('@/api/charts', () => ({
  useChartData: () => ({ data: { labels: [], datasets: [], currency: 'USD' } }),
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
  it('restores a copied section/filter URL without rendering independently filtered legacy consumers', async () => {
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
    expect(screen.getByText('Property-scoped chart migration pending')).toBeInTheDocument()
    expect(screen.queryByText('Cash Flow')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Currency exposure timeline')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Expense timeline')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Net income timeline')).not.toBeInTheDocument()

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

  it('updates router URL and analytics request from filter interactions, then fully serializes reset defaults', async () => {
    const user = userEvent.setup()
    const requestedUrls: string[] = []
    server.use(
      http.get('/api/v1/analytics/portfolio/summary/', ({ request }) => {
        requestedUrls.push(request.url)
        return HttpResponse.json(summary)
      }),
    )
    renderPage('/?section=risk&start=2026-01-01&end=2026-07-29&currency=GBP&grain=year&comparison=none&property=&measure=property_value')

    expect(screen.getByText('Currency exposure migration pending')).toBeInTheDocument()
    expect(screen.getByText('Occupancy migration pending')).toBeInTheDocument()
    expect(screen.getByText('Profit & Loss migration pending')).toBeInTheDocument()
    expect(screen.queryByText('Profit & Loss')).not.toBeInTheDocument()
    for (const toggle of screen.getAllByRole('button', { name: 'Table' })) {
      expect(toggle).toHaveClass('min-h-11')
    }

    await user.click(screen.getByRole('button', { name: 'Income & Costs' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Current dashboard URL')).toHaveTextContent('section=income-costs')
    })

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
      '?section=overview&start=2026-01-29&end=2026-07-29&currency=USD&grain=month&comparison=none&property=&measure=property_value',
    )
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
    expect(screen.getByRole('button', { name: 'Retry' })).toHaveClass('min-h-11')
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
