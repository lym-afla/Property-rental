import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { TenantDetailPage } from './TenantDetailPage'
import { server } from '@/test/handlers'

vi.mock('@/context/SessionProvider', () => ({
  useSession: () => ({
    user: { effective_date: '2024-01-31' },
    isLoading: false,
  }),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/tenants/1']}>
        <Routes>
          <Route path="/tenants/:id" element={<TenantDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TenantDetailPage (smoke)', () => {
  it('renders without crashing', () => {
    // The page shows a loading skeleton initially; just verify no throw.
    const { container } = renderPage()
    expect(container).toBeTruthy()
  })

  it('uses the typed rent-performance endpoint for the detail chart', async () => {
    let requestedEnd: string | null = null
    let requestedCurrency: string | null = null
    server.use(
      http.get('/api/v1/analytics/tenants/1/rent-performance/', ({ request }) => {
        requestedEnd = new URL(request.url).searchParams.get('end')
        requestedCurrency = new URL(request.url).searchParams.get('currency')
        return HttpResponse.json({
          metric: 'tenant_rent_performance', grain: 'month', currency: 'EUR', scale: 1,
          start: '2024-01-01', end: '2024-01-31', opening_arrears: 0,
          opening_issues: [], status: 'ok', issues: [],
          series: [
            { key: 'expected', label: 'Expected rent', kind: 'expected' },
            { key: 'received', label: 'Received rent', kind: 'received' },
            { key: 'variance', label: 'Variance', kind: 'variance' },
            { key: 'cumulative_arrears', label: 'Cumulative arrears', kind: 'cumulative' },
          ],
          points: [{
            period_start: '2024-01-01', period_end: '2024-01-31', expected: 800,
            received: 800, variance: 0, cumulative_arrears: 0, status: 'ok', issues: [],
          }],
        })
      }),
    )
    renderPage()
    expect(await screen.findByText('Native currency: EUR · Reporting period: 2024-01-01 to 2024-01-31')).toBeInTheDocument()
    expect(requestedEnd).toBe('2024-01-31')
    expect(requestedCurrency).toBeNull()
    expect(screen.queryByText(/Server-calculated rent, revenue, and debt/)).not.toBeInTheDocument()
    expect(screen.queryByText('Net income (all-time)')).not.toBeInTheDocument()
  })

  it('omits the literal null from the header when the tenant has no last name', async () => {
    server.use(
      http.get('/api/v1/tenants/1/', () =>
        HttpResponse.json({
          id: 1,
          user: null,
          property: 1,
          first_name: 'Газимагомед',
          last_name: null,
          phone: '',
          email: null,
          lease_start: '2021-04-01',
          lease_end: '2025-04-30',
          payday: 1,
        }),
      ),
      http.get('/api/v1/tenants/with_stats/', () =>
        HttpResponse.json([
          {
            id: 1,
            user: null,
            property: 1,
            first_name: 'Газимагомед',
            last_name: null,
            phone: '',
            email: null,
            lease_start: '2021-04-01',
            lease_end: '2025-04-30',
            payday: 1,
            rent_rate: '65000.00',
            revenue_all_time: 0,
            revenue_ytd: 0,
            debt: 0,
            stats_currency: 'RUB',
          },
        ]),
      ),
      http.get('/api/v1/analytics/tenants/1/rent-performance/', () =>
        HttpResponse.json({
          metric: 'tenant_rent_performance', grain: 'month', currency: 'RUB', scale: 1,
          start: '2024-01-01', end: '2024-01-31', opening_arrears: 0,
          opening_issues: [], status: 'ok', issues: [],
          series: [
            { key: 'expected', label: 'Expected rent', kind: 'expected' },
            { key: 'received', label: 'Received rent', kind: 'received' },
            { key: 'variance', label: 'Variance', kind: 'variance' },
            { key: 'cumulative_arrears', label: 'Cumulative arrears', kind: 'cumulative' },
          ],
          points: [{
            period_start: '2024-01-01', period_end: '2024-01-31', expected: 0,
            received: 0, variance: 0, cumulative_arrears: 0, status: 'ok', issues: [],
          }],
        }),
      ),
    )

    renderPage()

    expect(await screen.findByText('Газимагомед')).toBeInTheDocument()
    expect(screen.queryByText('Газимагомед null')).not.toBeInTheDocument()
  })
})
