import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { fixtureUser } from '@/__fixtures__/user'
import { server } from '@/test/handlers'
import { useMe, useLogin, useLogout, useRegister } from './auth'
import { queryKeys } from './keys'
import type { ReactNode } from 'react'

const bob = { ...fixtureUser, id: fixtureUser.id + 1, username: 'bob' }
const aliceAnalyticsKey = queryKeys.analytics.portfolio.summary({
  start: '2026-01-01',
  end: '2026-07-29',
  currency: 'USD',
  grain: 'month',
})

function wrapperFor(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

function seedAliceData(qc: QueryClient) {
  qc.setQueryData(queryKeys.auth.me, fixtureUser)
  qc.setQueryData(
    aliceAnalyticsKey,
    { owner: 'alice', property_value: 500_000 },
  )
  qc.setQueryData(queryKeys.properties.all, [{ id: 1, name: 'Alice house' }])
}

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

  it('removes user A analytics and entity data before exposing user B', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    seedAliceData(qc)
    server.use(
      http.post('/api/v1/auth/login/', () =>
        HttpResponse.json({ user: bob }),
      ),
    )
    const { result } = renderHook(() => useLogin(), {
      wrapper: wrapperFor(qc),
    })

    result.current.mutate({ username: 'bob', password: 'Secret123!' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(qc.getQueryData(queryKeys.auth.me)).toMatchObject({ username: 'bob' })
    expect(qc.getQueryData(aliceAnalyticsKey)).toBeUndefined()
    expect(qc.getQueryData(queryKeys.properties.all)).toBeUndefined()
  })
})

describe('useRegister', () => {
  it('removes prior user data when registration establishes a new session', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    seedAliceData(qc)
    server.use(
      http.post('/api/v1/auth/register/', () =>
        HttpResponse.json({ user: bob }, { status: 201 }),
      ),
    )
    const { result } = renderHook(() => useRegister(), {
      wrapper: wrapperFor(qc),
    })

    result.current.mutate({
      username: 'bob',
      password: 'Secret123!',
      email: 'bob@example.com',
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(qc.getQueryData(queryKeys.auth.me)).toMatchObject({ username: 'bob' })
    expect(qc.getQueryData(aliceAnalyticsKey)).toBeUndefined()
    expect(qc.getQueryData(queryKeys.properties.all)).toBeUndefined()
  })
})

describe('session identity changes', () => {
  it('removes user A data when useMe resolves as user B', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    seedAliceData(qc)
    server.use(
      http.get('/api/v1/auth/me/', () => HttpResponse.json({ user: bob })),
    )

    const { result } = renderHook(() => useMe(), {
      wrapper: wrapperFor(qc),
    })
    await waitFor(() => expect(result.current.data?.username).toBe('bob'))

    expect(qc.getQueryData(aliceAnalyticsKey)).toBeUndefined()
    expect(qc.getQueryData(queryKeys.properties.all)).toBeUndefined()
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
