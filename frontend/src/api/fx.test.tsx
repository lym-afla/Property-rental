// Task 13 — React Query hook tests for FX.
//
// Covers the read-only `useFX` query hook. Production FX acquisition is
// performed by the scheduled `refresh_fx` management command, so this module
// intentionally exposes no browser-triggered mutation hooks.
import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { useFX } from './fx'
import { fixtureFX } from '@/__fixtures__/fx'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

describe('useFX', () => {
  it('returns the FX list', async () => {
    const { result } = renderHook(() => useFX(), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.length).toBe(2)
    expect(result.current.data?.[0].id).toBe(fixtureFX.id)
  })
})

it('sends bounded pair/date filters and retains the mirror envelope', async () => {
  const { http, HttpResponse } = await import('msw')
  const { server } = await import('@/test/handlers')
  server.use(http.get('/api/v1/fx/', ({ request }) => {
    const url = new URL(request.url)
    const valid = url.searchParams.get('base') === 'EUR' && url.searchParams.get('quote') === 'RUB' && url.searchParams.get('start') === '2026-01-01' && url.searchParams.get('end') === '2026-01-31'
    return HttpResponse.json({ backend: 'mirror', status: 'ok', release_id: 'pinned', count: valid ? 31 : 0, first: '/api/v1/fx/?cursor=pinned-first', next: null, results: [] })
  }))
  const { result } = renderHook(() => useFX({ base: 'EUR', quote: 'RUB', start: '2026-01-01', end: '2026-01-31' }), { wrapper: makeWrapper() })
  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(result.current.data).toMatchObject({ backend: 'mirror', release_id: 'pinned', count: 31 })
})
