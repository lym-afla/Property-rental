// Task 13 — React Query hook tests for tenants.
//
// Covers query hooks (`useTenants`, `useTenant`, `useTenantsWithStats`) and
// mutation hooks (`useCreateTenant`, `useUpdateTenant`, `useDeleteTenant`,
// `useVacateTenant`). Every mutation asserts both endpoint success AND the
// cascade invalidation. Invalidation targets `tenants.all` — the parent
// prefix that TanStack Query matches against every `tenants.*` key,
// including the `tenants.withStats(...)` variants the detail page uses.
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import {
  useTenants,
  useTenant,
  useTenantsWithStats,
  useCreateTenant,
  useUpdateTenant,
  useDeleteTenant,
  useVacateTenant,
} from './tenants'
import { queryKeys } from './keys'
import { fixtureTenant, fixtureTenantAlt } from '@/__fixtures__/tenant'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

function makeWrapperWithClient(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

describe('useTenants', () => {
  it('returns the tenant list', async () => {
    const { result } = renderHook(() => useTenants(), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.length).toBe(2)
    expect(result.current.data?.[0].id).toBe(fixtureTenant.id)
  })
})

describe('useTenant', () => {
  it('returns a single tenant by id', async () => {
    const { result } = renderHook(() => useTenant(fixtureTenantAlt.id), {
      wrapper: makeWrapper(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.first_name).toBe(fixtureTenantAlt.first_name)
  })
})

describe('useTenantsWithStats', () => {
  it('returns tenants with stats', async () => {
    const { result } = renderHook(() => useTenantsWithStats(), {
      wrapper: makeWrapper(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.[0].rent_rate).toBeDefined()
  })
})

describe('useCreateTenant', () => {
  it('POSTs and invalidates cascade keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useCreateTenant(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({ first_name: 'Dan', last_name: 'Lee', property: 1 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.id).toBe(999)
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.tenants.all,
    })
  })
})

describe('useUpdateTenant', () => {
  it('PATCHes and invalidates cascade keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useUpdateTenant(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({ id: fixtureTenant.id, data: { first_name: 'Renamed' } })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.first_name).toBe('Renamed')
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.tenants.all,
    })
  })
})

describe('useDeleteTenant', () => {
  it('DELETEs and invalidates cascade keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useDeleteTenant(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate(fixtureTenant.id)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.tenants.all,
    })
  })
})

describe('useVacateTenant', () => {
  it('POSTs to /vacate/ and invalidates cascade keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useVacateTenant(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({ id: fixtureTenant.id, leaseEnd: '2025-12-31' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // `TenantViewSet.vacate` returns `Response(TenantSerializer(tenant).data)`
    // — a full Tenant, not a `{detail, lease_end}` envelope. Assert the
    // tenant identity + the server-applied `lease_end`.
    expect(result.current.data?.id).toBe(fixtureTenant.id)
    expect(result.current.data?.lease_end).toBe('2025-12-31')
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.tenants.all,
    })
  })
})
