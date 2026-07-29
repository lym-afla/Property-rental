import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { TenantDetailPage } from './TenantDetailPage'
import { server } from '@/test/handlers'

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
    server.use(
      http.get('/api/v1/analytics/tenants/1/rent-performance/', () =>
        HttpResponse.json({
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
        }),
      ),
    )
    renderPage()
    expect(await screen.findByText('Reporting period: 2024-01-01 to 2024-01-31')).toBeInTheDocument()
  })
})
