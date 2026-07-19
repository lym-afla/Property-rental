import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useMe, useLogin, useLogout } from './auth'
import type { ReactNode } from 'react'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

describe('useMe', () => {
  it('returns the user when authenticated', async () => {
    const { result } = renderHook(() => useMe(), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.username).toBe('alice')
  })
})

describe('useLogin', () => {
  it('logs in and updates the cache', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useLogin(), { wrapper })
    result.current.mutate({ username: 'alice', password: 'TestPass123!' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(qc.getQueryData(['auth', 'me'])).toMatchObject({ username: 'alice' })
  })
})

describe('useLogout', () => {
  it('clears the cache', async () => {
    const qc = new QueryClient()
    qc.setQueryData(['auth', 'me'], { username: 'alice' })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useLogout(), { wrapper })
    // useLogout's mutationFn takes void; mutate() with no args.
    result.current.mutate()
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // useLogout's onSettled calls `setQueryData(['auth','me'], null)` THEN
    // `qc.clear()` (Task 7 wipes the whole cache so stale data doesn't leak
    // between users). After `clear()`, getQueryData returns `undefined`
    // (key absent) — not `null`. The brief's literal `toBeNull()` would
    // fail against that implementation, so we assert undefined here.
    expect(qc.getQueryData(['auth', 'me'])).toBeUndefined()
  })
})
