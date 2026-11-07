// frontend/src/pages/FXPage.test.tsx
//
// Smoke tests for the FX list page. The default MSW handlers return
// `fixtureFXList`, so the happy path resolves without per-test handler
// registration. The error and empty paths override handlers via
// `server.use(...)` to exercise the `ErrorState` and `EmptyState`
// affordances.
import { describe, it, expect } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'

import { FXPage } from './FXPage'
import { server } from '@/test/handlers'
import { fixtureFX } from '@/__fixtures__/fx'

function renderPage(qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
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

const mirrorRow = {
  date: '2026-01-06', from_currency: 'EUR', to_currency: 'RUB', rate: '160.000000000000000000',
  direction: 'RUB per EUR', kind: 'derived', path: ['EUR', 'USD', 'RUB'], sources: ['CBR', 'ECB'],
  observation_date: '2026-01-04', carried_forward: true, provisional: false,
  release_id: 'technical-release-id', snapshot_id: 'snapshot-6', details_token: 'pinned-detail', error: null,
  effective_date: '2026-01-06',
}
const mirrorPage = { backend: 'mirror', status: 'ok', release_id: 'technical-release-id', count: 11, first: '/api/v1/fx/?cursor=signed-first', next: '/api/v1/fx/?cursor=signed-page', results: [mirrorRow] }

it('shows date/source/direction and keeps technical release inside details', async () => {
  const user = (await import('@testing-library/user-event')).default.setup()
  server.use(
    http.get('/api/v1/fx/', () => HttpResponse.json(mirrorPage)),
    http.get('/api/v1/fx/details/', () => HttpResponse.json({ status: 'ok', result: { release_id: 'technical-release-id', snapshot_id: 'snapshot-6', path: ['EUR', 'USD', 'RUB'], observation_ids: ['observation-1'], observation_dates: { EUR: '2026-01-04' }, sources: { EUR: ['ECB'], RUB: ['CBR'] }, policy_id: 'initial-v1' } })),
  )
  renderPage()
  expect(await screen.findByText('RUB per EUR')).toBeInTheDocument()
  expect(screen.getByText('Jan 6, 2026')).toBeInTheDocument()
  expect(screen.getByText('Jan 4, 2026')).toBeInTheDocument()
  expect(screen.getByText('CBR, ECB')).toBeInTheDocument()
  expect(screen.getByText('Derived')).toBeInTheDocument()
  expect(screen.getByText('Carried forward')).toBeInTheDocument()
  expect(screen.queryByText('technical-release-id')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /details/i }))
  expect(await screen.findByText('technical-release-id')).toBeInTheDocument()
  expect(screen.getByText('EUR → USD → RUB')).toBeInTheDocument()
  expect(screen.getByText('observation-1')).toBeInTheDocument()
})

it('follows the pinned next page and clearly handles unavailable details', async () => {
  const user = (await import('@testing-library/user-event')).default.setup()
  server.use(
    http.get('/api/v1/fx/', ({ request }) => HttpResponse.json(new URL(request.url).searchParams.get('cursor') === 'signed-page' ? { ...mirrorPage, next: null, results: [{ ...mirrorRow, date: '2026-01-05' }] } : mirrorPage)),
    http.get('/api/v1/fx/details/', () => HttpResponse.json({ code: 'fx_details_unavailable' }, { status: 503 })),
  )
  renderPage()
  await screen.findByText('RUB per EUR')
  await user.click(screen.getByRole('button', { name: /next/i }))
  expect(await screen.findByText('Jan 5, 2026')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /details/i }))
  expect(await screen.findByText(/provenance is temporarily unavailable/i)).toBeInTheDocument()
  expect(screen.getByText('160.000000000000000000')).toBeInTheDocument()
})

it.each(['unsynced', 'empty'])('explains the mirror %s state', async (status) => {
  server.use(http.get('/api/v1/fx/', () => HttpResponse.json({ ...mirrorPage, status, results: [], count: 0, next: null })))
  renderPage()
  expect(await screen.findByText(status === 'unsynced' ? /shared rates have not synced yet/i : /no shared rates in this range/i)).toBeInTheDocument()
})

it('shows missing FX and provisional values honestly', async () => {
  server.use(http.get('/api/v1/fx/', () => HttpResponse.json({ ...mirrorPage, results: [{ ...mirrorRow, rate: null, error: 'before_coverage', details_token: null, provisional: true }] })))
  renderPage()
  expect(await screen.findByText(/rate unavailable.*before coverage/i)).toBeInTheDocument()
  expect(screen.getByText('Provisional')).toBeInTheDocument()
})

function productionClient() {
  return new QueryClient({ defaultOptions: { queries: {
    retry: 1, refetchOnWindowFocus: true, staleTime: 60_000,
  } } })
}

function pinnedSessionServer() {
  let promoted = false
  let initialReads = 0
  const old = { ...mirrorPage, first: '/api/v1/fx/?cursor=signed-first' }
  const fresh = { ...old, release_id: 'new', first: '/api/v1/fx/?cursor=new-first', results: [{ ...mirrorRow, rate: '170.000000000000000000' }] }
  server.use(http.get('/api/v1/fx/', ({ request }) => {
    const cursor = new URL(request.url).searchParams.get('cursor')
    if (cursor === 'signed-first') return HttpResponse.json(old)
    if (cursor === 'signed-page') return HttpResponse.json({ ...old, next: null, results: [{ ...mirrorRow, date: '2026-01-05' }] })
    if (cursor === 'new-first') return HttpResponse.json(fresh)
    initialReads += 1
    return HttpResponse.json(promoted ? fresh : old)
  }))
  return { promote: () => { promoted = true }, initialReads: () => initialReads }
}

it('keeps the first page pinned through stale focus and a Previous after cache eviction', async () => {
  const user = (await import('@testing-library/user-event')).default.setup()
  const service = pinnedSessionServer()
  const qc = productionClient()
  renderPage(qc)
  expect(await screen.findByText('160.000000000000000000')).toBeInTheDocument()
  service.promote()
  await act(async () => {
    for (const query of qc.getQueryCache().getAll()) {
      if (query.state.data) qc.setQueryData(query.queryKey, query.state.data, { updatedAt: Date.now() - 61_000 })
    }
    focusManager.setFocused(false)
    focusManager.setFocused(true)
  })
  expect(screen.queryByText('170.000000000000000000')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await screen.findByText('Jan 5, 2026')
  // An inactive signed first page can be reconstructed even after normal GC.
  qc.removeQueries({ predicate: (query) => query.getObserversCount() === 0 })
  await user.click(screen.getByRole('button', { name: 'Previous' }))
  expect(await screen.findByText('Jan 6, 2026')).toBeInTheDocument()
  expect(screen.getByText('160.000000000000000000')).toBeInTheDocument()
  expect(service.initialReads()).toBe(1)
  qc.clear()
})

it('one explicit Refresh range from a later fresh page fetches the current release', async () => {
  const user = (await import('@testing-library/user-event')).default.setup()
  const service = pinnedSessionServer()
  const qc = productionClient()
  renderPage(qc)
  await screen.findByText('160.000000000000000000')
  await user.click(screen.getByRole('button', { name: 'Next' }))
  await screen.findByText('Jan 5, 2026')
  service.promote()
  await user.click(screen.getByRole('button', { name: 'Refresh range' }))
  expect(await screen.findByText('170.000000000000000000')).toBeInTheDocument()
  await waitFor(() => expect(service.initialReads()).toBe(2))
  qc.clear()
})
