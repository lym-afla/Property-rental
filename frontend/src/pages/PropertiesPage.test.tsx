// frontend/src/pages/PropertiesPage.test.tsx
//
// Smoke tests for the Properties list page. The default MSW handlers
// (see `src/test/handlers.ts`) return `fixturePropertiesWithStats`, so the
// happy path resolves without per-test handler registration. The error and
// empty paths override handlers via `server.use(...)` to exercise the
// `ErrorState` and `EmptyState` affordances.
import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'

import { PropertiesPage } from './PropertiesPage'
import { server } from '@/test/handlers'
import { fixturePropertyWithStats } from '@/__fixtures__/property'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PropertiesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PropertiesPage', () => {
  it('renders the page title', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: /properties/i })).toBeInTheDocument()
  })

  it('renders the property rows from the default fixture', async () => {
    renderPage()
    expect(await screen.findByText(fixturePropertyWithStats.name)).toBeInTheDocument()
  })

  it('renders the New Property button', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: /new property/i })).toBeInTheDocument()
  })

  it('renders ErrorState when the with_stats request fails', async () => {
    server.use(
      http.get('/api/v1/properties/with_stats/', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderPage()
    expect(await screen.findByText(/failed to load properties/i)).toBeInTheDocument()
  })

  it('renders EmptyState when the list is empty', async () => {
    server.use(
      http.get('/api/v1/properties/with_stats/', () => HttpResponse.json([])),
    )
    renderPage()
    expect(await screen.findByText(/no properties yet/i)).toBeInTheDocument()
    // The empty state surfaces its own create affordance.
    expect(
      await waitFor(() => screen.getByRole('button', { name: /new property/i })),
    ).toBeInTheDocument()
  })
})
