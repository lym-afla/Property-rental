// Task 13 — React Query hook tests for properties.
//
// Covers every exported hook in `properties.ts`:
//   - Query hooks (`useProperties`, `useProperty`, `usePropertiesWithStats`)
//     return data from the MSW default handlers.
//   - Mutation hooks (`useCreateProperty`, `useUpdateProperty`,
//     `useDeleteProperty`) call the right endpoint AND invalidate the
//     cascade keys (`properties.all` + `properties.withStats()`). The
//     with-stats key is now a factory (so the cache can hold multiple
//     variants keyed by `asOf`/`currency`); invalidation passes the
//     factory's no-arg form, which is a prefix that matches every
//     with-stats variant.
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import {
  useProperties,
  useProperty,
  usePropertiesWithStats,
  useCreateProperty,
  useUpdateProperty,
  useDeleteProperty,
} from './properties'
import { queryKeys } from './keys'
import { fixtureProperty, fixturePropertyAlt } from '@/__fixtures__/property'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

// Helper that exposes the QueryClient used inside a renderHook wrapper so
// we can spy on `invalidateQueries`. Mutations instantiate their own client
// via `useQueryClient`, so we need to inject a client whose invalidation
// we can observe.
function makeWrapperWithClient(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

describe('useProperties', () => {
  it('returns the property list', async () => {
    const { result } = renderHook(() => useProperties(), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.length).toBe(2)
    expect(result.current.data?.[0].id).toBe(fixtureProperty.id)
  })
})

describe('useProperty', () => {
  it('returns a single property by id', async () => {
    const { result } = renderHook(() => useProperty(fixturePropertyAlt.id), {
      wrapper: makeWrapper(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.name).toBe(fixturePropertyAlt.name)
  })
})

describe('usePropertiesWithStats', () => {
  it('returns properties with stats', async () => {
    const { result } = renderHook(() => usePropertiesWithStats(), {
      wrapper: makeWrapper(),
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.[0].net_income_all_time).toBeDefined()
  })
})

describe('useCreateProperty', () => {
  it('POSTs and invalidates properties + withStats keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useCreateProperty(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({ name: 'New Place', location: 'Hamburg' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Response merges the new body with the fixture shape.
    expect(result.current.data?.id).toBe(999)
    expect(result.current.data?.name).toBe('New Place')

    // Invalidation cascade.
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.properties.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.properties.withStats(),
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.analytics.all,
    })
  })
})

describe('useUpdateProperty', () => {
  it('PATCHes and invalidates cascade keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useUpdateProperty(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({ id: fixtureProperty.id, data: { name: 'Renamed' } })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.name).toBe('Renamed')
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.properties.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.properties.withStats(),
    })
  })
})

describe('useDeleteProperty', () => {
  it('DELETEs and invalidates cascade keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useDeleteProperty(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate(fixtureProperty.id)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.properties.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.properties.withStats(),
    })
  })
})

// Sanity: confirm that a query observer actually refetches after a mutation
// invalidates its key. This guards against a future refactor that calls
// `setQueryData` instead of `invalidateQueries` (which would silently break
// the cascade behavior the spec requires).
describe('cascade invalidation actually refetches', () => {
  it('refetches useProperties after a create', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = makeWrapperWithClient(qc)

    // Prime the cache and count fetches.
    let fetchCount = 0
    const { result: queryResult } = renderHook(
      () =>
        useQuery({
          queryKey: queryKeys.properties.all,
          queryFn: () => {
            fetchCount += 1
            // Delegate to the same apiFetch path the real hook uses.
            return import('./client').then(({ apiFetch }) =>
              apiFetch<unknown[]>('/properties/'),
            )
          },
        }),
      { wrapper },
    )
    await waitFor(() => expect(queryResult.current.isSuccess).toBe(true))
    expect(fetchCount).toBe(1)

    const { result: mutateResult } = renderHook(() => useCreateProperty(), {
      wrapper,
    })
    mutateResult.current.mutate({ name: 'Cascade', location: 'DE' })
    await waitFor(() => expect(mutateResult.current.isSuccess).toBe(true))
    // After the mutation's onSuccess invalidation, the observer should
    // have refetched at least once more.
    expect(fetchCount).toBeGreaterThan(1)
  })
})
