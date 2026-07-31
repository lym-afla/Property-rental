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
