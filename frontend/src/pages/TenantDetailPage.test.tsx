import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TenantDetailPage } from './TenantDetailPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/tenants/1']}>
        <TenantDetailPage />
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
})
