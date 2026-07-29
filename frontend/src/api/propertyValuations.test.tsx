// Task 13 — React Query hook tests for property valuations.
//
// Covers query hooks (`usePropertyValuations`, `usePropertyValuation`) and
// mutation hooks (`useCreatePropertyValuation`, `useUpdatePropertyValuation`,
// `useDeletePropertyValuation`). The list hook is keyed by property via the
// `byProperty` factory; mutations invalidate the root key
// (`propertyValuations.all`) so every `byProperty` cache refetches.
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import {
  usePropertyValuations,
  usePropertyValuation,
  useCreatePropertyValuation,
  useUpdatePropertyValuation,
  useDeletePropertyValuation,
} from './propertyValuations'
import { queryKeys } from './keys'
import { fixturePropertyValuation } from '@/__fixtures__/propertyValuation'

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

describe('usePropertyValuations', () => {
  it('filters by property id (queries the byProperty cache)', async () => {
    // The fixture for property 1 is a single valuation.
    const { result } = renderHook(
      () => usePropertyValuations(fixturePropertyValuation.property),
      { wrapper: makeWrapper() },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.length).toBe(1)
    expect(result.current.data?.[0].id).toBe(fixturePropertyValuation.id)
  })
})

describe('usePropertyValuation', () => {
  it('returns a single valuation by id', async () => {
    const { result } = renderHook(
      () => usePropertyValuation(fixturePropertyValuation.id),
      { wrapper: makeWrapper() },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.capital_structure_value).toBe(
      fixturePropertyValuation.capital_structure_value,
    )
  })
})

describe('useCreatePropertyValuation', () => {
  it('POSTs and invalidates the root propertyValuations key', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useCreatePropertyValuation(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({ property: 1, capital_structure_value: '300000.00' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.id).toBe(999)
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.propertyValuations.all,
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.analytics.all,
    })
  })
})

describe('useUpdatePropertyValuation', () => {
  it('PATCHes and invalidates the root key', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useUpdatePropertyValuation(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate({
      id: fixturePropertyValuation.id,
      data: { capital_structure_value: '999.00' },
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.capital_structure_value).toBe('999.00')
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.propertyValuations.all,
    })
  })
})

describe('useDeletePropertyValuation', () => {
  it('DELETEs and invalidates the root key', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useDeletePropertyValuation(), {
      wrapper: makeWrapperWithClient(qc),
    })
    result.current.mutate(fixturePropertyValuation.id)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.propertyValuations.all,
    })
  })
})
