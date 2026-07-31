// frontend/src/pages/FXPage.test.tsx
//
// Smoke tests for the FX list page. The default MSW handlers return
// `fixtureFXList`, so the happy path resolves without per-test handler
// registration. The error and empty paths override handlers via
// `server.use(...)` to exercise the `ErrorState` and `EmptyState`
// affordances.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'

import { FXPage } from './FXPage'
import { server } from '@/test/handlers'
import { fixtureFX } from '@/__fixtures__/fx'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <FXPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('FXPage', () => {
  it('renders the page title', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: /fx rates/i })).toBeInTheDocument()
  })

  it('renders rows from the default fixture', async () => {
    renderPage()
    // The fixture exposes EUR/USD with rate '1.1000'; assert the table
    // surfaced the rate cell (unique per row) so the column wiring is verified.
    expect(await screen.findByText(fixtureFX.rate)).toBeInTheDocument()
    expect(await screen.findByText(fixtureFX.rate)).toBeInTheDocument()
  })

  it('explains scheduled refresh ownership', async () => {
    renderPage()
    expect(
      await screen.findByText(/scheduled refresh_fx command/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /update fx/i }),
    ).not.toBeInTheDocument()
  })

  it('renders ErrorState when the FX request fails', async () => {
    server.use(
      http.get('/api/v1/fx/', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderPage()
    expect(await screen.findByText(/failed to load fx rates/i)).toBeInTheDocument()
  })

  it('renders EmptyState when the list is empty', async () => {
    server.use(http.get('/api/v1/fx/', () => HttpResponse.json([])))
    renderPage()
    expect(await screen.findByText(/no fx rates yet/i)).toBeInTheDocument()
    expect(
      screen.getByText(/run the refresh_fx management command/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /update fx/i }),
    ).not.toBeInTheDocument()
  })
})
